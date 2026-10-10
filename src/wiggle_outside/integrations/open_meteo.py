"""Open-Meteo weather adapter (BACKEND-CONTRACT section 1).

One HTTP attempt per call and nothing else: the cache, the single flight and the one
permitted retry live in WP4's wrapper (CONTRACTS section 4.1).

The request asks for exactly the variables section 1 lists, with explicit units, and the
returned `hourly_units` and `daily_units` must match or the forecast is rejected. The
hourly arrays travel as received, `precipitation` among them (CC-001), because the
interval mapping and every predicate belong to `core.weather`, not here. Anything
missing, null, non-finite or the wrong length fails closed as `Malformed`, which the
planner reports as WEATHER_UNAVAILABLE.

`timeformat=unixtime` gives Unix seconds in UTC, and `timezone=auto` adds the place's
IANA name (`WeatherWindow.tz`) and `utc_offset_seconds`. The daily entries are keyed by
local midnight, so the offset turns one into its local date, which is how the sunrise and
sunset for the local date of `planned_start` are found.

The transport block below is repeated in each provider adapter on purpose: import-linter
contract 4 keeps the adapters independent of each other, and WP3 owns no shared module to
put it in.
"""

import itertools
import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, ClassVar, Final, override

import httpx

from wiggle_outside.core.result import (
    Malformed,
    Ok,
    Outcome,
    QuotaOrUnavailable,
    TransportFailure,
)
from wiggle_outside.core.types import WeatherWindow
from wiggle_outside.planner.ports import ProviderName, WeatherProvider
from wiggle_outside.settings import PROVIDERS_BUDGET_S

if TYPE_CHECKING:
    from datetime import date

    from wiggle_outside.core.types import Coordinates
    from wiggle_outside.settings import Settings

USER_AGENT: Final = "WiggleOutside/0.1"
# BACKEND-CONTRACT section 7: decompressed responses capped at 2 MiB while streaming.
MAX_RESPONSE_BYTES: Final = 2 * 1024 * 1024
STAGE_BUDGET_S: Final = PROVIDERS_BUDGET_S
CONNECT_BUDGET_S: Final = 2.0
# Today and tomorrow in local terms: a 4 h window that starts now always falls inside.
FORECAST_DAYS: Final = 2

# Exactly the variables BACKEND-CONTRACT section 1 requests, in its order.
HOURLY_VARIABLES: Final = (
    "temperature_2m",
    "apparent_temperature",
    "precipitation_probability",
    "precipitation",
    "wind_speed_10m",
    "weather_code",
)
DAILY_VARIABLES: Final = ("sunrise", "sunset")

# The units the request pins, as the API reports them back. Compared case-insensitively,
# so "°C" and "°c" both pass; a missing or different unit rejects the forecast.
EXPECTED_HOURLY_UNITS: Final[dict[str, frozenset[str]]] = {
    "time": frozenset({"unixtime"}),
    "temperature_2m": frozenset({"°c"}),
    "apparent_temperature": frozenset({"°c"}),
    "precipitation_probability": frozenset({"%"}),
    "precipitation": frozenset({"mm"}),
    "wind_speed_10m": frozenset({"km/h", "kmh"}),
    "weather_code": frozenset({"wmo code"}),
}
EXPECTED_DAILY_UNITS: Final[dict[str, frozenset[str]]] = {
    "time": frozenset({"unixtime"}),
    "sunrise": frozenset({"unixtime"}),
    "sunset": frozenset({"unixtime"}),
}

HTTP_OK: Final = 200
HTTP_TOO_MANY_REQUESTS: Final = 429
HTTP_SERVER_ERROR: Final = 500


class _PayloadError(Exception):
    """A required value is missing, null, non-finite, or an array is the wrong length."""


@dataclass(frozen=True, slots=True)
class _Body:
    """A 200 response read whole, inside the size cap."""

    payload: bytes


@dataclass(frozen=True, slots=True)
class _Hourly:
    """The hourly arrays as received, already length-checked against `times`."""

    times: tuple[datetime, ...]
    temp_c: tuple[float, ...]
    apparent_temp_c: tuple[float, ...]
    precip_probability: tuple[int, ...]
    precipitation_mm: tuple[float, ...]
    wind_kmh: tuple[float, ...]
    weather_code: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _Zone:
    """The provider's IANA name and the offset that turns a daily entry into its date."""

    name: str
    offset_s: int


type _Fetched = _Body | Malformed | TransportFailure | QuotaOrUnavailable


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class OpenMeteoWeather(WeatherProvider):
    """One forecast request per call. Never retries, never caches."""

    client: httpx.AsyncClient
    base_url: str
    now: Callable[[], datetime] = _utc_now
    monotonic: Callable[[], float] = time.monotonic
    max_bytes: int = MAX_RESPONSE_BYTES

    provider: ClassVar[ProviderName] = ProviderName.OPEN_METEO

    @override
    async def window(
        self,
        at: Coordinates,
        start: datetime,
        end: datetime,
        deadline: float,
    ) -> Outcome[WeatherWindow]:
        fetched = await self._fetch(at, deadline)
        if not isinstance(fetched, _Body):
            return fetched
        # `fetched_at` is our clock at receipt, never a provider issue time (section 1).
        return _window(fetched.payload, start=start, end=end, fetched_at=self.now())

    async def _fetch(self, at: Coordinates, deadline: float) -> _Fetched:
        budget = min(STAGE_BUDGET_S, deadline - self.monotonic())
        if budget <= 0:
            # No time for an attempt; the same outcome the attempt would have had.
            return TransportFailure()
        request = self.client.build_request(
            "GET",
            self.base_url,
            params=_params(at),
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            timeout=httpx.Timeout(budget, connect=min(budget, CONNECT_BUDGET_S)),
        )
        return await _read(self.client, request, max_bytes=self.max_bytes)


def from_settings(client: httpx.AsyncClient, settings: Settings) -> OpenMeteoWeather:
    """Build the adapter from configuration only (PLAN section 9: no URL from a request)."""
    return OpenMeteoWeather(client=client, base_url=settings.open_meteo_url)


def _params(at: Coordinates) -> dict[str, str]:
    """Typed values only; the coordinates are already rounded to 2 dp."""
    return {
        "latitude": f"{at.lat:.2f}",
        "longitude": f"{at.lon:.2f}",
        "hourly": ",".join(HOURLY_VARIABLES),
        "daily": ",".join(DAILY_VARIABLES),
        "timeformat": "unixtime",
        "timezone": "auto",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "forecast_days": str(FORECAST_DAYS),
    }


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


def _window(
    payload: bytes,
    *,
    start: datetime,
    end: datetime,
    fetched_at: datetime,
) -> Outcome[WeatherWindow]:
    try:
        decoded: object = json.loads(payload)
    except UnicodeDecodeError, json.JSONDecodeError:
        return Malformed()
    if not isinstance(decoded, dict) or not _units_match(decoded):
        return Malformed()
    return _build(decoded, start=start, end=end, fetched_at=fetched_at)


def _build(
    decoded: dict[str, object],
    *,
    start: datetime,
    end: datetime,
    fetched_at: datetime,
) -> Outcome[WeatherWindow]:
    zone = _zone(decoded)
    hourly = _hourly(decoded.get("hourly"))
    if zone is None or hourly is None or not _covers(hourly.times, start=start, end=end):
        return Malformed()
    daylight = _daylight(decoded.get("daily"), start=start, offset_s=zone.offset_s)
    if daylight is None:
        return Malformed()
    return Ok(
        WeatherWindow(
            # `start` and `end` report what the arrays cover, so WP4 can check that a
            # cached entry still spans a new outing window (ARCHITECTURE section 7).
            start=hourly.times[0],
            end=hourly.times[-1],
            fetched_at=fetched_at,
            tz=zone.name,
            times=hourly.times,
            temp_c=hourly.temp_c,
            apparent_temp_c=hourly.apparent_temp_c,
            precip_probability=hourly.precip_probability,
            precipitation_mm=hourly.precipitation_mm,
            wind_kmh=hourly.wind_kmh,
            weather_code=hourly.weather_code,
            sunrise=daylight[0],
            sunset=daylight[1],
        )
    )


def _covers(times: tuple[datetime, ...], *, start: datetime, end: datetime) -> bool:
    """Report whether the arrays span the whole outing window; nothing else is judgeable."""
    return times[0] <= start and end <= times[-1]


def _units_match(decoded: dict[str, object]) -> bool:
    """Section 1: a unit that is missing or different rejects the whole forecast."""
    return _units_ok(decoded.get("hourly_units"), EXPECTED_HOURLY_UNITS) and _units_ok(
        decoded.get("daily_units"), EXPECTED_DAILY_UNITS
    )


def _units_ok(raw: object, expected: dict[str, frozenset[str]]) -> bool:
    if not isinstance(raw, dict):
        return False
    return all(_unit(raw.get(name)) in accepted for name, accepted in expected.items())


def _unit(value: object) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def _zone(decoded: dict[str, object]) -> _Zone | None:
    name = decoded.get("timezone")
    offset = decoded.get("utc_offset_seconds")
    if not isinstance(name, str) or isinstance(offset, bool) or not isinstance(offset, int):
        return None
    return _Zone(name=name, offset_s=offset)


def _hourly(raw: object) -> _Hourly | None:
    try:
        return _parse_hourly(raw)
    except _PayloadError:
        return None


def _parse_hourly(raw: object) -> _Hourly:
    mapping = _mapping(raw)
    times = _times(mapping.get("time"))
    count = len(times)
    return _Hourly(
        times=times,
        temp_c=_floats(mapping.get("temperature_2m"), count),
        apparent_temp_c=_floats(mapping.get("apparent_temperature"), count),
        precip_probability=_ints(mapping.get("precipitation_probability"), count),
        precipitation_mm=_floats(mapping.get("precipitation"), count),
        wind_kmh=_floats(mapping.get("wind_speed_10m"), count),
        weather_code=_ints(mapping.get("weather_code"), count),
    )


def _daylight(
    raw: object,
    *,
    start: datetime,
    offset_s: int,
) -> tuple[datetime, datetime] | None:
    try:
        return _parse_daily(raw, start=start, offset_s=offset_s)
    except _PayloadError:
        return None


def _parse_daily(raw: object, *, start: datetime, offset_s: int) -> tuple[datetime, datetime]:
    """Take the sunrise and sunset of the local date of `planned_start` (section 1)."""
    mapping = _mapping(raw)
    days = _times(mapping.get("time"))
    sunrise = _times(mapping.get("sunrise"))
    sunset = _times(mapping.get("sunset"))
    if len(sunrise) != len(days) or len(sunset) != len(days):
        raise _PayloadError
    wanted = _local_date(start, offset_s)
    for index, day in enumerate(days):
        if _local_date(day, offset_s) == wanted:
            return _ordered(sunrise[index], sunset[index])
    raise _PayloadError


def _local_date(moment: datetime, offset_s: int) -> date:
    """Turn a moment into its local date: a daily entry is local midnight."""
    return (moment + timedelta(seconds=offset_s)).date()


def _ordered(sunrise: datetime, sunset: datetime) -> tuple[datetime, datetime]:
    if sunrise >= sunset:
        raise _PayloadError
    return (sunrise, sunset)


def _mapping(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise _PayloadError
    return raw


def _array(raw: object, count: int | None = None) -> list[object]:
    if not isinstance(raw, list) or (count is not None and len(raw) != count):
        raise _PayloadError
    return raw


def _times(raw: object) -> tuple[datetime, ...]:
    """Unix seconds in UTC. `timezone=auto` only moves where the local day begins."""
    values = tuple(_whole(value) for value in _array(raw))
    if not values or any(later <= earlier for earlier, later in itertools.pairwise(values)):
        raise _PayloadError
    try:
        return tuple(datetime.fromtimestamp(value, UTC) for value in values)
    except (OSError, OverflowError, ValueError) as error:
        raise _PayloadError from error


def _floats(raw: object, count: int) -> tuple[float, ...]:
    return tuple(_real(value) for value in _array(raw, count))


def _ints(raw: object, count: int) -> tuple[int, ...]:
    return tuple(_whole(value) for value in _array(raw, count))


def _real(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise _PayloadError
    return float(value)


def _whole(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _PayloadError
    return value
