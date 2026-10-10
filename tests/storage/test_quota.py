"""DEPLOYMENT section 2.3: one conditional transaction, restart-safe, UTC rollover."""

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from wiggle_outside.storage.quota import (
    DailyAllowance,
    LimitReached,
    Reserved,
    Unavailable,
    seconds_until_rollover,
    utc_day,
)
from wiggle_outside.storage.sqlite import Database, migrate

LIMIT = 5
RACERS = 20
NOON = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
LAST_SECOND = datetime(2026, 10, 10, 23, 59, 59, tzinfo=UTC)
MIDNIGHT = datetime(2026, 10, 11, 0, 0, tzinfo=UTC)
DAY_SECONDS = 24 * 60 * 60


async def allowance(
    path: str,
    limit: int = LIMIT,
    *,
    busy_ms: int = 2_000,
) -> tuple[DailyAllowance, Database]:
    db = Database(path, busy_timeout_ms=busy_ms)
    await db.open()
    quota = DailyAllowance(db, limit)
    await quota.prepare()
    return quota, db


@pytest.mark.asyncio
async def test_many_reservations_at_the_last_slot_give_exactly_one_success(
    tmp_path: Path,
) -> None:
    quota, db = await allowance(str(tmp_path / "wiggle.sqlite"))
    try:
        for _ in range(LIMIT - 1):
            await quota.reserve(NOON)

        racers = await asyncio.gather(*(quota.reserve(NOON) for _ in range(RACERS)))

        assert sum(isinstance(one, Reserved) for one in racers) == 1
        assert sum(isinstance(one, LimitReached) for one in racers) == RACERS - 1
        assert await quota.runs_today(NOON) == LIMIT
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_the_count_survives_a_restart(tmp_path: Path) -> None:
    path = str(tmp_path / "wiggle.sqlite")
    quota, db = await allowance(path)
    await quota.reserve(NOON)
    await quota.reserve(NOON)
    await db.close()  # a crash after the commit, or an ordinary restart

    restarted, again = await allowance(path)
    try:
        assert await restarted.runs_today(NOON) == 2
        assert await restarted.reserve(NOON) == Reserved(runs=3)
    finally:
        await again.close()


@pytest.mark.asyncio
async def test_a_crash_before_the_provider_call_still_counts_the_run(tmp_path: Path) -> None:
    # The reservation commits before any provider work starts, so the run stays counted.
    path = str(tmp_path / "wiggle.sqlite")
    quota, db = await allowance(path)
    assert await quota.reserve(NOON) == Reserved(runs=1)
    await db.close()  # nothing else ran

    restarted, again = await allowance(path)
    try:
        assert await restarted.runs_today(NOON) == 1
    finally:
        await again.close()


@pytest.mark.asyncio
async def test_the_first_run_after_midnight_utc_gets_a_new_row(tmp_path: Path) -> None:
    quota, db = await allowance(str(tmp_path / "wiggle.sqlite"))
    try:
        for _ in range(LIMIT):
            await quota.reserve(LAST_SECOND)

        assert isinstance(await quota.reserve(LAST_SECOND), LimitReached)
        assert await quota.reserve(MIDNIGHT) == Reserved(runs=1)
        assert await quota.runs_today(LAST_SECOND) == LIMIT  # yesterday is untouched
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_a_write_failure_is_unavailable_and_not_limit_reached(tmp_path: Path) -> None:
    path = str(tmp_path / "wiggle.sqlite")
    quota, db = await allowance(path, busy_ms=25)
    holder = sqlite3.connect(path)
    try:
        holder.execute("BEGIN EXCLUSIVE")  # the write lock is held, deterministically

        assert isinstance(await quota.reserve(NOON), Unavailable)
    finally:
        holder.close()
        await db.close()


@pytest.mark.asyncio
async def test_a_read_failure_is_reported_rather_than_guessed(tmp_path: Path) -> None:
    quota, db = await allowance(str(tmp_path / "wiggle.sqlite"))
    await db.close()

    assert isinstance(await quota.reserve(NOON), Unavailable)
    assert await quota.runs_today(NOON) is None


@pytest.mark.asyncio
async def test_a_limit_of_zero_counts_nothing(tmp_path: Path) -> None:
    quota, db = await allowance(str(tmp_path / "wiggle.sqlite"), limit=0)
    try:
        assert isinstance(await quota.reserve(NOON), LimitReached)
        assert await quota.runs_today(NOON) == 0
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_a_cache_migration_never_clears_the_allowance(tmp_path: Path) -> None:
    quota, db = await allowance(str(tmp_path / "wiggle.sqlite"))
    try:
        await quota.reserve(NOON)
        await db.run(lambda conn: conn.execute("PRAGMA user_version = 0"))
        await db.run(migrate)  # the cache is disposable; this is not

        assert await quota.runs_today(NOON) == 1
    finally:
        await db.close()


def test_a_refusal_points_at_the_next_midnight_utc() -> None:
    assert seconds_until_rollover(MIDNIGHT) == DAY_SECONDS
    assert seconds_until_rollover(LAST_SECOND) == 1.0
    assert seconds_until_rollover(NOON) == DAY_SECONDS / 2


def test_the_row_key_is_the_utc_date_whatever_the_local_offset() -> None:
    # 01:30 in UTC+2 is still the previous UTC day.
    local = datetime(2026, 10, 11, 1, 30, tzinfo=timezone(timedelta(hours=2)))

    assert utc_day(local) == "2026-10-10"
    assert utc_day(NOON) == "2026-10-10"
