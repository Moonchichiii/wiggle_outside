"""Hosted model adapter: Gemma 4 26B A4B through OpenRouter (DEPLOYMENT section 3, TC-010).

One HTTP attempt per call and nothing else: the slot, the gate and the deadline guard
are the planner's model stage; there is no cache and no retry for the model (D44).

Routing (TC-010): `provider.only` is the approved allowlist in `APPROVED_PROVIDERS`,
`require_parameters` is true so only endpoints that honour the strict JSON schema are
used, and fallbacks are allowed *within* that list. The basis for the list is
OpenRouter's published data policy per provider (no training, no prompt retention), not
an independent review of each provider's terms. Which provider served each request is
read from the response and logged, with the usage and the latency; never the prompt, the
answer or the key.

Bounds: the serialised request is refused above `MAX_REQUEST_BYTES` without a call;
`max_tokens` is 256; reasoning is off; the response body is capped while streaming.
"""

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from importlib import resources
from typing import TYPE_CHECKING, ClassVar, Final, override

import httpx

from wiggle_outside.core.result import (
    Malformed,
    Ok,
    Outcome,
    QuotaOrUnavailable,
    TransportFailure,
)
from wiggle_outside.planner.ports import ModelRequest, ProviderName, Ranker, RawSelection
from wiggle_outside.planner.prompting import user_message
from wiggle_outside.settings import MODEL_BUDGET_S

if TYPE_CHECKING:
    from wiggle_outside.settings import Settings

log = logging.getLogger(__name__)

USER_AGENT: Final = "WiggleOutside/0.1"
STAGE_BUDGET_S: Final = MODEL_BUDGET_S
CONNECT_BUDGET_S: Final = 2.0
# DEPLOYMENT section 1.3: the complete request body, messages and schema, before sending.
MAX_REQUEST_BYTES: Final = 10_000
# The answer is at most 256 tokens; an error body is small. Anything larger is wrong.
MAX_RESPONSE_BYTES: Final = 64 * 1024
MAX_TOKENS: Final = 256
# DEPLOYMENT section 1.3: the input-token assumption behind the cost estimate, checked on
# every run and logged when breached, never relied on.
PROMPT_TOKENS_ASSUMED: Final = 10_100

# TC-010: the approved providers, by OpenRouter provider slug. Verified on 11 October
# 2026 against the model's public endpoint list (openrouter.ai, api/v1/models/.../endpoints):
# NextBit, DeepInfra and CoreWeave, endpoint tags nextbit/bf16, deepinfra/fp8 and
# coreweave/bf16, each supporting response_format, structured_outputs, max_tokens and
# reasoning.
APPROVED_PROVIDERS: Final[tuple[str, ...]] = ("nextbit", "deepinfra", "coreweave")

HTTP_OK: Final = 200
HTTP_PAYMENT_REQUIRED: Final = 402
HTTP_FORBIDDEN: Final = 403
HTTP_NOT_FOUND: Final = 404
HTTP_TOO_MANY_REQUESTS: Final = 429
HTTP_SERVER_ERROR: Final = 500
# Each leads to the labelled fallback, never an error page (TC-010); the model stage
# gives the route a cooldown for them (QuotaOrUnavailable).
UNAVAILABLE_STATUSES: Final[frozenset[int]] = frozenset(
    {HTTP_PAYMENT_REQUIRED, HTTP_FORBIDDEN, HTTP_NOT_FOUND, HTTP_TOO_MANY_REQUESTS}
)
FINISH_LENGTH: Final = "length"
UNKNOWN_PROVIDER: Final = "unknown"

# Prompt and schema versions are planner constants, never request data; the pattern
# keeps a version name from ever being a path.
VERSION_NAME: Final = re.compile(r"^[a-z]+\.v[0-9]+$")
# Keywords the strict grammar engines behind the approved endpoints reject (measured on
# 11 October 2026: xgrammar answered "contains features not supported" to `uniqueItems`)
# or ignore. They are dropped from the copy sent; the schema files are unchanged and
# `core.ideas` still enforces uniqueness and every other rule on the answer (D4).
SCHEMA_UNSENT_KEYS: Final[frozenset[str]] = frozenset({"$schema", "title", "uniqueItems"})


@dataclass(frozen=True, slots=True)
class Served:
    """What one answered call is logged as (counts and names only)."""

    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    finish_reason: str
    latency_s: float
    request_bytes: int


@dataclass(frozen=True, slots=True)
class _Body:
    payload: bytes


type _Fetched = _Body | Malformed | TransportFailure | QuotaOrUnavailable


def request_body(model_id: str, request: ModelRequest) -> dict[str, object]:
    """Build the chat-completions body: messages, strict schema, bounds and routing."""
    return {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt(request.prompt_version)},
            {"role": "user", "content": user_message(request)},
        ],
        "max_tokens": MAX_TOKENS,
        "reasoning": {"effort": "none"},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": request.schema_version.replace(".", "_"),
                "strict": True,
                "schema": output_schema(request.schema_version),
            },
        },
        "provider": {
            "only": list(APPROVED_PROVIDERS),
            "allow_fallbacks": True,
            "require_parameters": True,
            "data_collection": "deny",
        },
    }


def serialise(body: dict[str, object]) -> bytes:
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()


def system_prompt(version: str) -> str:
    """Read `planner/prompts/<version>.md`, the versioned system prompt (CONTRACTS 6)."""
    return _planner_file("prompts", f"{_checked(version)}.md")


def output_schema(version: str) -> dict[str, object]:
    """Read `planner/schema/<version>.json` without the keywords the engines reject."""
    decoded: object = json.loads(_planner_file("schema", f"{_checked(version)}.json"))
    if not isinstance(decoded, dict):
        msg = f"schema {version} is not an object"
        raise TypeError(msg)
    sent = _without_unsent(decoded)
    assert isinstance(sent, dict)  # noqa: S101  a dict in is a dict out
    return sent


def _without_unsent(node: object) -> object:
    if isinstance(node, dict):
        return {str(k): _without_unsent(v) for k, v in node.items() if k not in SCHEMA_UNSENT_KEYS}
    if isinstance(node, list):
        return [_without_unsent(item) for item in node]
    return node


def _checked(version: str) -> str:
    if not VERSION_NAME.match(version):
        msg = f"not a prompt or schema version: {version!r}"
        raise ValueError(msg)
    return version


def _planner_file(folder: str, name: str) -> str:
    return (
        resources.files("wiggle_outside.planner").joinpath(folder, name).read_text(encoding="utf-8")
    )


@dataclass(frozen=True, slots=True)
class OpenRouterRanker(Ranker):
    """One OpenRouter request per call. Never retries, never caches."""

    client: httpx.AsyncClient
    url: str
    api_key: str
    model_id: str
    monotonic: Callable[[], float] = time.monotonic
    max_bytes: int = MAX_RESPONSE_BYTES
    on_served: Callable[[Served], None] | None = None

    provider: ClassVar[ProviderName] = ProviderName.OPENROUTER

    @override
    async def select(self, request: ModelRequest, deadline: float) -> Outcome[RawSelection]:
        budget = min(STAGE_BUDGET_S, deadline - self.monotonic())
        if budget <= 0:
            return TransportFailure()
        payload = serialise(request_body(self.model_id, request))
        if len(payload) > MAX_REQUEST_BYTES:
            # The run uses the labelled fallback; the event is logged (DEPLOYMENT 3).
            log.warning("model request refused: %d bytes over the cap", len(payload))
            return Malformed()
        started = self.monotonic()
        fetched = await self._fetch(payload, budget)
        if not isinstance(fetched, _Body):
            return fetched
        return self._answer(fetched.payload, self.monotonic() - started, len(payload))

    async def _fetch(self, payload: bytes, budget: float) -> _Fetched:
        request = self.client.build_request(
            "POST",
            self.url,
            content=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
            timeout=httpx.Timeout(budget, connect=min(budget, CONNECT_BUDGET_S)),
        )
        return await _read(self.client, request, max_bytes=self.max_bytes)

    def _answer(
        self, payload: bytes, latency_s: float, request_bytes: int
    ) -> Outcome[RawSelection]:
        parsed = _parse(payload)
        if parsed is None:
            return Malformed()
        content, served = parsed
        served = Served(
            provider=served.provider,
            model=served.model,
            prompt_tokens=served.prompt_tokens,
            completion_tokens=served.completion_tokens,
            reasoning_tokens=served.reasoning_tokens,
            finish_reason=served.finish_reason,
            latency_s=latency_s,
            request_bytes=request_bytes,
        )
        _log_served(served)
        if self.on_served is not None:
            self.on_served(served)
        if content is None:
            return QuotaOrUnavailable()  # the provider reported an error inside a 200
        if served.finish_reason == FINISH_LENGTH and not content.strip():
            return Malformed()  # cut off with nothing to show: invalid, fallback
        return Ok(RawSelection(payload=content))


def from_settings(client: httpx.AsyncClient, settings: Settings) -> OpenRouterRanker | None:
    """Build the adapter from configuration, or None without a key (then no model)."""
    if settings.openrouter_api_key is None:
        return None
    return OpenRouterRanker(
        client=client,
        url=settings.openrouter_url,
        api_key=settings.openrouter_api_key,
        model_id=settings.model_id,
    )


# --- Transport ------------------------------------------------------------------------


async def _read(
    client: httpx.AsyncClient,
    request: httpx.Request,
    *,
    max_bytes: int,
) -> _Fetched:
    """One attempt: no redirect is followed, and the stream is always closed."""
    try:
        response = await client.send(request, stream=True, follow_redirects=False)
        try:
            if response.status_code != HTTP_OK:
                return _status_outcome(response.status_code, response.headers.get("retry-after"))
            return _capped(await _collect(response, max_bytes))
        finally:
            # Cancellation closes the stream here and then propagates (CONTRACTS 1).
            await response.aclose()
    except httpx.HTTPError:
        return TransportFailure()


async def _collect(response: httpx.Response, max_bytes: int) -> bytes | None:
    payload = bytearray()
    async for chunk in response.aiter_bytes():
        payload += chunk
        if len(payload) > max_bytes:
            return None
    return bytes(payload)


def _capped(payload: bytes | None) -> _Fetched:
    return TransportFailure() if payload is None else _Body(payload)


def _status_outcome(status: int, retry_after: str | None) -> Malformed | QuotaOrUnavailable:
    if status in UNAVAILABLE_STATUSES or status >= HTTP_SERVER_ERROR:
        log.warning("model unavailable for this run: OpenRouter answered %d", status)
        return QuotaOrUnavailable(retry_after_s=_retry_after_seconds(retry_after))
    log.warning("model answer unusable: OpenRouter answered %d", status)
    return Malformed()


def _retry_after_seconds(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = raw.strip()
    try:
        return float(max(0, int(text)))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(text)
    except TypeError, ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


# --- The answer -----------------------------------------------------------------------


def _parse(payload: bytes) -> tuple[str | None, Served] | None:
    """Return the content (None for an in-body error) and what to log, or None if off-shape."""
    try:
        decoded: object = json.loads(payload)
    except UnicodeDecodeError, json.JSONDecodeError:
        return None
    if not isinstance(decoded, dict):
        return None
    body: dict[str, object] = {str(k): v for k, v in decoded.items()}
    usage = _mapping(body.get("usage"))
    details = _mapping(usage.get("completion_tokens_details"))
    choice = _first_choice(body.get("choices"))
    message = _mapping(choice.get("message"))
    content = message.get("content")
    served = Served(
        provider=_text(body.get("provider")) or UNKNOWN_PROVIDER,
        model=_text(body.get("model")) or UNKNOWN_PROVIDER,
        prompt_tokens=_count(usage.get("prompt_tokens")),
        completion_tokens=_count(usage.get("completion_tokens")),
        reasoning_tokens=_count(details.get("reasoning_tokens")),
        finish_reason=_text(choice.get("finish_reason")) or "",
        latency_s=0.0,
        request_bytes=0,
    )
    if "error" in body or "error" in choice:
        return None, served
    if not isinstance(content, str):
        return None
    return content, served


def _first_choice(choices: object) -> dict[str, object]:
    if isinstance(choices, list) and choices:
        return _mapping(choices[0])
    return {}


def _mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}
    return {}


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _log_served(served: Served) -> None:
    """Log who served the request and what it cost; never the prompt or the answer."""
    log.info(
        "model served by %s (%s): prompt=%d completion=%d reasoning=%d finish=%s "
        "latency=%.2fs request_bytes=%d",
        served.provider,
        served.model,
        served.prompt_tokens,
        served.completion_tokens,
        served.reasoning_tokens,
        served.finish_reason,
        served.latency_s,
        served.request_bytes,
    )
    if served.prompt_tokens > PROMPT_TOKENS_ASSUMED:
        log.warning(
            "model prompt tokens %d exceed the %d assumed (DEPLOYMENT 1.3)",
            served.prompt_tokens,
            PROMPT_TOKENS_ASSUMED,
        )
    if served.reasoning_tokens:
        log.warning(
            "model reported %d reasoning tokens with reasoning off", served.reasoning_tokens
        )
