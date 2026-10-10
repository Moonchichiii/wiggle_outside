"""BACKEND-CONTRACT section 1: interval mapping, predicates and the daylight table."""

import dataclasses
import math
from datetime import UTC, datetime, timedelta

import pytest
from support import (
    APPARENT,
    BOUNDARY_WINDOW,
    OUTING,
    SUNRISE,
    SUNSET,
    TIMES,
    samples,
)

from wiggle_outside.core.answers import OutingWindow
from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import WeatherCondition
from wiggle_outside.core.weather import (
    CONDITION_BY_CODE,
    CONDITION_RANK,
    HEAT_LIMIT_ALONE_C,
    HEAT_LIMIT_WITH_KIDS_C,
    SEVERE_CODES,
    SEVERE_WIND_KMH,
    Samples,
    WeatherLimits,
    ceil_hour,
    daylight_outcome,
    exceeds_heat_limit,
    floor_hour,
    is_dry_window,
    is_in_daylight,
    is_severe,
    limits_satisfied,
    rain_within_limits,
    run_weather_outcome,
    summarise,
    temperature_within_limits,
    used_samples,
    wind_within_limits,
)

ON_THE_HOUR = OutingWindow(start=TIMES[0], end=TIMES[1])


def used(window: OutingWindow = OUTING) -> tuple[tuple[datetime, ...], tuple[datetime, ...]]:
    chosen = used_samples(BOUNDARY_WINDOW, window)
    assert chosen is not None
    return (
        tuple(instant.at for instant in chosen.instants),
        tuple(interval.ends_at for interval in chosen.intervals),
    )


# --- hour arithmetic ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("minute", "expected_floor_hour", "expected_ceil_hour"),
    [(0, 8, 8), (1, 8, 9), (31, 8, 9), (59, 8, 9)],
)
def test_hour_rounding(minute: int, expected_floor_hour: int, expected_ceil_hour: int) -> None:
    at = datetime(2026, 10, 10, 8, minute, tzinfo=UTC)
    assert floor_hour(at) == datetime(2026, 10, 10, expected_floor_hour, tzinfo=UTC)
    assert ceil_hour(at) == datetime(2026, 10, 10, expected_ceil_hour, tzinfo=UTC)


# --- interval mapping (the worked example) -----------------------------------------


def test_instants_are_floor_to_ceil_inclusive() -> None:
    instants, _ = used()
    assert instants == (TIMES[0], TIMES[1], TIMES[2])


def test_intervals_are_those_overlapping_the_window() -> None:
    _, intervals = used()
    assert intervals == (TIMES[1], TIMES[2])


def test_window_ending_on_the_hour_uses_one_interval() -> None:
    instants, intervals = used(ON_THE_HOUR)
    assert instants == (TIMES[0], TIMES[1])
    assert intervals == (TIMES[1],)


def test_window_outside_the_arrays_has_no_samples() -> None:
    earlier = TIMES[0] - timedelta(days=2)
    far = OutingWindow(start=earlier, end=earlier + timedelta(hours=1))
    assert used_samples(BOUNDARY_WINDOW, far) is None


# --- validation fails closed --------------------------------------------------------


@pytest.mark.parametrize(
    "broken",
    [
        {"times": ()},
        {"temp_c": APPARENT[:2]},
        {"apparent_temp_c": APPARENT[:3]},
        {"precip_probability": (20, 30)},
        {"wind_kmh": (12.0,)},
        {"weather_code": (3, 3, 80)},
        {"weather_code": (3, 3, 80, 4)},
        {"apparent_temp_c": (10.6, 11.4, math.nan, 12.2)},
        {"wind_kmh": (12.0, 14.0, math.inf, 20.0)},
        {"precipitation_mm": (0.0, 0.0)},
        {"precipitation_mm": (0.0, 0.0, math.nan, 0.4)},
        {"precipitation_mm": (0.0, 0.0, math.inf, 0.4)},
    ],
)
def test_invalid_arrays_fail_closed(broken: dict[str, object]) -> None:
    window = dataclasses.replace(BOUNDARY_WINDOW, **broken)
    assert used_samples(window, OUTING) is None


def test_precipitation_length_mismatch_fails_closed() -> None:
    window = dataclasses.replace(BOUNDARY_WINDOW, precipitation_mm=(0.0, 0.0))
    assert used_samples(window, OUTING) is None


def test_non_finite_precipitation_fails_closed() -> None:
    window = dataclasses.replace(BOUNDARY_WINDOW, precipitation_mm=(0.0, 0.0, math.nan, 0.4))
    assert used_samples(window, OUTING) is None


def test_the_millimetre_array_reaches_the_intervals() -> None:
    chosen = used_samples(BOUNDARY_WINDOW, OUTING)
    assert chosen is not None
    # The samples used are the 09:00 and 10:00 intervals: 0.0 mm and 0.1 mm.
    assert tuple(interval.precipitation_mm for interval in chosen.intervals) == (0.0, 0.1)


# --- the stored summary -------------------------------------------------------------


def test_summary_comes_from_the_samples_used() -> None:
    chosen = used_samples(BOUNDARY_WINDOW, OUTING)
    assert chosen is not None
    summary = summarise(BOUNDARY_WINDOW, OUTING, chosen)
    assert summary.condition is WeatherCondition.SHOWERS_POSSIBLE
    assert (summary.temp_min_c, summary.temp_max_c) == (11, 12)
    assert summary.max_precip_probability == 40
    assert summary.max_wind_kmh == 18
    assert (summary.window_start, summary.window_end) == (OUTING.start, OUTING.end)
    assert summary.fetched_at == BOUNDARY_WINDOW.fetched_at
    assert summary.tz == BOUNDARY_WINDOW.tz


def test_every_documented_code_maps_to_a_condition() -> None:
    assert set(CONDITION_RANK) == set(WeatherCondition)
    assert set(CONDITION_BY_CODE.values()) == set(WeatherCondition)
    assert set(CONDITION_BY_CODE) >= SEVERE_CODES


def test_the_most_significant_sample_sets_the_condition() -> None:
    chosen = samples(codes=(0, 71, 3))
    summary = summarise(BOUNDARY_WINDOW, OUTING, chosen)
    assert summary.condition is WeatherCondition.SNOW


# --- severe and heat (run-wide) -----------------------------------------------------


@pytest.mark.parametrize("code", sorted(SEVERE_CODES))
def test_every_severe_code_is_severe(code: int) -> None:
    assert is_severe(samples(codes=(code,)))


@pytest.mark.parametrize(
    ("wind", "severe"), [(SEVERE_WIND_KMH, False), (SEVERE_WIND_KMH + 0.1, True)]
)
def test_the_wind_ceiling_is_above_not_at(wind: float, *, severe: bool) -> None:
    assert is_severe(samples(wind=(wind,))) is severe


def test_a_mild_window_is_not_severe() -> None:
    assert not is_severe(samples(codes=(3, 80, 61), wind=(12.0, 18.0, 20.0)))


@pytest.mark.parametrize(
    ("apparent", "with_kids", "expected"),
    [
        (HEAT_LIMIT_WITH_KIDS_C, True, False),
        (HEAT_LIMIT_WITH_KIDS_C + 0.1, True, True),
        (HEAT_LIMIT_WITH_KIDS_C + 0.1, False, False),
        (HEAT_LIMIT_ALONE_C, False, False),
        (HEAT_LIMIT_ALONE_C + 0.1, False, True),
    ],
)
def test_the_heat_rule_is_stricter_with_kids(
    apparent: float, *, with_kids: bool, expected: bool
) -> None:
    assert exceeds_heat_limit(samples(apparent=(apparent,)), with_kids=with_kids) is expected


@pytest.mark.parametrize(
    ("chosen", "expected"),
    [
        (samples(), None),
        (samples(codes=(95,)), ErrorCode.WEATHER_RESTRICTED),
        (samples(apparent=(31.0,)), ErrorCode.WEATHER_RESTRICTED),
    ],
)
def test_run_weather_outcome(chosen: Samples, expected: ErrorCode | None) -> None:
    assert run_weather_outcome(chosen, with_kids=True) == expected


# --- per-entry limits ---------------------------------------------------------------


@pytest.mark.parametrize(("apparent", "expected"), [(5.0, True), (4.9, False), (20.0, True)])
def test_the_temperature_floor_includes_its_own_value(apparent: float, *, expected: bool) -> None:
    assert temperature_within_limits(samples(apparent=(apparent,)), min_temp_c=5) is expected


@pytest.mark.parametrize(("apparent", "expected"), [(25.0, True), (25.1, False)])
def test_an_optional_temperature_ceiling_includes_its_own_value(
    apparent: float, *, expected: bool
) -> None:
    chosen = samples(apparent=(apparent,))
    assert temperature_within_limits(chosen, min_temp_c=0, max_temp_c=25) is expected


@pytest.mark.parametrize(("wind", "expected"), [(30.0, True), (30.1, False)])
def test_the_wind_limit_includes_its_own_value(wind: float, *, expected: bool) -> None:
    assert wind_within_limits(samples(wind=(wind,)), max_wind_kmh=30) is expected


def test_one_bad_sample_breaks_a_limit() -> None:
    assert not wind_within_limits(samples(wind=(10.0, 40.0, 10.0)), max_wind_kmh=30)
    assert not temperature_within_limits(samples(apparent=(10.0, 1.0, 10.0)), min_temp_c=5)


@pytest.mark.parametrize(
    ("rain", "rain_ok", "expected"),
    [
        (((60, 0.0),), False, True),
        (((60, 0.1),), False, False),
        (((60, 0.1),), True, True),
        (((61, 0.0),), True, False),
        (((61, 0.0),), False, False),
        (((20, 0.0), (60, 0.0)), False, True),
        (((20, 0.0), (61, 0.0)), True, False),
    ],
)
def test_rain_limits(rain: tuple[tuple[int, float], ...], *, rain_ok: bool, expected: bool) -> None:
    chosen = samples(rain=rain)
    assert rain_within_limits(chosen, rain_ok=rain_ok, max_rain_pct=60) is expected


@pytest.mark.parametrize(
    ("rain", "expected"),
    [
        (((20, 0.0),), True),
        (((21, 0.0),), False),
        (((20, 0.1),), False),
        (((0, 0.0), (20, 0.0)), True),
    ],
)
def test_dry_window_reason(rain: tuple[tuple[int, float], ...], *, expected: bool) -> None:
    assert is_dry_window(samples(rain=rain)) is expected


def test_limits_satisfied_needs_every_limit() -> None:
    limits = WeatherLimits(min_temp_c=5, max_wind_kmh=30, max_rain_pct=60, rain_ok=True)
    assert limits_satisfied(samples(apparent=(10.0,), wind=(20.0,), rain=((40, 0.1),)), limits)
    assert not limits_satisfied(samples(apparent=(4.0,), wind=(20.0,), rain=((40, 0.1),)), limits)
    assert not limits_satisfied(samples(apparent=(10.0,), wind=(31.0,), rain=((40, 0.1),)), limits)
    assert not limits_satisfied(samples(apparent=(10.0,), wind=(20.0,), rain=((61, 0.0),)), limits)


def test_the_walkthrough_window_passes_a_rain_ready_entry() -> None:
    chosen = used_samples(BOUNDARY_WINDOW, OUTING)
    assert chosen is not None
    rain_ready = WeatherLimits(min_temp_c=5, max_wind_kmh=30, max_rain_pct=60, rain_ok=True)
    dry_only = WeatherLimits(min_temp_c=5, max_wind_kmh=30, max_rain_pct=60, rain_ok=False)
    assert limits_satisfied(chosen, rain_ready)
    assert not limits_satisfied(chosen, dry_only)
    assert run_weather_outcome(chosen, with_kids=True) is None


# --- daylight (family path) ---------------------------------------------------------


def window_at(start: datetime, minutes: int = 60) -> OutingWindow:
    return OutingWindow(start=start, end=start + timedelta(minutes=minutes))


@pytest.mark.parametrize(
    ("window", "expected"),
    [
        (window_at(SUNRISE - timedelta(minutes=1)), ErrorCode.DAYLIGHT_NIGHT),
        (window_at(SUNRISE), None),
        (window_at(SUNRISE + timedelta(minutes=1)), None),
        (window_at(SUNSET - timedelta(minutes=61)), None),
        (window_at(SUNSET - timedelta(minutes=60)), None),
        (window_at(SUNSET - timedelta(minutes=59)), ErrorCode.DAYLIGHT_TOO_SHORT),
        (window_at(SUNSET - timedelta(minutes=1)), ErrorCode.DAYLIGHT_TOO_SHORT),
        (window_at(SUNSET), ErrorCode.DAYLIGHT_NIGHT),
        (window_at(SUNSET + timedelta(minutes=1)), ErrorCode.DAYLIGHT_NIGHT),
    ],
)
def test_daylight_outcome_at_the_boundaries(
    window: OutingWindow, expected: ErrorCode | None
) -> None:
    assert daylight_outcome(window, SUNRISE, SUNSET) == expected


def test_start_at_sunset_is_night_not_too_short() -> None:
    # Both conditions hold at start = sunset; the table orders night first.
    assert daylight_outcome(window_at(SUNSET), SUNRISE, SUNSET) is ErrorCode.DAYLIGHT_NIGHT


def test_end_exactly_at_sunset_still_fits() -> None:
    window = OutingWindow(start=SUNSET - timedelta(hours=1), end=SUNSET)
    assert daylight_outcome(window, SUNRISE, SUNSET) is None
    assert is_in_daylight(window, SUNRISE, SUNSET)


@pytest.mark.parametrize(
    ("window", "expected"),
    [
        (window_at(SUNRISE), True),
        (window_at(SUNRISE - timedelta(minutes=1)), False),
        (OutingWindow(start=SUNSET - timedelta(hours=1), end=SUNSET), True),
        (window_at(SUNSET - timedelta(minutes=30)), False),
    ],
)
def test_is_in_daylight_matches_the_daylight_row(window: OutingWindow, *, expected: bool) -> None:
    assert is_in_daylight(window, SUNRISE, SUNSET) is expected
