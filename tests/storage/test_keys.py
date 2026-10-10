"""ARCHITECTURE section 15: a key carries every input that affects the result."""

import dataclasses
import json

import pytest
from fakes import key_for

from wiggle_outside.core.types import Coordinates, TypedPlace
from wiggle_outside.planner.ports import CacheKey, CacheNamespace, ProviderName
from wiggle_outside.storage.keys import (
    CACHE_SCHEMA_VERSION,
    GEOCODE_LANGUAGE,
    WEATHER_VARIABLES,
    digest_of,
    geocode_key,
    normalise_query,
    places_key,
    weather_key,
)

AT = Coordinates(lat=59.3293, lon=18.0686)
KINDS = frozenset({"park", "forest", "playground"})
RADIUS = 3_000

# Pinned on purpose: the canonical encoding is part of every key, so changing it
# invalidates every entry and must come with a CACHE_SCHEMA_VERSION bump.
GUBBANGEN_DIGEST = "bf5cff4e162896f466f6a9018ae98521aeb5aaf55440b434637af849018e12a2"


@pytest.mark.parametrize(
    "changed",
    [
        {"namespace": CacheNamespace.WEATHER},
        {"provider": ProviderName.OPEN_METEO},
        {"params": (("q", "elsewhere"),)},
        {"schema_version": CACHE_SCHEMA_VERSION + 1},
    ],
)
def test_every_part_of_the_key_changes_the_digest(changed: dict[str, object]) -> None:
    original = key_for()

    assert digest_of(dataclasses.replace(original, **changed)) != digest_of(original)


def test_the_digest_ignores_the_order_params_were_written_in() -> None:
    one = dataclasses.replace(key_for(), params=(("a", "1"), ("b", "2")))
    other = dataclasses.replace(key_for(), params=(("b", "2"), ("a", "1")))

    assert digest_of(one) == digest_of(other)


def test_the_digest_is_the_same_every_time() -> None:
    assert digest_of(key_for()) == digest_of(key_for())
    assert len(digest_of(key_for())) == 64  # SHA-256, hex


def test_the_canonical_encoding_is_pinned() -> None:
    assert digest_of(geocode_key(TypedPlace(text="Gubbängen"))) == GUBBANGEN_DIGEST


@pytest.mark.parametrize("text", ["  Gubbängen  ", "GUBBÄNGEN", "Gubbängen", "Gubbängen "])
def test_one_typed_place_is_one_key_however_it_was_typed(text: str) -> None:
    assert normalise_query(TypedPlace(text=text)) == "gubbängen"


def test_a_place_with_inner_whitespace_collapses_to_single_spaces() -> None:
    assert normalise_query(TypedPlace(text="Old   Town  Square")) == "old town square"


def test_the_geocode_key_carries_the_language_and_the_schema_version() -> None:
    key = geocode_key(TypedPlace(text="Gubbängen"))

    assert key.namespace is CacheNamespace.GEOCODE
    assert key.provider is ProviderName.NOMINATIM
    assert key.schema_version == CACHE_SCHEMA_VERSION
    assert dict(key.params) == {"language": GEOCODE_LANGUAGE, "query": "gubbängen"}


def test_the_places_key_carries_sorted_kinds_the_radius_and_the_rounded_location() -> None:
    key = places_key(AT, RADIUS, KINDS)

    assert key.namespace is CacheNamespace.PLACES
    assert key.provider is ProviderName.OVERPASS
    assert dict(key.params) == {
        "kinds": "forest,park,playground",
        "radius_m": "3000",
        "lat": "59.33",
        "lon": "18.07",
    }


def test_a_different_radius_is_a_different_key() -> None:
    assert digest_of(places_key(AT, RADIUS, KINDS)) != digest_of(
        places_key(AT, RADIUS + 500, KINDS)
    )


def test_the_weather_key_carries_the_variables_and_not_the_window() -> None:
    key = weather_key(AT)

    assert key.namespace is CacheNamespace.WEATHER
    assert key.provider is ProviderName.OPEN_METEO
    assert dict(key.params) == {
        "variables": ",".join(WEATHER_VARIABLES),
        "lat": "59.33",
        "lon": "18.07",
    }


def test_locations_that_round_to_the_same_two_places_are_one_key() -> None:
    near = Coordinates(lat=59.3291, lon=18.0684)

    assert digest_of(weather_key(AT)) == digest_of(weather_key(near))


def test_the_weather_variables_are_the_ones_the_backend_contract_requests() -> None:
    # BACKEND-CONTRACT section 1: hourly six, daily two.
    assert set(WEATHER_VARIABLES) == {
        "temperature_2m",
        "apparent_temperature",
        "precipitation_probability",
        "precipitation",
        "wind_speed_10m",
        "weather_code",
        "sunrise",
        "sunset",
    }


def test_a_key_is_hashable_and_carries_no_free_text_beyond_its_params() -> None:
    key: CacheKey = geocode_key(TypedPlace(text="Gubbängen"))

    assert hash(key) == hash(geocode_key(TypedPlace(text="gubbängen")))
    # The digest is the only thing stored, and it is not reversible.
    assert "gubbängen" not in digest_of(key)
    assert json.dumps(dict(key.params))  # params stay plain strings, so they serialise
