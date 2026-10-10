"""CONTRACTS section 4.1: the order inside a wrapper, and the one retry it owns."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta

import pytest
from fakes import (
    BYTES_CODEC,
    TICK,
    DictStore,
    FakeClock,
    GatedCall,
    RecordingCounters,
    RecordingGate,
    ScriptedProvider,
    engine_for,
    key_for,
    until,
)

from wiggle_outside.core.result import (
    Empty,
    Malformed,
    Ok,
    Outcome,
    OutcomeClass,
    QuotaOrUnavailable,
    TransportFailure,
)
from wiggle_outside.planner.ports import ProviderName
from wiggle_outside.storage.counters import (
    CACHE_UNREADABLE,
    DUPLICATE_PREVENTED,
    GATE_BLOCKED,
    UPSTREAM_CALL,
    UPSTREAM_RETRY,
)
from wiggle_outside.storage.flight import MemorySingleFlight
from wiggle_outside.storage.gate import MemoryGate
from wiggle_outside.storage.keys import digest_of
from wiggle_outside.storage.wrapper import CacheWiring, Codec, Engine, Request, obtain

DEADLINE = TICK + 10.0
TTL = timedelta(minutes=30)
OVERPASS = ProviderName.OVERPASS
COLD = ["admit:Allow", "pace:True"]
RETRY_AFTER = 120.0


@dataclass(slots=True)
class Rig:
    store: DictStore
    gate: RecordingGate
    counters: RecordingCounters
    clock: FakeClock
    engine: Engine


def rig(*, broken: bool = False) -> Rig:
    clock = FakeClock()
    counters = RecordingCounters()
    gate = RecordingGate(MemoryGate(clock))
    store = DictStore(broken=broken)
    wiring = CacheWiring(
        store=store,
        gate=gate,
        flight=MemorySingleFlight(counters, clock),
        counters=counters,
        clock=clock,
    )
    return Rig(store, gate, counters, clock, engine_for(wiring, TTL))


def asking[T](
    inner: object,
    codec: Codec[T] = BYTES_CODEC,
    deadline: float = DEADLINE,
) -> Request[T]:
    return Request(key=key_for(), deadline=deadline, inner=inner, codec=codec)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_a_cold_cache_runs_admit_then_pace_then_the_call_then_record() -> None:
    held = rig()
    provider = ScriptedProvider([Ok(b"payload")])

    result = await obtain(held.engine, asking(provider))

    assert result == Ok(b"payload")
    assert held.gate.calls == [*COLD, "record:ok"]
    assert provider.attempts == 1
    assert provider.deadlines == [DEADLINE]  # the stage deadline, unchanged
    assert held.counters.count(UPSTREAM_CALL) == 1
    assert held.store.entries[digest_of(key_for())][0] == b"payload"


@pytest.mark.asyncio
async def test_a_hit_costs_no_upstream_work_at_all() -> None:
    held = rig()
    await held.store.put(key_for(), b"cached", held.clock.now() + TTL)
    provider = ScriptedProvider([Ok(b"fresh")])

    result = await obtain(held.engine, asking(provider))

    assert result == Ok(b"cached")
    assert provider.attempts == 0
    assert held.gate.calls == []


@pytest.mark.asyncio
async def test_an_empty_answer_is_cached_and_read_back_as_empty() -> None:
    held = rig()
    provider = ScriptedProvider([Empty()])

    assert await obtain(held.engine, asking(provider)) == Empty()
    assert held.store.entries[digest_of(key_for())][0] == b""
    assert await obtain(held.engine, asking(provider)) == Empty()
    assert provider.attempts == 1


@pytest.mark.asyncio
async def test_a_transport_failure_is_retried_once_and_both_attempts_are_gated() -> None:
    held = rig()
    provider = ScriptedProvider([TransportFailure(), Ok(b"second")])

    result = await obtain(held.engine, asking(provider))

    assert result == Ok(b"second")
    assert provider.attempts == 2
    assert held.gate.calls == [*COLD, "record:transport_failure", *COLD, "record:ok"]
    assert held.counters.count(UPSTREAM_RETRY) == 1
    assert held.counters.count(UPSTREAM_CALL) == 2


@pytest.mark.asyncio
async def test_the_retry_is_the_only_one() -> None:
    held = rig()
    provider = ScriptedProvider([TransportFailure()])

    result = await obtain(held.engine, asking(provider))

    assert result == TransportFailure()
    assert provider.attempts == 2
    assert held.counters.count(UPSTREAM_RETRY) == 1
    assert held.store.puts == 0  # a failure is never cached as a result


@pytest.mark.asyncio
async def test_no_retry_once_the_stage_budget_is_gone() -> None:
    held = rig()
    provider = ScriptedProvider([TransportFailure()])

    result = await obtain(held.engine, asking(provider, deadline=held.clock.monotonic()))

    # Attempt 1 is the adapter's to bound - it takes min(stage budget, remaining) - but
    # the wrapper owns the retry, and there is no budget left for one.
    assert result == TransportFailure()
    assert provider.attempts == 1
    assert held.counters.count(UPSTREAM_RETRY) == 0


@pytest.mark.asyncio
async def test_the_final_failure_is_negative_cached_for_the_next_caller() -> None:
    held = rig()
    await obtain(held.engine, asking(ScriptedProvider([TransportFailure()])))
    later = ScriptedProvider([Ok(b"payload")])

    result = await obtain(held.engine, asking(later))

    assert result == TransportFailure()
    assert later.attempts == 0  # the cached failure, without touching the provider
    assert held.counters.count(GATE_BLOCKED) == 1
    # A gate refusal is not a provider failure, so it is never retried.
    assert held.counters.count(UPSTREAM_RETRY) == 1


@pytest.mark.asyncio
async def test_a_quota_answer_on_the_first_attempt_stops_the_retry() -> None:
    held = rig()
    provider = ScriptedProvider([QuotaOrUnavailable(retry_after_s=RETRY_AFTER), Ok(b"second")])

    result = await obtain(held.engine, asking(provider))

    assert result == QuotaOrUnavailable(retry_after_s=RETRY_AFTER)
    assert provider.attempts == 1
    assert held.gate.calls == [*COLD, "record:quota_or_unavailable"]
    assert held.gate.inner.cooldown_until(OVERPASS) == TICK + RETRY_AFTER
    assert held.store.puts == 0


@pytest.mark.asyncio
async def test_a_cooling_provider_is_not_called_and_not_held() -> None:
    held = rig()
    held.gate.inner.record(
        OVERPASS, key_for("other"), OutcomeClass.QUOTA_OR_UNAVAILABLE, RETRY_AFTER, TICK
    )
    provider = ScriptedProvider([Ok(b"payload")])

    result = await obtain(held.engine, asking(provider))

    assert result == QuotaOrUnavailable(retry_after_s=RETRY_AFTER)
    assert provider.attempts == 0
    assert held.gate.calls == ["admit:CoolingDown"]


@pytest.mark.asyncio
async def test_a_malformed_answer_is_neither_retried_nor_cached() -> None:
    held = rig()
    provider = ScriptedProvider([Malformed()])

    result = await obtain(held.engine, asking(provider))

    assert result == Malformed()
    assert provider.attempts == 1
    assert held.store.puts == 0


@pytest.mark.asyncio
async def test_a_payload_that_will_not_decode_is_a_counted_miss() -> None:
    held = rig()

    def refuse(_payload: bytes) -> bytes:
        msg = "not the shape we require"
        raise ValueError(msg)

    codec: Codec[bytes] = Codec(encode=BYTES_CODEC.encode, decode=refuse)
    await held.store.put(key_for(), b"rubbish", held.clock.now() + TTL)
    provider = ScriptedProvider([Ok(b"fresh")])

    result = await obtain(held.engine, asking(provider, codec))

    assert result == Malformed()  # the fresh answer cannot be decoded back either
    assert provider.attempts == 1
    assert held.counters.count(CACHE_UNREADABLE) == 2


@pytest.mark.asyncio
async def test_a_cancelled_fetch_never_reaches_the_cache() -> None:
    held = rig()
    provider = GatedCall()
    caller = asyncio.create_task(obtain(held.engine, asking(provider)))
    await provider.started.wait()

    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    await until(lambda: provider.cancelled == 1)

    assert held.store.puts == 0
    assert held.store.entries == {}


@pytest.mark.asyncio
async def test_a_broken_cache_still_costs_exactly_one_upstream_call() -> None:
    held = rig(broken=True)
    provider = ScriptedProvider([Ok(b"payload")])

    result = await obtain(held.engine, asking(provider))

    assert result == Ok(b"payload")
    assert provider.attempts == 1
    assert held.counters.count(UPSTREAM_CALL) == 1


@pytest.mark.asyncio
async def test_a_broken_cache_cannot_cause_a_stampede() -> None:
    # Coalescing lives in memory, so a disk failure does not multiply provider calls.
    held = rig(broken=True)
    provider = GatedCall()
    first = asyncio.create_task(obtain(held.engine, asking(provider)))
    await provider.started.wait()
    joiners = [asyncio.create_task(obtain(held.engine, asking(provider))) for _ in range(2)]
    await until(lambda: held.counters.count(DUPLICATE_PREVENTED) == 2)

    provider.release.set()
    results: list[Outcome[bytes]] = await asyncio.gather(first, *joiners)

    assert provider.calls == 1
    assert results == [Ok(b"payload")] * 3
    assert held.counters.count(UPSTREAM_CALL) == 1


@pytest.mark.asyncio
async def test_one_fetch_writes_the_cache_once_for_every_joiner() -> None:
    held = rig()
    provider = GatedCall()
    first = asyncio.create_task(obtain(held.engine, asking(provider)))
    await provider.started.wait()
    joiner = asyncio.create_task(obtain(held.engine, asking(provider)))
    await until(lambda: held.counters.count(DUPLICATE_PREVENTED) == 1)

    provider.release.set()
    await asyncio.gather(first, joiner)

    assert held.store.puts == 1
