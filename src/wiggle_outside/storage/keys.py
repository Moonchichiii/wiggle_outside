"""Cache keys: every input that affects the result (ARCHITECTURE section 15).

`CacheKey.digest()` is declared in `planner/ports.py`, which WP0 owns, and still raises
`NotImplementedError`; the canonical encoding it promises lives here until that lands, and
`tests/storage/test_keys.py` cross-checks the two as soon as it does.
"""

import hashlib
from typing import TYPE_CHECKING, Final

from wiggle_outside.core.types import COORD_DP
from wiggle_outside.planner.ports import CacheKey, CacheNamespace, ProviderName

if TYPE_CHECKING:
    from wiggle_outside.core.types import Coordinates, TypedPlace

# Bumping this invalidates every entry: the version is part of the key (section 15).
CACHE_SCHEMA_VERSION: Final = 1

# Mirrors the Nominatim adapter's Accept-Language. Change it with the schema version.
GEOCODE_LANGUAGE: Final = "en"

# The hourly and daily variables BACKEND-CONTRACT section 1 requests. Part of the weather
# key, so a changed request can never read an entry fetched for the old one.
WEATHER_VARIABLES: Final = (
    "apparent_temperature",
    "precipitation",
    "precipitation_probability",
    "sunrise",
    "sunset",
    "temperature_2m",
    "weather_code",
    "wind_speed_10m",
)

_FIELD_SEPARATOR: Final = "\x1f"


def digest_of(key: CacheKey) -> str:
    """SHA-256 hex of a canonical encoding (CONTRACTS section 4.1)."""
    fields = [
        key.namespace.value,
        key.provider.value,
        str(key.schema_version),
        *(f"{name}={value}" for name, value in sorted(key.params)),
    ]
    return hashlib.sha256(_FIELD_SEPARATOR.join(fields).encode()).hexdigest()


def normalise_query(place: TypedPlace) -> str:
    """Collapse whitespace and case so one typed place is one key."""
    return " ".join(place.text.split()).casefold()


def geocode_key(place: TypedPlace) -> CacheKey:
    return CacheKey(
        namespace=CacheNamespace.GEOCODE,
        provider=ProviderName.NOMINATIM,
        params=(("language", GEOCODE_LANGUAGE), ("query", normalise_query(place))),
        schema_version=CACHE_SCHEMA_VERSION,
    )


def places_key(at: Coordinates, radius_m: int, kinds: frozenset[str]) -> CacheKey:
    return CacheKey(
        namespace=CacheNamespace.PLACES,
        provider=ProviderName.OVERPASS,
        params=(
            ("kinds", ",".join(sorted(kinds))),
            ("radius_m", str(radius_m)),
            *_coordinate_params(at),
        ),
        schema_version=CACHE_SCHEMA_VERSION,
    )


def weather_key(at: Coordinates) -> CacheKey:
    """Key one location. The window is not part of it: coverage is checked after decoding."""
    return CacheKey(
        namespace=CacheNamespace.WEATHER,
        provider=ProviderName.OPEN_METEO,
        params=(("variables", ",".join(WEATHER_VARIABLES)), *_coordinate_params(at)),
        schema_version=CACHE_SCHEMA_VERSION,
    )


def _coordinate_params(at: Coordinates) -> tuple[tuple[str, str], ...]:
    # Coordinates round to COORD_DP on construction (CONTRACTS section 2); format to the
    # same precision so 59.3 and 59.30 are one key.
    return (("lat", f"{at.lat:.{COORD_DP}f}"), ("lon", f"{at.lon:.{COORD_DP}f}"))
