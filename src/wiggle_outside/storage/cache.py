"""The cache store: fresh entries only, and never an error to its caller.

CONTRACTS section 4.1 and ARCHITECTURE section 15. A storage failure, a full disk or an
oversized entry is a bypass, not a failure: the request still runs and still obeys its
budget (section 14). Every call goes to the one owned SQLite thread.
"""

from datetime import UTC
from functools import partial
from typing import TYPE_CHECKING

from wiggle_outside.storage.counters import CACHE_BYPASSED, CACHE_HIT, CACHE_MISS, CACHE_STORED
from wiggle_outside.storage.keys import digest_of
from wiggle_outside.storage.sqlite import (
    DEFAULT_BOUNDS,
    STORAGE_ERRORS,
    Bounds,
    Database,
    Entry,
    read_fresh,
    write_entry,
)

if TYPE_CHECKING:
    from datetime import datetime

    from wiggle_outside.planner.ports import CacheKey, Clock, Counters


def epoch(moment: datetime) -> float:
    """Epoch seconds. A naive value is read as UTC, which is what the planner uses."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC).timestamp()
    return moment.timestamp()


class SqliteCache:
    """CacheStore (CONTRACTS section 4.1) over the owned SQLite thread."""

    def __init__(
        self,
        db: Database,
        counters: Counters,
        clock: Clock,
        *,
        bounds: Bounds = DEFAULT_BOUNDS,
    ) -> None:
        self._db = db
        self._counters = counters
        self._clock = clock
        self._bounds = bounds

    async def get(self, key: CacheKey, now: datetime) -> bytes | None:
        stage = key.namespace.value
        work = partial(read_fresh, digest=digest_of(key), now=epoch(now))
        try:
            payload = await self._db.run(work)
        except STORAGE_ERRORS:
            self._counters.incr(CACHE_BYPASSED, stage)
            return None
        self._counters.incr(CACHE_HIT if payload is not None else CACHE_MISS, stage)
        return payload

    async def put(self, key: CacheKey, payload: bytes, fresh_until: datetime) -> None:
        stage = key.namespace.value
        if len(payload) > self._bounds.max_entry_bytes:
            self._counters.incr(CACHE_BYPASSED, stage)
            return
        entry = Entry(
            digest=digest_of(key),
            namespace=stage,
            payload=payload,
            fresh_until=epoch(fresh_until),
            last_used=epoch(self._clock.now()),
        )
        work = partial(write_entry, entry=entry, bounds=self._bounds, db_path=self._db.path)
        try:
            await self._db.run(work)
        except STORAGE_ERRORS:
            self._counters.incr(CACHE_BYPASSED, stage)
            return
        self._counters.incr(CACHE_STORED, stage)
