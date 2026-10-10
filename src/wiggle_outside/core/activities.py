"""Catalogue entries and the matching rules.

Age, energy (D18), stroller (D42), daylight, season (D30), time and the per-entry weather
limits. Pure functions; the run-wide severe, heat and daylight rules run first in
`core.weather`.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from wiggle_outside.core.answers import Constraints, allowed_energies
from wiggle_outside.core.weather import Samples, WeatherLimits, limits_satisfied

if TYPE_CHECKING:
    from wiggle_outside.core.types import Activity, AgeBand, Energy

# D30: inside the tropics no season-restricted activity qualifies.
TROPICS_LAT_DEG: Final = 23.44


class Season(StrEnum):
    """Meteorological seasons (D30). Not a stored value; derived per run."""

    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


# Meteorological seasons north of the tropics, by month of the local date.
NORTHERN_SEASON_BY_MONTH: Final[dict[int, Season]] = {
    1: Season.WINTER,
    2: Season.WINTER,
    3: Season.SPRING,
    4: Season.SPRING,
    5: Season.SPRING,
    6: Season.SUMMER,
    7: Season.SUMMER,
    8: Season.SUMMER,
    9: Season.AUTUMN,
    10: Season.AUTUMN,
    11: Season.AUTUMN,
    12: Season.WINTER,
}

OPPOSITE_SEASON: Final[dict[Season, Season]] = {
    Season.SPRING: Season.AUTUMN,
    Season.SUMMER: Season.WINTER,
    Season.AUTUMN: Season.SPRING,
    Season.WINTER: Season.SUMMER,
}


@dataclass(frozen=True, slots=True)
class Conditions:
    """Everything outside the answers that eligibility depends on, for one run."""

    samples: Samples
    local_date: date
    lat: float
    in_daylight: bool
    travel_min: int = 0


def hemisphere_season(on: date, lat: float) -> Season | None:
    """Return the season at a latitude, or None inside the tropics (D30)."""
    if abs(lat) < TROPICS_LAT_DEG:
        return None
    northern = NORTHERN_SEASON_BY_MONTH[on.month]
    return northern if lat > 0 else OPPOSITE_SEASON[northern]


def season_allows(seasons: frozenset[Season], on: date, lat: float) -> bool:
    """Allow any date when the season set is empty; otherwise require the run's season."""
    if not seasons:
        return True
    season = hemisphere_season(on, lat)
    return season is not None and season in seasons


def ages_ok(activity: Activity, age_bands: frozenset[AgeBand]) -> bool:
    """Every selected band must be listed; a solo run takes only entries with no bands."""
    if not age_bands:
        return not activity.ages
    return age_bands <= activity.ages


def energy_ok(activity: Activity, requested: Energy) -> bool:
    """Treat the quiz value as a ceiling, so a gentler entry still qualifies (D18)."""
    return bool(activity.energy & allowed_energies(requested))


def stroller_ok(activity: Activity, *, stroller: bool) -> bool:
    """D42: bringing a stroller keeps only entries the activity itself suits."""
    return activity.activity_suits_stroller or not stroller


def daylight_ok(activity: Activity, *, in_daylight: bool) -> bool:
    return in_daylight or not activity.daylight_only


def fits_time(activity: Activity, *, budget_min: int, travel_min: int) -> bool:
    """BACKEND-CONTRACT section 8: the pair qualifies only if travel + min <= budget."""
    return travel_min + activity.duration_min <= budget_min


def is_eligible(
    activity: Activity,
    constraints: Constraints,
    conditions: Conditions,
    limits: WeatherLimits,
    seasons: frozenset[Season],
) -> bool:
    """Apply every per-entry rule to one catalogue entry.

    `limits` and `seasons` are the catalogue fields `Activity` does not carry yet
    (CC-002 in the WP1 report).
    """
    checks = (
        ages_ok(activity, constraints.age_bands),
        energy_ok(activity, constraints.energy),
        stroller_ok(activity, stroller=constraints.stroller),
        daylight_ok(activity, in_daylight=conditions.in_daylight),
        season_allows(seasons, conditions.local_date, conditions.lat),
        fits_time(
            activity,
            budget_min=constraints.budget_min,
            travel_min=conditions.travel_min,
        ),
        limits_satisfied(conditions.samples, limits),
    )
    return all(checks)
