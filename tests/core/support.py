"""Builders for the core rule tests.

The weather values are the WALKTHROUGH fixture `open_meteo_boundary.json`
(BACKEND-CONTRACT section 1 worked example). `temperature_2m` is not in that fixture, so
it is set one degree above `apparent_temperature` here: the summary must report the
apparent values.
"""

from datetime import UTC, datetime
from typing import Final

from wiggle_outside.core.activities import Conditions, Season
from wiggle_outside.core.answers import Constraints, OutingWindow
from wiggle_outside.core.types import (
    Activity,
    AgeBand,
    Answers,
    Coordinates,
    Energy,
    TimeBudget,
    WeatherWindow,
    Who,
)
from wiggle_outside.core.weather import Instant, Interval, Samples, WeatherLimits

DAY: Final = (2026, 10, 10)
TIMES: Final = tuple(datetime(*DAY, hour, tzinfo=UTC) for hour in (8, 9, 10, 11))
APPARENT: Final = (10.6, 11.4, 11.9, 12.2)
WIND: Final = (12.0, 14.0, 18.0, 20.0)
CODES: Final = (3, 3, 80, 61)
PROBABILITY: Final = (20, 30, 40, 50)
PRECIPITATION_MM: Final = (0.0, 0.0, 0.1, 0.4)
SUNRISE: Final = datetime(*DAY, 5, 21, tzinfo=UTC)
SUNSET: Final = datetime(*DAY, 16, 20, tzinfo=UTC)
FETCHED_AT: Final = datetime(*DAY, 8, 31, 1, tzinfo=UTC)

# The walkthrough outing: 10:31-11:31 Europe/Stockholm.
OUTING: Final = OutingWindow(
    start=datetime(*DAY, 8, 31, tzinfo=UTC),
    end=datetime(*DAY, 9, 31, tzinfo=UTC),
)

BOUNDARY_WINDOW: Final = WeatherWindow(
    start=TIMES[0],
    end=TIMES[-1],
    fetched_at=FETCHED_AT,
    tz="Europe/Stockholm",
    times=TIMES,
    temp_c=tuple(value + 1.0 for value in APPARENT),
    apparent_temp_c=APPARENT,
    precip_probability=PROBABILITY,
    wind_kmh=WIND,
    weather_code=CODES,
    sunrise=SUNRISE,
    sunset=SUNSET,
)

# A kids' entry: every kids' entry in the catalogue is daylight-only (CATALOGUE W4).
KIDS_ACTIVITY: Final = Activity(
    activity_id="nature-bingo",
    title="Nature bingo",
    ages=frozenset({AgeBand.B0_2, AgeBand.B3_5, AgeBand.B6_9, AgeBand.B10_12}),
    energy=frozenset({Energy.GENTLE, Energy.MODERATE}),
    interests=(),
    generic_ok=False,
    activity_suits_stroller=True,
    daylight_only=True,
    min_temp_c=5,
    max_wind_kmh=30,
    duration_min=20,
    place_kinds=frozenset({"park"}),
    steps=("Look for a bird.",),
    optional=(),
    adapt="Listen instead.",
    ask="Which was hardest?",
    safety="Stay on the path.",
    card=(),
)

SOLO_ACTIVITY: Final = Activity(
    activity_id="slow-reset",
    title="Slow reset",
    ages=frozenset(),
    energy=frozenset({Energy.GENTLE}),
    interests=(),
    generic_ok=True,
    activity_suits_stroller=False,
    daylight_only=False,
    min_temp_c=0,
    max_wind_kmh=30,
    duration_min=20,
    place_kinds=frozenset({"any"}),
    steps=("Walk slowly.",),
    optional=(),
    adapt="Sit instead.",
    ask=None,
    safety="Mind the traffic.",
    card=(),
)

# Limits no sample in the fixture breaks.
OPEN_LIMITS: Final = WeatherLimits(min_temp_c=-50, max_wind_kmh=100, max_rain_pct=100, rain_ok=True)

KIDS_ANSWERS: Final = Answers(
    who=Who.KIDS,
    age_bands=frozenset({AgeBand.B3_5, AgeBand.B6_9}),
    time_budget=TimeBudget.H1,
    energy=Energy.MODERATE,
    location=Coordinates(lat=60.5, lon=17.2),
    stroller=False,
    step_free=False,
)

SOLO_ANSWERS: Final = Answers(
    who=Who.SOLO,
    age_bands=frozenset(),
    time_budget=TimeBudget.M30,
    energy=Energy.GENTLE,
    location=Coordinates(lat=60.5, lon=17.2),
    stroller=False,
    step_free=False,
)

ALL_BANDS: Final = (AgeBand.B0_2, AgeBand.B3_5, AgeBand.B6_9, AgeBand.B10_12)
ALL_ENERGIES: Final = (Energy.GENTLE, Energy.MODERATE, Energy.ENERGETIC)
ALL_SEASONS: Final = (Season.SPRING, Season.SUMMER, Season.AUTUMN, Season.WINTER)


def samples(
    *,
    apparent: tuple[float, ...] = (10.0,),
    wind: tuple[float, ...] = (10.0,),
    codes: tuple[int, ...] = (3,),
    rain: tuple[tuple[int, float], ...] = ((10, 0.0),),
) -> Samples:
    """Build the samples a window would use, straight from the values under test.

    The shortest arrays repeat, so one varying array sets how many instants there are.
    """
    count = max(len(apparent), len(wind), len(codes))
    instants = tuple(
        Instant(
            at=TIMES[index % len(TIMES)],
            temp_c=apparent[index % len(apparent)] + 1.0,
            apparent_temp_c=apparent[index % len(apparent)],
            wind_kmh=wind[index % len(wind)],
            code=codes[index % len(codes)],
        )
        for index in range(count)
    )
    intervals = tuple(
        Interval(
            ends_at=TIMES[index % len(TIMES)], probability=probability, precipitation_mm=millimetres
        )
        for index, (probability, millimetres) in enumerate(rain)
    )
    return Samples(instants=instants, intervals=intervals)


def kids_constraints() -> Constraints:
    return Constraints(
        window=OUTING,
        budget_min=TimeBudget.H1.value,
        age_bands=frozenset({AgeBand.B3_5, AgeBand.B6_9}),
        energy=Energy.MODERATE,
        with_kids=True,
        stroller=False,
        prefer_step_free=False,
    )


def kids_conditions() -> Conditions:
    return Conditions(
        samples=samples(),
        local_date=OUTING.start.date(),
        lat=60.5,
        in_daylight=True,
    )
