"""core.ideas: the reason conditions of hooks.toml, interest matches, and model output.

Each reason's `when` is reviewer prose; these tests pin the condition code implements for
it (CC-003). The model-output checks follow BACKEND-CONTRACT section 7: invalid picks are
dropped, valid ones kept, nothing repaired or padded (D44).
"""

import dataclasses
import json
from datetime import UTC, date, datetime

import pytest
from support import KIDS_ACTIVITY

from wiggle_outside.core.ideas import (
    CLOSE_BY_MAX_M,
    ReasonContext,
    allowed_reason_ids,
    matched_interests,
    parse_selection,
)
from wiggle_outside.core.places import PairCandidate
from wiggle_outside.core.types import (
    AgeBand,
    Energy,
    InterestOutcome,
    InterestTag,
    Pair,
    Season,
)
from wiggle_outside.core.weather import Instant, Interval, Samples

AT = datetime(2026, 10, 10, 9, tzinfo=UTC)
AUTUMN_DAY = date(2026, 10, 10)
LAT = 60.9


def samples(*, probability: int = 10, mm: float = 0.0) -> Samples:
    return Samples(
        instants=(Instant(at=AT, temp_c=12.0, apparent_temp_c=11.0, wind_kmh=10.0, code=3),),
        intervals=(Interval(ends_at=AT, probability=probability, precipitation_mm=mm),),
    )


def context(
    *,
    energy: Energy = Energy.MODERATE,
    bands: frozenset[AgeBand] = frozenset({AgeBand.B3_5}),
    weather: Samples | None = None,
) -> ReasonContext:
    return ReasonContext(
        budget_min=60,
        energy=energy,
        age_bands=bands,
        samples=weather or samples(),
        local_date=AUTUMN_DAY,
        lat=LAT,
    )


def candidate(
    distance_m: int | None = 400, travel_min: int = 16, **changes: object
) -> PairCandidate:
    activity = dataclasses.replace(KIDS_ACTIVITY, **changes)  # type: ignore[arg-type]
    return PairCandidate(
        activity=activity,
        place=None,
        distance_m=distance_m,
        travel_min=travel_min,
        duration_min=30,
    )


# --- Reasons ---------------------------------------------------------------------------


def test_close_by_is_one_kilometre_or_less() -> None:
    assert "close_by" in allowed_reason_ids(candidate(distance_m=CLOSE_BY_MAX_M), context())
    assert "close_by" not in allowed_reason_ids(candidate(distance_m=CLOSE_BY_MAX_M + 1), context())
    assert "close_by" not in allowed_reason_ids(candidate(distance_m=None), context())


def test_fits_time_needs_travel_plus_the_minimum_inside_the_budget() -> None:
    assert "fits_time" in allowed_reason_ids(candidate(travel_min=20, minutes_min=40), context())
    assert "fits_time" not in allowed_reason_ids(
        candidate(travel_min=21, minutes_min=40), context()
    )


def test_matches_energy_means_the_entry_lists_the_level_asked_for() -> None:
    moderate = frozenset({Energy.MODERATE})
    assert "matches_energy" in allowed_reason_ids(candidate(energy=moderate), context())
    assert "matches_energy" not in allowed_reason_ids(
        candidate(energy=moderate), context(energy=Energy.ENERGETIC)
    )


def test_dry_window_and_rain_allowed_are_complements_on_the_weather() -> None:
    dry = context(weather=samples(probability=20, mm=0.0))
    wet = context(weather=samples(probability=40, mm=0.2))
    rainproof = candidate(rain_ok=True)
    assert "dry_window" in allowed_reason_ids(rainproof, dry)
    assert "rain_allowed" not in allowed_reason_ids(rainproof, dry)
    assert "dry_window" not in allowed_reason_ids(rainproof, wet)
    assert "rain_allowed" in allowed_reason_ids(rainproof, wet)
    # An entry that is not rain-ready never claims the rain reason.
    assert "rain_allowed" not in allowed_reason_ids(candidate(rain_ok=False), wet)


def test_all_ages_needs_two_selected_bands_that_the_entry_lists() -> None:
    both = frozenset({AgeBand.B3_5, AgeBand.B6_9})
    assert "all_ages" in allowed_reason_ids(candidate(ages=both), context(bands=both))
    assert "all_ages" not in allowed_reason_ids(candidate(ages=both), context())
    assert "all_ages" not in allowed_reason_ids(
        candidate(ages=frozenset({AgeBand.B3_5})), context(bands=both)
    )


def test_in_season_needs_a_season_list_that_includes_today() -> None:
    assert "in_season" in allowed_reason_ids(
        candidate(seasons=frozenset({Season.AUTUMN})), context()
    )
    assert "in_season" not in allowed_reason_ids(
        candidate(seasons=frozenset({Season.SUMMER})), context()
    )
    # An all-year entry lists no season, so "the right season" is not a claim it makes.
    assert "in_season" not in allowed_reason_ids(candidate(seasons=frozenset()), context())


def test_matched_interests_keeps_tag_order_and_only_the_entry_s_tags() -> None:
    activity = dataclasses.replace(
        KIDS_ACTIVITY, interests=(InterestTag.PUDDLES, InterestTag.BIRDS)
    )
    tags = (InterestTag.BIRDS, InterestTag.TREES, InterestTag.PUDDLES)
    assert matched_interests(activity, tags) == (InterestTag.BIRDS, InterestTag.PUDDLES)


# --- Model output ------------------------------------------------------------------------


def pair(pair_id: str, activity_id: str) -> Pair:
    return Pair(
        pair_id=pair_id,
        idea_id=f"idea-{pair_id}",
        activity_id=activity_id,
        place=None,
        distance_m=None,
        travel_min=0,
        duration_min=20,
        allowed_hook_ids=frozenset({"expedition", "secret-spot"}),
        allowed_reason_ids=frozenset({"close_by", "fits_time"}),
    )


PAIRS = (pair("p1", "a"), pair("p2", "b"), pair("p3", "a"), pair("p4", "c"))


def output(picks: list[dict[str, object]], **top: object) -> str:
    body: dict[str, object] = {"interests": ["birds"], "interest_status": "matched", "picks": picks}
    body.update(top)
    return json.dumps(body)


def pick(
    pair_id: str, hook: str = "expedition", reasons: list[str] | None = None
) -> dict[str, object]:
    return {"pair_id": pair_id, "hook_id": hook, "reason_ids": reasons or []}


def test_valid_picks_and_interests_pass_through() -> None:
    selection = parse_selection(
        output([pick("p1", reasons=["close_by", "fits_time"]), pick("p2")]), PAIRS
    )
    assert selection is not None
    assert [p.pair_id for p in selection.picks] == ["p1", "p2"]
    assert selection.picks[0].reason_ids == ("close_by", "fits_time")
    assert selection.interests.tags == (InterestTag.BIRDS,)
    assert selection.interests.outcome is InterestOutcome.MATCHED
    assert selection.dropped == 0


@pytest.mark.parametrize(
    "bad",
    [
        pick("p9"),  # unknown pair
        pick("p1", hook="not-allowed"),
        pick("p1", reasons=["in_season"]),  # a reason the pair does not allow
        pick("p1", reasons=["close_by", "close_by"]),  # duplicate reasons
        pick("p1", reasons=["close_by", "fits_time", "close_by"]),  # too many
        {"pair_id": "p1"},  # off-shape pick
        "p1",  # not an object at all
    ],
)
def test_an_invalid_pick_is_dropped_and_the_rest_kept(bad: object) -> None:
    selection = parse_selection(output([bad, pick("p2")]), PAIRS)  # type: ignore[list-item]
    assert selection is not None
    assert [p.pair_id for p in selection.picks] == ["p2"]
    assert selection.dropped == 1


def test_a_repeated_activity_keeps_the_higher_ranked_pick_only() -> None:
    selection = parse_selection(output([pick("p1"), pick("p3"), pick("p2")]), PAIRS)
    assert selection is not None
    assert [p.pair_id for p in selection.picks] == ["p1", "p2"]  # p3 is activity "a" again
    assert selection.dropped == 1


def test_more_than_three_picks_are_cut_and_counted() -> None:
    selection = parse_selection(output([pick("p1"), pick("p2"), pick("p4"), pick("p2")]), PAIRS)
    assert selection is not None
    assert len(selection.picks) == 3
    assert selection.dropped == 1


@pytest.mark.parametrize("payload", ["", "not json", "[]", '{"picks": "p1"}', '{"interests": []}'])
def test_an_off_schema_answer_is_none(payload: str) -> None:
    assert parse_selection(payload, PAIRS) is None


@pytest.mark.parametrize(
    "top",
    [
        {"interests": ["unicorns"]},
        {"interests": ["birds", "birds"]},
        {"interests": ["birds", "bugs", "sky", "trees"]},
        {"interest_status": "sure"},
        {"interest_status": 3},
        {"interests": "birds"},
    ],
)
def test_a_broken_interests_block_is_not_applied_but_the_picks_still_count(
    top: dict[str, object],
) -> None:
    selection = parse_selection(output([pick("p1")], **top), PAIRS)
    assert selection is not None
    assert selection.interests.outcome is InterestOutcome.NOT_APPLIED
    assert selection.interests.tags == ()
    assert [p.pair_id for p in selection.picks] == ["p1"]


def test_matched_with_no_tags_is_unclear_and_other_outcomes_carry_no_tags() -> None:
    nothing = parse_selection(output([], interests=[]), PAIRS)
    assert nothing is not None
    assert nothing.interests.outcome is InterestOutcome.UNCLEAR
    no_match = parse_selection(output([], interests=["birds"], interest_status="no_match"), PAIRS)
    assert no_match is not None
    assert no_match.interests.outcome is InterestOutcome.NO_MATCH
    assert no_match.interests.tags == ()
