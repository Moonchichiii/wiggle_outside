"""Deterministic ranking: interest preference, energy match, distance, D36 variety, hooks."""

import dataclasses

import pytest
from support import KIDS_ACTIVITY

from wiggle_outside.core.ranking import (
    RankingInputs,
    allowed_in_order,
    deterministic_ideas,
    deterministic_pick,
    first_allowed,
    matches_tags,
    rank,
    select,
)
from wiggle_outside.core.types import MAX_IDEAS, MAX_REASONS, Activity, Energy, InterestTag, Pair

HOOK_ORDER = ("pocket-adventure", "explorer-club", "todays-idea", "no-destination")
REASON_ORDER = ("close_by", "fits_time", "matches_energy", "in_season")


def activity(
    activity_id: str, *, tags: tuple[InterestTag, ...] = (), energy: Energy = Energy.MODERATE
) -> Activity:
    return dataclasses.replace(
        KIDS_ACTIVITY,
        activity_id=activity_id,
        interests=tags,
        energy=frozenset({energy}),
    )


def pair(
    pair_id: str,
    activity_id: str,
    *,
    distance_m: int | None = 500,
    hooks: tuple[str, ...] = HOOK_ORDER,
    reasons: tuple[str, ...] = REASON_ORDER,
) -> Pair:
    return Pair(
        pair_id=pair_id,
        idea_id=f"i{pair_id}",
        activity_id=activity_id,
        place=None,
        distance_m=distance_m,
        travel_min=20,
        duration_min=30,
        allowed_hook_ids=frozenset(hooks),
        allowed_reason_ids=frozenset(reasons),
    )


def inputs(*activities: Activity, tags: tuple[InterestTag, ...] = ()) -> RankingInputs:
    return RankingInputs(
        activities={found.activity_id: found for found in activities},
        energy=Energy.MODERATE,
        tags=tags,
    )


# --- the interest preference --------------------------------------------------------


def test_tags_are_a_preference_not_a_filter() -> None:
    birds = activity("birds", tags=(InterestTag.BIRDS,))
    other = activity("other", tags=(InterestTag.TREES,))
    pairs = (pair("p1", "other", distance_m=100), pair("p2", "birds", distance_m=900))
    ranked = rank(pairs, inputs(birds, other, tags=(InterestTag.BIRDS,)))
    assert [found.pair_id for found in ranked] == ["p2", "p1"]
    # Without tags the nearer pair wins again, and nothing is dropped either way.
    plain = rank(pairs, inputs(birds, other))
    assert [found.pair_id for found in plain] == ["p1", "p2"]
    assert set(ranked) == set(plain)


@pytest.mark.parametrize(
    ("entry_tags", "result_tags", "expected"),
    [
        ((InterestTag.BIRDS,), (InterestTag.BIRDS,), True),
        ((InterestTag.BIRDS,), (InterestTag.TREES,), False),
        ((InterestTag.BIRDS, InterestTag.TREES), (InterestTag.TREES,), True),
        ((), (InterestTag.BIRDS,), False),
        ((InterestTag.BIRDS,), (), False),
    ],
)
def test_matches_tags(
    entry_tags: tuple[InterestTag, ...],
    result_tags: tuple[InterestTag, ...],
    *,
    expected: bool,
) -> None:
    assert matches_tags(activity("a", tags=entry_tags), result_tags) is expected


# --- energy and distance ------------------------------------------------------------


def test_the_requested_energy_level_is_preferred() -> None:
    asked = activity("asked", energy=Energy.MODERATE)
    gentler = activity("gentler", energy=Energy.GENTLE)
    pairs = (pair("p1", "gentler", distance_m=100), pair("p2", "asked", distance_m=900))
    ranked = rank(pairs, inputs(asked, gentler))
    assert [found.pair_id for found in ranked] == ["p2", "p1"]


def test_closer_pairs_rank_first_when_everything_else_ties() -> None:
    one = activity("one")
    two = activity("two")
    pairs = (pair("p1", "one", distance_m=900), pair("p2", "two", distance_m=100))
    assert [found.pair_id for found in rank(pairs, inputs(one, two))] == ["p2", "p1"]


def test_equal_pairs_keep_their_build_order() -> None:
    one = activity("one")
    two = activity("two")
    pairs = (pair("p1", "one"), pair("p2", "two"))
    assert rank(pairs, inputs(one, two)) == pairs


def test_generic_pairs_rank_by_the_other_criteria() -> None:
    asked = activity("asked", energy=Energy.MODERATE)
    gentler = activity("gentler", energy=Energy.GENTLE)
    pairs = (pair("p1", "gentler", distance_m=None), pair("p2", "asked", distance_m=None))
    assert [found.pair_id for found in rank(pairs, inputs(asked, gentler))] == ["p2", "p1"]


# --- variety (D36) ------------------------------------------------------------------


def test_no_two_selected_pairs_share_an_activity() -> None:
    one = activity("one")
    two = activity("two")
    pairs = (
        pair("p1", "one", distance_m=100),
        pair("p2", "one", distance_m=200),
        pair("p3", "two", distance_m=300),
    )
    chosen = select(pairs, inputs(one, two))
    assert [found.pair_id for found in chosen] == ["p1", "p3"]


def test_at_most_three_ideas_are_selected() -> None:
    activities = tuple(activity(f"a{index}") for index in range(6))
    pairs = tuple(pair(f"p{index}", f"a{index}", distance_m=index * 100) for index in range(6))
    chosen = select(pairs, inputs(*activities))
    assert len(chosen) == MAX_IDEAS
    assert [found.pair_id for found in chosen] == ["p0", "p1", "p2"]


def test_fewer_pairs_give_fewer_ideas() -> None:
    one = activity("one")
    chosen = select((pair("p1", "one"),), inputs(one))
    assert len(chosen) == 1
    assert select((), inputs(one)) == ()


# --- the deterministic hook and reasons ---------------------------------------------


def test_the_first_allowed_id_in_catalogue_order_wins() -> None:
    assert first_allowed(HOOK_ORDER, frozenset({"todays-idea", "explorer-club"})) == "explorer-club"
    assert first_allowed(HOOK_ORDER, frozenset()) is None
    assert first_allowed(HOOK_ORDER, frozenset({"not-a-hook"})) is None


def test_reasons_keep_catalogue_order_and_stop_at_two() -> None:
    allowed = frozenset({"in_season", "fits_time", "close_by"})
    assert allowed_in_order(REASON_ORDER, allowed, MAX_REASONS) == ("close_by", "fits_time")


def test_a_pick_is_deterministic() -> None:
    chosen = deterministic_pick(pair("p1", "one"), HOOK_ORDER, REASON_ORDER)
    assert chosen is not None
    assert chosen.pair_id == "p1"
    assert chosen.hook_id == "pocket-adventure"
    assert chosen.reason_ids == ("close_by", "fits_time")


def test_a_pair_with_no_allowed_hook_has_no_pick() -> None:
    assert deterministic_pick(pair("p1", "one", hooks=()), HOOK_ORDER, REASON_ORDER) is None


def test_a_generic_pair_takes_the_no_destination_hook() -> None:
    generic = pair("p1", "one", distance_m=None, hooks=("no-destination",))
    chosen = deterministic_pick(generic, HOOK_ORDER, REASON_ORDER)
    assert chosen is not None
    assert chosen.hook_id == "no-destination"


def test_ideas_drop_only_the_pairs_with_no_hook() -> None:
    pairs = (pair("p1", "one"), pair("p2", "two", hooks=()), pair("p3", "three"))
    ideas = deterministic_ideas(pairs, HOOK_ORDER, REASON_ORDER)
    assert [idea.pair.pair_id for idea in ideas] == ["p1", "p3"]
    assert all(idea.hook_id == "pocket-adventure" for idea in ideas)
    assert all(len(idea.reason_ids) <= MAX_REASONS for idea in ideas)
