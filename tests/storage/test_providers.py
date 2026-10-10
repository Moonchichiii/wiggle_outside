"""CONTRACTS section 4.1: the wrappers return the same port types the planner uses."""

import inspect
import json
from dataclasses import dataclass, field
from datetime import timedelta

import pytest
from fakes import (
    BYTES_CODEC,
    TICK,
    DictStore,
    FakeClock,
    RecordingCounters,
    engine_for,
    key_for,
    weather_window,
)

from wiggle_outside.core.result import Empty, Ok, Outcome
from wiggle_outside.core.types import Coordinates, GeocodeHits, Place, TypedPlace, WeatherWindow
from wiggle_outside.planner.ports import (
    CacheStore,
    Geocoder,
    PlacesProvider,
    ProviderGate,
    ProviderName,
    SingleFlight,
    WeatherProvider,
)
from wiggle_outside.storage.cache import SqliteCache
from wiggle_outside.storage.counters import CACHE_NOT_COVERING, CACHE_UNWRITABLE
from wiggle_outside.storage.flight import MemorySingleFlight
from wiggle_outside.storage.gate import MemoryGate
from wiggle_outside.storage.providers import (
    GEOCODE_CODEC,
    GEOCODE_TTL,
    PLACES_CODEC,
    PLACES_TTL,
    WEATHER_TTL,
    cached_geocoder,
    cached_places,
    cached_weather,
    weather_codec,
)
from wiggle_outside.storage.wrapper import CacheWiring, Codec, Request, obtain

AT = Coordinates(lat=59.3293, lon=18.0686)
KINDS = frozenset({"park"})
RADIUS = 3_000
DEADLINE = TICK + 10.0
START = FakeClock().now()
END = START + timedelta(hours=2)
PLACE = Place(
    place_id="n/1",
    name="Gubbängsfältet",
    kind="park",
    coords=AT,
    fee="no",
    osm_access="unknown",
)


@dataclass(slots=True)
class SpyGeocoder:
    seen: list[tuple[TypedPlace, float]] = field(default_factory=list)

    async def resolve(self, place: TypedPlace, deadline: float) -> Outcome[GeocodeHits]:
        self.seen.append((place, deadline))
        return Empty()


@dataclass(slots=True)
class SpyPlaces:
    seen: list[tuple[Coordinates, int, frozenset[str], float]] = field(default_factory=list)

    async def nearby(
        self,
        at: Coordinates,
        radius_m: int,
        kinds: frozenset[str],
        deadline: float,
    ) -> Outcome[tuple[Place, ...]]:
        self.seen.append((at, radius_m, kinds, deadline))
        return Ok((PLACE,))


@dataclass(slots=True)
class SpyWeather:
    seen: list[tuple[Coordinates, object, object, float]] = field(default_factory=list)

    async def window(
        self,
        at: Coordinates,
        start: object,
        end: object,
        deadline: float,
    ) -> Outcome[WeatherWindow]:
        self.seen.append((at, start, end, deadline))
        return Empty()


def wiring() -> tuple[CacheWiring, DictStore, RecordingCounters, FakeClock]:
    clock = FakeClock()
    counters = RecordingCounters()
    store = DictStore()
    built = CacheWiring(
        store=store,
        gate=MemoryGate(clock),
        flight=MemorySingleFlight(counters, clock),
        counters=counters,
        clock=clock,
    )
    return built, store, counters, clock


def geocoder() -> tuple[Geocoder, SpyGeocoder]:
    built, _store, counters, clock = wiring()
    inner = SpyGeocoder()
    return cached_geocoder(inner, built.store, built.gate, built.flight, counters, clock), inner


@pytest.mark.asyncio
async def test_the_cached_geocoder_passes_the_place_and_the_deadline_through() -> None:
    wrapped, inner = geocoder()

    await wrapped.resolve(TypedPlace(text="Gubbängen"), DEADLINE)

    assert inner.seen == [(TypedPlace(text="Gubbängen"), DEADLINE)]


@pytest.mark.asyncio
async def test_the_cached_places_provider_passes_every_argument_through() -> None:
    built, _store, counters, clock = wiring()
    inner = SpyPlaces()
    wrapped = cached_places(inner, built.store, built.gate, built.flight, counters, clock)

    await wrapped.nearby(AT, RADIUS, KINDS, DEADLINE)

    assert inner.seen == [(AT, RADIUS, KINDS, DEADLINE)]


@pytest.mark.asyncio
async def test_the_cached_weather_provider_passes_the_window_through() -> None:
    built, _store, counters, clock = wiring()
    inner = SpyWeather()
    wrapped = cached_weather(inner, built.store, built.gate, built.flight, counters, clock)

    await wrapped.window(AT, START, END, DEADLINE)

    assert inner.seen == [(AT, START, END, DEADLINE)]


@pytest.mark.asyncio
async def test_an_empty_geocode_answer_is_served_from_the_cache_next_time() -> None:
    wrapped, inner = geocoder()
    place = TypedPlace(text="Gubbängen")

    assert await wrapped.resolve(place, DEADLINE) == Empty()
    assert await wrapped.resolve(place, DEADLINE) == Empty()
    assert len(inner.seen) == 1  # the second call never reached the provider


def test_each_wrapper_keeps_its_own_provider_and_ttl() -> None:
    built, _store, counters, clock = wiring()
    parts = (built.store, built.gate, built.flight, counters, clock)
    wrapped = (
        cached_geocoder(SpyGeocoder(), *parts),
        cached_places(SpyPlaces(), *parts),
        cached_weather(SpyWeather(), *parts),
    )

    assert [(one.engine.provider, one.engine.ttl) for one in wrapped] == [
        (ProviderName.NOMINATIM, GEOCODE_TTL),
        (ProviderName.OVERPASS, PLACES_TTL),
        (ProviderName.OPEN_METEO, WEATHER_TTL),
    ]


def test_the_ttls_are_the_ones_the_cache_contract_gives() -> None:
    # ARCHITECTURE section 15: geocode 30 days, places 7 days, weather 30 minutes.
    assert GEOCODE_TTL.days == 30
    assert PLACES_TTL.days == 7
    assert WEATHER_TTL.total_seconds() == 30 * 60


def test_places_encode_to_one_compact_json_object_per_line() -> None:
    payload = PLACES_CODEC.encode((PLACE, PLACE))
    lines = payload.split(b"\n")

    assert len(lines) == 2
    assert json.loads(lines[0])["name"] == "Gubbängsfältet"
    assert b"\n" not in lines[0]


def test_the_geocode_codec_uses_the_domain_types_own_encoding() -> None:
    # CONTRACTS section 4.1: to_cache and from_cache live with the type in core/types.py,
    # so WP3 and WP4 never depend on each other.
    assert GEOCODE_CODEC.encode is GeocodeHits.to_cache
    assert GEOCODE_CODEC.decode == GeocodeHits.from_cache


def test_a_weather_entry_covers_the_window_it_spans() -> None:
    covers = weather_codec(START, END).covers

    assert covers(weather_window(START, END)) is True
    assert covers(weather_window(START - timedelta(hours=1), END + timedelta(hours=1))) is True
    assert covers(weather_window(START + timedelta(minutes=1), END)) is False
    assert covers(weather_window(START, END - timedelta(minutes=1))) is False


@pytest.mark.asyncio
async def test_an_entry_that_stops_covering_the_window_is_a_counted_miss() -> None:
    built, store, counters, clock = wiring()
    engine = engine_for(built)
    narrow: Codec[bytes] = Codec(
        encode=BYTES_CODEC.encode, decode=BYTES_CODEC.decode, covers=lambda _payload: False
    )
    await store.put(key_for(), b"cached", clock.now() + timedelta(minutes=30))

    async def fresh(_deadline: float) -> Outcome[bytes]:
        return Ok(b"fetched")

    result = await obtain(engine, Request(key_for(), DEADLINE, fresh, narrow))

    assert result == Ok(b"fetched")
    assert counters.count(CACHE_NOT_COVERING) == 1


@pytest.mark.asyncio
async def test_a_value_that_cannot_be_encoded_is_reported_and_counted() -> None:
    # The port carries bytes, so a value that will not encode cannot cross it. The
    # wrapper says so rather than pretending, and never retries it.
    built, store, counters, clock = wiring()

    def refuse(_value: bytes) -> bytes:
        raise NotImplementedError

    unwritable: Codec[bytes] = Codec(encode=refuse, decode=BYTES_CODEC.decode)

    async def fresh(_deadline: float) -> Outcome[bytes]:
        return Ok(b"fetched")

    result = await obtain(engine_for(built), Request(key_for(), DEADLINE, fresh, unwritable))

    assert type(result).__name__ == "Malformed"
    assert counters.count(CACHE_UNWRITABLE) == 1
    assert store.entries == {}
    assert clock.now() == FakeClock().now()


def parameters(func: object) -> list[str]:
    """Parameter names, read from the code object so no annotation is resolved.

    Annotations in these modules are deferred (PEP 649) and some name types that are
    imported only for type checking, so resolving them here would fail for the wrong
    reason.
    """
    code = func.__code__  # type: ignore[attr-defined]
    return list(code.co_varnames[: code.co_argcount + code.co_kwonlyargcount])


PORTS = [
    (CacheStore, SqliteCache),
    (ProviderGate, MemoryGate),
    (SingleFlight, MemorySingleFlight),
]


@pytest.mark.parametrize(("port", "implementation"), PORTS)
def test_each_implementation_matches_its_port(port: type, implementation: type) -> None:
    for name, declared in inspect.getmembers(port, inspect.isfunction):
        if name.startswith("_"):
            continue
        actual = getattr(implementation, name)

        assert inspect.iscoroutinefunction(actual) == inspect.iscoroutinefunction(declared)
        assert parameters(actual) == parameters(declared)


@pytest.mark.parametrize(
    ("port", "factory", "inner"),
    [
        (Geocoder, cached_geocoder, SpyGeocoder()),
        (PlacesProvider, cached_places, SpyPlaces()),
        (WeatherProvider, cached_weather, SpyWeather()),
    ],
)
def test_each_wrapper_matches_the_port_it_replaces(
    port: type,
    factory: object,
    inner: object,
) -> None:
    built, _store, counters, clock = wiring()
    wrapped = factory(inner, built.store, built.gate, built.flight, counters, clock)  # type: ignore[operator]

    for name, declared in inspect.getmembers(port, inspect.isfunction):
        if name.startswith("_"):
            continue
        actual = getattr(type(wrapped), name)

        assert inspect.iscoroutinefunction(actual)
        assert parameters(actual) == parameters(declared)
