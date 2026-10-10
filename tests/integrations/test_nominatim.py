"""Nominatim adapter: one attempt, five candidates, outcomes as values.

No test opens a socket: respx answers at the transport layer (PLAN section 8).

`nominatim_bergby.json` is a verbatim capture of
`https://nominatim.openstreetmap.org/search?q=Bergby&format=jsonv2&limit=5`, taken on
10 October 2026. `nominatim_bergby_walkthrough.json` is hand-built: it carries the three
labels WALKTHROUGH names, with the chosen candidate at the coordinates the rest of the
repository uses for that journey.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from typing import Final

import httpx
import pytest
import respx

from wiggle_outside.core.result import (
    Empty,
    Malformed,
    Ok,
    Outcome,
    QuotaOrUnavailable,
    TransportFailure,
)
from wiggle_outside.core.types import (
    MAX_CANDIDATES,
    PLACE_TEXT_MAX,
    GeocodeHits,
    TypedPlace,
)
from wiggle_outside.integrations import nominatim
from wiggle_outside.planner.ports import Geocoder, ProviderName
from wiggle_outside.settings import Settings

FIXTURES: Final = Path(__file__).resolve().parents[1] / "fixtures" / "providers"
HOST: Final = "nominatim.test"
BASE_URL: Final = f"https://{HOST}"
CONTACT: Final = "wiggle@example.test"
NOW: Final = 1_000.0
DEADLINE: Final = NOW + 10.0
PLACE: Final = TypedPlace(text="Bergby")
RETRY_AFTER_S: Final = 120.0
OVERSIZED: Final = nominatim.MAX_RESPONSE_BYTES + 1
# Long enough that only cancellation can end the attempt.
SLOW_S: Final = 30.0
WALKTHROUGH_COORDS: Final = (60.5, 17.2)
CAPTURED_COORDS: Final = (60.93, 17.04)


@dataclass(frozen=True, slots=True)
class _Answered:
    outcome: Outcome[GeocodeHits]
    route: respx.Route


def _fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _clock() -> float:
    return NOW


def _geocoder(
    client: httpx.AsyncClient,
    monotonic: Callable[[], float] = _clock,
) -> nominatim.NominatimGeocoder:
    return nominatim.NominatimGeocoder(
        client=client,
        base_url=BASE_URL,
        contact_email=CONTACT,
        monotonic=monotonic,
    )


def _search(router: respx.MockRouter) -> respx.Route:
    """Match the endpoint without pinning the query, so a test can inspect it."""
    return router.route(method="GET", host=HOST, path=nominatim.SEARCH_PATH)


async def _resolve(reply: httpx.Response | Exception) -> _Answered:
    """Answer one search with `reply`, and report the outcome beside the route."""
    with respx.mock(assert_all_called=False) as router:
        route = _search(router)
        if isinstance(reply, Exception):
            route.mock(side_effect=reply)
        else:
            route.mock(return_value=reply)
        async with httpx.AsyncClient() as client:
            outcome = await _geocoder(client).resolve(PLACE, DEADLINE)
    return _Answered(outcome=outcome, route=route)


@pytest.mark.asyncio
async def test_the_captured_search_gives_five_hits() -> None:
    answered = await _resolve(httpx.Response(200, json=_fixture("nominatim_bergby.json")))
    assert answered.route.call_count == 1  # exactly one HTTP attempt per call
    assert isinstance(answered.outcome, Ok)
    hits = answered.outcome.value.hits
    assert len(hits) == MAX_CANDIDATES
    assert hits[0].label == "Bergby, Gävle kommun, Gävleborg County, 817 40, Sweden"
    # jsonv2 sends the coordinates as strings; Coordinates rounds them to 2 dp.
    assert (hits[0].coords.lat, hits[0].coords.lon) == CAPTURED_COORDS


@pytest.mark.asyncio
async def test_the_walkthrough_fixture_gives_its_three_candidates() -> None:
    answered = await _resolve(
        httpx.Response(200, json=_fixture("nominatim_bergby_walkthrough.json"))
    )
    assert isinstance(answered.outcome, Ok)
    hits = answered.outcome.value.hits
    assert [hit.label for hit in hits] == [
        "Bergby, Gävleborg, Sweden",
        "Bergby, Uppsala län, Sweden",
        "Bergby, Åland, Finland",
    ]
    assert (hits[1].coords.lat, hits[1].coords.lon) == WALKTHROUGH_COORDS


@pytest.mark.asyncio
async def test_the_request_is_a_typed_query_with_a_real_contact() -> None:
    answered = await _resolve(httpx.Response(200, json=[]))
    request = answered.route.calls[0].request
    assert request.url.path == nominatim.SEARCH_PATH
    assert request.url.params["q"] == PLACE.text
    assert request.url.params["format"] == nominatim.RESULT_FORMAT
    assert request.url.params["limit"] == str(MAX_CANDIDATES)
    assert request.url.params["accept-language"] == nominatim.ACCEPT_LANGUAGE
    assert request.headers["user-agent"] == f"WiggleOutside/0.1 ({CONTACT})"


@pytest.mark.asyncio
async def test_more_entries_than_we_allow_are_truncated() -> None:
    entry = {"lat": "60.5", "lon": "17.2", "display_name": "Somewhere, Sweden"}
    answered = await _resolve(httpx.Response(200, json=[entry] * 9))
    assert isinstance(answered.outcome, Ok)
    assert len(answered.outcome.value.hits) == MAX_CANDIDATES


@pytest.mark.asyncio
async def test_an_empty_array_is_empty_not_a_failure() -> None:
    answered = await _resolve(httpx.Response(200, json=[]))
    assert isinstance(answered.outcome, Empty)
    assert answered.route.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"not json at all", id="not-json"),
        pytest.param(b'{"hits": []}', id="an-object-not-an-array"),
        pytest.param(b'[{"display_name": "Nowhere"}]', id="no-coordinates"),
        pytest.param(b'[{"lat": "60.5", "lon": "17.2"}]', id="no-label"),
        pytest.param(b'[{"lat": "911.0", "lon": "17.2", "display_name": "x"}]', id="out-of-range"),
        pytest.param(b'[{"lat": "sixty", "lon": "17.2", "display_name": "x"}]', id="not-a-number"),
        pytest.param(b'[{"lat": true, "lon": "17.2", "display_name": "x"}]', id="a-boolean"),
    ],
)
async def test_a_body_we_cannot_use_is_malformed(body: bytes) -> None:
    answered = await _resolve(httpx.Response(200, content=body))
    assert isinstance(answered.outcome, Malformed)
    assert answered.route.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(httpx.ConnectError("refused"), id="connect"),
        pytest.param(httpx.ReadTimeout("too slow"), id="read-timeout"),
        pytest.param(httpx.ConnectTimeout("too slow"), id="connect-timeout"),
    ],
)
async def test_a_transport_failure_is_the_only_retryable_outcome(failure: Exception) -> None:
    answered = await _resolve(failure)
    assert isinstance(answered.outcome, TransportFailure)
    # The adapter never retries: the one permitted retry belongs to WP4's wrapper.
    assert answered.route.call_count == 1


@pytest.mark.asyncio
async def test_too_many_requests_carries_the_retry_after_seconds() -> None:
    answered = await _resolve(httpx.Response(429, headers={"Retry-After": "120"}, json={}))
    assert answered.outcome == QuotaOrUnavailable(retry_after_s=RETRY_AFTER_S)


@pytest.mark.asyncio
async def test_retry_after_may_be_an_http_date() -> None:
    when = datetime.now(UTC) + timedelta(seconds=90)
    answered = await _resolve(
        httpx.Response(503, headers={"Retry-After": format_datetime(when, usegmt=True)}, json={})
    )
    assert isinstance(answered.outcome, QuotaOrUnavailable)
    assert answered.outcome.retry_after_s is not None
    assert 60.0 <= answered.outcome.retry_after_s <= 90.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply",
    [
        pytest.param(httpx.Response(503, json={}), id="no-header"),
        pytest.param(httpx.Response(500, headers={"Retry-After": "soon"}, json={}), id="garbage"),
    ],
)
async def test_an_unavailable_provider_without_a_usable_delay_reports_none(
    reply: httpx.Response,
) -> None:
    answered = await _resolve(reply)
    assert answered.outcome == QuotaOrUnavailable(retry_after_s=None)


@pytest.mark.asyncio
async def test_an_oversized_body_is_a_transport_failure() -> None:
    answered = await _resolve(httpx.Response(200, content=b'["' + b"x" * OVERSIZED + b'"]'))
    assert isinstance(answered.outcome, TransportFailure)
    assert answered.route.call_count == 1


@pytest.mark.asyncio
async def test_a_redirect_is_never_followed() -> None:
    answered = await _resolve(
        httpx.Response(302, headers={"Location": "https://elsewhere.test/search"})
    )
    # One attempt, and the redirect target is never fetched.
    assert answered.route.call_count == 1
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
async def test_cancellation_is_never_converted_to_an_outcome() -> None:
    """A cancelled caller raises; it never becomes TransportFailure (CONTRACTS 1)."""
    started = asyncio.Event()

    async def never_answer(_request: httpx.Request) -> httpx.Response:
        started.set()
        await asyncio.sleep(SLOW_S)
        return httpx.Response(200, json=[])

    with respx.mock(assert_all_called=False) as router:
        _search(router).mock(side_effect=never_answer)
        async with httpx.AsyncClient() as client:
            attempt = asyncio.create_task(_geocoder(client).resolve(PLACE, DEADLINE))
            await started.wait()
            attempt.cancel()
            with pytest.raises(asyncio.CancelledError):
                await attempt


@pytest.mark.asyncio
async def test_a_passed_deadline_spends_no_attempt() -> None:
    with respx.mock(assert_all_called=False) as router:
        route = _search(router).mock(return_value=httpx.Response(200, json=[]))
        async with httpx.AsyncClient() as client:
            outcome = await _geocoder(client).resolve(PLACE, NOW - 1.0)
    assert isinstance(outcome, TransportFailure)
    assert route.call_count == 0


@pytest.mark.asyncio
async def test_the_adapter_paces_nothing_itself() -> None:
    """Pacing is application-wide and lives in WP4's wrapper; here it is only a hook."""
    assert nominatim.PACE_MIN_INTERVAL_S == 1.0
    assert nominatim.NominatimGeocoder.pace_min_interval_s == 1.0
    assert nominatim.NominatimGeocoder.provider is ProviderName.NOMINATIM
    with respx.mock(assert_all_called=False) as router:
        route = _search(router).mock(return_value=httpx.Response(200, json=[]))
        async with httpx.AsyncClient() as client:
            geocoder = _geocoder(client)
            await geocoder.resolve(PLACE, DEADLINE)
            await geocoder.resolve(PLACE, DEADLINE)
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_a_label_is_plain_text_within_the_candidate_limit() -> None:
    hostile = "A" + "b" * 200
    answered = await _resolve(
        httpx.Response(200, json=[{"lat": "60.5", "lon": "17.2", "display_name": hostile}])
    )
    assert isinstance(answered.outcome, Ok)
    label = answered.outcome.value.hits[0].label
    assert len(label) <= PLACE_TEXT_MAX
    assert label.isprintable()


@pytest.mark.asyncio
async def test_the_contact_address_is_required() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError, match="contact address"):
            nominatim.NominatimGeocoder(client=client, base_url=BASE_URL, contact_email="")


@pytest.mark.asyncio
async def test_the_endpoint_comes_from_settings_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WO_NOMINATIM_URL", "https://geocoder.invalid/base")
    monkeypatch.setenv("WO_CONTACT_EMAIL", CONTACT)
    async with httpx.AsyncClient() as client:
        geocoder = nominatim.from_settings(client, Settings.from_env())
    assert geocoder.base_url == "https://geocoder.invalid/base"
    assert geocoder.contact_email == CONTACT


def test_the_adapter_declares_the_geocoder_port() -> None:
    """Explicit inheritance, so the mypy gate checks `resolve` against the port."""
    assert Geocoder in nominatim.NominatimGeocoder.__mro__
