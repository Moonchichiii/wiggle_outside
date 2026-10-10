"""Which response a terminal result carries (CONTRACTS section 3, canonical).

A pure function over a `PlanResult`, so every row of the GET table can be asserted
without a request.
"""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import JobState, PlanResult
from wiggle_outside.web.security import (
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_SERVER_ERROR,
    HTTP_SERVICE_UNAVAILABLE,
    HTTP_UNPROCESSABLE,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


class PageKind(StrEnum):
    """Which page answers a result."""

    RESULTS = "results"  # the ideas, with any notices
    CHOICE = "choice"  # the form page with the candidate radios (LOCATION_AMBIGUOUS)
    FORM = "form"  # the form page, answers kept (LOCATION_NOT_FOUND)
    NOTICE = "notice"  # a notice or error page
    MISSING = "missing"  # 404, the same body as an unknown ID


@dataclass(frozen=True, slots=True)
class Outcome:
    status: int
    kind: PageKind
    code: ErrorCode | None = None


RESULTS: Final = Outcome(HTTP_OK, PageKind.RESULTS)
MISSING: Final = Outcome(HTTP_NOT_FOUND, PageKind.MISSING)

# Codes that are notices on a successful result, not a different status.
_RESULT_NOTICES: Final[frozenset[ErrorCode]] = frozenset(
    {
        ErrorCode.MODEL_FALLBACK,
        ErrorCode.FEWER_MATCHES,
        ErrorCode.PLACES_CACHED,
    }
)

# Evaluated, and nothing qualified: 200 with a notice (ERROR-HANDLING section 3).
_EVALUATED: Final[frozenset[ErrorCode]] = frozenset(
    {
        ErrorCode.NO_MATCHES,
        ErrorCode.WEATHER_RESTRICTED,
        ErrorCode.DAYLIGHT_NIGHT,
        ErrorCode.DAYLIGHT_TOO_SHORT,
    }
)

# A required service was unavailable, so nothing could be evaluated.
_UNAVAILABLE: Final[frozenset[ErrorCode]] = frozenset(
    {
        ErrorCode.WEATHER_UNAVAILABLE,
        ErrorCode.GEOCODER_UNAVAILABLE,
        ErrorCode.SERVICE_LIMIT_REACHED,
        ErrorCode.SERVICE_UNAVAILABLE,
        # Only without generic ideas; `outcome_for` checks the ideas first.
        ErrorCode.PLACES_UNAVAILABLE,
    }
)

_BY_CODE: Final[Mapping[ErrorCode, Outcome]] = MappingProxyType(
    {
        ErrorCode.LOCATION_NOT_FOUND: Outcome(
            HTTP_UNPROCESSABLE, PageKind.FORM, ErrorCode.LOCATION_NOT_FOUND
        ),
        ErrorCode.UNEXPECTED_FAILURE: Outcome(
            HTTP_SERVER_ERROR, PageKind.NOTICE, ErrorCode.UNEXPECTED_FAILURE
        ),
        **{code: Outcome(HTTP_OK, PageKind.NOTICE, code) for code in _EVALUATED},
        **{code: Outcome(HTTP_SERVICE_UNAVAILABLE, PageKind.NOTICE, code) for code in _UNAVAILABLE},
    }
)


def outcome_for(result: PlanResult) -> Outcome:
    """Map a terminal result to its status and page (CONTRACTS section 3, GET table)."""
    if result.state is JobState.EXPIRED:
        return MISSING
    if result.state is JobState.NEEDS_LOCATION_CHOICE:
        return Outcome(HTTP_OK, PageKind.CHOICE, ErrorCode.LOCATION_AMBIGUOUS)
    if result.state is JobState.FAILED:
        return _BY_CODE[ErrorCode.UNEXPECTED_FAILURE]
    return _by_code(result)


def _by_code(result: PlanResult) -> Outcome:
    code = result.error
    if code is None or code in _RESULT_NOTICES:
        return RESULTS
    # PLACES_UNAVAILABLE with eligible generic ideas is a successful, labelled result.
    if code is ErrorCode.PLACES_UNAVAILABLE and result.ideas:
        return RESULTS
    return _BY_CODE.get(code, Outcome(HTTP_OK, PageKind.NOTICE, code))
