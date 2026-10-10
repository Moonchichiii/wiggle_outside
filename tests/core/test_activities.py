"""Activity eligibility: ages, energy ceiling (D18), stroller (D42), daylight, D30, time."""

import dataclasses
import itertools
from datetime import date

import pytest
from support import (
    ALL_BANDS,
    ALL_ENERGIES,
    ALL_SEASONS,
    KIDS_ACTIVITY,
    OPEN_LIMITS,
    SOLO_ACTIVITY,
    kids_conditions,
    kids_constraints,
    samples,
)

from wiggle_outside.core.activities import (
    TROPICS_LAT_DEG,
    Season,
    ages_ok,
    daylight_ok,
    energy_ok,
    fits_time,
    hemisphere_season,
    is_eligible,
    season_allows,
    stroller_ok,
)
from wiggle_outside.core.answers import allowed_energies
from wiggle_outside.core.types import AgeBand, Energy
from wiggle_outside.core.weather import WeatherLimits

STOCKHOLM_LAT = 60.5
CAPE_TOWN_LAT = -33.9
NAIROBI_LAT = -1.3
NO_SEASONS: frozenset[Season] = frozenset()


def band_sets() -> list[frozenset[AgeBand]]:
    return [
        frozenset(combination)
        for size in range(len(ALL_BANDS) + 1)
        for combination in itertools.combinations(ALL_BANDS, size)
    ]


def energy_sets() -> list[frozenset[Energy]]:
    return [
        frozenset(combination)
        for size in range(1, len(ALL_ENERGIES) + 1)
        for combination in itertools.combinations(ALL_ENERGIES, size)
    ]


# --- ages: mandatory for every selected band ----------------------------------------


@pytest.mark.parametrize(("selected", "listed"), list(itertools.product(band_sets(), band_sets())))
def test_an_entry_qualifies_only_if_it_lists_every_selected_band(
    selected: frozenset[AgeBand],
    listed: frozenset[AgeBand],
) -> None:
    activity = dataclasses.replace(KIDS_ACTIVITY, ages=listed)
    expected = (not listed) if not selected else selected <= listed
    assert ages_ok(activity, selected) is expected


def test_mixed_bands_need_an_entry_listing_both() -> None:
    both = frozenset({AgeBand.B0_2, AgeBand.B6_9})
    assert ages_ok(KIDS_ACTIVITY, both)
    narrower = dataclasses.replace(KIDS_ACTIVITY, ages=frozenset({AgeBand.B6_9}))
    assert not ages_ok(narrower, both)


def test_a_solo_run_takes_only_entries_with_no_bands() -> None:
    assert ages_ok(SOLO_ACTIVITY, frozenset())
    assert not ages_ok(KIDS_ACTIVITY, frozenset())


# --- the energy ceiling (D18) -------------------------------------------------------


@pytest.mark.parametrize(
    ("requested", "listed"),
    list(itertools.product(ALL_ENERGIES, energy_sets())),
)
def test_the_ceiling_admits_every_gentler_entry(
    requested: Energy, listed: frozenset[Energy]
) -> None:
    activity = dataclasses.replace(KIDS_ACTIVITY, energy=listed)
    expected = bool(listed & allowed_energies(requested))
    assert energy_ok(activity, requested) is expected


def test_moderate_includes_gentle_and_energetic_includes_both() -> None:
    gentle_entry = dataclasses.replace(KIDS_ACTIVITY, energy=frozenset({Energy.GENTLE}))
    high_entry = dataclasses.replace(KIDS_ACTIVITY, energy=frozenset({Energy.ENERGETIC}))
    assert energy_ok(gentle_entry, Energy.MODERATE)
    assert energy_ok(gentle_entry, Energy.ENERGETIC)
    assert not energy_ok(high_entry, Energy.MODERATE)
    assert not energy_ok(high_entry, Energy.GENTLE)


# --- stroller (D42) and daylight ----------------------------------------------------


@pytest.mark.parametrize(
    ("suits", "stroller", "expected"),
    [(True, True, True), (False, True, False), (False, False, True), (True, False, True)],
)
def test_the_stroller_answer_filters_on_the_activity_only(
    *,
    suits: bool,
    stroller: bool,
    expected: bool,
) -> None:
    activity = dataclasses.replace(KIDS_ACTIVITY, activity_suits_stroller=suits)
    assert stroller_ok(activity, stroller=stroller) is expected


@pytest.mark.parametrize(
    ("daylight_only", "in_daylight", "expected"),
    [(True, True, True), (True, False, False), (False, False, True), (False, True, True)],
)
def test_daylight_only_entries_need_daylight(
    *,
    daylight_only: bool,
    in_daylight: bool,
    expected: bool,
) -> None:
    activity = dataclasses.replace(KIDS_ACTIVITY, daylight_only=daylight_only)
    assert daylight_ok(activity, in_daylight=in_daylight) is expected


def test_a_solo_entry_after_dark_is_unaffected() -> None:
    # The family short-circuit never runs for a solo entry; its own flag decides.
    assert daylight_ok(SOLO_ACTIVITY, in_daylight=False)


# --- seasons (D30) ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("month", "northern"),
    [
        (1, Season.WINTER),
        (2, Season.WINTER),
        (3, Season.SPRING),
        (4, Season.SPRING),
        (5, Season.SPRING),
        (6, Season.SUMMER),
        (7, Season.SUMMER),
        (8, Season.SUMMER),
        (9, Season.AUTUMN),
        (10, Season.AUTUMN),
        (11, Season.AUTUMN),
        (12, Season.WINTER),
    ],
)
def test_the_hemispheres_are_opposite_every_month(month: int, northern: Season) -> None:
    opposites = {
        Season.WINTER: Season.SUMMER,
        Season.SPRING: Season.AUTUMN,
        Season.SUMMER: Season.WINTER,
        Season.AUTUMN: Season.SPRING,
    }
    on = date(2026, month, 15)
    assert hemisphere_season(on, STOCKHOLM_LAT) is northern
    assert hemisphere_season(on, CAPE_TOWN_LAT) is opposites[northern]


@pytest.mark.parametrize("lat", [0.0, 1.3, -1.3, 23.43, -23.43])
def test_inside_the_tropics_there_is_no_season(lat: float) -> None:
    assert hemisphere_season(date(2026, 10, 10), lat) is None


@pytest.mark.parametrize("lat", [TROPICS_LAT_DEG, -TROPICS_LAT_DEG])
def test_the_tropic_boundary_itself_has_a_season(lat: float) -> None:
    assert hemisphere_season(date(2026, 10, 10), lat) is not None


@pytest.mark.parametrize("season", ALL_SEASONS)
def test_no_season_restricted_entry_qualifies_inside_the_tropics(season: Season) -> None:
    assert not season_allows(frozenset({season}), date(2026, 10, 10), NAIROBI_LAT)


def test_an_unrestricted_entry_qualifies_everywhere() -> None:
    for lat in (STOCKHOLM_LAT, CAPE_TOWN_LAT, NAIROBI_LAT):
        assert season_allows(NO_SEASONS, date(2026, 10, 10), lat)


def test_an_autumn_entry_is_out_of_season_in_the_south() -> None:
    autumn = frozenset({Season.AUTUMN})
    assert season_allows(autumn, date(2026, 10, 10), STOCKHOLM_LAT)
    assert not season_allows(autumn, date(2026, 10, 10), CAPE_TOWN_LAT)
    assert season_allows(autumn, date(2026, 4, 10), CAPE_TOWN_LAT)


# --- time (BACKEND-CONTRACT section 8) ----------------------------------------------


@pytest.mark.parametrize(
    ("duration", "travel", "budget", "expected"),
    [
        (20, 0, 30, True),
        (30, 0, 30, True),
        (31, 0, 30, False),
        (20, 10, 30, True),
        (20, 11, 30, False),
        (45, 15, 60, True),
    ],
)
def test_a_pair_qualifies_only_if_travel_plus_duration_fits(
    duration: int,
    travel: int,
    budget: int,
    *,
    expected: bool,
) -> None:
    activity = dataclasses.replace(KIDS_ACTIVITY, duration_min=duration)
    assert fits_time(activity, budget_min=budget, travel_min=travel) is expected


# --- the whole rule set -------------------------------------------------------------


def test_an_eligible_entry_passes_every_rule() -> None:
    assert is_eligible(
        KIDS_ACTIVITY,
        kids_constraints(),
        kids_conditions(),
        OPEN_LIMITS,
        NO_SEASONS,
    )


@pytest.mark.parametrize(
    "broken",
    [
        {"ages": frozenset({AgeBand.B6_9})},
        {"energy": frozenset({Energy.ENERGETIC})},
        {"duration_min": 61},
    ],
)
def test_one_failing_rule_excludes_the_entry(broken: dict[str, object]) -> None:
    activity = dataclasses.replace(KIDS_ACTIVITY, **broken)
    assert not is_eligible(activity, kids_constraints(), kids_conditions(), OPEN_LIMITS, NO_SEASONS)


def test_the_night_run_excludes_a_daylight_only_entry() -> None:
    at_night = dataclasses.replace(kids_conditions(), in_daylight=False)
    assert not is_eligible(KIDS_ACTIVITY, kids_constraints(), at_night, OPEN_LIMITS, NO_SEASONS)


def test_a_stroller_run_excludes_an_unsuitable_entry() -> None:
    with_stroller = dataclasses.replace(kids_constraints(), stroller=True)
    unsuitable = dataclasses.replace(KIDS_ACTIVITY, activity_suits_stroller=False)
    assert not is_eligible(unsuitable, with_stroller, kids_conditions(), OPEN_LIMITS, NO_SEASONS)
    assert is_eligible(KIDS_ACTIVITY, with_stroller, kids_conditions(), OPEN_LIMITS, NO_SEASONS)


def test_a_weather_limit_excludes_the_entry() -> None:
    conditions = dataclasses.replace(kids_conditions(), samples=samples(apparent=(3.0,)))
    baby_limits = WeatherLimits(min_temp_c=5, max_wind_kmh=30, max_rain_pct=60, rain_ok=True)
    assert not is_eligible(
        KIDS_ACTIVITY,
        kids_constraints(),
        conditions,
        baby_limits,
        NO_SEASONS,
    )


def test_the_step_free_preference_never_filters() -> None:
    # D42 P: the preference changes ranking only, so eligibility is identical.
    preferred = dataclasses.replace(kids_constraints(), prefer_step_free=True)
    assert is_eligible(KIDS_ACTIVITY, preferred, kids_conditions(), OPEN_LIMITS, NO_SEASONS)
