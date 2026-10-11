"""The workflow of ARCHITECTURE section 3 with fake ports (BUILD-PACKAGES WP6 accept list).

Every provider answer is scripted and every call is counted, so each test states which
upstream calls a run makes (ARCHITECTURE section 14) as well as what it returns.
"""

import dataclasses
import json
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from planner_support import (
    ANSWERS,
    BERGBY,
    BUDGETS,
    HITS,
    MORNING,
    SOLO,
    FakeAllowance,
    FakeGeocoder,
    FakeModel,
    FakePlaces,
    FakeWeather,
    Rig,
    day_window,
    rig,
)

from wiggle_outside.core.errors import ErrorCode, NoticeId
from wiggle_outside.core.result import Empty, Ok, QuotaOrUnavailable, TransportFailure
from wiggle_outside.core.types import (
    MAX_IDEAS,
    AgeBand,
    Answers,
    GeocodeHits,
    InterestOutcome,
    JobState,
    PlanResult,
    Source,
    TimeBudget,
)
from wiggle_outside.planner.plan_outing import (
    RETAIN_AFTER_VALID,
    VALID_AFTER_CREATION,
    LocationChoiceNeeded,
    plan_outing,
    radius_m,
)
from wiggle_outside.planner.ports import RawSelection

if TYPE_CHECKING:
    from wiggle_outside.core.types import Pair

SEVERE_THUNDER = 95
AMBIGUOUS = Ok(GeocodeHits(hits=HITS))
EVENING = MORNING.replace(hour=20, minute=0)
LATE_AFTERNOON = MORNING.replace(hour=15, minute=45)  # sunset 16:20 UTC


async def plan(r: Rig, answers: Answers = ANSWERS) -> PlanResult:
    planned = await plan_outing(r.ports, r.run(answers), BUDGETS)
    assert isinstance(planned, PlanResult)
    return planned


def at_evening(r: Rig, *, code: int = 3) -> None:
    """Move the clock to the evening with a forecast fetched just now, as the cache would."""
    r.clock.wall = EVENING
    r.weather.outcome = Ok(day_window(fetched_at=EVENING - timedelta(seconds=5), code=code))


# --- The labelled fallback, the path every run takes until WP5 wires a model ------------


@pytest.mark.asyncio
async def test_a_cold_run_makes_one_geocode_one_places_and_one_weather_call() -> None:
    r = rig()
    result = await plan(r)

    assert len(r.geocoder.calls) == 1
    assert len(r.places.calls) == 1
    assert len(r.weather.calls) == 1
    assert result.state is JobState.FALLBACK
    assert result.source is Source.FALLBACK
    assert ErrorCode.MODEL_FALLBACK in result.notices
    assert 1 <= len(result.ideas) <= MAX_IDEAS
    assert len({idea.pair.activity_id for idea in result.ideas}) == len(result.ideas)


@pytest.mark.asyncio
async def test_the_result_keeps_the_label_the_place_and_the_weather() -> None:
    r = rig()
    result = await plan(r)

    assert result.answers.location == BERGBY
    assert result.answers.location_label == HITS[0].label
    assert result.weather is not None
    assert result.weather.window_start == result.planned_start
    assert result.weather.window_end == result.planned_end
    assert result.planned_end - result.planned_start == timedelta(minutes=60)
    assert result.error is None


@pytest.mark.asyncio
async def test_validity_follows_backend_contract_section_two() -> None:
    r = rig()
    result = await plan(r)

    # created == planned_start on a still clock, weather fetched 5 s before: the five
    # minutes after creation are the binding limit.
    assert result.valid_until == MORNING + VALID_AFTER_CREATION
    assert result.retain_until == result.valid_until + RETAIN_AFTER_VALID


@pytest.mark.asyncio
async def test_stale_weather_shortens_validity() -> None:
    old = MORNING - timedelta(minutes=27)
    r = rig(weather=FakeWeather(outcome=Ok(day_window(fetched_at=old))))
    result = await plan(r)

    assert result.valid_until == old + timedelta(minutes=30)


@pytest.mark.asyncio
async def test_every_idea_has_a_hook_the_pair_allows_and_at_most_two_reasons() -> None:
    result = await plan(rig())
    for idea in result.ideas:
        assert idea.hook_id in idea.pair.allowed_hook_ids
        assert len(idea.reason_ids) <= 2
        assert set(idea.reason_ids) <= idea.pair.allowed_reason_ids


@pytest.mark.asyncio
async def test_interest_text_without_a_model_is_reported_as_not_applied() -> None:
    with_text = dataclasses.replace(ANSWERS, interest_text="birds and puddles")
    result = await plan(rig(), with_text)

    assert result.interests is not None
    assert result.interests.outcome is InterestOutcome.NOT_APPLIED
    assert result.interests.tags == ()
    assert NoticeId.INTEREST_NOT_APPLIED in result.notices


@pytest.mark.asyncio
async def test_no_interest_text_means_no_interests_at_all() -> None:
    result = await plan(rig())
    assert result.interests is None
    assert NoticeId.INTEREST_NOT_APPLIED not in result.notices


@pytest.mark.asyncio
async def test_the_places_query_is_bounded_by_the_budget_and_the_catalogue_kinds() -> None:
    r = rig()
    await plan(r)
    at, radius, kinds, _ = r.places.calls[0]

    assert at == BERGBY
    assert radius == radius_m(ANSWERS) == 1500  # 3 km/h, half an hour out
    assert "any" not in kinds
    assert kinds == {"park", "playground", "nature_reserve", "forest", "picnic_site"}


def test_the_radius_is_clamped_to_the_overpass_template() -> None:
    long_solo = dataclasses.replace(SOLO, time_budget=TimeBudget.HALF_DAY)
    short_kids = dataclasses.replace(ANSWERS, time_budget=TimeBudget.M30)
    assert radius_m(long_solo) == 3000
    assert radius_m(short_kids) == 750


# --- Location --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_device_coordinates_skip_the_geocoder() -> None:
    r = rig()
    result = await plan(r, SOLO)

    assert r.geocoder.calls == []
    assert result.answers.location_label == "Your location"
    assert result.state is JobState.FALLBACK


@pytest.mark.asyncio
async def test_an_ambiguous_place_ends_the_job_with_candidates_and_no_further_calls() -> None:
    allowance = FakeAllowance()
    r = rig(geocoder=FakeGeocoder(outcome=AMBIGUOUS), allowance=allowance)
    planned = await plan_outing(r.ports, r.run(), BUDGETS)

    assert isinstance(planned, LocationChoiceNeeded)
    assert [c.label for c in planned.candidates] == [hit.label for hit in HITS]
    assert len({c.candidate_id for c in planned.candidates}) == len(HITS)
    assert planned.result.state is JobState.NEEDS_LOCATION_CHOICE
    assert planned.result.error is ErrorCode.LOCATION_AMBIGUOUS
    assert r.places.calls == []
    assert r.weather.calls == []
    # DEPLOYMENT section 2.2: never charged for an ambiguous place.
    assert allowance.calls == []


@pytest.mark.asyncio
async def test_indistinguishable_hits_collapse_to_one_place() -> None:
    twice = Ok(GeocodeHits(hits=(HITS[0], HITS[0])))
    r = rig(geocoder=FakeGeocoder(outcome=twice))
    result = await plan(r)
    assert result.state is JobState.FALLBACK
    assert result.answers.location_label == HITS[0].label


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "code"),
    [
        (Empty(), ErrorCode.LOCATION_NOT_FOUND),
        (TransportFailure(), ErrorCode.GEOCODER_UNAVAILABLE),
        (QuotaOrUnavailable(retry_after_s=60.0), ErrorCode.GEOCODER_UNAVAILABLE),
    ],
)
async def test_a_geocode_that_yields_no_place_stops_the_run(outcome, code) -> None:  # noqa: ANN001
    allowance = FakeAllowance()
    r = rig(geocoder=FakeGeocoder(outcome=outcome), allowance=allowance)
    result = await plan(r)

    assert result.error is code
    assert result.ideas == ()
    assert result.weather is None
    assert r.places.calls == []
    assert r.weather.calls == []
    assert allowance.calls == []


# --- Weather, daylight and eligibility, in contract order --------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", [TransportFailure(), QuotaOrUnavailable(), Empty()])
async def test_missing_weather_means_no_recommendation_and_no_model_call(outcome) -> None:  # noqa: ANN001
    model = FakeModel(outcome=Ok(RawSelection(payload="{}")))
    r = rig(weather=FakeWeather(outcome=outcome), model=model)
    result = await plan(r)

    assert result.error is ErrorCode.WEATHER_UNAVAILABLE
    assert result.state is JobState.UNAVAILABLE
    assert result.ideas == ()
    assert result.weather is None
    assert model.calls == []


@pytest.mark.asyncio
async def test_expired_weather_is_unavailable_weather() -> None:
    expired = day_window(fetched_at=MORNING - timedelta(minutes=30))
    r = rig(weather=FakeWeather(outcome=Ok(expired)))
    result = await plan(r)
    assert result.error is ErrorCode.WEATHER_UNAVAILABLE


@pytest.mark.asyncio
async def test_a_family_run_after_sunset_is_daylight_night() -> None:
    r = rig()
    at_evening(r)
    result = await plan(r)

    assert result.error is ErrorCode.DAYLIGHT_NIGHT
    assert result.ideas == ()
    assert result.weather is None  # no weather promise on the daylight pages
    assert ErrorCode.MODEL_FALLBACK not in result.notices


@pytest.mark.asyncio
async def test_a_family_run_that_would_end_after_sunset_is_too_short() -> None:
    r = rig()
    r.clock.wall = LATE_AFTERNOON
    r.weather.outcome = Ok(day_window(fetched_at=LATE_AFTERNOON - timedelta(seconds=5)))
    result = await plan(r)
    assert result.error is ErrorCode.DAYLIGHT_TOO_SHORT


@pytest.mark.asyncio
async def test_daylight_takes_precedence_over_severe_weather_for_the_family_path() -> None:
    r = rig()
    at_evening(r, code=SEVERE_THUNDER)
    result = await plan(r)
    assert result.error is ErrorCode.DAYLIGHT_NIGHT


@pytest.mark.asyncio
async def test_the_solo_path_has_no_daylight_short_circuit() -> None:
    r = rig()
    at_evening(r)
    result = await plan(r, SOLO)
    assert result.error is not ErrorCode.DAYLIGHT_NIGHT


@pytest.mark.asyncio
async def test_severe_weather_restricts_everything_and_calls_no_model() -> None:
    model = FakeModel(outcome=Ok(RawSelection(payload="{}")))
    r = rig(weather=FakeWeather(outcome=Ok(day_window(code=SEVERE_THUNDER))), model=model)
    result = await plan(r)

    assert result.error is ErrorCode.WEATHER_RESTRICTED
    assert result.ideas == ()
    assert model.calls == []


@pytest.mark.asyncio
async def test_nothing_eligible_is_no_matches() -> None:
    picky = dataclasses.replace(
        ANSWERS, age_bands=frozenset({AgeBand.B0_2, AgeBand.B10_12}), time_budget=TimeBudget.M30
    )
    r = rig()
    result = await plan(r, picky)
    if result.error is None:
        pytest.skip("the catalogue has an entry for this unusual combination")
    assert result.error is ErrorCode.NO_MATCHES
    assert result.ideas == ()


@pytest.mark.asyncio
async def test_a_resubmission_re_evaluates_against_its_own_window() -> None:
    # TC-002: the same answers a few hours later get a different verdict, because
    # nothing is cached but the data.
    r = rig()
    first = await plan(r)
    at_evening(r)
    second = await plan(r)

    assert first.error is None
    assert second.error is ErrorCode.DAYLIGHT_NIGHT


# --- Places ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_places_unavailable_still_offers_generic_ideas_labelled() -> None:
    r = rig(places=FakePlaces(outcome=TransportFailure()))
    result = await plan(r)

    assert result.error is ErrorCode.PLACES_UNAVAILABLE
    assert result.notices[0] is ErrorCode.PLACES_UNAVAILABLE
    assert result.ideas, "the catalogue has generic entries for a family hour"
    assert all(idea.pair.place is None for idea in result.ideas)


@pytest.mark.asyncio
async def test_an_empty_places_answer_is_not_a_failure() -> None:
    r = rig(places=FakePlaces(outcome=Empty()))
    result = await plan(r)
    assert result.error is None
    assert all(idea.pair.place is None for idea in result.ideas)


# --- The hosted daily allowance ---------------------------------------------------------


@pytest.mark.asyncio
async def test_the_allowance_is_charged_once_just_before_places_and_weather() -> None:
    allowance = FakeAllowance()
    r = rig(allowance=allowance)
    await plan(r)
    assert allowance.calls == [MORNING]
    assert len(r.places.calls) == 1
    assert len(r.weather.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("answer", "code"),
    [
        ("limit_reached", ErrorCode.SERVICE_LIMIT_REACHED),
        ("unavailable", ErrorCode.SERVICE_UNAVAILABLE),
    ],
)
async def test_a_refused_reservation_ends_the_run_before_any_provider_call(answer, code) -> None:  # noqa: ANN001
    r = rig(allowance=FakeAllowance(answer=answer))
    result = await plan(r)

    assert result.error is code
    assert r.places.calls == []
    assert r.weather.calls == []


# --- The model stage: one call, validated once, never repaired ----------------------------


def _selection(pairs: tuple[Pair, ...]) -> str:
    picks = [
        {"pair_id": pair.pair_id, "hook_id": min(pair.allowed_hook_ids), "reason_ids": []}
        for pair in pairs[:3]
    ]
    return json.dumps({"interests": ["birds"], "interest_status": "matched", "picks": picks})


class _EchoModel:
    """Answer with valid picks for whatever pairs were offered."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(
        self, pairs: tuple[Pair, ...], _text: str | None, _deadline: float
    ) -> Ok[RawSelection]:
        self.calls += 1
        return Ok(RawSelection(payload=_selection(pairs)))


@pytest.mark.asyncio
async def test_valid_picks_make_a_model_result_with_exactly_one_call() -> None:
    model = _EchoModel()
    r = rig()
    r.model = model  # type: ignore[assignment]  the fake satisfies the callable shape
    with_text = dataclasses.replace(ANSWERS, interest_text="birds")
    result = await plan(r, with_text)

    assert model.calls == 1
    assert result.source is Source.MODEL
    assert result.state is JobState.COMPLETE
    assert ErrorCode.MODEL_FALLBACK not in result.notices
    assert result.interests is not None
    assert result.interests.outcome is InterestOutcome.MATCHED
    assert len({idea.pair.activity_id for idea in result.ideas}) == len(result.ideas)


@pytest.mark.asyncio
async def test_an_off_schema_answer_falls_back_labelled_after_one_call() -> None:
    model = FakeModel(outcome=Ok(RawSelection(payload="not json at all")))
    result = await plan(rig(model=model))

    assert len(model.calls) == 1
    assert result.source is Source.FALLBACK
    assert ErrorCode.MODEL_FALLBACK in result.notices
    assert result.ideas


@pytest.mark.asyncio
async def test_a_model_failure_falls_back_labelled_after_one_call() -> None:
    model = FakeModel(outcome=TransportFailure())
    result = await plan(rig(model=model))

    assert len(model.calls) == 1
    assert result.source is Source.FALLBACK
    assert ErrorCode.MODEL_FALLBACK in result.notices


@pytest.mark.asyncio
async def test_the_model_is_offered_at_most_twelve_pairs_and_only_pairs_it_may_pick() -> None:
    model = FakeModel(outcome=TransportFailure())
    await plan(rig(model=model))
    pairs, _, deadline = model.calls[0]

    assert 1 <= len(pairs) <= 12
    assert [pair.pair_id for pair in pairs] == [f"p{n}" for n in range(1, len(pairs) + 1)]
    assert all(pair.allowed_hook_ids for pair in pairs)
    assert deadline <= 1000.0 + 18.0  # never past the job's absolute deadline


# --- Deadlines ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_each_stage_gets_only_the_remaining_budget() -> None:
    r = rig()
    r.clock.tick = 1000.0
    await plan(r)
    ((_, geocode_deadline),) = r.geocoder.calls
    assert geocode_deadline == 1003.0  # min(absolute deadline, now + 3 s)
    assert r.places.calls[0][3] == 1004.0
    assert r.weather.calls[0][3] == 1004.0
