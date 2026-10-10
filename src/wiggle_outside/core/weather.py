"""Outing-window summary, weather limits and daylight.

The interval semantics, predicates and the daylight table are BACKEND-CONTRACT section 1;
where this file and another document differ, that contract wins. Every function is pure:
no verdict is stored, so the daylight short-circuit lasts exactly one run (TC-002).
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import WeatherCondition, WeatherSummary, WeatherWindow

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from wiggle_outside.core.answers import OutingWindow

HOUR: Final = timedelta(hours=1)

# Severe weather excludes every activity. Code set: starting value (BACKEND-CONTRACT 1).
SEVERE_CODES: Final[frozenset[int]] = frozenset({56, 57, 65, 66, 67, 75, 82, 86, 95, 96, 99})
SEVERE_WIND_KMH: Final = 50.0
HEAT_LIMIT_WITH_KIDS_C: Final = 30.0
HEAT_LIMIT_ALONE_C: Final = 32.0
DRY_WINDOW_MAX_PCT: Final = 20
DRY_MM: Final = 0.0

# The WMO codes Open-Meteo documents. A code outside this map fails closed.
# No document gives the code-to-condition mapping: this one is WP1's choice,
# with Mats to confirm it. It reproduces the WALKTHROUGH step 6 summary.
CONDITION_BY_CODE: Final[dict[int, WeatherCondition]] = {
    0: WeatherCondition.CLEAR,
    1: WeatherCondition.CLEAR,
    2: WeatherCondition.CLOUDY,
    3: WeatherCondition.CLOUDY,
    45: WeatherCondition.FOG,
    48: WeatherCondition.FOG,
    51: WeatherCondition.SHOWERS_POSSIBLE,
    53: WeatherCondition.SHOWERS_POSSIBLE,
    55: WeatherCondition.SHOWERS_POSSIBLE,
    56: WeatherCondition.RAIN_LIKELY,
    57: WeatherCondition.RAIN_LIKELY,
    61: WeatherCondition.RAIN_LIKELY,
    63: WeatherCondition.RAIN_LIKELY,
    65: WeatherCondition.RAIN_LIKELY,
    66: WeatherCondition.RAIN_LIKELY,
    67: WeatherCondition.RAIN_LIKELY,
    71: WeatherCondition.SNOW,
    73: WeatherCondition.SNOW,
    75: WeatherCondition.SNOW,
    77: WeatherCondition.SNOW,
    80: WeatherCondition.SHOWERS_POSSIBLE,
    81: WeatherCondition.SHOWERS_POSSIBLE,
    82: WeatherCondition.RAIN_LIKELY,
    85: WeatherCondition.SNOW,
    86: WeatherCondition.SNOW,
    95: WeatherCondition.RAIN_LIKELY,
    96: WeatherCondition.RAIN_LIKELY,
    99: WeatherCondition.RAIN_LIKELY,
}

# Least to most significant; the summary reports the most significant sample used.
# The order is WP1's choice too, pending the same review.
CONDITION_SEVERITY: Final[tuple[WeatherCondition, ...]] = (
    WeatherCondition.CLEAR,
    WeatherCondition.CLOUDY,
    WeatherCondition.FOG,
    WeatherCondition.SHOWERS_POSSIBLE,
    WeatherCondition.RAIN_LIKELY,
    WeatherCondition.SNOW,
)

CONDITION_RANK: Final[dict[WeatherCondition, int]] = {
    condition: rank for rank, condition in enumerate(CONDITION_SEVERITY)
}


@dataclass(frozen=True, slots=True)
class Instant:
    """One instant sample: `weather_code`, temperatures and wind at `at`."""

    at: datetime
    temp_c: float
    apparent_temp_c: float
    wind_kmh: float
    code: int


@dataclass(frozen=True, slots=True)
class Interval:
    """One preceding-hour sample `(ends_at - 1h, ends_at]`: probability and millimetres."""

    ends_at: datetime
    probability: int
    precipitation_mm: float


@dataclass(frozen=True, slots=True)
class Samples:
    """The samples an outing window actually uses, and the only input to the predicates."""

    instants: tuple[Instant, ...]
    intervals: tuple[Interval, ...]


@dataclass(frozen=True, slots=True)
class WeatherLimits:
    """One activity's weather limits, applied on top of the severe and heat rules."""

    min_temp_c: int
    max_wind_kmh: int
    max_rain_pct: int
    rain_ok: bool
    max_temp_c: int | None = None


def floor_hour(at: datetime) -> datetime:
    return at.replace(minute=0, second=0, microsecond=0)


def ceil_hour(at: datetime) -> datetime:
    floored = floor_hour(at)
    return floored if floored == at else floored + HOUR


def used_samples(window: WeatherWindow, outing: OutingWindow) -> Samples | None:
    """Select the samples an outing window uses, or None if the arrays fail validation."""
    if not _arrays_usable(window):
        return None
    instants = tuple(_select_instants(window, outing))
    intervals = tuple(_select_intervals(window, outing))
    if not instants or not intervals:
        return None
    return Samples(instants=instants, intervals=intervals)


def summarise(window: WeatherWindow, outing: OutingWindow, samples: Samples) -> WeatherSummary:
    """Derive the stored summary from the samples used, never from the whole forecast.

    The temperatures are the apparent ones, rounded to the nearest degree: the
    WALKTHROUGH fixture carries no `temperature_2m` and only this reading gives its
    stated 11-12 degrees. WP1's choice, pending review.
    """
    apparent = tuple(instant.apparent_temp_c for instant in samples.instants)
    return WeatherSummary(
        fetched_at=window.fetched_at,
        tz=window.tz,
        window_start=outing.start,
        window_end=outing.end,
        condition=_worst_condition(samples.instants),
        temp_min_c=round(min(apparent)),
        temp_max_c=round(max(apparent)),
        max_precip_probability=max(interval.probability for interval in samples.intervals),
        max_wind_kmh=round(max(instant.wind_kmh for instant in samples.instants)),
    )


def is_severe(samples: Samples) -> bool:
    """Severe weather excludes every activity, whatever an entry's own limits say."""
    return any(
        instant.code in SEVERE_CODES or instant.wind_kmh > SEVERE_WIND_KMH
        for instant in samples.instants
    )


def exceeds_heat_limit(samples: Samples, *, with_kids: bool) -> bool:
    """Apply the global heat rule: 30 degrees apparent with kids, 32 alone."""
    limit = HEAT_LIMIT_WITH_KIDS_C if with_kids else HEAT_LIMIT_ALONE_C
    return any(instant.apparent_temp_c > limit for instant in samples.instants)


def run_weather_outcome(samples: Samples, *, with_kids: bool) -> ErrorCode | None:
    """Return WEATHER_RESTRICTED when a run-wide rule excludes everything."""
    if is_severe(samples) or exceeds_heat_limit(samples, with_kids=with_kids):
        return ErrorCode.WEATHER_RESTRICTED
    return None


def temperature_within_limits(
    samples: Samples,
    *,
    min_temp_c: int,
    max_temp_c: int | None = None,
) -> bool:
    """Every apparent-temperature sample is at or above the floor, and under any ceiling."""
    apparent = tuple(instant.apparent_temp_c for instant in samples.instants)
    if any(value < min_temp_c for value in apparent):
        return False
    return max_temp_c is None or all(value <= max_temp_c for value in apparent)


def wind_within_limits(samples: Samples, *, max_wind_kmh: int) -> bool:
    return all(instant.wind_kmh <= max_wind_kmh for instant in samples.instants)


def rain_within_limits(samples: Samples, *, rain_ok: bool, max_rain_pct: int) -> bool:
    """Probability stays under the entry's limit; an entry that is not rain-ready needs 0 mm."""
    if any(interval.probability > max_rain_pct for interval in samples.intervals):
        return False
    return rain_ok or all(interval.precipitation_mm <= DRY_MM for interval in samples.intervals)


def is_dry_window(samples: Samples) -> bool:
    """Reason `dry_window`: every interval at or under 20 per cent and 0 mm."""
    return all(
        interval.probability <= DRY_WINDOW_MAX_PCT and interval.precipitation_mm <= DRY_MM
        for interval in samples.intervals
    )


def limits_satisfied(samples: Samples, limits: WeatherLimits) -> bool:
    """Apply one entry's own limits. The severe and heat rules are checked separately."""
    checks = (
        temperature_within_limits(
            samples,
            min_temp_c=limits.min_temp_c,
            max_temp_c=limits.max_temp_c,
        ),
        wind_within_limits(samples, max_wind_kmh=limits.max_wind_kmh),
        rain_within_limits(samples, rain_ok=limits.rain_ok, max_rain_pct=limits.max_rain_pct),
    )
    return all(checks)


def daylight_outcome(
    window: OutingWindow,
    sunrise: datetime,
    sunset: datetime,
) -> ErrorCode | None:
    """Decide the family path before any activity is checked (BACKEND-CONTRACT section 1).

    `sunrise` and `sunset` are the validated daily values for the local date of
    `window.start`. None means carry on with the normal eligibility rules.
    """
    if window.start < sunrise or window.start >= sunset:
        return ErrorCode.DAYLIGHT_NIGHT
    if window.end > sunset:
        return ErrorCode.DAYLIGHT_TOO_SHORT
    return None


def is_in_daylight(window: OutingWindow, sunrise: datetime, sunset: datetime) -> bool:
    """Apply the daylight row of the interval table: `sunrise <= start`, `end <= sunset`."""
    return sunrise <= window.start and window.end <= sunset


def _worst_condition(instants: tuple[Instant, ...]) -> WeatherCondition:
    ranks = (CONDITION_RANK[CONDITION_BY_CODE[instant.code]] for instant in instants)
    return CONDITION_SEVERITY[max(ranks)]


def _arrays_usable(window: WeatherWindow) -> bool:
    if not window.times:
        return False
    expected = len(window.times)
    lengths = (
        len(window.temp_c),
        len(window.apparent_temp_c),
        len(window.precip_probability),
        len(window.precipitation_mm),
        len(window.wind_kmh),
        len(window.weather_code),
    )
    if any(length != expected for length in lengths):
        return False
    if any(code not in CONDITION_BY_CODE for code in window.weather_code):
        return False
    return _all_finite(
        window.temp_c,
        window.apparent_temp_c,
        window.wind_kmh,
        window.precipitation_mm,
    )


def _all_finite(*arrays: Iterable[float]) -> bool:
    return all(math.isfinite(value) for array in arrays for value in array)


def _select_instants(window: WeatherWindow, outing: OutingWindow) -> Iterator[Instant]:
    first = floor_hour(outing.start)
    last = ceil_hour(outing.end)
    for index, at in enumerate(window.times):
        if first <= at <= last:
            yield Instant(
                at=at,
                temp_c=window.temp_c[index],
                apparent_temp_c=window.apparent_temp_c[index],
                wind_kmh=window.wind_kmh[index],
                code=window.weather_code[index],
            )


def _select_intervals(window: WeatherWindow, outing: OutingWindow) -> Iterator[Interval]:
    for index, at in enumerate(window.times):
        if at - HOUR < outing.end and at > outing.start:
            yield Interval(
                ends_at=at,
                probability=window.precip_probability[index],
                precipitation_mm=window.precipitation_mm[index],
            )
