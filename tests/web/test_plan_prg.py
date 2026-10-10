"""The plain-form path: GET / -> POST /plan -> 303 -> GET /results/{job_id} (D43)."""

import re
from typing import Final

from web_support import ANSWERS, Harness

from wiggle_outside.web.security import DEV_SESSION_COOKIE, HTML_CACHE_CONTROL

DETAIL_URL: Final = re.compile(r"/results/[^\"]+/ideas/[^\"]+")


def test_the_form_page_creates_a_session_and_renders_the_form(harness: Harness) -> None:
    page = harness.client.get("/")

    assert page.status_code == 200
    assert 'action="/plan"' in page.text
    # The harness runs in development mode, where the cookie drops the __Host-
    # prefix so a browser on plain HTTP will actually keep it (TC-008).
    assert DEV_SESSION_COOKIE in page.cookies or DEV_SESSION_COOKIE in harness.client.cookies
    assert page.headers["cache-control"] == HTML_CACHE_CONTROL
    assert len(harness.sessions) == 1


def test_the_form_carries_a_csrf_token_and_a_fresh_idempotency_key(harness: Harness) -> None:
    first = harness.start()
    second = harness.start()

    assert first["csrf_token"] == second["csrf_token"]  # one token per session
    assert first["idempotency_key"] != second["idempotency_key"]  # a new job each time


def test_a_valid_submission_redirects_to_its_result(harness: Harness) -> None:
    posted = harness.plan()

    assert posted.status_code == 303
    assert posted.headers["location"].startswith("/results/")
    assert posted.headers["cache-control"] == HTML_CACHE_CONTROL


def test_the_result_page_shows_the_ideas(harness: Harness) -> None:
    posted = harness.plan()

    shown = harness.client.get(posted.headers["location"])

    assert shown.status_code == 200
    assert shown.headers["cache-control"] == HTML_CACHE_CONTROL
    assert shown.text.count("/ideas/") == 3
    assert "Bergby" in shown.text


def test_a_place_name_with_markup_is_escaped_once(harness: Harness) -> None:
    # The preview places include "Elm & Oak Playground" (BACKEND-CONTRACT section 7).
    shown = harness.client.get(harness.plan().headers["location"])

    assert "Elm &amp; Oak Playground" in shown.text
    assert "&amp;amp;" not in shown.text


def test_resubmitting_the_same_form_joins_rather_than_starting_again(harness: Harness) -> None:
    tokens = harness.start()
    body = harness.body(tokens)

    first = harness.post("/plan", body)
    second = harness.post("/plan", body)

    assert first.status_code == second.status_code == 303
    assert first.headers["location"] == second.headers["location"]


def test_the_detail_page_is_addressed_by_its_idea_id(harness: Harness) -> None:
    shown = harness.client.get(harness.plan().headers["location"])
    found = DETAIL_URL.search(shown.text)
    assert found is not None

    detail = harness.client.get(found.group(0))

    assert detail.status_code == 200
    assert detail.headers["cache-control"] == HTML_CACHE_CONTROL
    # Immutable results mean a detail URL answers the same way every time (D46).
    assert harness.client.get(found.group(0)).text == detail.text


def test_solo_answers_need_no_age_band(harness: Harness) -> None:
    posted = harness.plan(who="solo", age_band="")

    assert posted.status_code == 303


def test_coordinates_are_accepted_instead_of_a_typed_place(harness: Harness) -> None:
    tokens = harness.start()
    body = {
        "csrf_token": tokens["csrf_token"],
        "idempotency_key": tokens["idempotency_key"],
        **{name: value for name, value in ANSWERS.items() if name != "place"},
        "location_mode": "coords",
        "lat": "60.123456",
        "lon": "17.9",
    }

    posted = harness.post("/plan", body)

    assert posted.status_code == 303
