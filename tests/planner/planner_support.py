"""Fake ports for the planner tests: scripted providers, a clock the test moves, counters.

No sockets, no sleeps. The weather is a whole day of mild hourly samples around the
WALKTHROUGH fixture's sunrise and sunset, so one window serves the daylight, night,
too-short and severe cases by moving the clock.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Final

from wiggle_outside.core.result import Ok, Outcome
from wiggle_outside.core.types import (
    AgeBand,
    Answers,
    Coordinates,
    Energy,
    GeocodeHit,
    GeocodeHits,
    Pair,
    Place,
    TimeBudget,
    TypedPlace,
    WeatherWindow,
    Who,
)
from wiggle_outside.planner.catalogue import TomlCatalogue, load_catalogue
from wiggle_outside.planner.plan_outing import AllowanceOutcome, Budgets, Ports, Run
from wiggle_outside.planner.ports import RawSelection

DAY: Final = (2026, 10, 10)
MORNING: Final = datetime(*DAY, 8, 31, 6, tzinfo=UTC)  # 10:31 Europe/Stockholm
SUNRISE: Final = datetime(*DAY, 5, 21, tzinfo=UTC)
SUNSET: Final = datetime(*DAY, 16, 20, tzinfo=UTC)
TICK: Final = 1000.0
DEADLINE_S: Final = 18.0
BUDGETS: Final = Budgets(geocode_s=3.0, providers_s=4.0, model_s=11.0)

BERGBY: Final = Coordinates(lat=60.93, lon=17.04)
HITS: Final = (
    GeocodeHit(label="Bergby, Gävleborg, Sweden", coords=BERGBY),
    GeocodeHit(label="Bergby, Uppsala län, Sweden", coords=Coordinates(lat=60.12, lon=17.9)),
    GeocodeHit(label="Bergby, Åland, Finland", coords=Coordinates(lat=60.25, lon=19.95)),
)


def _place(place_id: str, name: str, kind: str, *, at: tuple[float, float]) -> Place:
    # The WALKTHROUGH places: Birchwood reports free admission, Oak Lane step-free access.
    return Place(
        place_id=place_id,
        name=name,
        kind=kind,
        coords=Coordinates(lat=at[0], lon=at[1]),
        fee="no" if place_id == "osm:2" else "unknown",
        osm_access="yes" if place_id == "osm:3" else "unknown",
    )


PLACES: Final = (
    _place("osm:1", "Linden Park", "park", at=(60.935, 17.045)),
    _place("osm:2", "Birchwood Nature Area", "nature_reserve", at=(60.938, 17.04)),
    _place("osm:3", "Oak Lane Park", "park", at=(60.933, 17.038)),
    _place("osm:4", "Elm & Oak Playground", "playground", at=(60.928, 17.042)),
)

ANSWERS: Final = Answers(
    who=Who.KIDS,
    age_bands=frozenset({AgeBand.B3_5, AgeBand.B6_9}),
    time_budget=TimeBudget.H1,
    energy=Energy.MODERATE,
    location=TypedPlace(text="Bergby"),
    stroller=False,
    step_free=False,
)
SOLO: Final = Answers(
    who=Who.SOLO,
    age_bands=frozenset(),
    time_budget=TimeBudget.H1,
    energy=Energy.MODERATE,
    location=BERGBY,
    stroller=False,
    step_free=False,
)


def day_window(
    fetched_at: datetime = MORNING - timedelta(seconds=5), *, code: int = 3
) -> WeatherWindow:
    """Build a whole day of hourly samples: mild, cloudy, dry-ish; `code` sets every hour."""
    times = tuple(datetime(*DAY, hour, tzinfo=UTC) for hour in range(24))
    count = len(times)
    return WeatherWindow(
        start=times[0],
        end=times[-1],
        fetched_at=fetched_at,
        tz="Europe/Stockholm",
        times=times,
        temp_c=(12.0,) * count,
        apparent_temp_c=(11.0,) * count,
        precip_probability=(20,) * count,
        precipitation_mm=(0.0,) * count,
        wind_kmh=(12.0,) * count,
        weather_code=(code,) * count,
        sunrise=SUNRISE,
        sunset=SUNSET,
    )


def day_window_around(moment: datetime, *, code: int = 3) -> WeatherWindow:
    """Build the same mild day around a real `moment`, with daylight either side of it.

    For tests that share a clock with the web layer (real time): the samples cover the
    moment's whole UTC day and the sun is up from six hours before it to six after.
    """
    day = moment.date()
    times = tuple(datetime(day.year, day.month, day.day, hour, tzinfo=UTC) for hour in range(24))
    # A window that ends on the hour needs the next hour's sample too.
    times = (*times, times[-1] + timedelta(hours=1), times[-1] + timedelta(hours=2))
    count = len(times)
    return WeatherWindow(
        start=times[0],
        end=times[-1],
        fetched_at=moment - timedelta(seconds=5),
        tz="Europe/Stockholm",
        times=times,
        temp_c=(12.0,) * count,
        apparent_temp_c=(11.0,) * count,
        precip_probability=(20,) * count,
        precipitation_mm=(0.0,) * count,
        wind_kmh=(12.0,) * count,
        weather_code=(code,) * count,
        sunrise=moment - timedelta(hours=6),
        sunset=moment + timedelta(hours=6),
    )


def window_for(
    start_local: datetime,
    *,
    sunrise_h: int = 7,
    sunset_h: int = 18,
    fetched_at: datetime | None = None,
    code: int = 3,
) -> WeatherWindow:
    """Build two mild days of hourly samples around a local moment (TC-011 tests).

    `start_local` carries a ZoneInfo; the entry's timezone is that zone, and the sun is
    up from `sunrise_h` to `sunset_h` on the local date of `start_local`, as the adapter
    would report for a window starting then. The samples run 48 hours from the UTC
    midnight before the moment, so a next-morning window is covered too.
    """
    tz = getattr(start_local.tzinfo, "key", "UTC")
    moment = start_local.astimezone(UTC)
    first = datetime(moment.year, moment.month, moment.day, tzinfo=UTC)
    times = tuple(first + timedelta(hours=hour) for hour in range(48))
    count = len(times)
    day = start_local.date()
    return WeatherWindow(
        start=times[0],
        end=times[-1],
        fetched_at=fetched_at if fetched_at is not None else moment - timedelta(seconds=5),
        tz=tz,
        times=times,
        temp_c=(12.0,) * count,
        apparent_temp_c=(11.0,) * count,
        precip_probability=(20,) * count,
        precipitation_mm=(0.0,) * count,
        wind_kmh=(12.0,) * count,
        weather_code=(code,) * count,
        sunrise=datetime(day.year, day.month, day.day, sunrise_h, tzinfo=start_local.tzinfo),
        sunset=datetime(day.year, day.month, day.day, sunset_h, tzinfo=start_local.tzinfo),
    )


@dataclass(slots=True)
class FakeClock:
    wall: datetime = MORNING
    tick: float = TICK

    def now(self) -> datetime:
        return self.wall

    def monotonic(self) -> float:
        return self.tick

    def advance(self, seconds: float) -> None:
        self.wall += timedelta(seconds=seconds)
        self.tick += seconds


@dataclass(slots=True)
class Counters:
    events: list[tuple[str, str]] = field(default_factory=list)

    def incr(self, name: str, stage: str) -> None:
        self.events.append((name, stage))


@dataclass(slots=True)
class FakeGeocoder:
    outcome: Outcome[GeocodeHits] = field(default_factory=lambda: Ok(GeocodeHits(hits=HITS[:1])))
    calls: list[tuple[str, float]] = field(default_factory=list)
    gate: asyncio.Event | None = None  # when set, the call blocks until released

    async def resolve(self, place: TypedPlace, deadline: float) -> Outcome[GeocodeHits]:
        self.calls.append((place.text, deadline))
        if self.gate is not None:
            await self.gate.wait()
        return self.outcome


@dataclass(slots=True)
class FakePlaces:
    outcome: Outcome[tuple[Place, ...]] = field(default_factory=lambda: Ok(PLACES))
    calls: list[tuple[Coordinates, int, frozenset[str], float]] = field(default_factory=list)

    async def nearby(
        self, at: Coordinates, radius_m: int, kinds: frozenset[str], deadline: float
    ) -> Outcome[tuple[Place, ...]]:
        self.calls.append((at, radius_m, kinds, deadline))
        return self.outcome


@dataclass(slots=True)
class FakeWeather:
    outcome: Outcome[WeatherWindow] = field(default_factory=lambda: Ok(day_window()))
    calls: list[tuple[Coordinates, datetime, datetime, float]] = field(default_factory=list)
    # Answers for the calls after the first, in order (the morning fetch, TC-011); when
    # exhausted, `outcome` answers again.
    queued: list[Outcome[WeatherWindow]] = field(default_factory=list)

    async def window(
        self, at: Coordinates, start: datetime, end: datetime, deadline: float
    ) -> Outcome[WeatherWindow]:
        self.calls.append((at, start, end, deadline))
        if len(self.calls) > 1 and self.queued:
            return self.queued.pop(0)
        return self.outcome


@dataclass(slots=True)
class FakeModel:
    outcome: Outcome[RawSelection]
    calls: list[tuple[tuple[Pair, ...], str | None, float]] = field(default_factory=list)

    async def __call__(
        self, pairs: tuple[Pair, ...], text: str | None, deadline: float
    ) -> Outcome[RawSelection]:
        self.calls.append((pairs, text, deadline))
        return self.outcome


@dataclass(slots=True)
class FakeAllowance:
    answer: AllowanceOutcome = "reserved"
    calls: list[datetime] = field(default_factory=list)

    async def reserve(self, now: datetime) -> AllowanceOutcome:
        self.calls.append(now)
        return self.answer


@dataclass(slots=True)
class Rig:
    clock: FakeClock
    counters: Counters
    geocoder: FakeGeocoder
    places: FakePlaces
    weather: FakeWeather
    catalogue: TomlCatalogue
    allowance: FakeAllowance | None = None
    model: FakeModel | None = None

    @property
    def ports(self) -> Ports:
        return Ports(
            geocoder=self.geocoder,
            places=self.places,
            weather=self.weather,
            catalogue=self.catalogue,
            clock=self.clock,
            counters=self.counters,
            allowance=self.allowance,
            model=self.model,
        )

    def run(self, answers: Answers = ANSWERS, job_id: str = "J1") -> Run:
        return Run(
            job_id=job_id,
            answers=answers,
            planned_start=self.clock.now(),
            deadline=self.clock.monotonic() + DEADLINE_S,
        )


def rig(
    *,
    geocoder: FakeGeocoder | None = None,
    places: FakePlaces | None = None,
    weather: FakeWeather | None = None,
    allowance: FakeAllowance | None = None,
    model: FakeModel | None = None,
) -> Rig:
    return Rig(
        clock=FakeClock(),
        counters=Counters(),
        geocoder=geocoder or FakeGeocoder(),
        places=places or FakePlaces(),
        weather=weather or FakeWeather(),
        catalogue=load_catalogue(),
        allowance=allowance,
        model=model,
    )
