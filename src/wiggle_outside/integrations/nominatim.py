"""Nominatim geocoding adapter (BACKEND-CONTRACT sections 6 and 9).

One HTTP attempt per call and nothing else. The cache, the single flight, the one
permitted retry and the application-wide 1 request/s pacing all live in WP4's wrapper
(CONTRACTS section 4.1); this module only exposes `PACE_MIN_INTERVAL_S` as the interval
that wrapper must honour.

The base URL and the contact address are configuration (PLAN section 9): a user sends a
typed place, never a URL. Redirects are refused, TLS verification stays on and the
decompressed body is capped while streaming (BACKEND-CONTRACT section 7).

The transport block below is repeated in each provider adapter on purpose: import-linter
contract 4 keeps the adapters independent of each other, and WP3 owns no shared module to
put it in.
"""

import json
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, ClassVar, Final, override

import httpx

from wiggle_outside.core.result import (
    Empty,
    Malformed,
    Ok,
    Outcome,
    QuotaOrUnavailable,
    TransportFailure,
)
from wiggle_outside.core.types import (
    MAX_CANDIDATES,
    PLACE_TEXT_MAX,
    Coordinates,
    GeocodeHit,
    GeocodeHits,
)
from wiggle_outside.planner.ports import Geocoder, ProviderName
from wiggle_outside.settings import GEOCODE_BUDGET_S

if TYPE_CHECKING:
    from wiggle_outside.core.types import TypedPlace
    from wiggle_outside.settings import Settings

SEARCH_PATH: Final = "/search"
RESULT_FORMAT: Final = "jsonv2"
# One fixed language, so the cache key's language component is constant (ARCHITECTURE 15).
ACCEPT_LANGUAGE: Final = "en"
USER_AGENT_PRODUCT: Final = "WiggleOutside/0.1"
# BACKEND-CONTRACT section 7: decompressed responses capped at 2 MiB while streaming.
MAX_RESPONSE_BYTES: Final = 2 * 1024 * 1024
STAGE_BUDGET_S: Final = GEOCODE_BUDGET_S
CONNECT_BUDGET_S: Final = 2.0
# The hook, not the limiter: BACKEND-CONTRACT section 6 puts pacing in the wrapper.
PACE_MIN_INTERVAL_S: Final = 1.0

HTTP_OK: Final = 200
HTTP_TOO_MANY_REQUESTS: Final = 429
HTTP_SERVER_ERROR: Final = 500


@dataclass(frozen=True, slots=True)
class _Body:
    """A 200 response read whole, inside the size cap."""

    payload: bytes


type _Fetched = _Body | Malformed | TransportFailure | QuotaOrUnavailable


@dataclass(frozen=True, slots=True)
class NominatimGeocoder(Geocoder):
    """One search request per call. Never retries, never paces, never caches."""

    client: httpx.AsyncClient
    base_url: str
    contact_email: str
    monotonic: Callable[[], float] = time.monotonic
    max_bytes: int = MAX_RESPONSE_BYTES

    provider: ClassVar[ProviderName] = ProviderName.NOMINATIM
    pace_min_interval_s: ClassVar[float] = PACE_MIN_INTERVAL_S

    def __post_init__(self) -> None:
        # The usage policy wants a real contact in the User-Agent, so an unset
        # CONTACT_EMAIL fails at startup instead of sending anonymous traffic.
        if "@" not in self.contact_email:
            msg = "Nominatim needs a real contact address in the User-Agent (WO_CONTACT_EMAIL)"
            raise ValueError(msg)

    @property
    def user_agent(self) -> str:
        return f"{USER_AGENT_PRODUCT} ({self.contact_email})"

    @override
    async def resolve(self, place: TypedPlace, deadline: float) -> Outcome[GeocodeHits]:
        fetched = await self._fetch(place.text, deadline)
        if not isinstance(fetched, _Body):
            return fetched
        return _hits(fetched.payload)

    async def _fetch(self, query: str, deadline: float) -> _Fetched:
        budget = min(STAGE_BUDGET_S, deadline - self.monotonic())
        if budget <= 0:
            # No time for an attempt; the same outcome the attempt would have had.
            return TransportFailure()
        params = {
            "q": query,  # a typed value, never part of the URL or the host
            "format": RESULT_FORMAT,
            "limit": str(MAX_CANDIDATES),
            "addressdetails": "0",
            "accept-language": ACCEPT_LANGUAGE,
        }
        request = self.client.build_request(
            "GET",
            self.base_url.rstrip("/") + SEARCH_PATH,
            params=params,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            timeout=httpx.Timeout(budget, connect=min(budget, CONNECT_BUDGET_S)),
        )
        return await _read(self.client, request, max_bytes=self.max_bytes)


def from_settings(client: httpx.AsyncClient, settings: Settings) -> NominatimGeocoder:
    """Build the adapter from configuration only (PLAN section 9: no URL from a request)."""
    return NominatimGeocoder(
        client=client,
        base_url=settings.nominatim_url,
        contact_email=settings.contact_email,
    )


async def _read(
    client: httpx.AsyncClient,
    request: httpx.Request,
    *,
    max_bytes: int,
) -> _Fetched:
    """One attempt: no redirect is followed, and the stream is always closed."""
    try:
        response = await client.send(request, stream=True, follow_redirects=False)
        try:
            if response.status_code != HTTP_OK:
                return _status_outcome(response.status_code, response.headers.get("retry-after"))
            return _capped(await _collect(response, max_bytes))
        finally:
            # Cancellation closes the stream here and then propagates, because
            # asyncio.CancelledError is a BaseException and is never caught below
            # (CONTRACTS section 1).
            await response.aclose()
    except httpx.HTTPError:
        return TransportFailure()


async def _collect(response: httpx.Response, max_bytes: int) -> bytes | None:
    """Read the decompressed body, or None as soon as it passes the cap."""
    payload = bytearray()
    async for chunk in response.aiter_bytes():
        payload += chunk
        if len(payload) > max_bytes:
            return None
    return bytes(payload)


def _capped(payload: bytes | None) -> _Fetched:
    # An oversized body is a transport-level failure (core.result.TransportFailure).
    return TransportFailure() if payload is None else _Body(payload)


def _status_outcome(status: int, retry_after: str | None) -> Malformed | QuotaOrUnavailable:
    if status == HTTP_TOO_MANY_REQUESTS or status >= HTTP_SERVER_ERROR:
        return QuotaOrUnavailable(retry_after_s=_retry_after_seconds(retry_after))
    # Anything else (a redirect we refuse to follow, a 4xx) is an answer we cannot use:
    # not cached, counted, never retried.
    return Malformed()


def _retry_after_seconds(raw: str | None) -> float | None:
    """Retry-After as seconds or an HTTP date; missing or unparseable means None."""
    if raw is None:
        return None
    text = raw.strip()
    try:
        return float(max(0, int(text)))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(text)
    except TypeError, ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


def _hits(payload: bytes) -> Outcome[GeocodeHits]:
    try:
        decoded: object = json.loads(payload)
    except UnicodeDecodeError, json.JSONDecodeError:
        return Malformed()
    if not isinstance(decoded, list):
        return Malformed()
    if not decoded:
        return Empty()
    found: list[GeocodeHit] = []
    for entry in decoded[:MAX_CANDIDATES]:
        hit = _hit(entry)
        if hit is None:
            return Malformed()
        found.append(hit)
    return Ok(GeocodeHits(hits=tuple(found)))


def _hit(entry: object) -> GeocodeHit | None:
    if not isinstance(entry, dict):
        return None
    coords = _coords(entry.get("lat"), entry.get("lon"))
    label = _label(entry.get("display_name"))
    if coords is None or label is None:
        return None
    return GeocodeHit(label=label, coords=coords)


def _coords(lat: object, lon: object) -> Coordinates | None:
    """jsonv2 sends the coordinates as strings; Coordinates rounds and range-checks them."""
    try:
        values = (float(_numeric(lat)), float(_numeric(lon)))
    except TypeError, ValueError:
        return None
    try:
        return Coordinates(lat=values[0], lon=values[1])
    except ValueError:
        return None


def _numeric(value: object) -> str | float:
    if isinstance(value, str | int | float) and not isinstance(value, bool):
        return value
    msg = "not a coordinate"
    raise TypeError(msg)


def _label(value: object) -> str | None:
    """Plain text, NFC, printable, capped at the length LocationCandidate allows."""
    if not isinstance(value, str):
        return None
    text = "".join(
        character for character in unicodedata.normalize("NFC", value) if character.isprintable()
    ).strip()
    # A cut label is honest; an invented ellipsis would not be part of the OSM name.
    return text[:PLACE_TEXT_MAX].strip() or None
