"""A family search after dark is planned for the next morning (TC-011 round 2).

After sunset and before midnight, or from 04:30 until sunrise, the run keeps the answers
and plans 09:00 local at the place, the same duration, with a second forecast for that
window so its own date's sun times decide. Between 00:00 and 04:30 the night page stays.
Driven through the real workflow with fake ports, in two timezones including the
Pacific, where the evening and the next morning share one UTC date.
"""

from datetime import UTC, datetime, timedelta
from typing import Final
from zoneinfo import ZoneInfo

import pytest
from planner_support import ANSWERS, BUDGETS, SOLO, FakeWeather, Rig, rig, window_for

from wiggle_outside.core.errors import ErrorCode, NoticeId
from wiggle_outside.core.night import next_morning
from wiggle_outside.core.result import Ok
from wiggle_outside.core.types import Answers, JobState, PlanResult
from wiggle_outside.planner.plan_outing import plan_outing

ZONES: Final = ("Europe/Stockholm", "Pacific/Auckland")
DAY: Final = (2026, 10, 11)
HOUR: Final = timedelta(hours=1)


def local(tz: str, hour: int, minute: int, day_offset: int = 0) -> datetime:
    y, m, d = DAY
    return datetime(y, m, d, hour, minute, tzinfo=ZoneInfo(tz)) + timedelta(days=day_offset)


def searching_at(r: Rig, moment: datetime, *, morning_sunrise_h: int = 7) -> datetime:
    """Put the clock at a local moment and give the fake both forecasts the run may ask for.

    The first answer is the forecast for now (today's sun times); the queued one is what
    the adapter would return for a window starting the next morning there (that date's
    sun times, `morning_sunrise_h`). Returns the expected morning start, in UTC.
    """
    tz = getattr(moment.tzinfo, "key", "UTC")
    wall = moment.astimezone(UTC)
    r.clock.wall = wall
    morning = next_morning(wall, tz)
    r.weather = FakeWeather(
        outcome=Ok(window_for(moment, fetched_at=wall - timedelta(seconds=5))),
        queued=[
            Ok(
                window_for(
                    morning.astimezone(ZoneInfo(tz)),
                    sunrise_h=morning_sunrise_h,
                    fetched_at=wall - timedelta(seconds=5),
                )
            )
        ],
    )
    return morning


async def plan(r: Rig, answers: Answers = ANSWERS) -> PlanResult:
    planned = await plan_outing(r.ports, r.run(answers), BUDGETS)
    assert isinstance(planned, PlanResult)
    return planned


# --- Planned ahead: after sunset until midnight, and from 04:30 until sunrise --------------


@pytest.mark.asyncio
@pytest.mark.parametrize("tz", ZONES)
@pytest.mark.parametrize(
    ("hour", "minute", "day_offset", "morning_offset"),
    [
        (21, 0, 0, 1),  # evening: tomorrow 09:00
        (23, 59, 0, 1),
        (4, 31, 1, 1),  # just after the lock: 09:00 the same local day
        (6, 30, 1, 1),  # before sunrise (07:00)
    ],
)
async def test_a_dark_family_search_is_planned_for_the_next_morning(
    tz: str, hour: int, minute: int, day_offset: int, morning_offset: int
) -> None:
    r = rig()
    morning = searching_at(r, local(tz, hour, minute, day_offset))
    assert morning == local(tz, 9, 0, morning_offset).astimezone(UTC)

    result = await plan(r)

    assert result.error is None, result.error
    assert result.state is JobState.FALLBACK
    assert result.notices[0] is NoticeId.PLANNED_FOR_MORNING
    assert result.ideas
    assert result.planned_start == morning
    assert result.planned_end == morning + HOUR
    # The second forecast is for the morning window itself, so the adapter takes that
    # date's sunrise and sunset; the result's weather is that window's.
    assert len(r.weather.calls) == 2
    assert r.weather.calls[1][1] == morning
    assert r.weather.calls[1][2] == morning + HOUR
    assert result.weather is not None
    assert result.weather.window_start == morning
    # Never valid past the start of its window.
    assert result.valid_until <= morning
    assert result.retain_until > result.valid_until


@pytest.mark.asyncio
@pytest.mark.parametrize("tz", ZONES)
async def test_tomorrows_daylight_is_checked_against_tomorrows_sun_times(tz: str) -> None:
    # Today's forecast says the sun rose at 07:00; the forecast for the morning window
    # says it will not be up until 10:00 there. The morning window is judged by the
    # latter, so the family gets the night page rather than a dark 09:00.
    r = rig()
    searching_at(r, local(tz, 21, 0), morning_sunrise_h=10)

    result = await plan(r)

    assert result.error is ErrorCode.DAYLIGHT_NIGHT
    assert result.ideas == ()
    assert NoticeId.PLANNED_FOR_MORNING not in result.notices
    assert len(r.weather.calls) == 2


# --- The lock: 00:00 to 04:30 local keeps the night page -----------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("tz", ZONES)
@pytest.mark.parametrize(("hour", "minute"), [(0, 1), (4, 29)])
async def test_in_the_lock_the_night_page_stays(tz: str, hour: int, minute: int) -> None:
    r = rig()
    searching_at(r, local(tz, hour, minute, 1))

    result = await plan(r)

    assert result.error is ErrorCode.DAYLIGHT_NIGHT
    assert result.ideas == ()
    assert result.weather is None
    assert NoticeId.PLANNED_FOR_MORNING not in result.notices
    assert len(r.weather.calls) == 1  # no second forecast is fetched for a locked search


@pytest.mark.asyncio
async def test_in_the_lock_the_night_page_comes_before_the_weather_rules() -> None:
    r = rig()
    moment = local("Europe/Stockholm", 0, 1, 1)
    searching_at(r, moment)
    r.weather.outcome = Ok(window_for(moment, code=95, fetched_at=r.clock.wall))

    result = await plan(r)

    assert result.error is ErrorCode.DAYLIGHT_NIGHT


# --- Solo is unchanged -----------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("tz", ZONES)
async def test_a_solo_search_after_dark_is_planned_for_now_as_before(tz: str) -> None:
    r = rig()
    moment = local(tz, 21, 0)
    searching_at(r, moment)

    result = await plan(r, SOLO)

    assert result.error is not ErrorCode.DAYLIGHT_NIGHT
    assert NoticeId.PLANNED_FOR_MORNING not in result.notices
    assert result.planned_start == moment.astimezone(UTC)
    assert len(r.weather.calls) == 1
