"""The fixture planner must teach the web layer the right shape.

It decides nothing, but if it got idempotency or ownership wrong, WP7 would be built
against a lie. These assert the four behaviours it does honour.
"""

import dataclasses
from typing import Final

import pytest

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import JobState, Source
from wiggle_outside.planner.ports import Conflict, NotFound
from wiggle_outside.preview_planner import SAMPLE_ANSWERS, PreviewPlanner

SESSION: Final = "s1"
OTHER_SESSION: Final = "s2"
KEY: Final = "k1"
MAX_IDEAS: Final = 3


@pytest.mark.asyncio
async def test_a_result_has_three_ideas_and_a_fallback_label() -> None:
    planner = PreviewPlanner()
    ref = await planner.start_or_join(SESSION, KEY, SAMPLE_ANSWERS)
    result = await planner.wait(SESSION, ref.job_id)

    assert not ref.joined
    assert len(result.ideas) == MAX_IDEAS
    # A fallback result must say so; the label is not decoration (D44).
    assert result.source is Source.FALLBACK
    assert ErrorCode.MODEL_FALLBACK in result.notices
    assert result.state is JobState.FALLBACK
    assert result.weather is not None


@pytest.mark.asyncio
async def test_the_same_key_and_answers_joins_rather_than_starting_again() -> None:
    planner = PreviewPlanner()
    first = await planner.start_or_join(SESSION, KEY, SAMPLE_ANSWERS)
    second = await planner.start_or_join(SESSION, KEY, SAMPLE_ANSWERS)

    assert second.joined
    assert second.job_id == first.job_id


@pytest.mark.asyncio
async def test_the_same_key_with_different_answers_is_a_conflict() -> None:
    planner = PreviewPlanner()
    await planner.start_or_join(SESSION, KEY, SAMPLE_ANSWERS)
    changed = dataclasses.replace(SAMPLE_ANSWERS, stroller=True)

    with pytest.raises(Conflict):
        await planner.start_or_join(SESSION, KEY, changed)


@pytest.mark.asyncio
async def test_only_the_interest_text_differing_is_still_a_different_submission() -> None:
    # CONTRACTS section 7: interest text is part of the discriminator. Answers excludes it
    # from repr and comparison so it cannot leak, which is exactly the trap here.
    planner = PreviewPlanner()
    await planner.start_or_join(SESSION, KEY, SAMPLE_ANSWERS)
    with_interests = dataclasses.replace(SAMPLE_ANSWERS, interest_text="birds")

    with pytest.raises(Conflict):
        await planner.start_or_join(SESSION, KEY, with_interests)


@pytest.mark.asyncio
async def test_another_session_cannot_read_the_result() -> None:
    planner = PreviewPlanner()
    ref = await planner.start_or_join(SESSION, KEY, SAMPLE_ANSWERS)

    # Indistinguishable from an unknown id (CONTRACTS section 3).
    assert planner.get(OTHER_SESSION, ref.job_id) is None
    assert planner.get(SESSION, "no-such-job") is None
    with pytest.raises(NotFound):
        await planner.wait(OTHER_SESSION, ref.job_id)


@pytest.mark.asyncio
async def test_a_result_is_immutable_once_made() -> None:
    planner = PreviewPlanner()
    ref = await planner.start_or_join(SESSION, KEY, SAMPLE_ANSWERS)
    first = await planner.wait(SESSION, ref.job_id)
    again = await planner.wait(SESSION, ref.job_id)

    # Same object, same idea ids: nothing is rebuilt from newer state (D46).
    assert first is again
    assert [idea.pair.idea_id for idea in first.ideas] == [
        idea.pair.idea_id for idea in again.ideas
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code",
    [ErrorCode.DAYLIGHT_NIGHT, ErrorCode.DAYLIGHT_TOO_SHORT, ErrorCode.NO_MATCHES],
)
async def test_a_blocked_outcome_carries_no_ideas_and_no_weather_promise(
    code: ErrorCode,
) -> None:
    planner = PreviewPlanner(outcome=code)
    ref = await planner.start_or_join(SESSION, KEY, SAMPLE_ANSWERS)
    result = await planner.wait(SESSION, ref.job_id)

    assert result.error is code
    assert result.ideas == ()
    assert result.weather is None
    # No fallback label on a run that produced nothing to label.
    assert ErrorCode.MODEL_FALLBACK not in result.notices


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 1, 2, 3])
async def test_the_idea_count_is_honoured_so_every_layout_can_be_seen(count: int) -> None:
    planner = PreviewPlanner(ideas=count)
    ref = await planner.start_or_join(SESSION, KEY, SAMPLE_ANSWERS)
    result = await planner.wait(SESSION, ref.job_id)
    assert len(result.ideas) == count
