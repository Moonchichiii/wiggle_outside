"""OpenRouter adapter: request shape, bounds, every error, and what is logged (WP5 accept).

No test opens a socket: respx answers at the transport layer (PLAN section 8). The
request body is asserted field by field because DEPLOYMENT section 3 and TC-010 fix it:
the model, the strict schema, `max_tokens` 256, reasoning off, the approved-provider
allowlist with `require_parameters`, and the 10,000-byte cap checked before sending.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

import httpx
import pytest
import respx

from wiggle_outside.core.result import (
    Malformed,
    Ok,
    Outcome,
    QuotaOrUnavailable,
    TransportFailure,
)
from wiggle_outside.integrations import openrouter
from wiggle_outside.planner.ports import ModelRequest, ProviderName, Ranker, RawSelection
from wiggle_outside.planner.prompting import PROMPT_V2, SCHEMA_V2
from wiggle_outside.settings import Settings

HOST: Final = "openrouter.test"
PATH: Final = "/api/v1/chat/completions"
URL: Final = f"https://{HOST}{PATH}"
KEY: Final = "sk-or-test-never-logged"
MODEL: Final = "google/gemma-4-26b-a4b-it"
NOW: Final = 1_000.0
DEADLINE: Final = NOW + 20.0
RETRY_AFTER_S: Final = 90.0
SLOW_S: Final = 30.0
EXPECTED_MAX_TOKENS: Final = 256

ANSWER: Final = json.dumps(
    {
        "interests": ["birds"],
        "interest_status": "matched",
        "picks": [{"pair_id": "p1", "hook_id": "expedition", "reason_ids": ["close_by"]}],
    }
)

REQUEST: Final = ModelRequest(
    prompt_version=PROMPT_V2,
    schema_version=SCHEMA_V2,
    pairs_block='[{"pair_id":"p1","activity_id":"leaf-colour-hunt"}]',
    vocabulary_block="animals, birds",
    family_text_block="birds",
)


def completion(  # noqa: PLR0913  a response builder with one knob per field under test
    content: str | None = ANSWER,
    *,
    finish_reason: str = "stop",
    provider: str = "DeepInfra",
    prompt_tokens: int = 1800,
    reasoning_tokens: int = 0,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": "gen-1",
        "provider": provider,
        "model": MODEL,
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "native_finish_reason": finish_reason,
                "message": {"role": "assistant", "content": content},
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": 60,
            "total_tokens": prompt_tokens + 60,
            "completion_tokens_details": {"reasoning_tokens": reasoning_tokens},
        },
    }
    if error is not None:
        body["error"] = error
    return body


@dataclass(frozen=True, slots=True)
class _Answered:
    outcome: Outcome[RawSelection]
    route: respx.Route
    served: list[openrouter.Served]


def _clock() -> float:
    return NOW


def _ranker(
    client: httpx.AsyncClient,
    served: list[openrouter.Served],
    monotonic: Callable[[], float] = _clock,
) -> openrouter.OpenRouterRanker:
    return openrouter.OpenRouterRanker(
        client=client,
        url=URL,
        api_key=KEY,
        model_id=MODEL,
        monotonic=monotonic,
        on_served=served.append,
    )


def _completions(router: respx.MockRouter) -> respx.Route:
    return router.route(method="POST", host=HOST, path=PATH)


async def _select(
    reply: httpx.Response | Exception,
    request: ModelRequest = REQUEST,
    deadline: float = DEADLINE,
) -> _Answered:
    served: list[openrouter.Served] = []
    with respx.mock(assert_all_called=False) as router:
        route = _completions(router)
        if isinstance(reply, Exception):
            route.mock(side_effect=reply)
        else:
            route.mock(return_value=reply)
        async with httpx.AsyncClient() as client:
            outcome = await _ranker(client, served).select(request, deadline)
    return _Answered(outcome=outcome, route=route, served=served)


def _sent(answered: _Answered) -> dict[str, Any]:
    body: dict[str, Any] = json.loads(answered.route.calls[0].request.content)
    return body


# --- The request ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_valid_answer_is_the_raw_selection_after_one_request() -> None:
    answered = await _select(httpx.Response(200, json=completion()))

    assert answered.route.call_count == 1  # exactly one HTTP attempt per call
    assert answered.outcome == Ok(RawSelection(payload=ANSWER))


@pytest.mark.asyncio
async def test_the_request_is_the_contracted_shape() -> None:
    answered = await _select(httpx.Response(200, json=completion()))
    body = _sent(answered)

    assert body["model"] == MODEL
    assert body["max_tokens"] == EXPECTED_MAX_TOKENS
    assert body["reasoning"] == {"effort": "none"}
    assert body["response_format"]["type"] == "json_schema"
    schema = body["response_format"]["json_schema"]
    assert schema["name"] == "selection_v2"
    assert schema["strict"] is True
    assert schema["schema"]["additionalProperties"] is False
    assert set(schema["schema"]["required"]) == {"interests", "interest_status", "picks"}
    assert "$schema" not in schema["schema"]
    assert "title" not in schema["schema"]
    # xgrammar (behind the approved endpoints) rejects uniqueItems; core enforces it.
    assert "uniqueItems" not in json.dumps(schema["schema"])
    assert schema["schema"]["properties"]["picks"]["maxItems"] == 3
    assert schema["schema"]["properties"]["interests"]["items"]["enum"][0] == "animals"
    assert "stream" not in body
    assert "temperature" not in body


@pytest.mark.asyncio
async def test_routing_is_the_approved_allowlist_with_required_parameters() -> None:
    # TC-010: approved providers, not open routing; fallbacks only within the list.
    answered = await _select(httpx.Response(200, json=completion()))
    provider = _sent(answered)["provider"]

    assert provider["only"] == ["nextbit", "deepinfra", "coreweave"]
    assert provider["require_parameters"] is True
    assert provider["allow_fallbacks"] is True
    assert provider["data_collection"] == "deny"
    assert "order" not in provider
    assert "zdr" not in provider


@pytest.mark.asyncio
async def test_the_messages_are_the_system_prompt_and_the_three_blocks() -> None:
    answered = await _select(httpx.Response(200, json=completion()))
    messages = _sent(answered)["messages"]

    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[0]["content"] == openrouter.system_prompt(PROMPT_V2)
    assert "<pairs>" in messages[1]["content"]
    assert "<vocabulary>" in messages[1]["content"]
    assert "<family_text>\nbirds\n</family_text>" in messages[1]["content"]


@pytest.mark.asyncio
async def test_the_key_travels_as_a_bearer_header_and_nowhere_else() -> None:
    answered = await _select(httpx.Response(200, json=completion()))
    request = answered.route.calls[0].request

    assert request.headers["Authorization"] == f"Bearer {KEY}"
    assert KEY not in str(request.url)
    assert KEY not in request.content.decode()


@pytest.mark.asyncio
async def test_a_request_over_the_cap_is_refused_without_a_call(
    caplog: pytest.LogCaptureFixture,
) -> None:
    oversized = ModelRequest(
        prompt_version=PROMPT_V2,
        schema_version=SCHEMA_V2,
        pairs_block="x" * openrouter.MAX_REQUEST_BYTES,
        vocabulary_block="",
        family_text_block="",
    )
    with caplog.at_level(logging.WARNING, logger="wiggle_outside.integrations.openrouter"):
        answered = await _select(httpx.Response(200, json=completion()), request=oversized)

    assert answered.route.call_count == 0
    assert isinstance(answered.outcome, Malformed)
    assert "over the cap" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("deadline", "expected"),
    [
        pytest.param(NOW + 20.0, openrouter.STAGE_BUDGET_S, id="the-stage-budget-is-smaller"),
        pytest.param(NOW + 1.5, 1.5, id="the-remaining-deadline-is-smaller"),
    ],
)
async def test_the_attempt_gets_min_of_the_stage_budget_and_what_is_left(
    deadline: float, expected: float
) -> None:
    answered = await _select(httpx.Response(200, json=completion()), deadline=deadline)
    assert answered.route.calls[0].request.extensions["timeout"]["read"] == pytest.approx(expected)


@pytest.mark.asyncio
async def test_no_time_left_means_no_attempt() -> None:
    answered = await _select(httpx.Response(200, json=completion()), deadline=NOW)
    assert answered.route.call_count == 0
    assert isinstance(answered.outcome, TransportFailure)


# --- Errors: every one leads to an outcome, never an exception -------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [402, 403, 404, 429])
async def test_refusals_are_unavailable_for_the_run_with_retry_after(status: int) -> None:
    # TC-010: 402, 403, 404 and 429 lead to the labelled fallback, never an error page.
    answered = await _select(
        httpx.Response(status, headers={"Retry-After": str(int(RETRY_AFTER_S))}, json={})
    )
    assert answered.outcome == QuotaOrUnavailable(retry_after_s=RETRY_AFTER_S)
    assert answered.route.call_count == 1  # no retry


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [500, 502, 503])
async def test_server_errors_are_unavailable_for_the_run(status: int) -> None:
    answered = await _select(httpx.Response(status))
    assert answered.outcome == QuotaOrUnavailable(retry_after_s=None)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 422])
async def test_other_client_errors_are_malformed(status: int) -> None:
    answered = await _select(httpx.Response(status, json={"error": {"code": status}}))
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(httpx.ConnectError("refused"), id="connect"),
        pytest.param(httpx.ReadTimeout("slow"), id="read-timeout"),
        pytest.param(httpx.RemoteProtocolError("torn"), id="protocol"),
    ],
)
async def test_transport_failures_are_transport_failures(failure: Exception) -> None:
    answered = await _select(failure)
    assert isinstance(answered.outcome, TransportFailure)


@pytest.mark.asyncio
async def test_a_redirect_is_not_followed() -> None:
    answered = await _select(httpx.Response(302, headers={"Location": "https://elsewhere.test"}))
    assert answered.route.call_count == 1
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"not json", id="not-json"),
        pytest.param(b"[]", id="not-an-object"),
        pytest.param(b'{"choices": []}', id="no-choice"),
        pytest.param(b'{"choices": [{"message": {"content": 7}}]}', id="content-not-text"),
    ],
)
async def test_an_off_shape_body_is_malformed(body: bytes) -> None:
    answered = await _select(httpx.Response(200, content=body))
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
async def test_an_oversized_body_is_a_transport_failure() -> None:
    answered = await _select(
        httpx.Response(200, content=b"{" + b" " * openrouter.MAX_RESPONSE_BYTES + b"}")
    )
    assert isinstance(answered.outcome, TransportFailure)


@pytest.mark.asyncio
async def test_cut_off_with_nothing_to_show_is_invalid() -> None:
    answered = await _select(httpx.Response(200, json=completion("", finish_reason="length")))
    assert isinstance(answered.outcome, Malformed)


@pytest.mark.asyncio
async def test_cut_off_with_content_is_handed_on_for_validation() -> None:
    # The planner's validation decides; a truncated object fails there (D44).
    answered = await _select(
        httpx.Response(200, json=completion('{"interests": [', finish_reason="length"))
    )
    assert answered.outcome == Ok(RawSelection(payload='{"interests": ['))


@pytest.mark.asyncio
async def test_an_error_inside_a_200_is_unavailable() -> None:
    answered = await _select(
        httpx.Response(200, json=completion(None, error={"code": 502, "message": "upstream"}))
    )
    assert isinstance(answered.outcome, QuotaOrUnavailable)


@pytest.mark.asyncio
async def test_cancellation_closes_the_stream_and_propagates() -> None:
    async def slow(_request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(SLOW_S)
        return httpx.Response(200, json=completion())

    with respx.mock(assert_all_called=False) as router:
        _completions(router).mock(side_effect=slow)
        async with httpx.AsyncClient() as client:
            task = asyncio.create_task(_ranker(client, []).select(REQUEST, DEADLINE))
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


# --- What is logged ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_serving_provider_usage_and_latency_are_logged_and_reported(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="wiggle_outside.integrations.openrouter"):
        answered = await _select(httpx.Response(200, json=completion(provider="NextBit")))

    (served,) = answered.served
    assert served.provider == "NextBit"
    assert served.model == MODEL
    assert (served.prompt_tokens, served.completion_tokens, served.reasoning_tokens) == (
        1800,
        60,
        0,
    )
    assert served.finish_reason == "stop"
    assert served.request_bytes == len(answered.route.calls[0].request.content)
    assert "model served by NextBit" in caplog.text
    assert "prompt=1800" in caplog.text


@pytest.mark.asyncio
async def test_neither_the_key_the_prompt_nor_the_answer_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        await _select(httpx.Response(200, json=completion()))

    assert KEY not in caplog.text
    assert "birds" not in caplog.text  # the family text
    assert "expedition" not in caplog.text  # the answer


@pytest.mark.asyncio
async def test_breaching_the_prompt_token_assumption_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="wiggle_outside.integrations.openrouter"):
        await _select(httpx.Response(200, json=completion(prompt_tokens=12_000)))
    assert "exceed the 10100 assumed" in caplog.text


@pytest.mark.asyncio
async def test_reasoning_tokens_with_reasoning_off_are_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="wiggle_outside.integrations.openrouter"):
        await _select(httpx.Response(200, json=completion(reasoning_tokens=40)))
    assert "40 reasoning tokens" in caplog.text


# --- Construction --------------------------------------------------------------------


def test_the_adapter_is_the_ranker_port_for_the_openrouter_route() -> None:
    assert openrouter.OpenRouterRanker.provider is ProviderName.OPENROUTER
    ranker: Ranker = openrouter.OpenRouterRanker(
        client=httpx.AsyncClient(), url=URL, api_key=KEY, model_id=MODEL
    )
    assert ranker is not None  # the port is structural; mypy checks the assignment


def test_without_a_key_there_is_no_adapter() -> None:
    # conftest clears OPENROUTER_API_KEY for the test process.
    assert openrouter.from_settings(httpx.AsyncClient(), Settings.from_env()) is None


def test_prompt_and_schema_versions_are_names_not_paths() -> None:
    with pytest.raises(ValueError, match="not a prompt or schema version"):
        openrouter.system_prompt("../secrets")
    with pytest.raises(ValueError, match="not a prompt or schema version"):
        openrouter.output_schema("select.v2/../x")


def test_the_largest_contracted_request_fits_the_cap() -> None:
    # 12 pairs with every field at its widest, plus 120 characters of family text.
    entry = {
        "pair_id": "p12",
        "activity_id": "x" * 40,
        "title": "y" * 60,
        "place_kind": "nature_reserve",
        "distance_band": "500m_to_1km",
        "energy": ["energetic", "gentle", "moderate"],
        "interests": ["building", "colours", "drawing"],
        "allowed_hook_ids": ["expedition", "explorer-club", "pocket-adventure", "secret-spot"],
        "allowed_reason_ids": ["all_ages", "close_by", "dry_window", "fits_time", "in_season"],
    }
    widest = ModelRequest(
        prompt_version=PROMPT_V2,
        schema_version=SCHEMA_V2,
        pairs_block=json.dumps([entry] * 12, separators=(",", ":")),
        vocabulary_block=", ".join(["puddles"] * 14),
        family_text_block="z" * 120,
    )
    size = len(openrouter.serialise(openrouter.request_body(MODEL, widest)))
    assert size <= openrouter.MAX_REQUEST_BYTES, size
