"""BACKEND-CONTRACT section 6: cooldowns, the negative cache, concurrency and pacing."""

from collections.abc import Mapping
from types import MappingProxyType

import pytest
from fakes import FakeClock, key_for

from wiggle_outside.core.result import OutcomeClass
from wiggle_outside.planner.ports import (
    Allow,
    CoolingDown,
    NegativeCached,
    ProviderName,
    Saturated,
)
from wiggle_outside.storage.gate import (
    DEFAULT_LIMITS,
    MIN_COOLDOWN_S,
    NEGATIVE_TTL_S,
    MemoryGate,
    ProviderLimits,
)

OVERPASS = ProviderName.OVERPASS
NOMINATIM = ProviderName.NOMINATIM
LEASE = 5.0
LONG_RETRY_AFTER = 900.0
PACED = MappingProxyType({NOMINATIM: ProviderLimits(min_interval_s=1.0, max_in_flight=1)})
SINGLE = MappingProxyType({OVERPASS: ProviderLimits(min_interval_s=0.0, max_in_flight=1)})


def gated(
    clock: FakeClock,
    *,
    limits: Mapping[ProviderName, ProviderLimits] = DEFAULT_LIMITS,
) -> MemoryGate:
    return MemoryGate(clock, limits=limits, lease_s=LEASE)


def fail(gate: MemoryGate, clock: FakeClock, provider: ProviderName = OVERPASS) -> None:
    gate.record(provider, key_for(), OutcomeClass.TRANSPORT_FAILURE, None, clock.monotonic())


def test_a_quota_answer_cools_the_provider_for_the_full_retry_after() -> None:
    clock = FakeClock()
    gate = gated(clock)

    gate.record(OVERPASS, key_for(), OutcomeClass.QUOTA_OR_UNAVAILABLE, LONG_RETRY_AFTER, 100.0)

    # No cap below the delay the provider asked for.
    assert gate.cooldown_until(OVERPASS) == 100.0 + LONG_RETRY_AFTER


@pytest.mark.parametrize("retry_after", [None, 0.0, 5.0, MIN_COOLDOWN_S])
def test_a_short_or_missing_retry_after_still_cools_for_sixty_seconds(
    retry_after: float | None,
) -> None:
    clock = FakeClock()
    gate = gated(clock)

    gate.record(OVERPASS, key_for(), OutcomeClass.QUOTA_OR_UNAVAILABLE, retry_after, 100.0)

    assert gate.cooldown_until(OVERPASS) == 100.0 + MIN_COOLDOWN_S


def test_a_cooling_provider_is_refused_at_once_and_only_that_provider() -> None:
    clock = FakeClock()
    gate = gated(clock)
    gate.record(OVERPASS, key_for(), OutcomeClass.QUOTA_OR_UNAVAILABLE, None, 100.0)

    decision = gate.admit(OVERPASS, key_for(), 100.0)

    assert decision == CoolingDown(until=100.0 + MIN_COOLDOWN_S)
    assert gate.admit(NOMINATIM, key_for(), 100.0) == Allow()


def test_a_cooldown_ends_when_it_runs_out() -> None:
    clock = FakeClock()
    gate = gated(clock)
    gate.record(OVERPASS, key_for(), OutcomeClass.QUOTA_OR_UNAVAILABLE, None, 100.0)

    assert gate.admit(OVERPASS, key_for(), 100.0 + MIN_COOLDOWN_S) == Allow()


def test_the_one_permitted_retry_is_not_blocked_by_its_own_first_failure() -> None:
    clock = FakeClock()
    gate = gated(clock)

    fail(gate, clock)

    # The retry passes; the attempt after it is the one the cached failure stops.
    assert gate.admit(OVERPASS, key_for(), clock.monotonic()) == Allow()
    assert gate.admit(OVERPASS, key_for(), clock.monotonic()) == NegativeCached(
        until=clock.monotonic() + NEGATIVE_TTL_S
    )


def test_a_failure_that_repeats_blocks_the_key_at_once() -> None:
    clock = FakeClock()
    gate = gated(clock)

    fail(gate, clock)
    gate.admit(OVERPASS, key_for(), clock.monotonic())  # the retry pass
    fail(gate, clock)

    assert gate.admit(OVERPASS, key_for(), clock.monotonic()) == NegativeCached(
        until=clock.monotonic() + NEGATIVE_TTL_S
    )


def test_the_negative_entry_is_per_key_and_lasts_sixty_seconds() -> None:
    clock = FakeClock()
    gate = gated(clock)

    fail(gate, clock)
    gate.admit(OVERPASS, key_for(), clock.monotonic())  # spend the retry pass

    assert isinstance(gate.admit(OVERPASS, key_for(), clock.monotonic()), NegativeCached)
    assert gate.admit(OVERPASS, key_for("elsewhere"), clock.monotonic()) == Allow()
    assert gate.admit(OVERPASS, key_for(), clock.monotonic() + NEGATIVE_TTL_S) == Allow()


@pytest.mark.parametrize("outcome", [OutcomeClass.OK, OutcomeClass.EMPTY])
def test_a_good_answer_clears_the_negative_entry(outcome: OutcomeClass) -> None:
    clock = FakeClock()
    gate = gated(clock)
    fail(gate, clock)
    gate.admit(OVERPASS, key_for(), clock.monotonic())  # spend the retry pass

    gate.record(OVERPASS, key_for(), outcome, None, clock.monotonic())

    assert gate.admit(OVERPASS, key_for(), clock.monotonic()) == Allow()


def test_a_malformed_answer_is_not_negative_cached() -> None:
    clock = FakeClock()
    gate = gated(clock)

    gate.record(OVERPASS, key_for(), OutcomeClass.MALFORMED, None, clock.monotonic())

    assert gate.admit(OVERPASS, key_for(), clock.monotonic()) == Allow()


def test_concurrency_is_bounded_per_provider() -> None:
    clock = FakeClock()
    gate = gated(clock, limits=SINGLE)

    assert gate.admit(OVERPASS, key_for("one"), 100.0) == Allow()
    assert gate.admit(OVERPASS, key_for("two"), 100.0) == Saturated()


def test_recording_an_attempt_frees_its_slot() -> None:
    clock = FakeClock()
    gate = gated(clock, limits=SINGLE)
    gate.admit(OVERPASS, key_for("one"), 100.0)

    gate.record(OVERPASS, key_for("one"), OutcomeClass.OK, None, 100.0)

    assert gate.admit(OVERPASS, key_for("two"), 100.0) == Allow()


def test_a_slot_cannot_leak_when_an_attempt_never_reports_back() -> None:
    # `pace` may run out of deadline, and a caller may be cancelled, so the slot an
    # admitted attempt holds expires on its own after the stage budget.
    clock = FakeClock()
    gate = gated(clock, limits=SINGLE)
    gate.admit(OVERPASS, key_for("one"), 100.0)

    assert gate.admit(OVERPASS, key_for("two"), 100.0 + LEASE) == Allow()


@pytest.mark.asyncio
async def test_an_unpaced_provider_takes_its_turn_immediately() -> None:
    clock = FakeClock()
    gate = gated(clock, limits=SINGLE)

    assert await gate.pace(OVERPASS, clock.monotonic() + 10.0) is True
    assert gate.next_turn_at(OVERPASS) == 0.0  # pacing is off, so no turn is recorded


@pytest.mark.asyncio
async def test_pacing_moves_the_next_turn_on_by_the_interval() -> None:
    clock = FakeClock()
    gate = gated(clock, limits=PACED)

    assert await gate.pace(NOMINATIM, clock.monotonic() + 10.0) is True
    assert gate.next_turn_at(NOMINATIM) == clock.monotonic() + 1.0

    clock.advance(1.0)  # the turn has come round, so nothing waits

    assert await gate.pace(NOMINATIM, clock.monotonic() + 10.0) is True
    assert gate.next_turn_at(NOMINATIM) == clock.monotonic() + 1.0


@pytest.mark.asyncio
async def test_pacing_refuses_a_deadline_that_has_already_passed() -> None:
    clock = FakeClock()
    gate = gated(clock, limits=PACED)

    assert await gate.pace(NOMINATIM, clock.monotonic()) is False


@pytest.mark.asyncio
async def test_pacing_refuses_rather_than_running_past_the_deadline() -> None:
    # The interval under test is 1 s and the deadline 10 ms away: a hundredfold margin,
    # so the refusal is decided by the deadline and not by how long a sleep took.
    clock = FakeClock()
    gate = gated(clock, limits=PACED)
    await gate.pace(NOMINATIM, clock.monotonic() + 10.0)

    assert await gate.pace(NOMINATIM, clock.monotonic() + 0.01) is False
