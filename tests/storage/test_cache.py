"""CONTRACTS section 4.1: the cache store serves fresh entries and never raises."""

import dataclasses
import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest
from fakes import FakeClock, RecordingCounters, key_for

from wiggle_outside.storage.cache import SqliteCache, epoch
from wiggle_outside.storage.counters import CACHE_BYPASSED, CACHE_HIT, CACHE_MISS, CACHE_STORED
from wiggle_outside.storage.keys import digest_of
from wiggle_outside.storage.sqlite import DEFAULT_BOUNDS, Bounds, Database, record_count

HALF_HOUR = timedelta(minutes=30)


class Fixture:
    """A cache on a real owned thread, with a clock the test moves."""

    def __init__(self, db: Database, *, bounds: Bounds = DEFAULT_BOUNDS) -> None:
        self.db = db
        self.clock = FakeClock()
        self.counters = RecordingCounters()
        self.store = SqliteCache(db, self.counters, self.clock, bounds=bounds)


async def fixture(path: str, *, bounds: Bounds = DEFAULT_BOUNDS, busy_ms: int = 2_000) -> Fixture:
    db = Database(path, busy_timeout_ms=busy_ms)
    await db.open()
    return Fixture(db, bounds=bounds)


@pytest.mark.asyncio
async def test_a_fresh_entry_comes_back_and_is_counted_as_a_hit(tmp_path: Path) -> None:
    held = await fixture(str(tmp_path / "cache.sqlite"))
    key = key_for("home")
    try:
        await held.store.put(key, b"payload", held.clock.now() + HALF_HOUR)

        assert await held.store.get(key, held.clock.now()) == b"payload"
        assert held.counters.count(CACHE_STORED) == 1
        assert held.counters.count(CACHE_HIT) == 1
        assert held.counters.stages(CACHE_HIT) == ["places"]
    finally:
        await held.db.close()


@pytest.mark.asyncio
async def test_an_entry_past_its_freshness_is_a_miss(tmp_path: Path) -> None:
    held = await fixture(str(tmp_path / "cache.sqlite"))
    key = key_for("home")
    try:
        await held.store.put(key, b"payload", held.clock.now() + HALF_HOUR)
        held.clock.advance(HALF_HOUR.total_seconds())

        assert await held.store.get(key, held.clock.now()) is None
        assert held.counters.count(CACHE_MISS) == 1
    finally:
        await held.db.close()


@pytest.mark.asyncio
async def test_a_different_schema_version_cannot_read_the_old_entry(tmp_path: Path) -> None:
    held = await fixture(str(tmp_path / "cache.sqlite"))
    old = key_for("home")
    newer = dataclasses.replace(old, schema_version=old.schema_version + 1)
    try:
        await held.store.put(old, b"payload", held.clock.now() + HALF_HOUR)

        assert digest_of(newer) != digest_of(old)
        assert await held.store.get(newer, held.clock.now()) is None
    finally:
        await held.db.close()


@pytest.mark.asyncio
async def test_an_oversized_entry_is_bypassed_not_stored(tmp_path: Path) -> None:
    held = await fixture(str(tmp_path / "cache.sqlite"), bounds=Bounds(max_entry_bytes=8))
    key = key_for("home")
    try:
        await held.store.put(key, b"x" * 9, held.clock.now() + HALF_HOUR)

        assert await held.store.get(key, held.clock.now()) is None
        assert held.counters.count(CACHE_BYPASSED) == 1
        assert held.counters.count(CACHE_STORED) == 0
    finally:
        await held.db.close()


@pytest.mark.asyncio
async def test_a_locked_database_is_a_bypass_not_an_error(tmp_path: Path) -> None:
    path = str(tmp_path / "cache.sqlite")
    held = await fixture(path, busy_ms=25)
    holder = sqlite3.connect(path)
    try:
        holder.execute("BEGIN EXCLUSIVE")  # the write lock is held, deterministically

        await held.store.put(key_for("home"), b"payload", held.clock.now() + HALF_HOUR)

        assert held.counters.count(CACHE_BYPASSED) == 1
        assert held.counters.count(CACHE_STORED) == 0
    finally:
        holder.close()
        await held.db.close()


@pytest.mark.asyncio
async def test_a_closed_database_is_a_bypass_not_an_error(tmp_path: Path) -> None:
    held = await fixture(str(tmp_path / "cache.sqlite"))
    await held.db.close()

    assert await held.store.get(key_for("home"), held.clock.now()) is None
    await held.store.put(key_for("home"), b"payload", held.clock.now() + HALF_HOUR)

    assert held.counters.count(CACHE_BYPASSED) == 2


@pytest.mark.asyncio
async def test_putting_the_same_key_twice_keeps_one_record(tmp_path: Path) -> None:
    held = await fixture(str(tmp_path / "cache.sqlite"))
    key = key_for("home")
    try:
        await held.store.put(key, b"first", held.clock.now() + HALF_HOUR)
        await held.store.put(key, b"second", held.clock.now() + HALF_HOUR)

        assert await held.db.run(record_count) == 1
        assert await held.store.get(key, held.clock.now()) == b"second"
    finally:
        await held.db.close()


def test_a_naive_timestamp_is_read_as_utc() -> None:
    aware = FakeClock().now()

    assert epoch(aware.replace(tzinfo=None)) == epoch(aware)
