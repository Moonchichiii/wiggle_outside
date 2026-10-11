"""The model stage around the adapter: the slot, the gate and the deadline (DEPLOYMENT 3).

Driven by a fake Ranker and the storage test fakes' gate shape, never by sleeping past
a real budget: the deadlines here are fractions of a second of real time.
"""

import asyncio
from dataclasses import dataclass, field

import pytest
from planner_support import ANSWERS, Counters, FakeClock, FakeModel, rig

from wiggle_outside.core.result import (
    Ok,
    Outcome,
    OutcomeClass,
    QuotaOrUnavailable,
    TransportFailure,
)
from wiggle_outside.core.types import JobState, Pair, Source
from wiggle_outside.planner.model_stage import (
    GATE_BLOCKED,
    GATE_KEY,
    SLOT_TIMEOUT,
    STAGE,
    STAGE_TIMEOUT,
    UPSTREAM_CALL,
    ModelWiring,
    model_stage,
)
from wiggle_outside.planner.plan_outing import Budgets, plan_outing
from wiggle_outside.planner.ports import (
    Allow,
    CacheKey,
    CoolingDown,
    GateDecision,
    ModelRequest,
    NegativeCached,
    ProviderName,
    RawSelection,
)

NOW = 1_000.0
ANSWER = '{"interests": [], "interest_status": "not_provided", "picks": []}'


@dataclass(slots=True)
class FakeRanker:
    outcome: Outcome[RawSelection] = field(default_factory=lambda: Ok(RawSelection(ANSWER)))
    hang: bool = False
    calls: list[tuple[ModelRequest, float]] = field(default_factory=list)
    cancelled: int = 0

    async def select(self, request: ModelRequest, deadline: float) -> Outcome[RawSelection]:
        self.calls.append((request, deadline))
        if self.hang:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled += 1
                raise
        return self.outcome


@dataclass(slots=True)
class FakeGate:
    decision: GateDecision = field(default_factory=Allow)
    admitted: list[tuple[ProviderName, CacheKey]] = field(default_factory=list)
    recorded: list[tuple[ProviderName, OutcomeClass, float | None]] = field(default_factory=list)

    def admit(self, provider: ProviderName, key: CacheKey, now: float) -> GateDecision:  # noqa: ARG002
        self.admitted.append((provider, key))
        return self.decision

    def record(
        self,
        provider: ProviderName,
        key: CacheKey,  # noqa: ARG002
        outcome: OutcomeClass,
        retry_after_s: float | None,
        now: float,  # noqa: ARG002
    ) -> None:
        self.recorded.append((provider, outcome, retry_after_s))

    async def pace(self, provider: ProviderName, deadline: float) -> bool:  # noqa: ARG002
        return True


def wiring(ranker: FakeRanker, gate: FakeGate, clock: FakeClock) -> ModelWiring:
    return ModelWiring(
        ranker=ranker,
        catalogue=rig().catalogue,
        gate=gate,
        counters=Counters(),
        clock=clock,
        d39_enabled=True,
    )


@pytest.mark.asyncio
async def test_one_call_passes_the_gate_and_is_recorded() -> None:
    ranker, gate, clock = FakeRanker(), FakeGate(), FakeClock()
    w = wiring(ranker, gate, clock)
    stage = model_stage(w)

    outcome = await stage((), "birds", NOW + 9.0)

    assert outcome == Ok(RawSelection(ANSWER))
    assert len(ranker.calls) == 1
    assert gate.admitted == [(ProviderName.OPENROUTER, GATE_KEY)]
    assert gate.recorded == [(ProviderName.OPENROUTER, OutcomeClass.OK, None)]
    assert (UPSTREAM_CALL, STAGE) in w.counters.events


@pytest.mark.asyncio
async def test_the_request_is_built_from_the_pairs_and_the_text() -> None:
    ranker = FakeRanker()
    stage = model_stage(wiring(ranker, FakeGate(), FakeClock()))
    await stage((), "birds and puddles", NOW + 9.0)
    ((request, deadline),) = ranker.calls
    assert request.family_text_block == "birds and puddles"
    assert deadline == NOW + 9.0


@pytest.mark.asyncio
async def test_a_cooldown_means_no_call_and_an_unavailable_outcome() -> None:
    ranker, gate = FakeRanker(), FakeGate(decision=CoolingDown(until=NOW + 45.0))
    w = wiring(ranker, gate, FakeClock())
    outcome = await model_stage(w)((), None, NOW + 9.0)

    assert outcome == QuotaOrUnavailable(retry_after_s=45.0)
    assert ranker.calls == []
    assert gate.recorded == []
    assert (GATE_BLOCKED, STAGE) in w.counters.events


@pytest.mark.asyncio
async def test_a_negative_cached_route_fails_fast() -> None:
    ranker, gate = FakeRanker(), FakeGate(decision=NegativeCached(until=NOW + 30.0))
    outcome = await model_stage(wiring(ranker, gate, FakeClock()))((), None, NOW + 9.0)
    assert isinstance(outcome, TransportFailure)
    assert ranker.calls == []


@pytest.mark.asyncio
async def test_a_refusal_is_recorded_with_its_retry_after() -> None:
    ranker = FakeRanker(outcome=QuotaOrUnavailable(retry_after_s=120.0))
    gate = FakeGate()
    outcome = await model_stage(wiring(ranker, gate, FakeClock()))((), None, NOW + 9.0)
    assert outcome == QuotaOrUnavailable(retry_after_s=120.0)
    assert gate.recorded == [(ProviderName.OPENROUTER, OutcomeClass.QUOTA_OR_UNAVAILABLE, 120.0)]


@pytest.mark.asyncio
async def test_a_call_still_running_at_the_deadline_is_cancelled_and_falls_back() -> None:
    # The adapter bounds itself; this is the guard above it (ARCHITECTURE section 4).
    ranker, gate = FakeRanker(hang=True), FakeGate()
    w = wiring(ranker, gate, FakeClock())
    outcome = await model_stage(w)((), None, NOW + 0.05)  # 50 ms of real time

    assert isinstance(outcome, TransportFailure)
    assert ranker.cancelled == 1
    assert (STAGE_TIMEOUT, STAGE) in w.counters.events
    assert gate.recorded == [(ProviderName.OPENROUTER, OutcomeClass.TRANSPORT_FAILURE, None)]


@pytest.mark.asyncio
async def test_only_one_request_is_open_and_a_waiter_gives_up_at_its_deadline() -> None:
    ranker, gate = FakeRanker(hang=True), FakeGate()
    w = wiring(ranker, gate, FakeClock())
    stage = model_stage(w)
    first = asyncio.create_task(stage((), None, NOW + 0.3))
    await asyncio.sleep(0.01)  # the first holds the slot
    second = await stage((), None, NOW + 0.05)

    assert isinstance(second, TransportFailure)
    assert len(ranker.calls) == 1  # the second never reached the adapter
    assert (SLOT_TIMEOUT, STAGE) in w.counters.events
    assert isinstance(await first, TransportFailure)


@pytest.mark.asyncio
async def test_the_slot_is_released_after_a_failure() -> None:
    ranker = FakeRanker(outcome=TransportFailure())
    stage = model_stage(wiring(ranker, FakeGate(), FakeClock()))
    await stage((), None, NOW + 9.0)
    ranker.outcome = Ok(RawSelection(ANSWER))
    assert await stage((), None, NOW + 9.0) == Ok(RawSelection(ANSWER))


@pytest.mark.asyncio
async def test_a_shutdown_cancellation_propagates_and_is_not_a_timeout() -> None:
    ranker = FakeRanker(hang=True)
    stage = model_stage(wiring(ranker, FakeGate(), FakeClock()))
    task = asyncio.create_task(stage((), None, NOW + 9.0))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


# --- Through the workflow: the stage deadline cancels a hung model and the run falls back


@pytest.mark.asyncio
async def test_a_model_that_ignores_its_deadline_is_cancelled_and_the_run_falls_back() -> None:
    class Hanging(FakeModel):
        cancelled: int = 0

        async def __call__(
            self, pairs: tuple[Pair, ...], text: str | None, deadline: float
        ) -> Outcome[RawSelection]:
            self.calls.append((pairs, text, deadline))
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled += 1
                raise
            return self.outcome

    model = Hanging(outcome=TransportFailure())
    r = rig(model=model)
    budgets = Budgets(geocode_s=3.0, providers_s=6.0, model_s=0.05)
    planned = await plan_outing(r.ports, r.run(ANSWERS), budgets)

    assert model.cancelled == 1
    assert planned.state is JobState.FALLBACK  # type: ignore[union-attr]
    assert planned.source is Source.FALLBACK  # type: ignore[union-attr]
    assert planned.ideas  # type: ignore[union-attr]
    assert (STAGE_TIMEOUT, "choosing") in r.counters.events
