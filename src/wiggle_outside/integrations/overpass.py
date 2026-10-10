"""Overpass places adapter (BACKEND-CONTRACT sections 6, 7 and 8).

One HTTP attempt per call and nothing else: the cache, the single flight and the one
permitted retry live in WP4's wrapper (CONTRACTS section 4.1).

The query is built from a fixed template plus numbers (BACKEND-CONTRACT section 7). The
only strings that ever reach it are the selector fragments in `KIND_SELECTORS`, which are
written here; a kind this module does not know contributes nothing, so no request text can
reach the provider. The endpoint is configuration (PLAN section 9).

The transport block below is repeated in each provider adapter on purpose: import-linter
contract 4 keeps the adapters independent of each other, and WP3 owns no shared module to
put it in.
"""

import json
import math
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, ClassVar, Final, Literal, override

import httpx

from wiggle_outside.core.places import ANY_PLACE_KIND
from wiggle_outside.core.result import (
    Empty,
    Malformed,
    Ok,
    Outcome,
    QuotaOrUnavailable,
    TransportFailure,
)
from wiggle_outside.core.types import Coordinates, Place
from wiggle_outside.planner.ports import PlacesProvider, ProviderName
from wiggle_outside.settings import PROVIDERS_BUDGET_S

if TYPE_CHECKING:
    from wiggle_outside.settings import Settings

USER_AGENT: Final = "WiggleOutside/0.1"
# BACKEND-CONTRACT section 7: decompressed responses capped at 2 MiB while streaming.
MAX_RESPONSE_BYTES: Final = 2 * 1024 * 1024
STAGE_BUDGET_S: Final = PROVIDERS_BUDGET_S
CONNECT_BUDGET_S: Final = 2.0

# PLAN section 3: the radius comes from the time budget and never exceeds 3 km.
MIN_RADIUS_M: Final = 100
MAX_RADIUS_M: Final = 3000
# Starting value: enough candidates for core to rank down to 8 places, inside the cap.
OUT_LIMIT: Final = 60

NAME_MAX: Final = 60
HTTP_OK: Final = 200
HTTP_TOO_MANY_REQUESTS: Final = 429
HTTP_SERVER_ERROR: Final = 500

# The whole query vocabulary. PLAN section 3: park, playground, nature reserve, forest,
# picnic site. Viewpoints and beaches are out of v1.
KIND_SELECTORS: Final[dict[str, tuple[str, ...]]] = {
    "park": ('nwr["leisure"="park"]',),
    "playground": ('nwr["leisure"="playground"]',),
    "nature_reserve": ('nwr["leisure"="nature_reserve"]',),
    "forest": ('nwr["landuse"="forest"]', 'nwr["natural"="wood"]'),
    "picnic_site": ('nwr["tourism"="picnic_site"]',),
}

# Which kind a returned element is, by the first matching tag. Fixed priority: the more
# specific tag wins, so a wood inside a reserve is reported as the reserve.
KIND_BY_TAG: Final[tuple[tuple[str, str, str], ...]] = (
    ("leisure", "playground", "playground"),
    ("leisure", "nature_reserve", "nature_reserve"),
    ("leisure", "park", "park"),
    ("tourism", "picnic_site", "picnic_site"),
    ("landuse", "forest", "forest"),
    ("natural", "wood", "forest"),
)

# BACKEND-CONTRACT section 8: excluded outright.
BLOCKED_ACCESS: Final[frozenset[str]] = frozenset({"private", "no"})
LIFECYCLE_PREFIXES: Final = ("disused:", "abandoned:", "demolished:")

QUERY_TEMPLATE: Final = (
    "[out:json][timeout:{timeout}];\n(\n{clauses}\n);\nout tags center {limit};\n"
)
CLAUSE_TEMPLATE: Final = "  {selector}(around:{radius},{lat},{lon});"


@dataclass(frozen=True, slots=True)
class _Body:
    """A 200 response read whole, inside the size cap."""

    payload: bytes


type _Fetched = _Body | Malformed | TransportFailure | QuotaOrUnavailable


@dataclass(frozen=True, slots=True)
class OverpassPlaces(PlacesProvider):
    """One Overpass request per call. Never retries, never caches."""

    client: httpx.AsyncClient
    base_url: str
    monotonic: Callable[[], float] = time.monotonic
    max_bytes: int = MAX_RESPONSE_BYTES

    provider: ClassVar[ProviderName] = ProviderName.OVERPASS

    @override
    async def nearby(
        self,
        at: Coordinates,
        radius_m: int,
        kinds: frozenset[str],
        deadline: float,
    ) -> Outcome[tuple[Place, ...]]:
        selectors = _selectors(kinds)
        if not selectors:
            # Nothing this provider can be asked for, so there is nothing to ask: an
            # empty answer rather than an empty query.
            return Empty()
        budget = min(STAGE_BUDGET_S, deadline - self.monotonic())
        if budget <= 0:
            # No time for an attempt; the same outcome the attempt would have had.
            return TransportFailure()
        query = _query(selectors, at=at, radius_m=radius_m, budget=budget)
        fetched = await self._fetch(query, budget)
        if not isinstance(fetched, _Body):
            return fetched
        return _places(fetched.payload)

    async def _fetch(self, query: str, budget: float) -> _Fetched:
        request = self.client.build_request(
            "POST",
            self.base_url,
            content=query.encode(),
            headers={
                "Content-Type": "text/plain; charset=utf-8",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
            timeout=httpx.Timeout(budget, connect=min(budget, CONNECT_BUDGET_S)),
        )
        return await _read(self.client, request, max_bytes=self.max_bytes)


def from_settings(client: httpx.AsyncClient, settings: Settings) -> OverpassPlaces:
    """Build the adapter from configuration only (PLAN section 9: no URL from a request)."""
    return OverpassPlaces(client=client, base_url=settings.overpass_url)


def _selectors(kinds: frozenset[str]) -> tuple[str, ...]:
    """Map the catalogue's kinds onto fixed fragments; an unknown kind maps to nothing."""
    chosen = (
        tuple(KIND_SELECTORS)
        if ANY_PLACE_KIND in kinds
        else tuple(kind for kind in sorted(kinds) if kind in KIND_SELECTORS)
    )
    return tuple(selector for kind in chosen for selector in KIND_SELECTORS[kind])


def _query(selectors: tuple[str, ...], *, at: Coordinates, radius_m: int, budget: float) -> str:
    """Fill the fixed template with numbers. Coordinates are already rounded to 2 dp."""
    radius = min(max(radius_m, MIN_RADIUS_M), MAX_RADIUS_M)
    clauses = "\n".join(
        CLAUSE_TEMPLATE.format(
            selector=selector,
            radius=radius,
            lat=f"{at.lat:.2f}",
            lon=f"{at.lon:.2f}",
        )
        for selector in selectors
    )
    # The server-side timeout matches ours, so Overpass stops when we would.
    return QUERY_TEMPLATE.format(timeout=max(1, int(budget)), clauses=clauses, limit=OUT_LIMIT)


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


def _places(payload: bytes) -> Outcome[tuple[Place, ...]]:
    try:
        decoded: object = json.loads(payload)
    except UnicodeDecodeError, json.JSONDecodeError:
        return Malformed()
    if not isinstance(decoded, dict):
        return Malformed()
    unavailable = _remark_outcome(decoded.get("remark"))
    if unavailable is not None:
        return unavailable
    return _from_elements(decoded.get("elements"))


def _from_elements(elements: object) -> Outcome[tuple[Place, ...]]:
    if not isinstance(elements, list):
        return Malformed()
    parsed = (_place(element) for element in elements[:OUT_LIMIT])
    found = tuple(place for place in parsed if place is not None)
    # Every element filtered out is still a valid, empty answer, not a failure.
    return Ok(found) if found else Empty()


def _remark_outcome(remark: object) -> QuotaOrUnavailable | None:
    """Overpass reports a runtime error in `remark` with status 200.

    An incomplete or timed-out answer must never be cached as "no places nearby", so it
    is reported as the provider being unavailable and earns the cooldown.
    """
    if isinstance(remark, str) and "error" in remark.lower():
        return QuotaOrUnavailable()
    return None


def _place(element: object) -> Place | None:
    if not isinstance(element, dict):
        return None
    tags = element.get("tags")
    if not isinstance(tags, dict) or _excluded(tags):
        return None
    return _build(element, tags)


def _build(element: dict[str, object], tags: dict[str, object]) -> Place | None:
    identity = _identity(element.get("type"), element.get("id"))
    coords = _coords(element)
    kind = _kind(tags)
    name = _name(tags.get("name"))
    if identity is None or coords is None or kind is None or name is None:
        return None
    return Place(
        place_id=identity,
        name=name,
        kind=kind,
        coords=coords,
        fee=_fee(tags.get("fee")),
        osm_access=_access(tags.get("wheelchair")),
    )


def _excluded(tags: dict[str, object]) -> bool:
    """BACKEND-CONTRACT section 8: `access` private or no, and lifecycle prefixes."""
    access = tags.get("access")
    if isinstance(access, str) and access.strip().lower() in BLOCKED_ACCESS:
        return True
    return any(_lifecycle(key) or _lifecycle(value) for key, value in tags.items())


def _lifecycle(value: object) -> bool:
    return isinstance(value, str) and value.startswith(LIFECYCLE_PREFIXES)


def _identity(osm_type: object, osm_id: object) -> str | None:
    """Stable and internal: the same place keeps its ID across a cache round trip."""
    if not isinstance(osm_type, str) or isinstance(osm_id, bool) or not isinstance(osm_id, int):
        return None
    return f"{osm_type}:{osm_id}"


def _kind(tags: dict[str, object]) -> str | None:
    for key, value, kind in KIND_BY_TAG:
        if tags.get(key) == value:
            return kind
    return None


def _name(value: object) -> str | None:
    """Plain text, NFC, printable, capped at the 60 characters `Place.name` allows."""
    if not isinstance(value, str):
        return None
    text = "".join(
        character for character in unicodedata.normalize("NFC", value) if character.isprintable()
    ).strip()
    return text[:NAME_MAX].strip() or None


def _fee(value: object) -> Literal["no", "yes", "unknown"]:
    """D37: `fee=yes` is excluded by core; anything unstated stays unknown, and labelled."""
    if value == "yes":
        return "yes"
    if value == "no":
        return "no"
    return "unknown"


def _access(value: object) -> Literal["yes", "limited", "no", "unknown"]:
    """Read the OSM `wheelchair` tag: reported, never verified (D42 P)."""
    if value == "yes":
        return "yes"
    if value == "limited":
        return "limited"
    if value == "no":
        return "no"
    return "unknown"


def _coords(element: dict[str, object]) -> Coordinates | None:
    """Take the centre: a node carries lat/lon, a way or relation the `center` we ask for."""
    pair = _pair(element.get("lat"), element.get("lon")) or _centre(element.get("center"))
    if pair is None:
        return None
    try:
        return Coordinates(lat=pair[0], lon=pair[1])
    except ValueError:
        return None


def _centre(centre: object) -> tuple[float, float] | None:
    if not isinstance(centre, dict):
        return None
    return _pair(centre.get("lat"), centre.get("lon"))


def _pair(lat: object, lon: object) -> tuple[float, float] | None:
    values = (_number(lat), _number(lon))
    if values[0] is None or values[1] is None:
        return None
    return (values[0], values[1])


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) else None
