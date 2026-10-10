"""ARCHITECTURE section 7: one owned thread, migrations, bounds and eviction order."""

import asyncio
import sqlite3
import threading
from pathlib import Path

import pytest

from wiggle_outside.storage.sqlite import (
    BUSY_TIMEOUT_MS,
    MEMORY_PATH,
    SCHEMA_VERSION,
    Bounds,
    Database,
    DatabaseClosedError,
    Entry,
    disk_bytes,
    evict,
    migrate,
    read_fresh,
    record_count,
    write_entry,
)

CALLS = 40
OWNED_THREAD_PREFIX = "wo-sqlite"


def entry(digest: str, *, fresh_until: float, last_used: float, size: int = 16) -> Entry:
    return Entry(
        digest=digest,
        namespace="places",
        payload=b"x" * size,
        fresh_until=fresh_until,
        last_used=last_used,
    )


def insert(conn: sqlite3.Connection, digest: str, fresh_until: float, last_used: float) -> None:
    """Place a row directly, so a test can set up one that is already expired."""
    conn.execute(
        "INSERT INTO cache_entry VALUES (?, ?, ?, ?, ?)",
        (digest, "places", b"payload", fresh_until, last_used),
    )


def digests(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT digest FROM cache_entry")}


def owned_threads() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name.startswith(OWNED_THREAD_PREFIX)]


async def opened(path: str, *, busy_timeout_ms: int = BUSY_TIMEOUT_MS) -> Database:
    db = Database(path, busy_timeout_ms=busy_timeout_ms)
    await db.open()
    return db


def migrated(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    migrate(conn)
    return conn


@pytest.mark.asyncio
async def test_every_call_runs_on_the_one_thread_that_created_the_connection() -> None:
    db = await opened(MEMORY_PATH)
    try:
        owned = owned_threads()

        # Exactly one owned thread exists, and it is the one that created the connection.
        assert len(owned) == 1
        assert db.owner_ident == owned[0].ident
        assert db.owner_ident != threading.get_ident()

        seen = {await db.run(lambda _conn: threading.get_ident()) for _ in range(CALLS)}

        assert seen == {db.owner_ident}
    finally:
        await db.close()

    # close() only suppresses DatabaseClosedError, so closing on another thread would have
    # raised ThreadOwnershipError out of here instead of retiring the thread.
    assert owned_threads() == []


@pytest.mark.asyncio
async def test_concurrent_calls_still_share_the_single_thread() -> None:
    db = await opened(MEMORY_PATH)
    try:
        idents = await asyncio.gather(
            *(db.run(lambda _conn: threading.get_ident()) for _ in range(CALLS))
        )
    finally:
        await db.close()

    assert set(idents) == {db.owner_ident}


@pytest.mark.asyncio
async def test_the_connection_refuses_other_threads_outright() -> None:
    db = await opened(MEMORY_PATH)
    try:
        conn = await db.run(lambda conn: conn)
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")  # this thread does not own the connection
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_a_closed_database_reports_itself_instead_of_hanging() -> None:
    db = await opened(MEMORY_PATH)
    await db.close()

    with pytest.raises(DatabaseClosedError):
        await db.run(record_count)


@pytest.mark.asyncio
async def test_the_migration_records_the_schema_version(tmp_path: Path) -> None:
    db = await opened(str(tmp_path / "cache.sqlite"))
    try:
        applied = await db.run(lambda conn: conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        await db.close()

    assert applied == SCHEMA_VERSION


@pytest.mark.asyncio
async def test_busy_timeout_is_set_on_the_owned_connection(tmp_path: Path) -> None:
    db = await opened(str(tmp_path / "cache.sqlite"), busy_timeout_ms=25)
    try:
        timeout = await db.run(lambda conn: conn.execute("PRAGMA busy_timeout").fetchone()[0])
    finally:
        await db.close()

    assert timeout == 25


@pytest.mark.asyncio
async def test_a_write_locked_out_gives_up_after_busy_timeout(tmp_path: Path) -> None:
    path = str(tmp_path / "cache.sqlite")
    db = await opened(path, busy_timeout_ms=25)
    holder = sqlite3.connect(path)
    try:
        holder.execute("BEGIN EXCLUSIVE")  # hold the write lock; no sleep decides this
        with pytest.raises(sqlite3.OperationalError):
            await db.run(
                lambda conn: write_entry(
                    conn,
                    entry("locked", fresh_until=2_000.0, last_used=1_000.0),
                    Bounds(),
                    path,
                )
            )
    finally:
        holder.close()
        await db.close()


def test_a_schema_version_change_discards_the_cache(tmp_path: Path) -> None:
    path = str(tmp_path / "cache.sqlite")
    conn = migrated(path)
    try:
        write_entry(conn, entry("keep", fresh_until=2_000.0, last_used=1_000.0), Bounds(), path)
        assert record_count(conn) == 1

        conn.execute("PRAGMA user_version = 0")  # as an older build would have left it
        migrate(conn)

        assert record_count(conn) == 0
    finally:
        conn.close()


def test_a_schema_version_change_leaves_the_quota_table_alone(tmp_path: Path) -> None:
    # The cache is disposable; a hosted quota table is not (DEPLOYMENT section 2.3).
    conn = migrated(str(tmp_path / "cache.sqlite"))
    try:
        conn.execute("CREATE TABLE quota (utc_day TEXT PRIMARY KEY, runs INTEGER NOT NULL)")
        conn.execute("INSERT INTO quota VALUES ('2026-10-10', 7)")
        conn.execute("PRAGMA user_version = 0")
        migrate(conn)

        assert conn.execute("SELECT runs FROM quota").fetchone()[0] == 7
    finally:
        conn.close()


def test_expired_entries_go_before_the_least_recently_used(tmp_path: Path) -> None:
    path = str(tmp_path / "cache.sqlite")
    conn = migrated(path)
    try:
        # "stale" is expired but the most recently used; "cold" is fresh and the least
        # recently used. Expired first, then LRU, so "stale" goes and "cold" survives.
        insert(conn, "stale", fresh_until=500.0, last_used=900.0)
        insert(conn, "cold", fresh_until=5_000.0, last_used=100.0)
        insert(conn, "warm", fresh_until=5_000.0, last_used=800.0)

        evict(conn, 1_000.0, Bounds(max_records=2), path)

        assert digests(conn) == {"cold", "warm"}

        evict(conn, 1_000.0, Bounds(max_records=1), path)

        assert digests(conn) == {"warm"}
    finally:
        conn.close()


def test_a_write_purges_expired_entries(tmp_path: Path) -> None:
    path = str(tmp_path / "cache.sqlite")
    conn = migrated(path)
    try:
        insert(conn, "stale", fresh_until=500.0, last_used=100.0)
        write_entry(conn, entry("new", fresh_until=9_000.0, last_used=1_000.0), Bounds(), path)

        assert digests(conn) == {"new"}
    finally:
        conn.close()


def test_the_record_bound_holds_after_every_write(tmp_path: Path) -> None:
    path = str(tmp_path / "cache.sqlite")
    conn = migrated(path)
    bounds = Bounds(max_records=5)
    try:
        for index in range(20):
            write_entry(
                conn, entry(f"d{index}", fresh_until=9_000.0, last_used=float(index)), bounds, path
            )
            assert record_count(conn) <= bounds.max_records

        assert digests(conn) == {f"d{index}" for index in range(15, 20)}
    finally:
        conn.close()


def test_a_storage_budget_that_cannot_fit_an_entry_leaves_the_cache_empty(tmp_path: Path) -> None:
    # ARCHITECTURE section 7: if storage cannot fit an entry, bypass caching rather than
    # fail a valid request. Eviction must stop instead of looping.
    path = str(tmp_path / "cache.sqlite")
    conn = migrated(path)
    try:
        write_entry(
            conn,
            entry("big", fresh_until=9_000.0, last_used=1.0),
            Bounds(storage_budget_bytes=1),
            path,
        )

        assert record_count(conn) == 0
    finally:
        conn.close()


def test_a_fresh_entry_reads_back_and_an_expired_one_does_not(tmp_path: Path) -> None:
    conn = migrated(str(tmp_path / "cache.sqlite"))
    try:
        insert(conn, "fresh", fresh_until=2_000.0, last_used=1_000.0)

        assert read_fresh(conn, "fresh", 1_500.0) == b"payload"
        assert read_fresh(conn, "fresh", 2_000.0) is None  # at fresh_until it is expired
        assert read_fresh(conn, "missing", 1_500.0) is None
    finally:
        conn.close()


def test_reading_an_entry_makes_it_the_most_recently_used(tmp_path: Path) -> None:
    path = str(tmp_path / "cache.sqlite")
    conn = migrated(path)
    try:
        insert(conn, "old", fresh_until=9_000.0, last_used=100.0)
        insert(conn, "new", fresh_until=9_000.0, last_used=200.0)

        read_fresh(conn, "old", 300.0)
        evict(conn, 300.0, Bounds(max_records=1), path)

        assert digests(conn) == {"old"}
    finally:
        conn.close()


def test_disk_accounting_includes_the_wal_file(tmp_path: Path) -> None:
    path = str(tmp_path / "cache.sqlite")
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        migrate(conn)
        write_entry(conn, entry("one", fresh_until=9_000.0, last_used=1.0), Bounds(), path)

        pages: int = conn.execute("PRAGMA page_count").fetchone()[0]
        page_size: int = conn.execute("PRAGMA page_size").fetchone()[0]
        wal_bytes = Path(path + "-wal").stat().st_size

        assert wal_bytes > 0
        assert disk_bytes(conn, path) == pages * page_size + wal_bytes
    finally:
        conn.close()
