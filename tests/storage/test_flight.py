"""BACKEND-CONTRACT section 6: one fetch per key, owned deadlines, waiter cancellation.

Every race here is driven by an event or by yielding to the loop, never by a sleep.
"""

import asyncio

import pytest
from fakes import FakeClock, GatedCall, RecordingCounters, key_for, until

from wiggle_outside.core.result import Ok, TransportFailure
from wiggle_outside.storage.counters import DUPLICATE_PREVENTED
from wiggle_outside.storage.flight import MemorySingleFlight

PAYLOAD = Ok(b"payload")
WAITERS = 3


def built() -> tuple[MemorySingleFlight, RecordingCounters]:
    counters = RecordingCounters()
    return MemorySingleFlight(counters, FakeClock()), counters


@pytest.mark.asyncio
async def test_one_fetch_serves_every_waiter_for_the_same_key() -> None:
    flight, counters = built()
    fetch = GatedCall()
    first = asyncio.create_task(flight.run(key_for(), 500.0, 500.0, fetch))
    await fetch.started.wait()

    joiners = [asyncio.create_task(flight.run(key_for(), 500.0, 500.0, fetch)) for _ in range(2)]
    await until(lambda: counters.count(DUPLICATE_PREVENTED) == 2)
    fetch.release.set()
    results = await asyncio.gather(first, *joiners)

    assert fetch.calls == 1
    assert results == [PAYLOAD] * WAITERS
    assert flight.pending() == 0


@pytest.mark.asyncio
async def test_different_keys_get_their_own_fetch() -> None:
    flight, counters = built()
    fetch = GatedCall()
    first = asyncio.create_task(flight.run(key_for("here"), 500.0, 500.0, fetch))
    await fetch.started.wait()
    second = asyncio.create_task(flight.run(key_for("there"), 500.0, 500.0, fetch))
    await until(lambda: fetch.calls == 2)

    fetch.release.set()
    await asyncio.gather(first, second)

    assert counters.count(DUPLICATE_PREVENTED) == 0


@pytest.mark.asyncio
async def test_a_joiner_never_extends_the_first_callers_fetch_deadline() -> None:
    flight, counters = built()
    fetch = GatedCall()
    first = asyncio.create_task(flight.run(key_for(), 150.0, 160.0, fetch))
    await fetch.started.wait()

    joiner = asyncio.create_task(flight.run(key_for(), 9_000.0, 9_000.0, fetch))
    await until(lambda: counters.count(DUPLICATE_PREVENTED) == 1)
    fetch.release.set()
    await asyncio.gather(first, joiner)

    assert fetch.deadlines == [150.0]  # the joiner's deadline never reached the fetch


@pytest.mark.asyncio
async def test_the_last_waiter_leaving_cancels_the_fetch() -> None:
    flight, _ = built()
    fetch = GatedCall()
    only = asyncio.create_task(flight.run(key_for(), 500.0, 500.0, fetch))
    await fetch.started.wait()

    only.cancel()
    with pytest.raises(asyncio.CancelledError):
        await only
    await until(lambda: fetch.cancelled == 1)

    assert fetch.finished == 0
    assert flight.pending() == 0


@pytest.mark.asyncio
async def test_one_waiter_leaving_does_not_cancel_work_the_others_need() -> None:
    flight, counters = built()
    fetch = GatedCall()
    first = asyncio.create_task(flight.run(key_for(), 500.0, 500.0, fetch))
    await fetch.started.wait()
    joiner = asyncio.create_task(flight.run(key_for(), 500.0, 500.0, fetch))
    await until(lambda: counters.count(DUPLICATE_PREVENTED) == 1)

    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first

    assert fetch.cancelled == 0

    fetch.release.set()

    assert await joiner == PAYLOAD
    assert fetch.calls == 1
    assert flight.pending() == 0


@pytest.mark.asyncio
async def test_a_waiter_out_of_deadline_detaches_and_is_told_so() -> None:
    flight, _ = built()
    fetch = GatedCall()

    result = await flight.run(key_for(), 500.0, FakeClock().monotonic(), fetch)

    assert result == TransportFailure()
    assert fetch.finished == 0
    assert flight.pending() == 0


@pytest.mark.asyncio
async def test_a_joiner_out_of_deadline_leaves_the_fetch_running() -> None:
    flight, counters = built()
    fetch = GatedCall()
    first = asyncio.create_task(flight.run(key_for(), 500.0, 500.0, fetch))
    await fetch.started.wait()

    late = await flight.run(key_for(), 500.0, FakeClock().monotonic(), fetch)
    await until(lambda: counters.count(DUPLICATE_PREVENTED) == 1)
    fetch.release.set()

    assert late == TransportFailure()
    assert await first == PAYLOAD
    assert fetch.calls == 1


@pytest.mark.asyncio
async def test_a_finished_fetch_is_not_reused_by_the_next_caller() -> None:
    flight, _ = built()
    first = GatedCall()
    first.release.set()

    assert await flight.run(key_for(), 500.0, 500.0, first) == PAYLOAD
    assert flight.pending() == 0

    second = GatedCall(outcome=Ok(b"later"))
    second.release.set()

    assert await flight.run(key_for(), 500.0, 500.0, second) == Ok(b"later")
