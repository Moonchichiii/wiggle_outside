"""The model stage: one gated, slotted, bounded call per run (DEPLOYMENT section 3).

Built by main.py from the Ranker adapter and the in-memory provider gate, and handed to
the workflow as `Ports.model`. What it adds around the adapter:

- **One open request from the app** (the hosted slot): a lock, waited for only inside
  the stage deadline. A run that cannot get the slot in time uses the labelled fallback.
- **The provider gate**: a 402, 403, 404 or 429 earns the route a cooldown of
  max(60 s, Retry-After) and later runs fall back at once without a call; two transport
  failures in a row negative-cache the route for 60 s (storage.gate).
- **The deadline**: the call is cancelled at the stage deadline even if the adapter were
  to overrun it, and the run still gets its fallback.

The stage never caches, never retries, and logs counts only (ARCHITECTURE section 14).
"""

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from wiggle_outside.core.result import (
    Empty,
    Malformed,
    Ok,
    Outcome,
    OutcomeClass,
    QuotaOrUnavailable,
    TransportFailure,
)
from wiggle_outside.planner.ports import (
    Allow,
    CacheKey,
    CacheNamespace,
    Catalogue,
    Clock,
    CoolingDown,
    Counters,
    ModelRequest,
    NegativeCached,
    ProviderGate,
    ProviderName,
    Ranker,
    RawSelection,
)
from wiggle_outside.planner.prompting import build_request

if TYPE_CHECKING:
    from wiggle_outside.core.types import Pair
    from wiggle_outside.planner.plan_outing import ModelStage

STAGE: Final = "model"
UPSTREAM_CALL: Final = "upstream_call"
GATE_BLOCKED: Final = "gate_blocked"
SLOT_TIMEOUT: Final = "slot_timeout"
STAGE_TIMEOUT: Final = "stage_timeout"
GATE_KEY_VERSION: Final = 1
# One key for the whole route: the gate's negative cache then applies to the model as a
# whole, which is what "the model is unavailable for the run" means.
GATE_KEY: Final = CacheKey(
    namespace=CacheNamespace.MODEL,
    provider=ProviderName.OPENROUTER,
    params=(),
    schema_version=GATE_KEY_VERSION,
)


@dataclass(frozen=True, slots=True)
class ModelWiring:
    ranker: Ranker
    catalogue: Catalogue
    gate: ProviderGate
    counters: Counters
    clock: Clock
    d39_enabled: bool


def model_stage(wiring: ModelWiring) -> ModelStage:
    """Return the one model call per run, with the slot, the gate and the deadline."""
    slot = asyncio.Lock()

    async def stage(
        pairs: tuple[Pair, ...], text: str | None, deadline: float
    ) -> Outcome[RawSelection]:
        request = build_request(pairs, wiring.catalogue, text, d39_enabled=wiring.d39_enabled)
        if not await _acquire(slot, wiring, deadline):
            wiring.counters.incr(SLOT_TIMEOUT, STAGE)
            return TransportFailure()
        try:
            return await _call(wiring, request, deadline)
        finally:
            slot.release()

    return stage


async def _acquire(slot: asyncio.Lock, wiring: ModelWiring, deadline: float) -> bool:
    remaining = deadline - wiring.clock.monotonic()
    if remaining <= 0:
        return False
    try:
        async with asyncio.timeout(remaining):
            await slot.acquire()
    except TimeoutError:
        return False
    return True


async def _call(
    wiring: ModelWiring, request: ModelRequest, deadline: float
) -> Outcome[RawSelection]:
    now = wiring.clock.monotonic()
    decision = wiring.gate.admit(ProviderName.OPENROUTER, GATE_KEY, now)
    if not isinstance(decision, Allow):
        wiring.counters.incr(GATE_BLOCKED, STAGE)
        if isinstance(decision, CoolingDown):
            return QuotaOrUnavailable(retry_after_s=max(0.0, decision.until - now))
        if isinstance(decision, NegativeCached):
            return TransportFailure()
        return QuotaOrUnavailable()  # Saturated: never with the slot, kept for the type
    outcome: Outcome[RawSelection]
    try:
        async with asyncio.timeout(max(0.0, deadline - now)):
            outcome = await wiring.ranker.select(request, deadline)
    except TimeoutError:
        wiring.counters.incr(STAGE_TIMEOUT, STAGE)
        outcome = TransportFailure()
    wiring.counters.incr(UPSTREAM_CALL, STAGE)
    wiring.gate.record(
        ProviderName.OPENROUTER,
        GATE_KEY,
        _class_of(outcome),
        outcome.retry_after_s if isinstance(outcome, QuotaOrUnavailable) else None,
        wiring.clock.monotonic(),
    )
    return outcome


def _class_of(outcome: Outcome[RawSelection]) -> OutcomeClass:
    if isinstance(outcome, Ok):
        return OutcomeClass.OK
    if isinstance(outcome, Empty):
        return OutcomeClass.EMPTY
    if isinstance(outcome, Malformed):
        return OutcomeClass.MALFORMED
    if isinstance(outcome, TransportFailure):
        return OutcomeClass.TRANSPORT_FAILURE
    return OutcomeClass.QUOTA_OR_UNAVAILABLE
