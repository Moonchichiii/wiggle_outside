"""The night rule for family searches (TC-011 round 2): lock, or plan for the morning.

Pure: local wall time at the searched place decides. Between 00:00 and 04:30 local the
adventures wait till morning (the night lock). At any other time outside daylight (after
sunset and before midnight, or from 04:30 until sunrise) the app plans ahead for the
next morning instead of saying no. Kids are still never sent out after dark: the
daylight rule itself is `core.weather.daylight_outcome` and is unchanged.
"""

from datetime import UTC, datetime, time, timedelta, tzinfo
from typing import TYPE_CHECKING, Final, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.weather import daylight_outcome

if TYPE_CHECKING:
    from wiggle_outside.core.answers import OutingWindow

# The morning window starts at 09:00 local time at the searched place.
MORNING_START: Final = time(9, 0)
# The lock: from local midnight up to, not including, 04:30.
LOCK_FROM: Final = time(0, 0)
LOCK_UNTIL: Final = time(4, 30)

type NightOutcome = Literal["daylight", "too_short", "lock", "plan_ahead"]


def zone(tz: str) -> tzinfo:
    """Resolve an IANA name, falling back to UTC for one the system does not know."""
    try:
        return ZoneInfo(tz)
    except ZoneInfoNotFoundError, ValueError:
        return UTC


def is_locked(moment: datetime, tz: str) -> bool:
    """Report whether `moment` falls in the lock, by local wall time at the place."""
    local = moment.astimezone(zone(tz)).timetz().replace(tzinfo=None)
    return LOCK_FROM <= local < LOCK_UNTIL


def next_morning(moment: datetime, tz: str) -> datetime:
    """Return the next 09:00 local at the place after `moment`, as an aware UTC moment.

    Before 09:00 local this is the coming morning (the one a parent up at 04:45 means);
    from 09:00 on it is the next local day. Daylight-saving changes are handled by
    building the wall time in the zone, so the result is 09:00 on the clock either way.
    """
    tzinfo_ = zone(tz)
    local = moment.astimezone(tzinfo_)
    candidate = datetime.combine(local.date(), MORNING_START, tzinfo=tzinfo_)
    if candidate <= local:
        candidate = datetime.combine(
            local.date() + timedelta(days=1), MORNING_START, tzinfo=tzinfo_
        )
    return candidate.astimezone(UTC)


def tomorrow_morning(moment: datetime, tz: str) -> datetime:
    """Return 09:00 local on the next local day at the place, as an aware UTC moment.

    This is the explicit "Tomorrow morning" choice: always the next calendar day there,
    whatever the time now.
    """
    tzinfo_ = zone(tz)
    local = moment.astimezone(tzinfo_)
    return datetime.combine(
        local.date() + timedelta(days=1), MORNING_START, tzinfo=tzinfo_
    ).astimezone(UTC)


def night_outcome(
    window: OutingWindow, sunrise: datetime, sunset: datetime, tz: str
) -> NightOutcome:
    """Classify a family window: daylight, too short, the lock, or plan for the morning."""
    blocked = daylight_outcome(window, sunrise, sunset)
    if blocked is None:
        return "daylight"
    if blocked is ErrorCode.DAYLIGHT_TOO_SHORT:
        return "too_short"
    return "lock" if is_locked(window.start, tz) else "plan_ahead"
