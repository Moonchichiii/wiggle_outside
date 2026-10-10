"""The provider gate, in memory: cooldowns, pacing, concurrency, negative cache.

BACKEND-CONTRACT section 6. None of this touches SQLite, so a database failure cannot
cause a stampede. Every HTTP attempt passes `admit` and `pace`, and every attempt that
happened is `record`ed, including the one retry the wrapper may make.
"""

import asyncio
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from wiggle_outside.core.result import OutcomeClass
from wiggle_outside.planner.ports import (
    Allow,
    CoolingDown,
    GateDecision,
    NegativeCached,
    ProviderName,
    Saturated,
)
from wiggle_outside.storage.keys import digest_of

if TYPE_CHECKING:
    from collections.abc import Mapping

    from wiggle_outside.planner.ports import CacheKey, Clock

MIN_COOLDOWN_S: Final = 60.0
NEGATIVE_TTL_S: Final = 60.0
NOMINATIM_INTERVAL_S: Final = 1.0

# An admitted attempt holds its slot for at most the providers stage budget
# (settings.PROVIDERS_BUDGET_S), so a slot cannot leak when `pace` runs out of deadline or
# the caller is cancelled before `record`.
LEASE_S: Final = 4.0

# One timestamp per provider costs nothing; the per-key negative cache is bounded.
MAX_NEGATIVE_ENTRIES: Final = 1_000


@dataclass(frozen=True, slots=True)
class ProviderLimits:
    """Pacing is ARCHITECTURE section 7 (Nominatim 1 request/s, app-wide).

    Concurrency is a starting value: no document fixes it, and D21 runs one worker.
    """

    min_interval_s: float
    max_in_flight: int


FALLBACK_LIMITS: Final = ProviderLimits(min_interval_s=0.0, max_in_flight=2)
DEFAULT_LIMITS: Final[Mapping[ProviderName, ProviderLimits]] = MappingProxyType(
    {
        ProviderName.NOMINATIM: ProviderLimits(
            min_interval_s=NOMINATIM_INTERVAL_S, max_in_flight=1
        ),
        ProviderName.OVERPASS: FALLBACK_LIMITS,
        ProviderName.OPEN_METEO: FALLBACK_LIMITS,
    }
)


@dataclass(slots=True)
class _Negative:
    """A failed key. `retries_left` is the one retry pass described in `_arm_negative`."""

    until: float
    retries_left: int


class MemoryGate:
    """ProviderGate (CONTRACTS section 4.1), independent of SQLite."""

    def __init__(
        self,
        clock: Clock,
        *,
        limits: Mapping[ProviderName, ProviderLimits] = DEFAULT_LIMITS,
        lease_s: float = LEASE_S,
    ) -> None:
        self._clock = clock
        self._limits = limits
        self._lease_s = lease_s
        self._cooldown: dict[ProviderName, float] = {}
        self._negative: dict[str, _Negative] = {}
        self._leases: dict[ProviderName, list[float]] = {}
        self._next_turn: dict[ProviderName, float] = {}
        self._pace_locks: dict[ProviderName, asyncio.Lock] = {}

    def cooldown_until(self, provider: ProviderName) -> float:
        """When this provider's cooldown ends; 0.0 when there is none."""
        return self._cooldown.get(provider, 0.0)

    def next_turn_at(self, provider: ProviderName) -> float:
        """Report the earliest monotonic time pacing allows this provider to be called."""
        return self._next_turn.get(provider, 0.0)

    def admit(self, provider: ProviderName, key: CacheKey, now: float) -> GateDecision:
        cooling = self._cooldown.get(provider, 0.0)
        if cooling > now:
            return CoolingDown(until=cooling)  # fail fast: the caller is never held
        cached = self._negative_decision(digest_of(key), now)
        if cached is not None:
            return cached
        leases = self._live_leases(provider, now)
        if len(leases) >= self._limits.get(provider, FALLBACK_LIMITS).max_in_flight:
            return Saturated()
        leases.append(now + self._lease_s)
        return Allow()

    def record(
        self,
        provider: ProviderName,
        key: CacheKey,
        outcome: OutcomeClass,
        retry_after_s: float | None,
        now: float,
    ) -> None:
        self._release(provider, now)
        digest = digest_of(key)
        if outcome is OutcomeClass.QUOTA_OR_UNAVAILABLE:
            # max(60 s, Retry-After): no cap below the delay the provider asked for.
            self._cooldown[provider] = now + max(MIN_COOLDOWN_S, retry_after_s or 0.0)
        elif outcome is OutcomeClass.TRANSPORT_FAILURE:
            self._arm_negative(digest, now)
        elif outcome in {OutcomeClass.OK, OutcomeClass.EMPTY}:
            self._negative.pop(digest, None)

    async def pace(self, provider: ProviderName, deadline: float) -> bool:
        """Take this provider's turn. False means the deadline would pass first."""
        interval = self._limits.get(provider, FALLBACK_LIMITS).min_interval_s
        if interval <= 0.0:
            return True
        remaining = deadline - self._clock.monotonic()
        if remaining <= 0.0:
            return False
        try:
            async with asyncio.timeout(remaining):
                return await self._take_turn(provider, interval)
        except TimeoutError:
            return False

    async def _take_turn(self, provider: ProviderName, interval: float) -> bool:
        # One lock per provider, so pacing is application-wide and not per request.
        lock = self._pace_locks.setdefault(provider, asyncio.Lock())
        async with lock:
            wait = self._next_turn.get(provider, 0.0) - self._clock.monotonic()
            if wait > 0.0:
                await asyncio.sleep(wait)
            self._next_turn[provider] = self._clock.monotonic() + interval
            return True

    def _negative_decision(self, digest: str, now: float) -> GateDecision | None:
        entry = self._negative.get(digest)
        if entry is None or entry.until <= now:
            return None
        if entry.retries_left > 0:
            entry.retries_left -= 1
            return None
        return NegativeCached(until=entry.until)

    def _arm_negative(self, digest: str, now: float) -> None:
        """Negative-cache a transport failure for 60 s, keeping one retry pass.

        The entry is armed by the first failure but lets exactly one further attempt
        through, so "the one permitted retry is not blocked by its own first failure"
        (BACKEND-CONTRACT section 6) holds without the gate knowing the wrapper's retry
        policy. After the retry has failed too, the key is blocked for the full 60 s.
        """
        self._purge_negative(now)
        entry = self._negative.get(digest)
        if entry is None:
            self._negative[digest] = _Negative(until=now + NEGATIVE_TTL_S, retries_left=1)
            return
        entry.until = now + NEGATIVE_TTL_S
        entry.retries_left = 0

    def _purge_negative(self, now: float) -> None:
        self._negative = {
            digest: entry for digest, entry in self._negative.items() if entry.until > now
        }
        while len(self._negative) >= MAX_NEGATIVE_ENTRIES:
            del self._negative[min(self._negative, key=self._expiry_of)]

    def _expiry_of(self, digest: str) -> float:
        return self._negative[digest].until

    def _release(self, provider: ProviderName, now: float) -> None:
        leases = self._live_leases(provider, now)
        if leases:
            leases.pop(0)

    def _live_leases(self, provider: ProviderName, now: float) -> list[float]:
        leases = self._leases.setdefault(provider, [])
        leases[:] = [expires_at for expires_at in leases if expires_at > now]
        return leases
