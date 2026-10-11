"""Session, CSRF, origin, host, body limits and headers (BACKEND-CONTRACT section 5).

Every refusal here is 403 SESSION_INVALID or a transport status, never a silent bypass,
and every one of them is still a full page with the PLAN section 9 headers.
"""

from collections.abc import Iterator

import pytest
from web_support import ANSWERS, FOREIGN_ORIGIN, Harness, build_harness, harness_settings

from wiggle_outside.core.types import DeploymentMode
from wiggle_outside.preview_planner import PreviewPlanner
from wiggle_outside.web.security import (
    DEV_SESSION_COOKIE,
    HSTS,
    HTML_CACHE_CONTROL,
    MAX_BODY_BYTES,
    SESSION_COOKIE,
    OriginPolicy,
    Session,
    SessionStore,
    TokenBucket,
    origin_policy,
)

HEADERS = (
    "content-security-policy",
    "x-content-type-options",
    "referrer-policy",
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
    "permissions-policy",
    "cache-control",
)


@pytest.fixture
def hosted() -> Iterator[Harness]:
    """Build a hosted-product harness, where HSTS and the upgrade apply."""
    yield from build_harness(
        PreviewPlanner(),
        harness_settings(mode=DeploymentMode.HOSTED_LIVE),
    )


# --- The cookie (D31, TC-005) -------------------------------------------------------


def test_the_product_cookie_is_host_prefixed_secure_httponly_and_strict(
    hosted: Harness,
) -> None:
    raw = hosted.client.get("/", headers={"Host": "wiggle-outside.fly.dev"}).headers["set-cookie"]

    assert raw.startswith(f"{SESSION_COOKIE}=")
    assert "Secure" in raw
    assert "HttpOnly" in raw
    assert "SameSite=strict" in raw.replace("SameSite=Strict", "SameSite=strict")
    assert "Path=/" in raw
    assert "Domain" not in raw  # __Host- forbids it


def test_development_drops_only_the_prefix_and_secure(harness: Harness) -> None:
    # A browser rejects `__Host-` and Secure on http://localhost, so the session would
    # never persist and every POST would be 403 (TC-008). Everything else is unchanged.
    raw = harness.client.get("/").headers["set-cookie"]

    assert raw.startswith(f"{DEV_SESSION_COOKIE}=")
    assert not raw.startswith("__Host-")
    assert "Secure" not in raw
    assert "HttpOnly" in raw
    assert "SameSite=strict" in raw.replace("SameSite=Strict", "SameSite=strict")
    assert "Path=/" in raw
    assert "Domain" not in raw


def test_the_session_id_is_not_derived_from_anything_the_client_sent(
    harness: Harness,
) -> None:
    first = harness.client.get("/").cookies[DEV_SESSION_COOKIE]
    harness.client.cookies.clear()
    second = harness.client.get("/").cookies[DEV_SESSION_COOKIE]

    assert first != second
    assert len(first) >= 40  # token_urlsafe(32)


# --- Headers and CSP (PLAN section 9) -----------------------------------------------


@pytest.mark.parametrize("header", HEADERS)
def test_every_page_carries_the_security_headers(harness: Harness, header: str) -> None:
    assert header in harness.client.get("/").headers


@pytest.mark.parametrize("header", HEADERS)
def test_an_error_page_carries_them_too(harness: Harness, header: str) -> None:
    refused = harness.post("/plan", dict(ANSWERS))

    assert refused.status_code == 403
    assert header in refused.headers


def test_the_csp_names_no_unsafe_source(harness: Harness) -> None:
    policy = harness.client.get("/").headers["content-security-policy"]

    assert policy.startswith("default-src 'none'")
    for source in ("unsafe-inline", "unsafe-eval", "*", "http:", "https:"):
        assert source not in policy
    for directive in ("script-src 'self'", "form-action 'self'", "frame-ancestors 'none'"):
        assert directive in policy


def test_the_hosted_product_adds_hsts_and_upgrades_insecure_requests(
    hosted: Harness,
) -> None:
    page = hosted.client.get("/", headers={"Host": "wiggle-outside.fly.dev"})

    assert page.headers["strict-transport-security"] == HSTS
    assert "upgrade-insecure-requests" in page.headers["content-security-policy"]


def test_html_is_never_stored(harness: Harness) -> None:
    assert harness.client.get("/").headers["cache-control"] == HTML_CACHE_CONTROL


def test_the_pages_we_emit_carry_no_inline_script_or_style(harness: Harness) -> None:
    shown = harness.client.get(harness.plan().headers["location"])

    for forbidden in ("<script", "<style", " style=", " onclick="):
        assert forbidden not in shown.text


# --- The origin rule ----------------------------------------------------------------


def test_a_post_without_origin_or_referer_is_refused(harness: Harness) -> None:
    tokens = harness.start()

    refused = harness.client.post("/plan", data=harness.body(tokens), follow_redirects=False)

    assert refused.status_code == 403


def test_a_null_origin_is_refused(harness: Harness) -> None:
    tokens = harness.start()

    refused = harness.post("/plan", harness.body(tokens), Origin="null")

    assert refused.status_code == 403


def test_a_foreign_origin_is_refused(harness: Harness) -> None:
    tokens = harness.start()

    refused = harness.post("/plan", harness.body(tokens), Origin=FOREIGN_ORIGIN)

    assert refused.status_code == 403


def test_a_same_origin_referer_stands_in_for_a_missing_origin(harness: Harness) -> None:
    tokens = harness.start()

    posted = harness.client.post(
        "/plan",
        data=harness.body(tokens),
        headers={"Referer": "https://testserver/"},
        follow_redirects=False,
    )

    assert posted.status_code == 303


def test_a_foreign_referer_does_not(harness: Harness) -> None:
    tokens = harness.start()

    refused = harness.client.post(
        "/plan",
        data=harness.body(tokens),
        headers={"Referer": f"{FOREIGN_ORIGIN}/page"},
        follow_redirects=False,
    )

    assert refused.status_code == 403


def test_the_allowed_origins_come_from_settings() -> None:
    policy = origin_policy(harness_settings(port=8000, host="127.0.0.1"))

    # Development allows both schemes on the local names: a browser refuses the __Host-
    # cookie over plain HTTP, so a developer may well be serving HTTPS locally.
    assert policy.origins == {
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://localhost:8000",
        "https://127.0.0.1:8000",
    }
    assert policy.hosts == {"localhost:8000", "127.0.0.1:8000"}


def test_the_hosted_product_never_allows_a_plain_http_origin() -> None:
    policy = origin_policy(harness_settings(mode=DeploymentMode.HOSTED_LIVE))

    assert not any(origin.startswith("http://") for origin in policy.origins)


def test_the_hosted_product_allows_only_its_own_host() -> None:
    policy = origin_policy(harness_settings(mode=DeploymentMode.HOSTED_LIVE))

    assert policy == OriginPolicy(
        hosts=frozenset({"wiggle-outside.fly.dev"}),
        origins=frozenset({"https://wiggle-outside.fly.dev"}),
    )


# --- Host ---------------------------------------------------------------------------


def test_an_unknown_host_header_is_refused(harness: Harness) -> None:
    refused = harness.client.get("/", headers={"Host": "elsewhere.example"})

    assert refused.status_code == 400


# --- Sessions and CSRF ---------------------------------------------------------------


def test_an_unknown_session_id_is_never_adopted(harness: Harness) -> None:
    tokens = harness.start()
    harness.client.cookies.clear()
    harness.client.cookies.set(DEV_SESSION_COOKIE, "not-a-session")

    refused = harness.post("/plan", harness.body(tokens))

    assert refused.status_code == 403
    # A fresh session is issued, so a resubmission can work; the old ID is not adopted.
    assert refused.cookies[DEV_SESSION_COOKIE] != "not-a-session"


def test_a_missing_csrf_token_is_refused(harness: Harness) -> None:
    tokens = harness.start()
    body = harness.body(tokens)
    del body["csrf_token"]

    refused = harness.post("/plan", body)

    assert refused.status_code == 403


def test_a_wrong_csrf_token_is_refused(harness: Harness) -> None:
    tokens = harness.start()

    wrong = "x" * 43  # a wrong token, not a secret
    refused = harness.post("/plan", harness.body(tokens, csrf_token=wrong))

    assert refused.status_code == 403


def test_one_session_token_does_not_work_in_another_session(harness: Harness) -> None:
    stolen = harness.start()["csrf_token"]
    harness.client.cookies.clear()
    mine = harness.start()

    refused = harness.post("/plan", harness.body(mine, csrf_token=stolen))

    assert refused.status_code == 403


# --- Body limits (BACKEND-CONTRACT section 7) ---------------------------------------


def test_a_body_over_eight_kibibytes_is_refused(harness: Harness) -> None:
    tokens = harness.start()

    refused = harness.post("/plan", harness.body(tokens, place="x" * (MAX_BODY_BYTES + 1)))

    assert refused.status_code == 413


def test_a_multipart_body_is_refused(harness: Harness) -> None:
    tokens = harness.start()

    refused = harness.client.post(
        "/plan",
        files={"place": ("a.txt", b"Bergby")},
        data={"csrf_token": tokens["csrf_token"]},
        headers={"Origin": "https://testserver"},
        follow_redirects=False,
    )

    assert refused.status_code == 415


def test_a_json_body_is_refused(harness: Harness) -> None:
    refused = harness.client.post(
        "/plan",
        json={"who": "solo"},
        headers={"Origin": "https://testserver"},
        follow_redirects=False,
    )

    assert refused.status_code == 415


def test_an_unparseable_body_is_a_bad_request(harness: Harness) -> None:
    refused = harness.client.post(
        "/plan",
        content=b"no-equals-sign-anywhere",
        headers={
            "Origin": "https://testserver",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        follow_redirects=False,
    )

    assert refused.status_code == 400


def test_a_body_that_is_not_utf8_is_a_bad_request(harness: Harness) -> None:
    refused = harness.client.post(
        "/plan",
        content=b"who=\xff\xfe",
        headers={
            "Origin": "https://testserver",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        follow_redirects=False,
    )

    assert refused.status_code == 400


# --- The session store (BACKEND-CONTRACT section 4) ---------------------------------


def test_an_idle_session_expires() -> None:
    clock = [0.0]
    store = SessionStore(monotonic=lambda: clock[0])
    session = store.create()

    clock[0] = 30 * 60
    assert store.get(session.session_id) is None


def test_a_session_expires_absolutely_even_while_in_use() -> None:
    clock = [0.0]
    store = SessionStore(monotonic=lambda: clock[0])
    session = store.create()

    for minute in range(1, 121):
        clock[0] = minute * 60
        found = store.get(session.session_id)

    assert found is None


def test_the_store_is_bounded_and_evicts_an_idle_session_first() -> None:
    store = SessionStore(limit=2)
    busy = store.create()
    busy.last_job_id = "job-1"
    idle = store.create()

    store.create()

    assert store.get(busy.session_id) is not None
    assert store.get(idle.session_id) is None


def test_the_submission_buckets_refuse_a_flood() -> None:
    store = SessionStore(monotonic=lambda: 0.0)
    session = store.create()

    admitted = [store.admit_submission(session) for _ in range(10)]

    assert admitted[:6] == [True] * 6
    assert admitted[6:] == [False] * 4


def test_a_token_bucket_refills_over_its_window() -> None:
    bucket = TokenBucket(capacity=2, window_s=60.0)

    assert bucket.take(0.0)
    assert bucket.take(0.0)
    assert not bucket.take(0.0)
    assert bucket.take(60.0)


def test_an_idempotency_key_with_a_different_fingerprint_is_refused_by_the_session() -> None:
    session = Session(
        session_id="s",
        csrf_token="t",  # noqa: S106  a stand-in token, not a secret
        created=0.0,
        seen=0.0,
    )

    assert session.remember("key", "digest-a")
    assert session.remember("key", "digest-a")
    assert not session.remember("key", "digest-b")


def test_a_form_post_is_accepted_with_the_referrer_policy_we_send(harness: Harness) -> None:
    """The header and the origin rule must not contradict each other.

    `Referrer-Policy: no-referrer` makes Chromium send `Origin: null` on a form POST,
    and BACKEND-CONTRACT section 5 refuses a null Origin with 403 - so with both rules
    in force no submission could ever succeed, in the hosted product as much as
    locally. This pins the header; a browser-level check belongs to WP9b's journeys.
    """
    page = harness.client.get("/")

    assert page.headers["referrer-policy"] == "same-origin"
    # Same-origin requests therefore carry an Origin, and the POST is accepted.
    assert harness.plan().status_code == 303


def test_a_raising_end_of_session_hook_does_not_fail_the_request() -> None:
    """CC-005: the session is removed first; a hook failure is logged, never raised."""
    ended: list[str] = []

    def hook(session_id: str) -> None:
        ended.append(session_id)
        msg = "the planner is broken"
        raise RuntimeError(msg)

    clock = [0.0]
    store = SessionStore(monotonic=lambda: clock[0], on_end=hook)
    session = store.create()

    clock[0] = 30 * 60
    assert store.get(session.session_id) is None  # expired: the hook ran and raised
    assert ended == [session.session_id]
    assert store.create() is not None  # the store still works after the failure
