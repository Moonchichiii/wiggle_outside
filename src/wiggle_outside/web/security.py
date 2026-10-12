"""Everything a request must pass, and the headers every response carries.

BACKEND-CONTRACT section 5 and PLAN section 9. No globals and no framework state: the
session store and the origin policy are values the caller builds and passes in
(PLAN section 7). Nothing here logs an answer, a coordinate, a typed place or a
fingerprint.
"""

import hmac
import logging
import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit

from starlette.responses import HTMLResponse, PlainTextResponse, Response

from wiggle_outside.core.types import (
    DeploymentMode,
    LocationCandidate,
    LocationCandidates,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping
    from datetime import datetime

    from starlette.requests import Request

    from wiggle_outside.settings import Settings

log = logging.getLogger(__name__)

# --- Statuses (CONTRACTS section 3) -------------------------------------------------

HTTP_OK: Final = 200
HTTP_SEE_OTHER: Final = 303
HTTP_BAD_REQUEST: Final = 400
HTTP_FORBIDDEN: Final = 403
HTTP_NOT_FOUND: Final = 404
HTTP_CONFLICT: Final = 409
HTTP_CONTENT_TOO_LARGE: Final = 413
HTTP_UNSUPPORTED_MEDIA_TYPE: Final = 415
HTTP_UNPROCESSABLE: Final = 422
HTTP_TOO_MANY_REQUESTS: Final = 429
HTTP_SERVER_ERROR: Final = 500
HTTP_SERVICE_UNAVAILABLE: Final = 503

# --- Session and token sizes (CONTRACTS section 1, D31) -----------------------------

SESSION_COOKIE: Final = "__Host-wo_session"  # TC-005; the product cookie
# Development over plain HTTP cannot use it: a browser rejects both the `__Host-`
# prefix and the Secure attribute on an insecure origin, so the session never
# persists and every POST becomes 403 SESSION_INVALID (TC-008).
DEV_SESSION_COOKIE: Final = "wo_session"
TOKEN_BYTES: Final = 32  # session and CSRF
ID_BYTES: Final = 16  # idempotency key

# BACKEND-CONTRACT section 4, starting values.
MAX_SESSIONS: Final = 500
IDLE_SECONDS: Final = 30 * 60
ABSOLUTE_SECONDS: Final = 2 * 60 * 60
SUBMISSIONS_PER_SESSION: Final = 6
SUBMISSIONS_GLOBAL: Final = 30
SUBMISSION_WINDOW_S: Final = 60.0
# One idempotency record per submission the session could still repeat; the oldest goes
# first. Bounded so a client cannot grow a session by sending new keys.
MAX_KEYS_PER_SESSION: Final = 16

# --- Transport limits (BACKEND-CONTRACT section 7) ----------------------------------

URLENCODED: Final = "application/x-www-form-urlencoded"
MAX_BODY_BYTES: Final = 8 * 1024

HTML_CACHE_CONTROL: Final = "no-store, private"
STATIC_CACHE_CONTROL: Final = "public, max-age=31536000, immutable"
# TC-011: /favicon.ico is not content-hashed, so a day rather than a year.
FAVICON_CACHE_CONTROL: Final = "public, max-age=86400"

# --- Hosts and origins (BACKEND-CONTRACT section 5) ---------------------------------

HTTP_PORT: Final = 80
HTTPS_PORT: Final = 443
HOSTED_HOST: Final = "wiggle-outside.fly.dev"  # D27; DEPLOYMENT section 1


@dataclass(frozen=True, slots=True)
class OriginPolicy:
    """The exact allowed `Host` values and the exact allowed origins."""

    hosts: frozenset[str]
    origins: frozenset[str]


def origin_policy(settings: Settings) -> OriginPolicy:
    """Derive the allowed hosts and origins from settings (scheme, host, port)."""
    if settings.mode is DeploymentMode.HOSTED_LIVE:
        return OriginPolicy(
            hosts=frozenset({HOSTED_HOST}),
            origins=frozenset({f"https://{HOSTED_HOST}"}),
        )
    # Development accepts both schemes on the local names, because neither alone works
    # in a browser: over plain HTTP the browser refuses the `__Host-` session cookie that
    # D31 requires, and over HTTPS an http-only origin list refuses the POST. A developer
    # may therefore serve either, and both are local. Hosted mode is https-only, above.
    schemes = ("http", "https")
    names = {"localhost", "127.0.0.1", settings.host.lower()}
    hosts = {f"{name}:{settings.port}" for name in names}
    origins = {f"{scheme}://{name}:{settings.port}" for name in names for scheme in schemes}
    if settings.port in {HTTP_PORT, HTTPS_PORT}:
        # The default port is not written in a Host header or an Origin.
        hosts |= names
        origins |= {f"{scheme}://{name}" for name in names for scheme in schemes}
    return OriginPolicy(hosts=frozenset(hosts), origins=frozenset(origins))


def host_allowed(request: Request, policy: OriginPolicy) -> bool:
    """Check the Host header on every request; no proxy is trusted."""
    host = request.headers.get("host")
    return host is not None and host.lower() in policy.hosts


def origin_allowed(request: Request, policy: OriginPolicy) -> bool:
    """Apply the unsafe-method rule, with no silent bypass (BACKEND-CONTRACT 5).

    `Origin` must equal an allowed origin. Only when it is absent does `Referer` stand
    in, and it must be same-origin. Both absent, or `Origin: null`, is a refusal.
    """
    origin = request.headers.get("origin")
    if origin is not None:
        return origin != "null" and origin in policy.origins
    referer = request.headers.get("referer")
    if not referer:
        return False
    parts = urlsplit(referer)
    if not parts.scheme or not parts.netloc:
        return False
    return f"{parts.scheme}://{parts.netloc}".lower() in policy.origins


# --- Headers and CSP (PLAN section 9) -----------------------------------------------

BASE_CSP: Final = (
    "default-src 'none'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self'; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "manifest-src 'self'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'; "
    "object-src 'none'"
)

# Restrictive, and geolocation for self only: "Use my location" is a same-origin feature.
PERMISSIONS_POLICY: Final = (
    "accelerometer=(), autoplay=(), camera=(), display-capture=(), "
    "encrypted-media=(), fullscreen=(), geolocation=(self), gyroscope=(), "
    "magnetometer=(), microphone=(), midi=(), payment=(), usb=()"
)

HSTS: Final = "max-age=63072000; includeSubDomains; preload"


def content_security_policy(mode: DeploymentMode) -> str:
    """Build the CSP of PLAN section 9; hosted also upgrades insecure requests."""
    if mode is DeploymentMode.HOSTED_LIVE:
        return f"{BASE_CSP}; upgrade-insecure-requests"
    return BASE_CSP


def security_headers(mode: DeploymentMode) -> dict[str, str]:
    """Build the PLAN section 9 header list, present on every response."""
    headers = {
        "Content-Security-Policy": content_security_policy(mode),
        "X-Content-Type-Options": "nosniff",
        # same-origin, not no-referrer: under no-referrer Chromium sends `Origin: null`
        # on a form POST, which BACKEND-CONTRACT section 5 refuses with 403, so every
        # submission would fail. same-origin sends no referrer cross-origin, which is
        # what the privacy rule is for (TC-008).
        "Referrer-Policy": "same-origin",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Permissions-Policy": PERMISSIONS_POLICY,
    }
    if mode is DeploymentMode.HOSTED_LIVE:
        headers["Strict-Transport-Security"] = HSTS
    return headers


def page_headers(mode: DeploymentMode) -> dict[str, str]:
    """Security headers plus `no-store, private` on every HTML response."""
    return {"Cache-Control": HTML_CACHE_CONTROL} | security_headers(mode)


def html_page(
    body: str,
    mode: DeploymentMode,
    status: int = HTTP_OK,
    extra: Mapping[str, str] | None = None,
) -> Response:
    return HTMLResponse(body, status_code=status, headers=page_headers(mode) | dict(extra or {}))


def see_other(location: str, mode: DeploymentMode) -> Response:
    """Answer a plain-form POST with the redirect of D43."""
    return Response(
        status_code=HTTP_SEE_OTHER,
        headers={"Location": location} | page_headers(mode),
    )


def plain_text(body: str, mode: DeploymentMode) -> Response:
    """`/healthz` and `/readyz`: text, never cached, same security headers."""
    return PlainTextResponse(body, headers=page_headers(mode))


def session_cookie_name(mode: DeploymentMode) -> str:
    """Name the session cookie: `__Host-` in the product, plain in development."""
    return SESSION_COOKIE if mode is DeploymentMode.HOSTED_LIVE else DEV_SESSION_COOKIE


def set_session_cookie(
    response: Response, session_id: str, mode: DeploymentMode = DeploymentMode.HOSTED_LIVE
) -> None:
    """D31 and TC-005: `__Host-` prefixed, so Secure, Path=/ and no Domain.

    Development drops the prefix and Secure, and only those two: HttpOnly, SameSite and
    Path are unchanged, and the hosted product is untouched. Without this a browser on
    http://localhost silently discards the cookie and every submission is refused.
    """
    hosted = mode is DeploymentMode.HOSTED_LIVE
    response.set_cookie(
        session_cookie_name(mode),
        session_id,
        max_age=ABSOLUTE_SECONDS,
        path="/",
        secure=hosted,
        httponly=True,
        samesite="strict",
    )


# --- Body limits (BACKEND-CONTRACT section 7) ---------------------------------------


def media_type_allowed(request: Request) -> bool:
    """Urlencoded only; multipart and file uploads are rejected (415)."""
    declared = request.headers.get("content-type", "")
    return declared.split(";", 1)[0].strip().lower() == URLENCODED


def declared_too_large(request: Request, limit: int = MAX_BODY_BYTES) -> bool:
    """Reject an oversized body from its own Content-Length, before reading it."""
    raw = request.headers.get("content-length")
    if raw is None:
        return False
    try:
        return int(raw) > limit
    except ValueError:
        return True


async def read_limited(request: Request, limit: int = MAX_BODY_BYTES) -> bytes | None:
    """Read at most `limit` bytes; None means the body is over the limit.

    Streamed, so an oversized body is refused before it is all in memory and before any
    expensive processing (ERROR-HANDLING section 2).
    """
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


# --- CSRF ---------------------------------------------------------------------------


def csrf_ok(expected: str, submitted: str | None) -> bool:
    """Per-session token, compared with `hmac.compare_digest` (D31)."""
    if not submitted:
        return False
    return hmac.compare_digest(expected, submitted)


# --- Submission rate limiting (BACKEND-CONTRACT section 4) --------------------------


@dataclass(slots=True)
class TokenBucket:
    """A token bucket over a fixed window. One timestamp and one float of state."""

    capacity: int
    window_s: float = SUBMISSION_WINDOW_S
    tokens: float = -1.0  # filled on first use, so the capacity is the only input
    updated: float = 0.0

    def take(self, now: float) -> bool:
        if self.tokens < 0:
            self.tokens, self.updated = float(self.capacity), now
        refill = (now - self.updated) * (self.capacity / self.window_s)
        self.tokens = min(float(self.capacity), self.tokens + max(0.0, refill))
        self.updated = now
        if self.tokens < 1.0:
            return False
        self.tokens -= 1.0
        return True


# --- The session --------------------------------------------------------------------


@dataclass(slots=True)
class Session:
    """Server-side state for one opaque cookie. Nothing of it reaches the client."""

    session_id: str
    csrf_token: str
    created: float
    seen: float
    # One candidate set per session (BACKEND-CONTRACT section 3).
    candidates: LocationCandidates | None = None
    # The most recent job this session started, for the busy link and the consumed-choice
    # redirect. Never an answer and never a fingerprint.
    last_job_id: str | None = None
    submissions: TokenBucket = field(
        default_factory=lambda: TokenBucket(capacity=SUBMISSIONS_PER_SESSION)
    )
    # Idempotency key -> submission fingerprint (web/forms.fingerprint). Kept for the
    # session only, never logged, rendered or sent anywhere (CONTRACTS section 7).
    keys: OrderedDict[str, str] = field(default_factory=OrderedDict)

    @property
    def active_job(self) -> str | None:
        return self.last_job_id

    def new_key(self) -> str:
        """Make a fresh idempotency key; changed answers are a new job (D46)."""
        return secrets.token_urlsafe(ID_BYTES)

    def remember(self, key: str, digest: str) -> bool:
        """Record a submission under its key; False when the key saw a different one.

        Same key and same fingerprint joins; same key and a different fingerprint is the
        409 in CONTRACTS section 3.
        """
        known = self.keys.get(key)
        if known is not None:
            self.keys.move_to_end(key)
            return hmac.compare_digest(known, digest)
        self.keys[key] = digest
        while len(self.keys) > MAX_KEYS_PER_SESSION:
            self.keys.popitem(last=False)
        return True

    def live_candidate(self, candidate_id: str, now: datetime) -> LocationCandidate | None:
        """Find the candidate with this ID in this session's live set, or None.

        Unknown, forged, from another session, expired or already removed all answer
        None, so the uniform 422 in CONTRACTS section 3 is the single outcome.
        """
        if self.candidates is None or not candidate_id:
            return None
        for candidate in self.candidates.candidates:
            if hmac.compare_digest(candidate.candidate_id, candidate_id):
                # A consumed candidate outlives the set's TTL: its job is still owned.
                if candidate.job_id is None and self.candidates.expires_at <= now:
                    return None
                return candidate
        return None

    def live_set(self, now: datetime) -> LocationCandidates | None:
        """Return the candidate set while it is unexpired; its answers go with it."""
        if self.candidates is None or self.candidates.expires_at <= now:
            return None
        return self.candidates

    def consume_candidate(self, candidate_id: str, job_id: str) -> None:
        """Record the job a candidate started, so a repeat returns the same one."""
        if self.candidates is None:
            return
        self.candidates = replace(
            self.candidates,
            candidates=tuple(
                replace(candidate, job_id=job_id)
                if candidate.candidate_id == candidate_id
                else candidate
                for candidate in self.candidates.candidates
            ),
        )
        self.last_job_id = job_id

    def latest_candidate_job(self) -> str | None:
        """Find the most recently started job from this set (BACKEND-CONTRACT 3)."""
        if self.candidates is None:
            return None
        started = [c.job_id for c in self.candidates.candidates if c.job_id is not None]
        if not started:
            return None
        if self.last_job_id in started:
            return self.last_job_id
        return started[-1]


# --- The store ----------------------------------------------------------------------


class SessionStore:
    """In-memory and bounded: 500 sessions, idle 30 min, absolute 2 h.

    A class rather than functions because this is real state with invariants
    (PLAN section 7): a bound, two expiries and an eviction rule that never takes a
    session with work in flight.
    """

    def __init__(
        self,
        *,
        limit: int = MAX_SESSIONS,
        monotonic: Callable[[], float] = time.monotonic,
        on_end: Callable[[str], None] | None = None,
    ) -> None:
        self._limit = limit
        self._monotonic = monotonic
        # Called with the session ID when a session expires or is evicted, so the planner
        # can remove everything the session owned, together (BACKEND-CONTRACT section 2).
        self._on_end = on_end
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._global = TokenBucket(capacity=SUBMISSIONS_GLOBAL)

    def __len__(self) -> int:
        return len(self._sessions)

    def __iter__(self) -> Iterator[Session]:
        return iter(tuple(self._sessions.values()))

    def create(self) -> Session:
        """Open a fresh session. Created on the first GET of the form page."""
        self._purge()
        if len(self._sessions) >= self._limit:
            self._evict()
        now = self._monotonic()
        session = Session(
            session_id=secrets.token_urlsafe(TOKEN_BYTES),
            csrf_token=secrets.token_urlsafe(TOKEN_BYTES),
            created=now,
            seen=now,
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str | None) -> Session | None:
        """Look up the session a cookie names; an unknown ID is never adopted."""
        self._purge()
        if not session_id:
            return None
        session = self._sessions.get(session_id)
        if session is None:
            return None
        session.seen = self._monotonic()
        self._sessions.move_to_end(session_id)
        return session

    def admit_submission(self, session: Session) -> bool:
        """Spend a token from the per-session and global buckets, before any work."""
        now = self._monotonic()
        return session.submissions.take(now) and self._global.take(now)

    def _purge(self) -> None:
        now = self._monotonic()
        for session_id, session in tuple(self._sessions.items()):
            idle = now - session.seen >= IDLE_SECONDS
            old = now - session.created >= ABSOLUTE_SECONDS
            if idle or old:
                self._end(session_id)

    def _evict(self) -> None:
        """Least-recently-used idle session first, never one with an active job."""
        for session_id, session in self._sessions.items():
            if session.active_job is None:
                self._end(session_id)
                return
        # Every session holds a job reference; the bound still has to hold, so the
        # least-recently-used one goes. Active jobs are capped far below the session
        # bound (BACKEND-CONTRACT section 4), so this is unreachable in practice.
        self._end(next(iter(self._sessions)))

    def _end(self, session_id: str) -> None:
        del self._sessions[session_id]
        if self._on_end is None:
            return
        try:
            self._on_end(session_id)
        except Exception:
            # CC-005: the session is gone either way; the unrelated request that
            # triggered the purge must not fail for it.
            log.exception("the end-of-session hook failed; the session is already removed")
