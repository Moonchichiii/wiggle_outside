"""The gated fetch sequence every cached provider shares.

CONTRACTS section 4.1 fixes the order:

    cache get - hit -> return
              - miss -> single flight (one fetch per key):
                    attempt 1: gate.admit -> gate.pace -> inner call -> gate.record
                    one retry on TransportFailure, inside the stage budget, same sequence
                    cache put (Ok and Empty only)

The put lives inside the fetch, so a cancelled fetch can never reach the cache
(BACKEND-CONTRACT section 6).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from functools import partial

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
    CacheStore,
    Clock,
    CoolingDown,
    Counters,
    GateDecision,
    NegativeCached,
    ProviderGate,
    ProviderName,
    SingleFlight,
)
from wiggle_outside.storage.counters import (
    CACHE_NOT_COVERING,
    CACHE_UNREADABLE,
    CACHE_UNWRITABLE,
    GATE_BLOCKED,
    PACE_EXCEEDED,
    UPSTREAM_CALL,
    UPSTREAM_RETRY,
)

# A payload that cannot be decoded is a miss, counted (CONTRACTS section 4.1).
# NotImplementedError is listed because `to_cache`/`from_cache` are still WP0 stubs for
# GeocodeHits, WeatherWindow and Place.from_cache.
CODEC_ERRORS = (ValueError, TypeError, LookupError, AttributeError, NotImplementedError)


def accepts_any(_value: object) -> bool:
    return True


@dataclass(frozen=True, slots=True)
class CacheWiring:
    """What every cached provider needs. main.py builds one and shares it."""

    store: CacheStore
    gate: ProviderGate
    flight: SingleFlight
    counters: Counters
    clock: Clock


@dataclass(frozen=True, slots=True)
class Engine:
    wiring: CacheWiring
    provider: ProviderName
    ttl: timedelta


@dataclass(frozen=True, slots=True)
class Codec[T]:
    """Bytes in the cache, domain values outside it (CONTRACTS section 4.1)."""

    encode: Callable[[T], bytes]
    decode: Callable[[bytes], T]
    # Weather is only a hit while the entry still covers the window (section 15).
    covers: Callable[[T], bool] = accepts_any


@dataclass(frozen=True, slots=True)
class Request[T]:
    key: CacheKey
    deadline: float
    inner: Callable[[float], Awaitable[Outcome[T]]]
    codec: Codec[T]


def _stage[T](request: Request[T]) -> str:
    return request.key.namespace.value


async def obtain[T](engine: Engine, request: Request[T]) -> Outcome[T]:
    """Serve one provider call from the cache, or fetch it once."""
    hit = await _from_cache(engine, request)
    if hit is not None:
        return hit
    # Both deadlines are this caller's; the flight keeps the first one and ignores later
    # ones, so joining never extends the fetch.
    fetched = await engine.wiring.flight.run(
        request.key, request.deadline, request.deadline, partial(_fetch, engine, request)
    )
    return _decoded(engine, request, fetched)


async def _from_cache[T](engine: Engine, request: Request[T]) -> Outcome[T] | None:
    payload = await engine.wiring.store.get(request.key, engine.wiring.clock.now())
    if payload is None:
        return None
    if not payload:
        return Empty()  # an empty payload is a cached Empty: valid, and cached normally
    value = _decode(engine, request, payload)
    if value is None:
        return None
    if not request.codec.covers(value):
        engine.wiring.counters.incr(CACHE_NOT_COVERING, _stage(request))
        return None
    return Ok(value)


async def _fetch[T](engine: Engine, request: Request[T], deadline: float) -> Outcome[bytes]:
    outcome = await _attempt(engine, request, deadline)
    if isinstance(outcome, TransportFailure) and engine.wiring.clock.monotonic() < deadline:
        engine.wiring.counters.incr(UPSTREAM_RETRY, _stage(request))
        outcome = await _attempt(engine, request, deadline)  # the only retry, in the wrapper
    if isinstance(outcome, Ok | Empty):
        await _store(engine, request, outcome)
    return outcome


async def _attempt[T](engine: Engine, request: Request[T], deadline: float) -> Outcome[bytes]:
    wiring = engine.wiring
    stage = _stage(request)
    decision = wiring.gate.admit(engine.provider, request.key, wiring.clock.monotonic())
    if not isinstance(decision, Allow):
        wiring.counters.incr(GATE_BLOCKED, stage)
        return _blocked(decision, wiring.clock.monotonic())
    if not await wiring.gate.pace(engine.provider, deadline):
        wiring.counters.incr(PACE_EXCEEDED, stage)
        return TransportFailure()
    outcome = await request.inner(deadline)
    wiring.counters.incr(UPSTREAM_CALL, stage)
    wiring.gate.record(
        engine.provider,
        request.key,
        _class_of(outcome),
        _retry_after(outcome),
        wiring.clock.monotonic(),
    )
    return _encoded(engine, request, outcome)


async def _store[T](engine: Engine, request: Request[T], outcome: Ok[bytes] | Empty) -> None:
    payload = outcome.value if isinstance(outcome, Ok) else b""
    await engine.wiring.store.put(request.key, payload, engine.wiring.clock.now() + engine.ttl)


def _blocked(decision: GateDecision, now: float) -> Outcome[bytes]:
    """Answer a blocked attempt at once, so the caller is never held."""
    if isinstance(decision, CoolingDown):
        return QuotaOrUnavailable(retry_after_s=max(0.0, decision.until - now))
    if isinstance(decision, NegativeCached):
        return TransportFailure()  # the cached failure, without touching the provider
    return QuotaOrUnavailable()  # Saturated: this provider's concurrency is full


def _class_of[T](outcome: Outcome[T]) -> OutcomeClass:
    if isinstance(outcome, Ok):
        return OutcomeClass.OK
    if isinstance(outcome, Empty):
        return OutcomeClass.EMPTY
    if isinstance(outcome, Malformed):
        return OutcomeClass.MALFORMED
    if isinstance(outcome, TransportFailure):
        return OutcomeClass.TRANSPORT_FAILURE
    return OutcomeClass.QUOTA_OR_UNAVAILABLE


def _retry_after[T](outcome: Outcome[T]) -> float | None:
    return outcome.retry_after_s if isinstance(outcome, QuotaOrUnavailable) else None


def _encoded[T](engine: Engine, request: Request[T], outcome: Outcome[T]) -> Outcome[bytes]:
    """Turn a value into the bytes the single flight carries.

    A value that cannot be encoded cannot cross the port's bytes channel at all, so the
    wrapper reports `Malformed` - the answer was not the shape we require - and counts it.
    It is never retried, because retrying would not change it.
    """
    if not isinstance(outcome, Ok):
        return outcome
    try:
        return Ok(request.codec.encode(outcome.value))
    except CODEC_ERRORS:
        engine.wiring.counters.incr(CACHE_UNWRITABLE, _stage(request))
        return Malformed()


def _decoded[T](engine: Engine, request: Request[T], outcome: Outcome[bytes]) -> Outcome[T]:
    if not isinstance(outcome, Ok):
        return outcome
    value = _decode(engine, request, outcome.value)
    return Ok(value) if value is not None else Malformed()


def _decode[T](engine: Engine, request: Request[T], payload: bytes) -> T | None:
    try:
        return request.codec.decode(payload)
    except CODEC_ERRORS:
        engine.wiring.counters.incr(CACHE_UNREADABLE, _stage(request))
        return None
