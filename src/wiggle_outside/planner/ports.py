"""What the planner needs from the outside world (CONTRACTS section 4).

Protocols are owned by the consumer (PLAN section 7). The planner never sees caching: WP4
wraps WP3 adapters and returns the same port types (section 4.1).
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import datetime

    from wiggle_outside.core.result import Outcome, OutcomeClass
    from wiggle_outside.core.types import (
        Activity,
        Answers,
        Coordinates,
        GeocodeHits,
        Hook,
        Place,
        PlanResult,
        Reason,
        TypedPlace,
        WeatherWindow,
    )

# --- Model request and raw output --------------------------------------------------


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """Built only by the planner. Carries no place names, coordinates or OSM free text."""

    prompt_version: str
    schema_version: str
    pairs_block: str
    vocabulary_block: str
    family_text_block: str


@dataclass(frozen=True, slots=True)
class RawSelection:
    """Untrusted parsed JSON. Only core.ideas turns this into Pick and Interests."""

    payload: str


# --- Provider and model ports ------------------------------------------------------


class Geocoder(Protocol):
    async def resolve(self, place: TypedPlace, deadline: float) -> Outcome[GeocodeHits]: ...


class PlacesProvider(Protocol):
    async def nearby(
        self,
        at: Coordinates,
        radius_m: int,
        kinds: frozenset[str],
        deadline: float,
    ) -> Outcome[tuple[Place, ...]]: ...


class WeatherProvider(Protocol):
    async def window(
        self,
        at: Coordinates,
        start: datetime,
        end: datetime,
        deadline: float,
    ) -> Outcome[WeatherWindow]: ...


class Ranker(Protocol):
    async def select(self, request: ModelRequest, deadline: float) -> Outcome[RawSelection]: ...


class Catalogue(Protocol):
    def activities(self) -> tuple[Activity, ...]: ...
    def hooks(self) -> tuple[Hook, ...]: ...
    def reasons(self) -> tuple[Reason, ...]: ...


class Clock(Protocol):
    def now(self) -> datetime: ...
    def monotonic(self) -> float: ...


# --- Cache, single flight and provider gate (section 4.1, WP4) ---------------------


class CacheNamespace(StrEnum):
    GEOCODE = "geocode"
    PLACES = "places"
    WEATHER = "weather"


class ProviderName(StrEnum):
    NOMINATIM = "nominatim"
    OVERPASS = "overpass"
    OPEN_METEO = "open_meteo"


@dataclass(frozen=True, slots=True)
class CacheKey:
    """Every input that affects the result (ARCHITECTURE section 15)."""

    namespace: CacheNamespace
    provider: ProviderName
    params: tuple[tuple[str, str], ...]  # normalised, sorted; coordinates rounded
    schema_version: int

    def digest(self) -> str:
        """SHA-256 hex of a canonical encoding."""
        raise NotImplementedError


class CacheStore(Protocol):
    """SQLite on the DB thread. Never raises to callers."""

    async def get(self, key: CacheKey, now: datetime) -> bytes | None: ...
    async def put(self, key: CacheKey, payload: bytes, fresh_until: datetime) -> None: ...


@dataclass(frozen=True, slots=True)
class Allow:
    """The attempt may proceed."""


@dataclass(frozen=True, slots=True)
class CoolingDown:
    until: float


@dataclass(frozen=True, slots=True)
class NegativeCached:
    until: float


@dataclass(frozen=True, slots=True)
class Saturated:
    """Provider concurrency is full."""


type GateDecision = Allow | CoolingDown | NegativeCached | Saturated


class ProviderGate(Protocol):
    """In memory, independent of SQLite (BACKEND-CONTRACT section 6)."""

    def admit(self, provider: ProviderName, key: CacheKey, now: float) -> GateDecision: ...

    def record(
        self,
        provider: ProviderName,
        key: CacheKey,
        outcome: OutcomeClass,
        retry_after_s: float | None,
        now: float,
    ) -> None: ...

    async def pace(self, provider: ProviderName, deadline: float) -> bool: ...


class SingleFlight(Protocol):
    """One fetch per key.

    The last waiter leaving cancels it, cancelled fetches never reach the cache, and
    joiners never extend the first caller's fetch deadline.
    """

    async def run(
        self,
        key: CacheKey,
        fetch_deadline: float,
        caller_deadline: float,
        fetch: Callable[[float], Awaitable[Outcome[bytes]]],
    ) -> Outcome[bytes]: ...


class Counters(Protocol):
    """Stage counters. No answers, no coordinates."""

    def incr(self, name: str, stage: str) -> None: ...


# --- Planner service (section 4.2) -------------------------------------------------


@dataclass(frozen=True, slots=True)
class JobRef:
    job_id: str
    joined: bool


class NotFound(Exception):  # noqa: N818  name fixed by CONTRACTS section 4.2
    """Ownership failure. Indistinguishable from an unknown ID (CONTRACTS section 3)."""


class Busy(Exception):  # noqa: N818  name fixed by CONTRACTS section 4.2
    """Admission failure."""

    def __init__(self, retry_after_s: float | None = None) -> None:
        super().__init__("planner busy")
        self.retry_after_s = retry_after_s


class Conflict(Exception):  # noqa: N818  name fixed by CONTRACTS section 4.2
    """Same idempotency key, different submission fingerprint."""


class PlannerService(Protocol):
    """The only way web depends on planner, so routes can use a fake."""

    async def start_or_join(self, session_id: str, key: str, answers: Answers) -> JobRef: ...

    async def choose_location(self, session_id: str, candidate_id: str) -> JobRef: ...

    async def wait(self, session_id: str, job_id: str) -> PlanResult: ...

    def get(self, session_id: str, job_id: str) -> PlanResult | None: ...
