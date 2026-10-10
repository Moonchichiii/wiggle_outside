"""Open-Meteo adapter: the section 1 request, unit checks, and outcomes as values.

No test opens a socket: respx answers at the transport layer (PLAN section 8).

`open_meteo_boundary.json` has the shape of a real forecast — key order, the exact unit
strings, and `timeformat=unixtime` with `timezone=auto`, where an hourly time is a true
UTC instant and a daily entry is the UTC instant of local midnight — captured from
api.open-meteo.com on 10 October 2026. The readings are not a recording: 08:00-11:00 UTC
are the WALKTHROUGH fixture table, and the rest of the two days is hand-built plausible
filler. The last test re-derives the BACKEND-CONTRACT section 1 worked example from the
fixture through `core.weather`, so the file and the contract cannot drift apart.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import httpx
import pytest
import respx

from wiggle_outside.core.answers import OutingWindow
from wiggle_outside.core.result import (
    Malformed,
    Ok,
    Outcome,
    QuotaOrUnavailable,
    TransportFailure,
)
from wiggle_outside.core.types import Coordinates, WeatherWindow
from wiggle_outside.core.weather import used_samples
from wiggle_outside.integrations import open_meteo
from wiggle_outside.planner.ports import ProviderName, WeatherProvider
from wiggle_outside.settings import Settings

FIXTURES: Final = Path(__file__).resolve().parents[1] / "fixtures" / "providers"
BOUNDARY: Final = "open_meteo_boundary.json"
HOST: Final = "open-meteo.test"
PATH: Final = "/v1/forecast"
BASE_URL: Final = f"https://{HOST}{PATH}"
NOW: Final = 1_000.0
DEADLINE: Final = NOW + 10.0
AT: Final = Coordinates(lat=60.5, lon=17.2)
SLOW_S: Final = 30.0
RETRY_AFTER_S: Final = 75.0
OVERSIZED: Final = open_meteo.MAX_RESPONSE_BYTES + 1

# The walkthrough outing: 10:31-11:31 Europe/Stockholm = 08:31-09:31 UTC.
DAY: Final = (2026, 10, 10)
START: Final = datetime(*DAY, 8, 31, tzinfo=UTC)
END: Final = datetime(*DAY, 9, 31, tzinfo=UTC)
FETCHED_AT: Final = datetime(*DAY, 8, 31, 1, tzinfo=UTC)
SUNRISE: Final = datetime(*DAY, 5, 21, tzinfo=UTC)
SUNSET: Final = datetime(*DAY, 16, 20, tzinfo=UTC)
FORECAST_HOURS: Final = 48
WINDOW_HOURS: Final = tuple(datetime(*DAY, hour, tzinfo=UTC) for hour in (8, 9, 10, 11))
WALKTHROUGH_APPARENT: Final = (10.6, 11.4, 11.9, 12.2)
WALKTHROUGH_PRECIPITATION_MM: Final = (0.0, 0.0, 0.1, 0.4)
WALKTHROUGH_PROBABILITY: Final = (20, 30, 40, 50)
WALKTHROUGH_CODES: Final = (3, 3, 80, 61)
WALKTHROUGH_WIND: Final = (12.0, 14.0, 18.0, 20.0)


@dataclass(frozen=True, slots=True)
class _Answered:
    outcome: Outcome[WeatherWindow]
    route: respx.Route


def _payload(name: str = BOUNDARY) -> dict[str, object]:
    decoded = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):  # pragma: no cover  the fixture is an object
        raise TypeError(name)
    return decoded


def _clock() -> float:
    return NOW


def _at_receipt() -> datetime:
    return FETCHED_AT


def _weather(
    client: httpx.AsyncClient,
    monotonic: Callable[[], float] = _clock,
) -> open_meteo.OpenMeteoWeather:
    return open_meteo.OpenMeteoWeather(
        client=client,
        base_url=BASE_URL,
        now=_at_receipt,
        monotonic=monotonic,
    )


def _forecast(router: respx.MockRouter) -> respx.Route:
    return router.route(method="GET", host=HOST, path=PATH)


async def _window(
    reply: httpx.Response | Exception,
    *,
    start: datetime = START,
    end: datetime = END,
) -> _Answered:
    """Answer one forecast with `reply`, and report the outcome beside the route."""
    with respx.mock(assert_all_called=False) as router:
        route = _forecast(router)
        if isinstance(reply, Exception):
            route.mock(side_effect=reply)
        else:
            route.mock(return_value=reply)
        async with httpx.AsyncClient() as client:
            outcome = await _weather(client).window(AT, start, end, DEADLINE)
    return _Answered(outcome=outcome, route=route)


def _index_of(window: WeatherWindow, moment: datetime) -> int:
    return window.times.index(moment)


def _readings(window: WeatherWindow, array: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(array[_index_of(window, moment)] for moment in WINDOW_HOURS)


@pytest.mark.asyncio
async def test_the_boundary_fixture_parses_into_the_window() -> None:
    answered = await _window(httpx.Response(200, json=_payload()))
    assert answered.route.call_count == 1  # exactly one HTTP attempt per call
    assert isinstance(answered.outcome, Ok)
    window = answered.outcome.value
    assert window.tz == "Europe/Stockholm"
    assert window.fetched_at == FETCHED_AT  # our clock at receipt, not a provider time
    assert len(window.times) == FORECAST_HOURS
    assert window.start == window.times[0]
    assert window.end == window.times[-1]
    assert window.sunrise == SUNRISE
    assert window.sunset == SUNSET


@pytest.mark.asyncio
async def test_the_hourly_arrays_arrive_as_received() -> None:
    answered = await _window(httpx.Response(200, json=_payload()))
    assert isinstance(answered.outcome, Ok)
    window = answered.outcome.value
    assert _readings(window, window.apparent_temp_c) == WALKTHROUGH_APPARENT
    assert _readings(window, window.wind_kmh) == WALKTHROUGH_WIND
    # CC-001: millimetres travel with the window, because two rules need them.
    assert _readings(window, window.precipitation_mm) == WALKTHROUGH_PRECIPITATION_MM
    probability = tuple(window.precip_probability[_index_of(window, m)] for m in WINDOW_HOURS)
    codes = tuple(window.weather_code[_index_of(window, m)] for m in WINDOW_HOURS)
    assert probability == WALKTHROUGH_PROBABILITY
    assert codes == WALKTHROUGH_CODES


@pytest.mark.asyncio
async def test_the_request_asks_for_exactly_the_contract_variables() -> None:
    answered = await _window(httpx.Response(200, json=_payload()))
    params = answered.route.calls[0].request.url.params
    assert params["hourly"].split(",") == [
        "temperature_2m",
        "apparent_temperature",
        "precipitation_probability",
        "precipitation",
        "wind_speed_10m",
        "weather_code",
    ]
    assert params["daily"].split(",") == ["sunrise", "sunset"]
    assert params["timeformat"] == "unixtime"
    assert params["temperature_unit"] == "celsius"
    assert params["wind_speed_unit"] == "kmh"
    assert params["precipitation_unit"] == "mm"
    # `timezone=auto` is what makes `WeatherWindow.tz` the place's IANA name.
    assert params["timezone"] == "auto"
    assert (params["latitude"], params["longitude"]) == ("60.50", "17.20")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("deadline", "expected"),
    [
        pytest.param(NOW + 10.0, open_meteo.STAGE_BUDGET_S, id="the-stage-budget-is-smaller"),
        pytest.param(NOW + 1.5, 1.5, id="the-remaining-deadline-is-smaller"),
    ],
)
async def test_the_attempt_gets_min_of_the_stage_budget_and_what_is_left(
    deadline: float, expected: float
) -> None:
    with respx.mock(assert_all_called=False) as router:
        route = _forecast(router).mock(return_value=httpx.Response(200, json=_payload()))
        async with httpx.AsyncClient() as client:
            await _weather(client).window(AT, START, END, deadline)
    timeout = route.calls[0].request.extensions["timeout"]
    assert timeout["read"] == pytest.approx(expected)
    assert timeout["connect"] == pytest.approx(min(expected, open_meteo.CONNECT_BUDGET_S))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("group", "name", "value"),
    [
        pytest.param("hourly_units", "temperature_2m", "°F", id="fahrenheit"),
        pytest.param("hourly_units", "wind_speed_10m", "mph", id="miles-per-hour"),
        pytest.param("hourly_units", "precipitation", "inch", id="inches"),
        pytest.param("hourly_units", "time", "iso8601", id="iso-times"),
        pytest.param("daily_units", "sunrise", "iso8601", id="iso-sunrise"),
    ],
)
async def test_a_unit_that_does_not_match_rejects_the_forecast(
    group: str, name: str, value: str
) -> None:
    payload = _payload()
    units = payload[group]
    assert isinstance(units, dict)
    units[name] = value
    answered = await _window(httpx.Response(200, json=payload))
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("group", "name"),
    [
        pytest.param("hourly_units", "precipitation", id="missing-hourly-unit"),
        pytest.param("daily_units", "sunset", id="missing-daily-unit"),
    ],
)
async def test_a_missing_unit_fails_closed(group: str, name: str) -> None:
    payload = _payload()
    units = payload[group]
    assert isinstance(units, dict)
    del units[name]
    answered = await _window(httpx.Response(200, json=payload))
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
async def test_a_whole_unit_block_that_is_absent_fails_closed() -> None:
    payload = _payload()
    del payload["hourly_units"]
    answered = await _window(httpx.Response(200, json=payload))
    assert isinstance(answered.outcome, Malformed)


def _hourly(payload: dict[str, object]) -> dict[str, object]:
    hourly = payload["hourly"]
    assert isinstance(hourly, dict)
    return hourly


@pytest.mark.asyncio
async def test_an_array_of_the_wrong_length_fails_closed() -> None:
    payload = _payload()
    hourly = _hourly(payload)
    precipitation = hourly["precipitation"]
    assert isinstance(precipitation, list)
    hourly["precipitation"] = precipitation[:-1]
    answered = await _window(httpx.Response(200, json=payload))
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name",
    ["temperature_2m", "apparent_temperature", "precipitation", "wind_speed_10m"],
)
async def test_a_null_reading_fails_closed(name: str) -> None:
    payload = _payload()
    hourly = _hourly(payload)
    array = hourly[name]
    assert isinstance(array, list)
    array[10] = None
    answered = await _window(httpx.Response(200, json=payload))
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
async def test_a_non_finite_reading_fails_closed() -> None:
    """Python's JSON reader accepts `NaN`, so the adapter has to refuse it itself."""
    payload = _payload()
    hourly = _hourly(payload)
    array = hourly["precipitation"]
    assert isinstance(array, list)
    array[10] = float("nan")
    raw = json.dumps(payload)
    assert "NaN" in raw
    answered = await _window(httpx.Response(200, content=raw.encode()))
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
async def test_empty_hourly_arrays_are_malformed_not_empty() -> None:
    """Section 1 requires the arrays, so nothing to judge fails closed rather than Empty."""
    payload = _payload()
    hourly = _hourly(payload)
    for name in hourly:
        hourly[name] = []
    answered = await _window(httpx.Response(200, json=payload))
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("start", "end"),
    [
        pytest.param(
            datetime(2026, 10, 9, 20, tzinfo=UTC),
            datetime(2026, 10, 9, 21, tzinfo=UTC),
            id="before-the-arrays",
        ),
        pytest.param(
            datetime(2026, 10, 11, 20, tzinfo=UTC),
            datetime(2026, 10, 11, 23, tzinfo=UTC),
            id="past-the-arrays",
        ),
    ],
)
async def test_a_window_the_forecast_does_not_cover_fails_closed(
    start: datetime, end: datetime
) -> None:
    answered = await _window(httpx.Response(200, json=_payload()), start=start, end=end)
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
async def test_a_day_without_its_sunrise_fails_closed() -> None:
    payload = _payload()
    daily = payload["daily"]
    assert isinstance(daily, dict)
    sunrise = daily["sunrise"]
    assert isinstance(sunrise, list)
    sunrise[0] = None  # polar day and night report null here
    answered = await _window(httpx.Response(200, json=payload))
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
async def test_a_local_date_the_daily_block_does_not_carry_fails_closed() -> None:
    payload = _payload()
    daily = payload["daily"]
    assert isinstance(daily, dict)
    for name in ("time", "sunrise", "sunset"):
        array = daily[name]
        assert isinstance(array, list)
        daily[name] = array[1:]  # only 11 October is left
    answered = await _window(httpx.Response(200, json=payload))
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
async def test_a_sunset_before_its_sunrise_fails_closed() -> None:
    payload = _payload()
    daily = payload["daily"]
    assert isinstance(daily, dict)
    daily["sunrise"], daily["sunset"] = daily["sunset"], daily["sunrise"]
    answered = await _window(httpx.Response(200, json=payload))
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"not json at all", id="not-json"),
        pytest.param(b"[]", id="an-array-not-an-object"),
        pytest.param(b'{"error": true, "reason": "No data"}', id="an-error-object"),
    ],
)
async def test_a_body_we_cannot_use_is_malformed(body: bytes) -> None:
    answered = await _window(httpx.Response(200, content=body))
    assert isinstance(answered.outcome, Malformed)
    assert answered.route.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(httpx.ConnectError("refused"), id="connect"),
        pytest.param(httpx.ReadTimeout("too slow"), id="read-timeout"),
    ],
)
async def test_a_transport_failure_is_the_only_retryable_outcome(failure: Exception) -> None:
    answered = await _window(failure)
    assert isinstance(answered.outcome, TransportFailure)
    # The adapter never retries: the one permitted retry belongs to WP4's wrapper.
    assert answered.route.call_count == 1


@pytest.mark.asyncio
async def test_the_provider_saying_no_carries_its_delay() -> None:
    answered = await _window(httpx.Response(429, headers={"Retry-After": "75"}, json={}))
    assert answered.outcome == QuotaOrUnavailable(retry_after_s=RETRY_AFTER_S)


@pytest.mark.asyncio
async def test_a_server_error_is_unavailable_without_a_delay() -> None:
    answered = await _window(httpx.Response(502, text="bad gateway"))
    assert answered.outcome == QuotaOrUnavailable(retry_after_s=None)


@pytest.mark.asyncio
async def test_an_oversized_body_is_a_transport_failure() -> None:
    body = b'{"filler": "' + b"x" * OVERSIZED + b'"}'
    answered = await _window(httpx.Response(200, content=body))
    assert isinstance(answered.outcome, TransportFailure)
    assert answered.route.call_count == 1


@pytest.mark.asyncio
async def test_a_redirect_is_never_followed() -> None:
    answered = await _window(
        httpx.Response(301, headers={"Location": "https://elsewhere.test/v1/forecast"})
    )
    assert answered.route.call_count == 1
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
async def test_cancellation_is_never_converted_to_an_outcome() -> None:
    started = asyncio.Event()

    async def never_answer(_request: httpx.Request) -> httpx.Response:
        started.set()
        await asyncio.sleep(SLOW_S)
        return httpx.Response(200, json=_payload())

    with respx.mock(assert_all_called=False) as router:
        _forecast(router).mock(side_effect=never_answer)
        async with httpx.AsyncClient() as client:
            attempt = asyncio.create_task(_weather(client).window(AT, START, END, DEADLINE))
            await started.wait()
            attempt.cancel()
            with pytest.raises(asyncio.CancelledError):
                await attempt


@pytest.mark.asyncio
async def test_a_passed_deadline_spends_no_attempt() -> None:
    with respx.mock(assert_all_called=False) as router:
        route = _forecast(router).mock(return_value=httpx.Response(200, json=_payload()))
        async with httpx.AsyncClient() as client:
            outcome = await _weather(client).window(AT, START, END, NOW - 1.0)
    assert isinstance(outcome, TransportFailure)
    assert route.call_count == 0


@pytest.mark.asyncio
async def test_the_endpoint_comes_from_settings_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WO_OPEN_METEO_URL", "https://weather.invalid/v1/forecast")
    async with httpx.AsyncClient() as client:
        provider = open_meteo.from_settings(client, Settings.from_env())
    assert provider.base_url == "https://weather.invalid/v1/forecast"
    assert provider.provider is ProviderName.OPEN_METEO


def test_the_adapter_declares_the_weather_port() -> None:
    """Explicit inheritance, so the mypy gate checks `window` against the port."""
    assert WeatherProvider in open_meteo.OpenMeteoWeather.__mro__


@pytest.mark.asyncio
async def test_the_fixture_reproduces_the_contract_worked_example() -> None:
    """BACKEND-CONTRACT section 1: 08:31-09:31 UTC uses two intervals and three instants."""
    answered = await _window(httpx.Response(200, json=_payload()))
    assert isinstance(answered.outcome, Ok)
    samples = used_samples(answered.outcome.value, OutingWindow(start=START, end=END))
    assert samples is not None
    assert [interval.ends_at for interval in samples.intervals] == [
        datetime(*DAY, 9, tzinfo=UTC),
        datetime(*DAY, 10, tzinfo=UTC),
    ]
    assert [instant.at for instant in samples.instants] == [
        datetime(*DAY, 8, tzinfo=UTC),
        datetime(*DAY, 9, tzinfo=UTC),
        datetime(*DAY, 10, tzinfo=UTC),
    ]
    assert [interval.precipitation_mm for interval in samples.intervals] == [0.0, 0.1]
    assert [interval.probability for interval in samples.intervals] == [30, 40]


@pytest.mark.asyncio
async def test_a_window_ending_on_the_hour_uses_one_interval() -> None:
    """The second case in section 1: `[08:00, 09:00]` uses the 09:00 sample only."""
    answered = await _window(
        httpx.Response(200, json=_payload()),
        start=datetime(*DAY, 8, tzinfo=UTC),
        end=datetime(*DAY, 9, tzinfo=UTC),
    )
    assert isinstance(answered.outcome, Ok)
    samples = used_samples(
        answered.outcome.value,
        OutingWindow(start=datetime(*DAY, 8, tzinfo=UTC), end=datetime(*DAY, 9, tzinfo=UTC)),
    )
    assert samples is not None
    assert [interval.ends_at for interval in samples.intervals] == [datetime(*DAY, 9, tzinfo=UTC)]
    assert [instant.at for instant in samples.instants] == [
        datetime(*DAY, 8, tzinfo=UTC),
        datetime(*DAY, 9, tzinfo=UTC),
    ]


@pytest.mark.asyncio
async def test_the_daily_entry_is_matched_by_local_date_not_utc_date() -> None:
    """A daily entry is local midnight: 2026-10-09T22:00Z *is* 10 October in Stockholm."""
    payload = _payload()
    daily = payload["daily"]
    assert isinstance(daily, dict)
    first = daily["time"]
    assert isinstance(first, list)
    assert datetime.fromtimestamp(first[0], UTC) == datetime(2026, 10, 9, 22, tzinfo=UTC)
    offset = payload["utc_offset_seconds"]
    assert isinstance(offset, int)
    assert (datetime.fromtimestamp(first[0], UTC) + timedelta(seconds=offset)).date() == datetime(
        *DAY, tzinfo=UTC
    ).date()
    answered = await _window(httpx.Response(200, json=payload))
    assert isinstance(answered.outcome, Ok)
    assert answered.outcome.value.sunrise == SUNRISE
