"""One fetch per key, in memory (BACKEND-CONTRACT section 6).

The first caller fixes the fetch deadline; joiners wait with their own and never extend
it. A waiter that times out or is cancelled detaches, the last waiter leaving cancels the
fetch, and the registry entry goes in `finally`. The cache write lives inside the fetch,
so a cancelled fetch can never reach the cache.
"""

import asyncio
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from wiggle_outside.core.result import Outcome, TransportFailure
from wiggle_outside.storage.counters import DUPLICATE_PREVENTED
from wiggle_outside.storage.keys import digest_of

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from wiggle_outside.planner.ports import CacheKey, Clock, Counters


@dataclass(slots=True)
class _Flight:
    task: asyncio.Task[Outcome[bytes]]
    waiters: int = 0


class MemorySingleFlight:
    """SingleFlight (CONTRACTS section 4.1)."""

    def __init__(self, counters: Counters, clock: Clock) -> None:
        self._counters = counters
        self._clock = clock
        self._flights: dict[str, _Flight] = {}

    def pending(self) -> int:
        """How many fetches are registered. Back to zero once the last waiter leaves."""
        return len(self._flights)

    async def run(
        self,
        key: CacheKey,
        fetch_deadline: float,
        caller_deadline: float,
        fetch: Callable[[float], Awaitable[Outcome[bytes]]],
    ) -> Outcome[bytes]:
        digest = digest_of(key)
        flight = self._join(digest, key.namespace.value, fetch_deadline, fetch)
        flight.waiters += 1
        try:
            async with asyncio.timeout(max(0.0, caller_deadline - self._clock.monotonic())):
                # Shielded: a waiter leaving never cancels work the others still need.
                return await asyncio.shield(flight.task)
        except TimeoutError:
            return TransportFailure()
        finally:
            flight.waiters -= 1
            if flight.waiters == 0:
                flight.task.cancel()
                self._retire(digest, flight)

    def _join(
        self,
        digest: str,
        stage: str,
        fetch_deadline: float,
        fetch: Callable[[float], Awaitable[Outcome[bytes]]],
    ) -> _Flight:
        existing = self._flights.get(digest)
        if existing is not None:
            self._counters.incr(DUPLICATE_PREVENTED, stage)
            return existing  # the first caller's deadline stands
        task = asyncio.ensure_future(fetch(fetch_deadline))
        flight = _Flight(task=task)
        self._flights[digest] = flight
        task.add_done_callback(partial(self._finished, digest, flight))
        return flight

    def _finished(self, digest: str, flight: _Flight, _task: object) -> None:
        self._retire(digest, flight)

    def _retire(self, digest: str, flight: _Flight) -> None:
        if self._flights.get(digest) is flight:
            del self._flights[digest]
