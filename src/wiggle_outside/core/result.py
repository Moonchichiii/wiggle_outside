"""Provider outcomes as values, not exceptions (CONTRACTS section 1, BACKEND-CONTRACT 6).

Cancellation propagates as asyncio.CancelledError and is never converted to an outcome.
"""

from dataclasses import dataclass
from enum import StrEnum


class OutcomeClass(StrEnum):
    """What a provider gate records about an attempt."""

    OK = "ok"
    EMPTY = "empty"
    MALFORMED = "malformed"
    TRANSPORT_FAILURE = "transport_failure"
    QUOTA_OR_UNAVAILABLE = "quota_or_unavailable"


@dataclass(frozen=True, slots=True)
class Ok[T]:
    value: T


@dataclass(frozen=True, slots=True)
class Empty:
    """The provider answered, and the answer was empty. Not a failure."""


@dataclass(frozen=True, slots=True)
class Malformed:
    """The body parsed as transport but not as the shape we require."""


@dataclass(frozen=True, slots=True)
class TransportFailure:
    """Connect, read, TLS or size failure. The only outcome the wrapper may retry."""


@dataclass(frozen=True, slots=True)
class QuotaOrUnavailable:
    """Provider said no: 4xx quota, 5xx, or an explicit Retry-After."""

    retry_after_s: float | None = None


type Outcome[T] = Ok[T] | Empty | Malformed | TransportFailure | QuotaOrUnavailable
