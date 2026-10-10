"""Cached providers with the same port types, so the planner never sees caching.

CONTRACTS section 4.1 fixes the three factory signatures; the shared order of operations
is in `storage/wrapper.py`. TTLs are ARCHITECTURE section 15: geocode 30 days, places
7 days, weather 30 minutes, and a weather entry must cover the whole outing window.
"""

from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING, Final

from wiggle_outside.core.types import GeocodeHits, Place, WeatherWindow
from wiggle_outside.planner.ports import (
    CacheStore,
    Clock,
    Counters,
    Geocoder,
    PlacesProvider,
    ProviderGate,
    ProviderName,
    SingleFlight,
    WeatherProvider,
)
from wiggle_outside.storage.keys import geocode_key, places_key, weather_key
from wiggle_outside.storage.wrapper import CacheWiring, Codec, Engine, Request, obtain

if TYPE_CHECKING:
    from datetime import datetime

    from wiggle_outside.core.result import Outcome
    from wiggle_outside.core.types import Coordinates, TypedPlace

GEOCODE_TTL: Final = timedelta(days=30)
PLACES_TTL: Final = timedelta(days=7)
WEATHER_TTL: Final = timedelta(minutes=30)


# Newline-delimited: Place.to_cache is one compact JSON object and contains no newline.
# An adapter reports an empty answer as Empty, never as Ok(()), so b"" stays unambiguous.
def _encode_places(places: tuple[Place, ...]) -> bytes:
    return b"\n".join(place.to_cache() for place in places)


def _decode_places(payload: bytes) -> tuple[Place, ...]:
    return tuple(Place.from_cache(line) for line in payload.split(b"\n"))


GEOCODE_CODEC: Final[Codec[GeocodeHits]] = Codec(
    encode=GeocodeHits.to_cache, decode=GeocodeHits.from_cache
)
PLACES_CODEC: Final[Codec[tuple[Place, ...]]] = Codec(encode=_encode_places, decode=_decode_places)


def weather_codec(start: datetime, end: datetime) -> Codec[WeatherWindow]:
    """Build the weather codec: a hit only while the entry covers the whole window."""

    def covers(window: WeatherWindow) -> bool:
        return window.start <= start and window.end >= end

    return Codec(encode=WeatherWindow.to_cache, decode=WeatherWindow.from_cache, covers=covers)


@dataclass(frozen=True, slots=True)
class _CachedGeocoder:
    inner: Geocoder
    engine: Engine

    async def resolve(self, place: TypedPlace, deadline: float) -> Outcome[GeocodeHits]:
        return await obtain(
            self.engine,
            Request(
                key=geocode_key(place),
                deadline=deadline,
                inner=partial(self.inner.resolve, place),
                codec=GEOCODE_CODEC,
            ),
        )


@dataclass(frozen=True, slots=True)
class _CachedPlaces:
    inner: PlacesProvider
    engine: Engine

    async def nearby(
        self,
        at: Coordinates,
        radius_m: int,
        kinds: frozenset[str],
        deadline: float,
    ) -> Outcome[tuple[Place, ...]]:
        return await obtain(
            self.engine,
            Request(
                key=places_key(at, radius_m, kinds),
                deadline=deadline,
                inner=partial(self.inner.nearby, at, radius_m, kinds),
                codec=PLACES_CODEC,
            ),
        )


@dataclass(frozen=True, slots=True)
class _CachedWeather:
    inner: WeatherProvider
    engine: Engine

    async def window(
        self,
        at: Coordinates,
        start: datetime,
        end: datetime,
        deadline: float,
    ) -> Outcome[WeatherWindow]:
        return await obtain(
            self.engine,
            Request(
                key=weather_key(at),
                deadline=deadline,
                inner=partial(self.inner.window, at, start, end),
                codec=weather_codec(start, end),
            ),
        )


def _engine(wiring: CacheWiring, provider: ProviderName, ttl: timedelta) -> Engine:
    return Engine(wiring=wiring, provider=provider, ttl=ttl)


# The six parameters are fixed by CONTRACTS section 4.1, which main.py calls as written.
def cached_geocoder(  # noqa: PLR0913, PLR0917
    inner: Geocoder,
    store: CacheStore,
    gate: ProviderGate,
    flight: SingleFlight,
    counters: Counters,
    clock: Clock,
) -> Geocoder:
    wiring = CacheWiring(store=store, gate=gate, flight=flight, counters=counters, clock=clock)
    return _CachedGeocoder(inner=inner, engine=_engine(wiring, ProviderName.NOMINATIM, GEOCODE_TTL))


def cached_places(  # noqa: PLR0913, PLR0917
    inner: PlacesProvider,
    store: CacheStore,
    gate: ProviderGate,
    flight: SingleFlight,
    counters: Counters,
    clock: Clock,
) -> PlacesProvider:
    wiring = CacheWiring(store=store, gate=gate, flight=flight, counters=counters, clock=clock)
    return _CachedPlaces(inner=inner, engine=_engine(wiring, ProviderName.OVERPASS, PLACES_TTL))


def cached_weather(  # noqa: PLR0913, PLR0917
    inner: WeatherProvider,
    store: CacheStore,
    gate: ProviderGate,
    flight: SingleFlight,
    counters: Counters,
    clock: Clock,
) -> WeatherProvider:
    wiring = CacheWiring(store=store, gate=gate, flight=flight, counters=counters, clock=clock)
    return _CachedWeather(inner=inner, engine=_engine(wiring, ProviderName.OPEN_METEO, WEATHER_TTL))
