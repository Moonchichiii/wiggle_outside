"""The cache codecs (CONTRACTS section 2): a value survives the round trip, junk does not.

The wrapper treats TypeError and ValueError as a miss (storage.wrapper.CODEC_ERRORS), so
a payload that is not what we wrote must raise one of those, never return a half value.
"""

import pytest
from support import BOUNDARY_WINDOW

from wiggle_outside.core.types import (
    Coordinates,
    GeocodeHit,
    GeocodeHits,
    Place,
    WeatherWindow,
)

PLACE = Place(
    place_id="node/1",
    name="Elm & Oak Playground",
    kind="playground",
    coords=Coordinates(lat=60.123, lon=17.456),
    fee="unknown",
    osm_access="limited",
)
HITS = GeocodeHits(
    hits=(
        GeocodeHit(label="Bergby, Gävleborg, Sweden", coords=Coordinates(lat=60.93, lon=17.04)),
        GeocodeHit(label="Bergby, Åland, Finland", coords=Coordinates(lat=60.25, lon=19.95)),
    )
)


def test_a_place_survives_the_round_trip() -> None:
    assert Place.from_cache(PLACE.to_cache()) == PLACE


def test_geocode_hits_survive_the_round_trip_and_carry_no_query() -> None:
    payload = HITS.to_cache()
    assert GeocodeHits.from_cache(payload) == HITS
    # BACKEND-CONTRACT section 9: the label and rounded coordinates only.
    assert b"query" not in payload


def test_a_weather_window_survives_the_round_trip() -> None:
    assert WeatherWindow.from_cache(BOUNDARY_WINDOW.to_cache()) == BOUNDARY_WINDOW


def test_the_cached_window_keeps_aware_timestamps() -> None:
    window = WeatherWindow.from_cache(BOUNDARY_WINDOW.to_cache())
    assert window.fetched_at.tzinfo is not None
    assert all(moment.tzinfo is not None for moment in window.times)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"not json",
        b"[]",
        b'{"hits": "nope"}',
        b'{"hits": [{"label": 3, "lat": 1, "lon": 2}]}',
        b'{"hits": [{"label": "x", "lat": "60", "lon": 2}]}',
        b'{"hits": [{"label": "x", "lat": 95.0, "lon": 2}]}',
    ],
)
def test_junk_is_refused_as_a_codec_error(payload: bytes) -> None:
    with pytest.raises((TypeError, ValueError)):
        GeocodeHits.from_cache(payload)


PLACE_FIELDS = '"place_id": "n", "name": "x", "kind": "park"'


@pytest.mark.parametrize(
    "rest",
    [
        '"lat": 1, "lon": 2, "fee": "free", "osm_access": "yes"',  # fee outside D37's words
        '"lat": 1, "lon": 2, "fee": "no"',  # access missing
        '"lat": true, "lon": 2, "fee": "no", "osm_access": "yes"',  # a bool is not a number
    ],
)
def test_a_place_outside_its_vocabulary_is_refused(rest: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        Place.from_cache(f"{{{PLACE_FIELDS}, {rest}}}".encode())


def test_a_naive_timestamp_is_refused() -> None:
    payload = BOUNDARY_WINDOW.to_cache().replace(b"+00:00", b"")
    with pytest.raises(ValueError, match="aware"):
        WeatherWindow.from_cache(payload)
