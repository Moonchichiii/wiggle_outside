"""Form fields and the submission fingerprint (CONTRACTS section 7).

A WP0 contract file: WP7 calls it, WP6 stores and compares what it returns.
Unknown field names and repeated scalar fields are rejected; so are values not listed.
"""

import hmac
import unicodedata
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Final

from wiggle_outside.core.types import (
    COORD_DP,
    INTEREST_TEXT_MAX,
    AgeBand,
    Energy,
    TimeBudget,
    Who,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# CONTRACTS section 7. The order is the canonical field order for the fingerprint.
PLAN_FIELDS: Final[tuple[str, ...]] = (
    "who",
    "age_band",
    "time",
    "energy",
    "location_mode",
    "place",
    "lat",
    "lon",
    "location_label",
    "stroller",
    "step_free",
    "interests_text",
)

# Present in the form but never part of the fingerprint (CONTRACTS section 7).
EXCLUDED_FROM_FINGERPRINT: Final[frozenset[str]] = frozenset(
    {
        "csrf_token",
        "idempotency_key",
        "hp_note",
    }
)

PLAN_FORM_FIELDS: Final[frozenset[str]] = frozenset(PLAN_FIELDS) | EXCLUDED_FROM_FINGERPRINT

LOCATION_CHOICE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "csrf_token",
        "candidate_id",
    }
)

REPEATABLE_FIELDS: Final[frozenset[str]] = frozenset({"age_band"})

# Values not listed are 422.
ALLOWED_VALUES: Final[Mapping[str, frozenset[str]]] = {
    "who": frozenset(w.value for w in Who),
    "age_band": frozenset(b.value for b in AgeBand),
    "time": frozenset(str(t.value) for t in TimeBudget),
    "energy": frozenset(e.value for e in Energy),
    "location_mode": frozenset({"typed", "coords"}),
    "stroller": frozenset({"1"}),
    "step_free": frozenset({"1"}),
}

DEFAULT_ENERGY: Final = Energy.MODERATE
DEFAULT_LOCATION_MODE: Final = "typed"
DEFAULT_LOCATION_LABEL: Final = "Your location"
MAX_BODY_BYTES: Final = 8 * 1024


@dataclass(frozen=True, slots=True)
class PlanSubmission:
    """A parsed, validated plan form. Built by WP7 from the request body."""

    csrf_token: str
    idempotency_key: str
    who: Who
    age_bands: frozenset[AgeBand]
    time_budget: TimeBudget
    energy: Energy
    location_mode: str
    place: str | None
    lat: float | None
    lon: float | None
    location_label: str | None
    stroller: bool
    step_free: bool
    interests_text: str | None


def canonical_form(values: Mapping[str, Sequence[str]]) -> bytes:
    """Normalise a plan submission to the bytes the fingerprint is taken over.

    CONTRACTS section 7: every plan field except csrf_token, idempotency_key and hp_note,
    in PLAN_FIELDS order, after NFC normalisation and whitespace trimming, with age bands
    sorted and de-duplicated, coordinates rounded, absent optional fields as empty
    strings, and including interests_text — so two submissions differing only in their
    interest text are different submissions.
    """
    parts: list[str] = []
    for name in PLAN_FIELDS:
        raw = values.get(name, ())
        if name in REPEATABLE_FIELDS:
            items = sorted({unicodedata.normalize("NFC", v).strip() for v in raw})
            parts.append(",".join(items))
            continue
        first = unicodedata.normalize("NFC", raw[0]).strip() if raw else ""
        if name in {"lat", "lon"} and first:
            first = f"{round(float(first), COORD_DP):.{COORD_DP}f}"
        if name == "interests_text":
            first = first[:INTEREST_TEXT_MAX]
        parts.append(first)
    return "\x1f".join(parts).encode()


def fingerprint(process_key: bytes, values: Mapping[str, Sequence[str]]) -> str:
    """HMAC-SHA256 over canonical_form, never dataclass hashing (CONTRACTS section 7).

    process_key is 32 random bytes created at startup and never stored. The result is
    kept with the idempotency record only, and is never logged, rendered or sent anywhere.
    """
    return hmac.new(process_key, canonical_form(values), sha256).hexdigest()


def candidate_key(candidate_id: str) -> str:
    """Derive the /location-choice submission key; it is never client-supplied."""
    return f"candidate:{candidate_id}"
