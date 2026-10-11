"""The job registry: idempotency, admission, ownership, candidates and lifecycle.

ARCHITECTURE section 4 and BACKEND-CONTRACT sections 2-4, driven by fake ports and an
event the test releases, never by sleeping.
"""

import asyncio
import dataclasses
from datetime import timedelta

import pytest
from planner_support import (
    ANSWERS,
    BUDGETS,
    DEADLINE_S,
    HITS,
    FakeGeocoder,
    Rig,
    rig,
)

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.result import Ok
from wiggle_outside.core.types import GeocodeHit, GeocodeHits, JobState, LocationCandidates
from wiggle_outside.planner import jobs
from wiggle_outside.planner.jobs import CANDIDATES_TTL, RESULT_CAP_BYTES, Limits, Planner
from wiggle_outside.planner.ports import Busy, Conflict, NotFound

S1 = "session-1"
S2 = "session-2"
K1 = "key-1"
AMBIGUOUS = Ok(GeocodeHits(hits=HITS))

type Published = list[tuple[str, LocationCandidates]]


def planner(r: Rig, **limits: int) -> tuple[Planner, Published]:
    published: Published = []

    def publish(session_id: str, held: LocationCandidates) -> None:
        published.append((session_id, held))

    return (
        Planner(
            r.ports,
            BUDGETS,
            deadline_s=DEADLINE_S,
            publish_candidates=publish,
            limits=Limits(**limits) if limits else Limits(),
        ),
        published,
    )


# --- Start, join, conflict, ownership --------------------------------------------------


@pytest.mark.asyncio
async def test_a_job_runs_to_an_immutable_result() -> None:
    p, _ = planner(rig())
    ref = await p.start_or_join(S1, K1, ANSWERS)
    first = await p.wait(S1, ref.job_id)
    again = await p.wait(S1, ref.job_id)

    assert not ref.joined
    assert first is again
    assert first.job_id == ref.job_id
    assert first.state is JobState.FALLBACK
    assert p.get(S1, ref.job_id) is first


@pytest.mark.asyncio
async def test_the_same_key_and_answers_joins() -> None:
    p, _ = planner(rig())
    first = await p.start_or_join(S1, K1, ANSWERS)
    second = await p.start_or_join(S1, K1, ANSWERS)

    assert second.joined
    assert second.job_id == first.job_id


@pytest.mark.asyncio
async def test_a_different_fingerprint_on_the_same_key_is_a_conflict() -> None:
    p, _ = planner(rig())
    await p.start_or_join(S1, K1, ANSWERS)
    with pytest.raises(Conflict):
        await p.start_or_join(S1, K1, dataclasses.replace(ANSWERS, stroller=True))
    with pytest.raises(Conflict):
        await p.start_or_join(S1, K1, dataclasses.replace(ANSWERS, interest_text="birds"))


@pytest.mark.asyncio
async def test_another_session_sees_nothing() -> None:
    p, _ = planner(rig())
    ref = await p.start_or_join(S1, K1, ANSWERS)
    await p.wait(S1, ref.job_id)

    assert p.get(S2, ref.job_id) is None
    assert p.get(S1, "no-such-job") is None
    with pytest.raises(NotFound):
        await p.wait(S2, ref.job_id)


@pytest.mark.asyncio
async def test_a_running_job_reads_as_running_until_it_finishes() -> None:
    gate = asyncio.Event()
    r = rig(geocoder=FakeGeocoder(gate=gate))
    p, _ = planner(r)
    ref = await p.start_or_join(S1, K1, ANSWERS)
    await asyncio.sleep(0)

    placeholder = p.get(S1, ref.job_id)
    assert placeholder is not None
    assert placeholder.state is JobState.RUNNING
    assert p.active_jobs() == 1

    gate.set()
    result = await p.wait(S1, ref.job_id)
    assert result.state is JobState.FALLBACK
    assert p.active_jobs() == 0


# --- Admission bounds ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_active_job_per_session() -> None:
    gate = asyncio.Event()
    p, _ = planner(rig(geocoder=FakeGeocoder(gate=gate)))
    await p.start_or_join(S1, K1, ANSWERS)
    with pytest.raises(Busy):
        await p.start_or_join(S1, "key-2", ANSWERS)
    gate.set()
    await p.close()


@pytest.mark.asyncio
async def test_the_global_active_bound_answers_busy_with_a_delay() -> None:
    gate = asyncio.Event()
    p, _ = planner(rig(geocoder=FakeGeocoder(gate=gate)), active_global=2)
    await p.start_or_join("a", K1, ANSWERS)
    await p.start_or_join("b", K1, ANSWERS)
    with pytest.raises(Busy) as refused:
        await p.start_or_join("c", K1, ANSWERS)
    assert refused.value.retry_after_s == DEADLINE_S
    gate.set()
    await p.close()


@pytest.mark.asyncio
async def test_terminal_records_are_bounded_and_stale_ones_go_first() -> None:
    r = rig()
    p, _ = planner(r, terminal_records=2)
    first = await p.start_or_join("a", K1, ANSWERS)
    await p.wait("a", first.job_id)
    second = await p.start_or_join("b", K1, ANSWERS)
    await p.wait("b", second.job_id)
    # A third record cannot be admitted while both are still current.
    with pytest.raises(Busy):
        await p.start_or_join("c", K1, ANSWERS)
    # Once both are past valid_until the older one is evicted to make room.
    r.clock.advance(6 * 60)
    third = await p.start_or_join("c", K1, ANSWERS)
    await p.wait("c", third.job_id)
    assert p.get("a", first.job_id) is None
    assert p.get("b", second.job_id) is not None


# --- Candidates ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_ambiguous_place_publishes_candidates_and_a_choice_starts_one_job() -> None:
    r = rig(geocoder=FakeGeocoder(outcome=AMBIGUOUS))
    p, published = planner(r)
    ref = await p.start_or_join(S1, K1, ANSWERS)
    result = await p.wait(S1, ref.job_id)

    assert result.state is JobState.NEEDS_LOCATION_CHOICE
    assert len(published) == 1
    session_id, held = published[0]
    assert session_id == S1
    assert held.answers == ANSWERS
    assert held.expires_at == r.clock.now() + CANDIDATES_TTL

    chosen = held.candidates[0]  # the hit beside the fake places; [1] is 100 km away
    choice = await p.choose_location(S1, chosen.candidate_id)
    assert not choice.joined
    chosen_result = await p.wait(S1, choice.job_id)
    assert chosen_result.state is JobState.FALLBACK
    assert chosen_result.answers.location == chosen.coords
    assert chosen_result.answers.location_label == chosen.label
    # The choice used the stored coordinates: no second geocode.
    assert len(r.geocoder.calls) == 1


@pytest.mark.asyncio
async def test_choosing_the_same_candidate_again_joins_the_same_job() -> None:
    p, published = planner(rig(geocoder=FakeGeocoder(outcome=AMBIGUOUS)))
    ref = await p.start_or_join(S1, K1, ANSWERS)
    await p.wait(S1, ref.job_id)
    candidate = published[0][1].candidates[0].candidate_id

    first = await p.choose_location(S1, candidate)
    await p.wait(S1, first.job_id)
    again = await p.choose_location(S1, candidate)
    assert again.joined
    assert again.job_id == first.job_id


@pytest.mark.asyncio
async def test_a_candidate_from_another_session_or_nowhere_is_not_found() -> None:
    p, published = planner(rig(geocoder=FakeGeocoder(outcome=AMBIGUOUS)))
    ref = await p.start_or_join(S1, K1, ANSWERS)
    await p.wait(S1, ref.job_id)
    candidate = published[0][1].candidates[0].candidate_id

    with pytest.raises(NotFound):
        await p.choose_location(S2, candidate)
    with pytest.raises(NotFound):
        await p.choose_location(S1, "forged")


@pytest.mark.asyncio
async def test_an_expired_candidate_set_is_not_found() -> None:
    r = rig(geocoder=FakeGeocoder(outcome=AMBIGUOUS))
    p, published = planner(r)
    ref = await p.start_or_join(S1, K1, ANSWERS)
    await p.wait(S1, ref.job_id)
    candidate = published[0][1].candidates[0].candidate_id

    r.clock.advance(CANDIDATES_TTL.total_seconds() + 1)
    with pytest.raises(NotFound):
        await p.choose_location(S1, candidate)


# --- Lifecycle ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_result_is_removed_at_retain_until() -> None:
    r = rig()
    p, _ = planner(r)
    ref = await p.start_or_join(S1, K1, ANSWERS)
    result = await p.wait(S1, ref.job_id)

    r.clock.wall = result.retain_until - timedelta(seconds=1)
    assert p.get(S1, ref.job_id) is result
    r.clock.wall = result.retain_until
    assert p.get(S1, ref.job_id) is None
    # The key is free again: the same submission starts a new job, not a join.
    fresh = await p.start_or_join(S1, K1, ANSWERS)
    assert not fresh.joined
    assert fresh.job_id != ref.job_id


@pytest.mark.asyncio
async def test_a_session_ending_removes_everything_it_owned() -> None:
    p, published = planner(rig(geocoder=FakeGeocoder(outcome=AMBIGUOUS)))
    ref = await p.start_or_join(S1, K1, ANSWERS)
    await p.wait(S1, ref.job_id)
    candidate = published[0][1].candidates[0].candidate_id

    p.forget_session(S1)

    assert p.get(S1, ref.job_id) is None
    with pytest.raises(NotFound):
        await p.choose_location(S1, candidate)


@pytest.mark.asyncio
async def test_shutdown_cancels_running_work_and_marks_it_failed() -> None:
    gate = asyncio.Event()
    p, _ = planner(rig(geocoder=FakeGeocoder(gate=gate)))
    ref = await p.start_or_join(S1, K1, ANSWERS)
    await asyncio.sleep(0)

    await p.close()

    result = p.get(S1, ref.job_id)
    assert result is not None
    assert result.state is JobState.FAILED
    assert result.error is ErrorCode.UNEXPECTED_FAILURE
    assert p.active_jobs() == 0


@pytest.mark.asyncio
async def test_an_exception_inside_the_workflow_is_a_safe_failure() -> None:
    class Broken:
        async def resolve(self, _place: object, _deadline: float) -> None:
            msg = "boom"
            raise RuntimeError(msg)

    r = rig()
    r.geocoder = Broken()  # type: ignore[assignment]
    p, _ = planner(r)
    ref = await p.start_or_join(S1, K1, ANSWERS)
    result = await p.wait(S1, ref.job_id)

    assert result.state is JobState.FAILED
    assert result.error is ErrorCode.UNEXPECTED_FAILURE
    assert result.ideas == ()


# --- Bounded storage: the serialised result cap (ARCHITECTURE section 4) -----------------


@pytest.mark.asyncio
async def test_an_oversized_result_is_never_stored_and_reads_as_a_safe_failure() -> None:
    # A geocoder label of 40 000 characters makes the result exceed 32 KiB through the
    # ordinary workflow: the label is carried into the answers summary unchanged.
    huge = GeocodeHit(label="x" * 40_000, coords=HITS[0].coords)
    p, _ = planner(rig(geocoder=FakeGeocoder(outcome=Ok(GeocodeHits(hits=(huge,))))))
    ref = await p.start_or_join(S1, K1, ANSWERS)
    result = await p.wait(S1, ref.job_id)

    assert result.state is JobState.FAILED
    assert result.error is ErrorCode.UNEXPECTED_FAILURE
    assert result.ideas == ()
    assert "x" * 100 not in repr(result), "the oversized record is not kept in any form"
    assert jobs.serialized_size(result) <= RESULT_CAP_BYTES


@pytest.mark.asyncio
async def test_an_ordinary_result_is_well_inside_the_cap() -> None:
    p, _ = planner(rig())
    ref = await p.start_or_join(S1, K1, ANSWERS)
    result = await p.wait(S1, ref.job_id)

    assert result.state is JobState.FALLBACK
    assert jobs.serialized_size(result) < RESULT_CAP_BYTES // 2


# --- The job-level deadline guard (the last resort behind the stage guards) ---------------


@pytest.mark.asyncio
async def test_a_job_that_overruns_its_deadline_is_cancelled_and_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The allowance is the one awaited port without a stage guard; let it hang."""
    cancelled = asyncio.Event()

    class Hanging:
        async def reserve(self, _now: object) -> str:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
            return "reserved"

    monkeypatch.setattr(jobs, "DEADLINE_GRACE_S", 0.0)
    r = rig()
    r.allowance = Hanging()  # type: ignore[assignment]
    p = Planner(r.ports, BUDGETS, deadline_s=0.05)
    ref = await p.start_or_join(S1, K1, ANSWERS)
    result = await asyncio.wait_for(p.wait(S1, ref.job_id), timeout=2.0)

    assert cancelled.is_set(), "the hanging call was cancelled, not left running"
    assert result.state is JobState.FAILED
    assert result.error is ErrorCode.UNEXPECTED_FAILURE
    assert p.active_jobs() == 0
    assert r.places.calls == [], "nothing after the hang ran"
