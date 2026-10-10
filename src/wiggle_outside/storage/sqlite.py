"""SQLite on one owned thread: the connection, its migrations and the cache bounds.

ARCHITECTURE section 7: one owned executor thread creates, uses and closes the
connection, so ownership is guaranteed rather than assumed (`asyncio.to_thread` does not
promise the same thread twice). Cache entries are disposable: a schema-version change
discards and rebuilds them (ARCHITECTURE section 15).
"""

import asyncio
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable

SCHEMA_VERSION: Final = 1
BUSY_TIMEOUT_MS: Final = 2_000
MEMORY_PATH: Final = ":memory:"

# One row per eviction step, so the order (expired first, then least recently used) is
# the order the bounds are restored in. At most 1,000 rows, so the loop stays cheap.
_EVICT_BATCH: Final = 1

_DROP_CACHE: Final = "DROP TABLE IF EXISTS cache_entry;\n"
_CREATE_CACHE: Final = """
CREATE TABLE IF NOT EXISTS cache_entry (
    digest TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    payload BLOB NOT NULL,
    fresh_until REAL NOT NULL,
    last_used REAL NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS cache_entry_fresh_until ON cache_entry (fresh_until);
CREATE INDEX IF NOT EXISTS cache_entry_last_used ON cache_entry (last_used);
"""
_INSERT_CACHE: Final = (
    "INSERT INTO cache_entry (digest, namespace, payload, fresh_until, last_used) "
    "VALUES (?, ?, ?, ?, ?) "
    "ON CONFLICT(digest) DO UPDATE SET payload = excluded.payload, "
    "fresh_until = excluded.fresh_until, last_used = excluded.last_used"
)
_EVICT_LRU: Final = (
    "DELETE FROM cache_entry WHERE digest IN "
    "(SELECT digest FROM cache_entry ORDER BY last_used, digest LIMIT ?)"
)


@dataclass(frozen=True, slots=True)
class Bounds:
    """Starting values (ARCHITECTURE section 7): measure them, never lower them silently."""

    max_records: int = 1_000
    max_entry_bytes: int = 1 << 20
    storage_budget_bytes: int = 64 << 20


DEFAULT_BOUNDS: Final = Bounds()


@dataclass(frozen=True, slots=True)
class Entry:
    """One disposable cache row. Timestamps are epoch seconds, UTC."""

    digest: str
    namespace: str
    payload: bytes
    fresh_until: float
    last_used: float


class ThreadOwnershipError(RuntimeError):
    """A database call reached a thread that does not own the connection."""


class DatabaseClosedError(RuntimeError):
    """The owned connection is gone, so the caller bypasses the cache."""


def read_fresh(conn: sqlite3.Connection, digest: str, now: float) -> bytes | None:
    """Return a fresh payload and touch it for the LRU order. Expired entries are a miss."""
    row = conn.execute(
        "SELECT payload FROM cache_entry WHERE digest = ? AND fresh_until > ?",
        (digest, now),
    ).fetchone()
    if row is None:
        return None
    conn.execute("UPDATE cache_entry SET last_used = ? WHERE digest = ?", (now, digest))
    payload: bytes = row[0]
    return payload


def write_entry(conn: sqlite3.Connection, entry: Entry, bounds: Bounds, db_path: str) -> None:
    conn.execute(
        _INSERT_CACHE,
        (entry.digest, entry.namespace, entry.payload, entry.fresh_until, entry.last_used),
    )
    evict(conn, entry.last_used, bounds, db_path)


def evict(conn: sqlite3.Connection, now: float, bounds: Bounds, db_path: str) -> None:
    """Expired entries first, then least recently used (ARCHITECTURE section 7)."""
    conn.execute("DELETE FROM cache_entry WHERE fresh_until <= ?", (now,))
    while _over_bounds(conn, bounds, db_path):
        if conn.execute(_EVICT_LRU, (_EVICT_BATCH,)).rowcount == 0:
            return  # nothing left to drop: the cache is bypassed rather than the request failed
        conn.execute("PRAGMA incremental_vacuum")


def record_count(conn: sqlite3.Connection) -> int:
    count: int = conn.execute("SELECT count(*) FROM cache_entry").fetchone()[0]
    return count


def disk_bytes(conn: sqlite3.Connection, db_path: str) -> int:
    """Database pages plus the WAL and journal files (ARCHITECTURE section 7)."""
    pages: int = conn.execute("PRAGMA page_count").fetchone()[0]
    page_size: int = conn.execute("PRAGMA page_size").fetchone()[0]
    total = pages * page_size
    for suffix in ("-wal", "-journal"):
        with suppress(OSError):
            total += Path(db_path + suffix).stat().st_size
    return total


def _over_bounds(conn: sqlite3.Connection, bounds: Bounds, db_path: str) -> bool:
    return (
        record_count(conn) > bounds.max_records
        or disk_bytes(conn, db_path) > bounds.storage_budget_bytes
    )


def migrate(conn: sqlite3.Connection) -> None:
    """Rebuild the cache when the stored schema version is not ours.

    The cache is disposable (ARCHITECTURE section 15). A hosted `quota` table is not cache
    and is never dropped here (DEPLOYMENT section 2.3).
    """
    applied: int = conn.execute("PRAGMA user_version").fetchone()[0]
    if applied == SCHEMA_VERSION:
        return
    conn.executescript(_DROP_CACHE + _CREATE_CACHE)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION:d}")


class Database:
    """One SQLite connection, created, used and closed on one owned thread."""

    def __init__(self, path: str, *, busy_timeout_ms: int = BUSY_TIMEOUT_MS) -> None:
        self._path = path
        self._busy_timeout_ms = busy_timeout_ms
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wo-sqlite")
        self._conn: sqlite3.Connection | None = None
        self._owner_ident: int | None = None

    @property
    def path(self) -> str:
        return self._path

    @property
    def owner_ident(self) -> int | None:
        """The one thread allowed to touch the connection; claimed when it is created."""
        return self._owner_ident

    async def open(self) -> None:
        await self._submit(self._connect)

    async def close(self) -> None:
        with suppress(DatabaseClosedError):
            await self._submit(self._disconnect)
        self._pool.shutdown(wait=True)

    async def run[T](self, work: Callable[[sqlite3.Connection], T]) -> T:
        """Run one unit of work, as one transaction, on the owned thread."""
        return await self._submit(partial(self._invoke, work))

    async def _submit[T](self, work: Callable[[], T]) -> T:
        loop = asyncio.get_running_loop()
        try:
            pending = loop.run_in_executor(self._pool, work)
        except RuntimeError as exc:  # the pool is shut down: there is no owned thread left
            raise DatabaseClosedError(str(exc)) from exc
        return await pending

    def _connect(self) -> None:
        self._claim()
        conn = sqlite3.connect(self._path, check_same_thread=True)
        conn.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms:d}")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA auto_vacuum = INCREMENTAL")
        conn.execute("PRAGMA trusted_schema = OFF")
        migrate(conn)
        self._conn = conn

    def _disconnect(self) -> None:
        self._claim()
        conn = self._require()
        self._conn = None
        conn.close()

    def _invoke[T](self, work: Callable[[sqlite3.Connection], T]) -> T:
        self._claim()
        conn = self._require()
        with conn:  # one transaction per call: none stays open across network or model work
            return work(conn)

    def _require(self) -> sqlite3.Connection:
        if self._conn is None:
            msg = "the SQLite connection is not open"
            raise DatabaseClosedError(msg)
        return self._conn

    def _claim(self) -> None:
        ident = threading.get_ident()
        if self._owner_ident is None:
            self._owner_ident = ident
        elif ident != self._owner_ident:
            msg = f"thread {ident} is not the owner {self._owner_ident}"
            raise ThreadOwnershipError(msg)
