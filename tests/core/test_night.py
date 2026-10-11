"""The night rule (TC-011 round 2): the 00:00-04:30 lock, and the morning window.

Wall times are built in the place's zone and converted to UTC, so each case is the
local time a parent sees, across timezones and across midnight.
"""

from datetime import UTC, datetime, timedelta
from typing import Final
from zoneinfo import ZoneInfo

import pytest

from wiggle_outside.core.answers import OutingWindow
from wiggle_outside.core.night import (
    is_locked,
    next_morning,
    night_outcome,
    tomorrow_morning,
)

ZONES: Final = ("Europe/Stockholm", "America/New_York", "Pacific/Auckland", "Asia/Kolkata")
# 11 October 2026: a local date, with the sun up roughly 07:00-18:00 at every place.
DAY: Final = (2026, 10, 11)
SUNRISE_H: Final = 7
SUNSET_H: Final = 18


def local(tz: str, hour: int, minute: int, day_offset: int = 0) -> datetime:
    y, m, d = DAY
    return datetime(y, m, d, hour, minute, tzinfo=ZoneInfo(tz)) + timedelta(days=day_offset)


def sun(tz: str, day_offset: int = 0) -> tuple[datetime, datetime]:
    return (
        local(tz, SUNRISE_H, 0, day_offset).astimezone(UTC),
        local(tz, SUNSET_H, 0, day_offset).astimezone(UTC),
    )


def window(start: datetime) -> OutingWindow:
    return OutingWindow(
        start=start.astimezone(UTC), end=(start + timedelta(hours=1)).astimezone(UTC)
    )


# --- The lock, by local wall time ---------------------------------------------------------


@pytest.mark.parametrize("tz", ZONES)
@pytest.mark.parametrize(
    ("hour", "minute", "locked"),
    [
        (21, 0, False),
        (23, 59, False),
        (0, 0, True),
        (0, 1, True),
        (4, 29, True),
        (4, 30, False),
        (4, 31, False),
        (6, 30, False),  # before sunrise, after the lock
    ],
)
def test_the_lock_runs_from_midnight_to_half_past_four_local(
    tz: str,
    hour: int,
    minute: int,
    locked: bool,  # noqa: FBT001  a parametrised expectation
) -> None:
    assert is_locked(local(tz, hour, minute), tz) is locked


def test_the_lock_follows_the_place_not_the_server() -> None:
    # 00:30 in Auckland is early afternoon in Stockholm the day before.
    moment = local("Pacific/Auckland", 0, 30)
    assert is_locked(moment, "Pacific/Auckland")
    assert not is_locked(moment, "Europe/Stockholm")


# --- The night outcome for a family window -------------------------------------------------


@pytest.mark.parametrize("tz", ZONES)
@pytest.mark.parametrize(
    ("hour", "minute", "day_offset", "expected"),
    [
        (21, 0, 0, "plan_ahead"),  # after sunset, before midnight
        (23, 59, 0, "plan_ahead"),
        (0, 1, 1, "lock"),  # the next local day: still night, now locked
        (4, 29, 1, "lock"),
        (4, 31, 1, "plan_ahead"),  # after the lock, before sunrise
        (6, 30, 1, "plan_ahead"),  # just before sunrise
        (12, 0, 0, "daylight"),
        (17, 30, 0, "too_short"),  # the hour would end after sunset
    ],
)
def test_after_dark_the_family_is_locked_or_planned_ahead(
    tz: str, hour: int, minute: int, day_offset: int, expected: str
) -> None:
    sunrise, sunset = sun(tz, day_offset)
    assert (
        night_outcome(window(local(tz, hour, minute, day_offset)), sunrise, sunset, tz) == expected
    )


# --- The morning window ---------------------------------------------------------------------


@pytest.mark.parametrize("tz", ZONES)
@pytest.mark.parametrize(
    ("hour", "minute", "day_offset", "morning_offset"),
    [
        (21, 0, 0, 1),  # evening: tomorrow 09:00
        (23, 59, 0, 1),
        (0, 1, 1, 1),  # just past midnight: 09:00 the same local day
        (4, 31, 1, 1),
        (8, 59, 1, 1),
        (9, 0, 1, 2),  # at 09:00 the next one is tomorrow's
    ],
)
def test_the_next_morning_is_nine_local_at_the_place(
    tz: str, hour: int, minute: int, day_offset: int, morning_offset: int
) -> None:
    start = next_morning(local(tz, hour, minute, day_offset), tz)

    assert start == local(tz, 9, 0, morning_offset).astimezone(UTC)
    assert start.tzinfo is UTC
    assert start.astimezone(ZoneInfo(tz)).strftime("%H:%M") == "09:00"


@pytest.mark.parametrize("tz", ZONES)
@pytest.mark.parametrize(("hour", "minute"), [(0, 1), (4, 31), (12, 0), (23, 59)])
def test_tomorrow_morning_is_always_the_next_local_day(tz: str, hour: int, minute: int) -> None:
    start = tomorrow_morning(local(tz, hour, minute), tz)

    assert start == local(tz, 9, 0, 1).astimezone(UTC)


def test_the_morning_window_crosses_a_daylight_saving_change_on_the_clock() -> None:
    # Stockholm leaves summer time on 25 October 2026 at 03:00; 09:00 stays 09:00 local.
    before = datetime(2026, 10, 24, 21, 0, tzinfo=ZoneInfo("Europe/Stockholm"))
    start = next_morning(before, "Europe/Stockholm")

    assert start.astimezone(ZoneInfo("Europe/Stockholm")).strftime("%Y-%m-%d %H:%M") == (
        "2026-10-25 09:00"
    )
    assert start == datetime(2026, 10, 25, 8, 0, tzinfo=UTC)  # UTC+1 after the change


def test_an_unknown_zone_falls_back_to_utc() -> None:
    moment = datetime(2026, 10, 11, 21, 0, tzinfo=UTC)
    assert next_morning(moment, "Mars/Olympus") == datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
    assert not is_locked(moment, "Mars/Olympus")
