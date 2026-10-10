"""Distance, travel, the caps (8 places, 12 pairs), generic pairs and D42 P ranking."""

import dataclasses
import itertools

import pytest
from support import HOOKS, KIDS_ACTIVITY, SOLO_ACTIVITY

from wiggle_outside.core.places import (
    WALK_KMH_ALONE,
    WALK_KMH_WITH_KIDS,
    PairCandidate,
    PairPlan,
    distance_m,
    fits_budget,
    is_usable,
    pair_candidates,
    place_kind_matches,
    rank_places,
    reports_step_free,
    selected_duration,
    to_pairs,
    travel_min,
    walking_speed_kmh,
)
from wiggle_outside.core.types import MAX_PAIRS, MAX_PLACES, Coordinates, Place

ORIGIN = Coordinates(lat=60.5, lon=17.2)
PLAN = PairPlan(origin=ORIGIN, budget_min=60, with_kids=True, prefer_step_free=False)
# Coordinates round to two decimal places, so 0.01 degrees is the smallest real step.
STEP_DEG = 0.01


def place(
    place_id: str,
    *,
    kind: str = "park",
    lat: float = 60.5,
    fee: str = "unknown",
    access: str = "unknown",
) -> Place:
    return Place(
        place_id=place_id,
        name=place_id.title(),
        kind=kind,
        coords=Coordinates(lat=lat, lon=17.2),
        fee=fee,  # type: ignore[arg-type]
        osm_access=access,  # type: ignore[arg-type]
    )


def ids(count: int) -> list[str]:
    return [f"i{index}" for index in range(count)]


# --- distance and time --------------------------------------------------------------


def test_distance_to_the_same_point_is_zero() -> None:
    assert distance_m(ORIGIN, ORIGIN) == 0


def test_distance_is_symmetric_and_grows_with_separation() -> None:
    near = Coordinates(lat=60.51, lon=17.2)
    far = Coordinates(lat=60.6, lon=17.2)
    assert distance_m(ORIGIN, near) == distance_m(near, ORIGIN)
    assert distance_m(ORIGIN, near) < distance_m(ORIGIN, far)


def test_a_degree_of_latitude_is_about_111_km() -> None:
    metres = distance_m(Coordinates(lat=0.0, lon=0.0), Coordinates(lat=1.0, lon=0.0))
    assert 111_000 <= metres <= 111_500


@pytest.mark.parametrize(
    ("with_kids", "expected_speed"),
    [(True, WALK_KMH_WITH_KIDS), (False, WALK_KMH_ALONE)],
)
def test_the_walking_speed_depends_on_the_company(
    *, with_kids: bool, expected_speed: float
) -> None:
    assert walking_speed_kmh(with_kids=with_kids) == expected_speed


@pytest.mark.parametrize(
    ("metres", "with_kids", "expected"),
    [(600, True, 24), (400, True, 16), (500, True, 20), (900, True, 36), (900, False, 24)],
)
def test_travel_is_the_round_trip_at_the_walking_speed(
    metres: int,
    expected: int,
    *,
    with_kids: bool,
) -> None:
    assert travel_min(metres, with_kids=with_kids) == expected


@pytest.mark.parametrize(
    ("travel", "minutes_min", "expected"),
    [(24, 20, True), (40, 20, True), (41, 20, False), (0, 60, True), (0, 61, False)],
)
def test_a_pair_needs_travel_plus_the_minimum_to_fit(
    travel: int,
    minutes_min: int,
    *,
    expected: bool,
) -> None:
    assert fits_budget(budget_min=60, travel=travel, minutes_min=minutes_min) is expected


@pytest.mark.parametrize(
    ("travel", "minutes_min", "minutes_max", "expected"),
    [
        (24, 20, 60, 36),
        (0, 20, 60, 60),
        (45, 20, 60, 20),
        (50, 20, 60, 20),
        (0, 20, 30, 30),
    ],
)
def test_the_selected_duration_is_the_clamped_remainder(
    travel: int,
    minutes_min: int,
    minutes_max: int,
    expected: int,
) -> None:
    duration = selected_duration(
        budget_min=60,
        travel=travel,
        minutes_min=minutes_min,
        minutes_max=minutes_max,
    )
    assert duration == expected


# --- which places may be offered ----------------------------------------------------


@pytest.mark.parametrize(("fee", "expected"), [("no", True), ("unknown", True), ("yes", False)])
def test_a_place_with_a_fee_is_excluded(fee: str, *, expected: bool) -> None:
    assert is_usable(place("p", fee=fee)) is expected


@pytest.mark.parametrize(
    ("access", "expected"),
    [("yes", True), ("limited", False), ("no", False), ("unknown", False)],
)
def test_only_a_reported_yes_counts_as_step_free(access: str, *, expected: bool) -> None:
    assert reports_step_free(place("p", access=access)) is expected


@pytest.mark.parametrize("access", ["yes", "limited", "no", "unknown"])
def test_access_never_removes_a_place(access: str) -> None:
    # D42 P: step-free is a preference. Every access value stays in the ranking.
    candidate = place("p", access=access)
    for prefer in (True, False):
        plan = dataclasses.replace(PLAN, prefer_step_free=prefer)
        assert rank_places((candidate,), plan) == (candidate,)


def test_the_step_free_preference_only_reorders() -> None:
    near = place("near", lat=60.501, access="unknown")
    far = place("far", lat=60.52, access="yes")
    plain = rank_places((near, far), PLAN)
    preferred = rank_places((near, far), dataclasses.replace(PLAN, prefer_step_free=True))
    assert plain == (near, far)
    assert preferred == (far, near)
    assert set(plain) == set(preferred)


def test_places_are_ranked_nearest_first_and_capped_at_eight() -> None:
    candidates = tuple(
        place(f"p{index:02d}", lat=60.5 + index * STEP_DEG) for index in reversed(range(12))
    )
    ranked = rank_places(candidates, PLAN)
    assert len(ranked) == MAX_PLACES
    assert [found.place_id for found in ranked] == [f"p{index:02d}" for index in range(MAX_PLACES)]


def test_a_fee_place_is_dropped_before_the_cap() -> None:
    paid = place("paid", lat=60.5, fee="yes")
    free = place("free", lat=60.51, fee="no")
    assert rank_places((paid, free), PLAN) == (free,)


@pytest.mark.parametrize(
    ("kinds", "kind", "expected"),
    [
        (("park",), "park", True),
        (("park",), "playground", False),
        (("any",), "playground", True),
        (("park", "forest"), "forest", True),
    ],
)
def test_place_kinds_must_match_unless_the_entry_takes_any(
    kinds: tuple[str, ...],
    kind: str,
    *,
    expected: bool,
) -> None:
    activity = dataclasses.replace(KIDS_ACTIVITY, place_kinds=frozenset(kinds))
    assert place_kind_matches(activity, place("p", kind=kind)) is expected


# --- pair building ------------------------------------------------------------------


def test_pairs_carry_the_distance_and_travel_of_their_place() -> None:
    near = place("near", lat=60.5 + STEP_DEG)
    half_day = dataclasses.replace(PLAN, budget_min=240)
    candidates = pair_candidates((KIDS_ACTIVITY,), (near,), half_day)
    assert len(candidates) == 1
    only = candidates[0]
    assert only.place is near
    assert only.distance_m == distance_m(ORIGIN, near.coords)
    assert only.travel_min == travel_min(only.distance_m or 0, with_kids=True)


def test_the_pair_duration_is_the_clamped_remainder() -> None:
    # 20-60 minutes on site; travel is 0 at the origin (CC-002 wires the clamp through).
    here = place("here")
    assert (KIDS_ACTIVITY.minutes_min, KIDS_ACTIVITY.minutes_max) == (20, 60)
    hour = pair_candidates((KIDS_ACTIVITY,), (here,), PLAN)[0]
    assert hour.duration_min == 60
    half_hour = dataclasses.replace(PLAN, budget_min=30)
    assert pair_candidates((KIDS_ACTIVITY,), (here,), half_hour)[0].duration_min == 30
    half_day = dataclasses.replace(PLAN, budget_min=240)
    assert pair_candidates((KIDS_ACTIVITY,), (here,), half_day)[0].duration_min == 60


def test_travel_comes_out_of_the_pair_duration() -> None:
    far = place("far", lat=60.5 + STEP_DEG)
    half_day = dataclasses.replace(PLAN, budget_min=240)
    only = pair_candidates((KIDS_ACTIVITY,), (far,), half_day)[0]
    assert only.duration_min == selected_duration(
        budget_min=240,
        travel=only.travel_min,
        minutes_min=KIDS_ACTIVITY.minutes_min,
        minutes_max=KIDS_ACTIVITY.minutes_max,
    )


def test_a_generic_pair_duration_is_clamped_too() -> None:
    generic_ready = dataclasses.replace(KIDS_ACTIVITY, generic_ok=True)
    only = pair_candidates((generic_ready,), (), dataclasses.replace(PLAN, budget_min=30))[0]
    assert only.travel_min == 0
    assert only.duration_min == 30


def test_an_activity_that_cannot_fit_the_budget_makes_no_pair() -> None:
    far = place("far", lat=61.5)
    assert pair_candidates((KIDS_ACTIVITY,), (far,), PLAN) == ()


def test_pairs_are_capped_at_twelve_and_spread_over_places() -> None:
    # All four at the origin, so only the fill order decides which 12 pairs survive.
    places = tuple(place(f"p{index}") for index in range(4))
    activities = tuple(
        dataclasses.replace(KIDS_ACTIVITY, activity_id=f"a{index}") for index in range(8)
    )
    candidates = pair_candidates(activities, places, PLAN)
    assert len(candidates) == MAX_PAIRS
    used = {candidate.place.place_id for candidate in candidates if candidate.place is not None}
    assert used == {found.place_id for found in places}
    # The first round takes one entry per place before any place gets a second.
    first_round = [candidate.place.place_id for candidate in candidates[:4] if candidate.place]
    assert sorted(first_round) == sorted(found.place_id for found in places)


def test_no_places_falls_back_to_generic_pairs() -> None:
    generic_ready = dataclasses.replace(KIDS_ACTIVITY, generic_ok=True)
    candidates = pair_candidates((generic_ready, KIDS_ACTIVITY), (), PLAN)
    assert len(candidates) == 1
    only = candidates[0]
    assert only.place is None
    assert only.distance_m is None
    assert only.travel_min == 0


def test_a_generic_pair_still_has_to_fit_the_budget() -> None:
    long_entry = dataclasses.replace(SOLO_ACTIVITY, minutes_min=61, minutes_max=90)
    assert pair_candidates((long_entry,), (), PLAN) == ()


def test_every_place_being_paid_leaves_the_generic_path() -> None:
    generic_ready = dataclasses.replace(KIDS_ACTIVITY, generic_ok=True)
    paid = place("paid", fee="yes")
    candidates = pair_candidates((generic_ready,), (paid,), PLAN)
    assert [candidate.place for candidate in candidates] == [None]


# --- Pair construction --------------------------------------------------------------


def no_reasons(_: PairCandidate) -> frozenset[str]:
    """`Reason.when` is reviewer prose; core.ideas supplies the real sets (CC-003)."""
    return frozenset()


def generic_candidate(activity_id: str = "nature-bingo") -> PairCandidate:
    return PairCandidate(
        activity=dataclasses.replace(KIDS_ACTIVITY, activity_id=activity_id),
        place=None,
        distance_m=None,
        travel_min=0,
        duration_min=20,
    )


def test_pair_ids_are_sequential_and_idea_ids_come_from_the_factory() -> None:
    tokens = iter(ids(3))
    candidates = tuple(generic_candidate(f"a{index}") for index in range(3))
    pairs = to_pairs(candidates, HOOKS, lambda: next(tokens), no_reasons)
    assert [pair.pair_id for pair in pairs] == ["p1", "p2", "p3"]
    assert [pair.idea_id for pair in pairs] == ids(3)
    assert [pair.activity_id for pair in pairs] == ["a0", "a1", "a2"]


def test_the_id_factory_is_called_once_per_pair() -> None:
    counter = itertools.count()
    candidates = tuple(generic_candidate() for _ in range(5))
    pairs = to_pairs(candidates, HOOKS, lambda: f"i{next(counter)}", no_reasons)
    assert len({pair.idea_id for pair in pairs}) == len(pairs)


def test_each_pair_carries_the_hooks_its_destination_allows() -> None:
    here = place("here")
    with_place = dataclasses.replace(generic_candidate(), place=here, distance_m=0)
    pairs = to_pairs((with_place, generic_candidate()), HOOKS, lambda: "i", no_reasons)
    assert pairs[0].allowed_hook_ids == frozenset({"expedition", "pocket-adventure"})
    assert pairs[1].allowed_hook_ids == frozenset({"no-destination"})


def test_the_reason_sets_come_from_the_injected_function() -> None:
    pairs = to_pairs((generic_candidate(),), HOOKS, lambda: "i", lambda _: frozenset({"close_by"}))
    assert pairs[0].allowed_reason_ids == frozenset({"close_by"})
