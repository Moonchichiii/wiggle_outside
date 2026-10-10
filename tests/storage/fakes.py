"""Fakes for the storage tests: a clock the test moves, and recording ports.

No sockets, no real providers and no sleeps: every race is driven by an event or by the
fake clock, so a test cannot pass because a sleep happened to be long enough.
"""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from wiggle_outside.core.result import Ok, Outcome, OutcomeClass
from wiggle_outside.core.types import WeatherWindow
from wiggle_outside.planner.ports import (
    CacheKey,
    CacheNamespace,
    GateDecision,
    ProviderGate,
    ProviderName,
)
from wiggle_outside.storage.keys import digest_of
from wiggle_outside.storage.wrapper import CacheWiring, Codec, Engine

START = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
TICK = 100.0


@dataclass(slots=True)
class FakeClock:
    """Wall and monotonic time the test moves by hand."""

    wall: datetime = START
    tick: float = TICK

    def now(self) -> datetime:
        return self.wall

    def monotonic(self) -> float:
        return self.tick

    def advance(self, seconds: float) -> None:
        self.wall += timedelta(seconds=seconds)
        self.tick += seconds


@dataclass(slots=True)
class RecordingCounters:
    events: list[tuple[str, str]] = field(default_factory=list)

    def incr(self, name: str, stage: str) -> None:
        self.events.append((name, stage))

    def count(self, name: str) -> int:
        return sum(1 for seen, _ in self.events if seen == name)

    def stages(self, name: str) -> list[str]:
        return [stage for seen, stage in self.events if seen == name]


@dataclass(slots=True)
class RecordingGate:
    """A real gate with the call sequence written down, so the order is checkable."""

    inner: ProviderGate
    calls: list[str] = field(default_factory=list)

    def admit(self, provider: ProviderName, key: CacheKey, now: float) -> GateDecision:
        decision = self.inner.admit(provider, key, now)
        self.calls.append(f"admit:{type(decision).__name__}")
        return decision

    def record(
        self,
        provider: ProviderName,
        key: CacheKey,
        outcome: OutcomeClass,
        retry_after_s: float | None,
        now: float,
    ) -> None:
        self.calls.append(f"record:{outcome.value}")
        self.inner.record(provider, key, outcome, retry_after_s, now)

    async def pace(self, provider: ProviderName, deadline: float) -> bool:
        allowed = await self.inner.pace(provider, deadline)
        self.calls.append(f"pace:{allowed}")
        return allowed


@dataclass(slots=True)
class ScriptedProvider:
    """One inner provider call per attempt. The last outcome repeats."""

    outcomes: Sequence[Outcome[bytes]]
    attempts: int = 0
    deadlines: list[float] = field(default_factory=list)

    async def __call__(self, deadline: float) -> Outcome[bytes]:
        self.attempts += 1
        self.deadlines.append(deadline)
        return self.outcomes[min(self.attempts - 1, len(self.outcomes) - 1)]


@dataclass(slots=True)
class GatedCall:
    """A call the test starts and finishes by hand, so no sleep decides a race."""

    started: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)
    outcome: Outcome[bytes] = field(default_factory=lambda: Ok(b"payload"))
    calls: int = 0
    finished: int = 0
    cancelled: int = 0
    deadlines: list[float] = field(default_factory=list)

    async def __call__(self, deadline: float) -> Outcome[bytes]:
        self.calls += 1
        self.deadlines.append(deadline)
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        self.finished += 1
        return self.outcome


@dataclass(slots=True)
class DictStore:
    """CacheStore without SQLite. `broken` is a cache that is simply unavailable."""

    broken: bool = False
    entries: dict[str, tuple[bytes, datetime]] = field(default_factory=dict)
    puts: int = 0
    gets: int = 0

    async def get(self, key: CacheKey, now: datetime) -> bytes | None:
        self.gets += 1
        if self.broken:
            return None
        found = self.entries.get(digest_of(key))
        if found is None or found[1] <= now:
            return None
        return found[0]

    async def put(self, key: CacheKey, payload: bytes, fresh_until: datetime) -> None:
        self.puts += 1
        if self.broken:
            return
        self.entries[digest_of(key)] = (payload, fresh_until)


async def until(condition: Callable[[], bool], *, yields: int = 100) -> None:
    """Yield to the event loop until the condition holds. No wall-clock time involved."""
    for _ in range(yields):
        if condition():
            return
        await asyncio.sleep(0)
    msg = f"the condition never held after {yields} turns of the event loop"
    raise AssertionError(msg)


def weather_window(start: datetime, end: datetime) -> WeatherWindow:
    """Build a minimal window: only its start and end matter to the coverage check."""
    return WeatherWindow(
        start=start,
        end=end,
        fetched_at=start,
        tz="Europe/Stockholm",
        times=(start, end),
        temp_c=(12.0, 13.0),
        apparent_temp_c=(11.0, 12.0),
        precip_probability=(5, 5),
        precipitation_mm=(0.0, 0.0),
        wind_kmh=(8.0, 9.0),
        weather_code=(0, 1),
        sunrise=start - timedelta(hours=3),
        sunset=end + timedelta(hours=5),
    )


def _identity(payload: bytes) -> bytes:
    return payload


BYTES_CODEC: Codec[bytes] = Codec(encode=_identity, decode=_identity)


def key_for(query: str = "home", namespace: CacheNamespace = CacheNamespace.PLACES) -> CacheKey:
    return CacheKey(
        namespace=namespace,
        provider=ProviderName.OVERPASS,
        params=(("q", query),),
        schema_version=1,
    )


def engine_for(wiring: CacheWiring, ttl: timedelta = timedelta(minutes=30)) -> Engine:
    return Engine(wiring=wiring, provider=ProviderName.OVERPASS, ttl=ttl)
