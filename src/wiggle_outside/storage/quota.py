"""Restart-safe daily planning allowance (DEPLOYMENT section 2.3).

One conditional transaction on the owned SQLite thread decides each reservation, and the
DB thread serialises them, so two jobs cannot both take the last slot. It commits before
any provider work starts, so a crash afterwards leaves the run counted - conservative on
purpose. The table is not cache: the migration in `storage/sqlite.py` never drops it and a
cache reset never clears it.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from functools import partial
from typing import TYPE_CHECKING, Final

from wiggle_outside.storage.sqlite import STORAGE_ERRORS

if TYPE_CHECKING:
    import sqlite3

    from wiggle_outside.storage.sqlite import Database

CREATE_QUOTA: Final = (
    "CREATE TABLE IF NOT EXISTS quota (utc_day TEXT PRIMARY KEY, runs INTEGER NOT NULL) STRICT"
)

# The one conditional statement DEPLOYMENT section 2.3 specifies.
RESERVE: Final = (
    "INSERT INTO quota (utc_day, runs) VALUES (:day, 1) "
    "ON CONFLICT(utc_day) DO UPDATE SET runs = runs + 1 WHERE runs < :limit"
)


@dataclass(frozen=True, slots=True)
class Reserved:
    """The run is counted. It stays counted even if the job then fails."""

    runs: int


@dataclass(frozen=True, slots=True)
class LimitReached:
    """Today's allowance is spent. Refuse before any work, until the next 00:00 UTC."""

    retry_after_s: float


@dataclass(frozen=True, slots=True)
class Unavailable:
    """The allowance could not be read or written, so the run is refused.

    Different wording from `LimitReached` (DEPLOYMENT section 2.3): it never tells people
    to wait until midnight, and the allowance never silently resets or grows.
    """


type Reservation = Reserved | LimitReached | Unavailable


def utc_day(now: datetime) -> str:
    """Give the UTC date at reservation time, which is the row key."""
    return now.astimezone(UTC).date().isoformat()


def seconds_until_rollover(now: datetime) -> float:
    """Count the seconds to the next 00:00 UTC, when a new row starts."""
    moment = now.astimezone(UTC)
    midnight = datetime.combine(moment.date() + timedelta(days=1), time.min, tzinfo=UTC)
    return (midnight - moment).total_seconds()


def _reserve(conn: sqlite3.Connection, day: str, limit: int) -> int | None:
    """Take one slot, or report that the day is full. One statement, one transaction."""
    if conn.execute(RESERVE, {"day": day, "limit": limit}).rowcount != 1:
        return None
    runs: int = conn.execute("SELECT runs FROM quota WHERE utc_day = ?", (day,)).fetchone()[0]
    return runs


class DailyAllowance:
    """The hosted daily run limit, kept in SQLite so a restart cannot reset it."""

    def __init__(self, db: Database, limit: int) -> None:
        self._db = db
        self._limit = limit

    async def prepare(self) -> None:
        """Create the table. Separate from the cache migration, which never drops it."""
        await self._db.run(lambda conn: conn.execute(CREATE_QUOTA))

    async def reserve(self, now: datetime) -> Reservation:
        if self._limit <= 0:
            # The documented statement inserts the first row unconditionally, so a limit
            # of zero is refused here rather than counted.
            return LimitReached(retry_after_s=seconds_until_rollover(now))
        try:
            runs = await self._db.run(partial(_reserve, day=utc_day(now), limit=self._limit))
        except STORAGE_ERRORS:
            return Unavailable()
        if runs is None:
            return LimitReached(retry_after_s=seconds_until_rollover(now))
        return Reserved(runs=runs)

    async def runs_today(self, now: datetime) -> int | None:
        """Today's count, or None when it cannot be read. Never reserves."""
        try:
            return await self._db.run(partial(_count, day=utc_day(now)))
        except STORAGE_ERRORS:
            return None


def _count(conn: sqlite3.Connection, day: str) -> int:
    row = conn.execute("SELECT runs FROM quota WHERE utc_day = ?", (day,)).fetchone()
    if row is None:
        return 0
    runs: int = row[0]
    return runs
