"""Overpass adapter: a query built only from the template, and outcomes as values.

No test opens a socket: respx answers at the transport layer (PLAN section 8).

`overpass_empty.json` is a verbatim capture of an `around:1500,60.50,17.20` query taken
on 10 October 2026 (that area really has no tagged park or playground), so the envelope
— `version`, `generator`, `osm3s`, `elements` — is the provider's own. The element shape
in `overpass_bergby.json` is captured too (a `way` with `center`, a `node` with
`lat`/`lon`, `tags` as an object), but its four places are hand-built: they are the ones
WALKTHROUGH names, placed so that their rounded coordinates keep the walkthrough's
distance order.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
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
from wiggle_outside.core.types import Coordinates, Place
from wiggle_outside.integrations import overpass
from wiggle_outside.planner.ports import PlacesProvider, ProviderName
from wiggle_outside.settings import Settings

FIXTURES: Final = Path(__file__).resolve().parents[1] / "fixtures" / "providers"
HOST: Final = "overpass.test"
PATH: Final = "/api/interpreter"
BASE_URL: Final = f"https://{HOST}{PATH}"
NOW: Final = 1_000.0
DEADLINE: Final = NOW + 10.0
AT: Final = Coordinates(lat=60.5, lon=17.2)
RADIUS_M: Final = 1500
KINDS: Final = frozenset({"park", "playground"})
RETRY_AFTER_S: Final = 90.0
OVERSIZED: Final = overpass.MAX_RESPONSE_BYTES + 1
SLOW_S: Final = 30.0
EXPECTED_PLACES: Final = 4
# The stage budget the adapter has at DEADLINE, as the `[timeout:N]` setting.
EXPECTED_TIMEOUT: Final = int(overpass.STAGE_BUDGET_S)


@dataclass(frozen=True, slots=True)
class _Answered:
    outcome: Outcome[tuple[Place, ...]]
    route: respx.Route


def _fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _clock() -> float:
    return NOW


def _places(
    client: httpx.AsyncClient,
    monotonic: Callable[[], float] = _clock,
) -> overpass.OverpassPlaces:
    return overpass.OverpassPlaces(client=client, base_url=BASE_URL, monotonic=monotonic)


def _interpreter(router: respx.MockRouter) -> respx.Route:
    return router.route(method="POST", host=HOST, path=PATH)


async def _nearby(
    reply: httpx.Response | Exception,
    *,
    kinds: frozenset[str] = KINDS,
    radius_m: int = RADIUS_M,
) -> _Answered:
    """Answer one query with `reply`, and report the outcome beside the route."""
    with respx.mock(assert_all_called=False) as router:
        route = _interpreter(router)
        if isinstance(reply, Exception):
            route.mock(side_effect=reply)
        else:
            route.mock(return_value=reply)
        async with httpx.AsyncClient() as client:
            outcome = await _places(client).nearby(AT, radius_m, kinds, DEADLINE)
    return _Answered(outcome=outcome, route=route)


def _by_name(places: tuple[Place, ...]) -> dict[str, Place]:
    return {place.name: place for place in places}


def _sent(answered: _Answered) -> str:
    return answered.route.calls[0].request.content.decode()


@pytest.mark.asyncio
async def test_the_walkthrough_fixture_gives_its_four_places() -> None:
    answered = await _nearby(
        httpx.Response(200, json=_fixture("overpass_bergby.json")),
        kinds=frozenset({"park", "playground", "nature_reserve"}),
    )
    assert answered.route.call_count == 1  # exactly one HTTP attempt per call
    assert isinstance(answered.outcome, Ok)
    found = _by_name(answered.outcome.value)
    assert len(found) == EXPECTED_PLACES
    assert found["Oak Lane Park"].kind == "park"
    assert found["Oak Lane Park"].osm_access == "yes"
    assert found["Oak Lane Park"].fee == "unknown"
    assert found["Birchwood Nature Area"].kind == "nature_reserve"
    assert found["Birchwood Nature Area"].fee == "no"
    # The ampersand stays plain text; escaping happens once, at render.
    playground = found["Elm & Oak Playground"]
    assert playground.kind == "playground"
    assert playground.place_id == "node:4382901662"
    assert (playground.coords.lat, playground.coords.lon) == (60.5, 17.18)
    # A way carries `center`, which we asked for with `out tags center`.
    assert (found["Linden Park"].coords.lat, found["Linden Park"].coords.lon) == (60.51, 17.2)


@pytest.mark.asyncio
async def test_the_captured_empty_answer_is_empty_not_a_failure() -> None:
    answered = await _nearby(httpx.Response(200, json=_fixture("overpass_empty.json")))
    assert isinstance(answered.outcome, Empty)
    assert answered.route.call_count == 1


@pytest.mark.asyncio
async def test_the_query_is_the_fixed_template_plus_numbers() -> None:
    answered = await _nearby(
        httpx.Response(200, json=_fixture("overpass_empty.json")),
        kinds=frozenset({"park", "playground"}),
    )
    expected = overpass.QUERY_TEMPLATE.format(
        timeout=EXPECTED_TIMEOUT,
        clauses="\n".join(
            overpass.CLAUSE_TEMPLATE.format(
                selector=selector,
                radius=RADIUS_M,
                lat="60.50",
                lon="17.20",
            )
            for selector in ('nwr["leisure"="park"]', 'nwr["leisure"="playground"]')
        ),
        limit=overpass.OUT_LIMIT,
    )
    assert _sent(answered) == expected


@pytest.mark.asyncio
async def test_no_request_text_can_reach_the_query() -> None:
    """A kind this module does not know contributes nothing: template plus numbers only."""
    hostile = 'park"];out meta;node["name"~"."]('
    answered = await _nearby(
        httpx.Response(200, json=_fixture("overpass_empty.json")),
        kinds=frozenset({"park", hostile, "../../etc/passwd", "<script>"}),
    )
    sent = _sent(answered)
    assert "out meta" not in sent
    assert "passwd" not in sent
    assert "script" not in sent
    assert sent.count("nwr[") == 1
    assert 'nwr["leisure"="park"]' in sent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("deadline", "expected"),
    [
        pytest.param(NOW + 10.0, overpass.STAGE_BUDGET_S, id="the-stage-budget-is-smaller"),
        pytest.param(NOW + 1.5, 1.5, id="the-remaining-deadline-is-smaller"),
    ],
)
async def test_the_attempt_gets_min_of_the_stage_budget_and_what_is_left(
    deadline: float, expected: float
) -> None:
    with respx.mock(assert_all_called=False) as router:
        route = _interpreter(router).mock(return_value=httpx.Response(200, json={"elements": []}))
        async with httpx.AsyncClient() as client:
            await _places(client).nearby(AT, RADIUS_M, KINDS, deadline)
    request = route.calls[0].request
    assert request.extensions["timeout"]["read"] == pytest.approx(expected)
    # The server-side timeout travels inside the query, as a whole number of seconds.
    assert f"[timeout:{int(expected)}]" in request.content.decode()


@pytest.mark.asyncio
async def test_only_unknown_kinds_asks_nothing_at_all() -> None:
    answered = await _nearby(
        httpx.Response(200, json=_fixture("overpass_empty.json")),
        kinds=frozenset({"beach", "viewpoint"}),
    )
    assert isinstance(answered.outcome, Empty)
    assert answered.route.call_count == 0


@pytest.mark.asyncio
async def test_any_asks_for_every_supported_kind() -> None:
    answered = await _nearby(
        httpx.Response(200, json=_fixture("overpass_empty.json")),
        kinds=frozenset({"any"}),
    )
    sent = _sent(answered)
    expected_clauses = sum(len(value) for value in overpass.KIND_SELECTORS.values())
    assert sent.count("nwr[") == expected_clauses


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("asked", "expected"),
    [
        pytest.param(99_999, overpass.MAX_RADIUS_M, id="above-the-3-km-maximum"),
        pytest.param(0, overpass.MIN_RADIUS_M, id="below-the-minimum"),
        pytest.param(1200, 1200, id="inside-the-range"),
    ],
)
async def test_the_radius_stays_inside_the_documented_range(asked: int, expected: int) -> None:
    answered = await _nearby(
        httpx.Response(200, json=_fixture("overpass_empty.json")),
        radius_m=asked,
    )
    assert f"(around:{expected},60.50,17.20)" in _sent(answered)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tags", "reason"),
    [
        pytest.param(
            {"leisure": "park", "name": "P", "access": "private"}, "private", id="private"
        ),
        pytest.param({"leisure": "park", "name": "P", "access": "no"}, "no access", id="no-access"),
        pytest.param({"disused:leisure": "park", "name": "P"}, "disused", id="disused-key"),
        pytest.param({"leisure": "abandoned:park", "name": "P"}, "abandoned", id="abandoned-value"),
        pytest.param({"leisure": "park"}, "no name", id="unnamed"),
        pytest.param({"name": "P"}, "no kind", id="no-supported-kind"),
    ],
)
async def test_a_place_we_may_not_offer_is_dropped(tags: dict[str, str], reason: str) -> None:
    body = {
        "elements": [
            {"type": "node", "id": 1, "lat": 60.5, "lon": 17.2, "tags": tags},
        ]
    }
    answered = await _nearby(httpx.Response(200, json=body))
    assert isinstance(answered.outcome, Empty), reason


@pytest.mark.asyncio
async def test_an_element_without_a_usable_centre_is_dropped() -> None:
    body = {
        "elements": [
            {"type": "way", "id": 2, "tags": {"leisure": "park", "name": "No centre"}},
            {
                "type": "node",
                "id": 3,
                "lat": 900.0,
                "lon": 17.2,
                "tags": {"leisure": "park", "name": "Off earth"},
            },
        ]
    }
    answered = await _nearby(httpx.Response(200, json=body))
    assert isinstance(answered.outcome, Empty)


@pytest.mark.asyncio
async def test_a_fee_charging_place_is_reported_for_core_to_exclude() -> None:
    """D37 (b): the adapter reports the tag; `core.places.is_usable` excludes it."""
    body = {
        "elements": [
            {
                "type": "node",
                "id": 4,
                "lat": 60.5,
                "lon": 17.2,
                "tags": {"leisure": "park", "name": "Paid Park", "fee": "yes"},
            }
        ]
    }
    answered = await _nearby(httpx.Response(200, json=body))
    assert isinstance(answered.outcome, Ok)
    assert answered.outcome.value[0].fee == "yes"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"not json at all", id="not-json"),
        pytest.param(b"[]", id="an-array-not-an-object"),
        pytest.param(b'{"elements": {}}', id="elements-not-a-list"),
        pytest.param(b"{}", id="no-elements-key"),
    ],
)
async def test_a_body_we_cannot_use_is_malformed(body: bytes) -> None:
    answered = await _nearby(httpx.Response(200, content=body))
    assert isinstance(answered.outcome, Malformed)
    assert answered.route.call_count == 1


@pytest.mark.asyncio
async def test_a_runtime_error_remark_is_never_cached_as_no_places() -> None:
    body = {"elements": [], "remark": "runtime error: Query timed out in 'query' at line 3"}
    answered = await _nearby(httpx.Response(200, json=body))
    assert answered.outcome == QuotaOrUnavailable(retry_after_s=None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(httpx.ConnectError("refused"), id="connect"),
        pytest.param(httpx.ReadTimeout("too slow"), id="read-timeout"),
    ],
)
async def test_a_transport_failure_is_the_only_retryable_outcome(failure: Exception) -> None:
    answered = await _nearby(failure)
    assert isinstance(answered.outcome, TransportFailure)
    # The adapter never retries: the one permitted retry belongs to WP4's wrapper.
    assert answered.route.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(429, RETRY_AFTER_S, id="too-many-requests"),
        pytest.param(504, RETRY_AFTER_S, id="gateway-timeout"),
    ],
)
async def test_the_provider_saying_no_carries_its_delay(status: int, expected: float) -> None:
    answered = await _nearby(httpx.Response(status, headers={"Retry-After": "90"}, text="slow"))
    assert answered.outcome == QuotaOrUnavailable(retry_after_s=expected)


@pytest.mark.asyncio
async def test_an_oversized_body_is_a_transport_failure() -> None:
    body = b'{"elements": [], "filler": "' + b"x" * OVERSIZED + b'"}'
    answered = await _nearby(httpx.Response(200, content=body))
    assert isinstance(answered.outcome, TransportFailure)
    assert answered.route.call_count == 1


@pytest.mark.asyncio
async def test_a_redirect_is_never_followed() -> None:
    answered = await _nearby(
        httpx.Response(302, headers={"Location": "https://elsewhere.test/api/interpreter"})
    )
    assert answered.route.call_count == 1
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
async def test_cancellation_is_never_converted_to_an_outcome() -> None:
    started = asyncio.Event()

    async def never_answer(_request: httpx.Request) -> httpx.Response:
        started.set()
        await asyncio.sleep(SLOW_S)
        return httpx.Response(200, json={"elements": []})

    with respx.mock(assert_all_called=False) as router:
        _interpreter(router).mock(side_effect=never_answer)
        async with httpx.AsyncClient() as client:
            attempt = asyncio.create_task(_places(client).nearby(AT, RADIUS_M, KINDS, DEADLINE))
            await started.wait()
            attempt.cancel()
            with pytest.raises(asyncio.CancelledError):
                await attempt


@pytest.mark.asyncio
async def test_a_passed_deadline_spends_no_attempt() -> None:
    with respx.mock(assert_all_called=False) as router:
        route = _interpreter(router).mock(return_value=httpx.Response(200, json={"elements": []}))
        async with httpx.AsyncClient() as client:
            outcome = await _places(client).nearby(AT, RADIUS_M, KINDS, NOW - 1.0)
    assert isinstance(outcome, TransportFailure)
    assert route.call_count == 0


@pytest.mark.asyncio
async def test_the_endpoint_comes_from_settings_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WO_OVERPASS_URL", "https://places.invalid/interpreter")
    async with httpx.AsyncClient() as client:
        provider = overpass.from_settings(client, Settings.from_env())
    assert provider.base_url == "https://places.invalid/interpreter"
    assert provider.provider is ProviderName.OVERPASS


def test_the_adapter_declares_the_places_port() -> None:
    """Explicit inheritance, so the mypy gate checks `nearby` against the port."""
    assert PlacesProvider in overpass.OverpassPlaces.__mro__
