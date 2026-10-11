"""Ideas: the per-reason conditions, interest matches, and validation of model output.

Pure functions (PLAN section 3). `Reason.when` in hooks.toml is reviewer prose, not an
expression, so each reason's condition is implemented here (CC-003), and this is the only
module that turns untrusted model output into `Pick`s and `Interests`
(CONTRACTS section 4.2, BACKEND-CONTRACT section 7): invalid picks are dropped and the
valid ones kept, never repaired, never padded (D44).
"""

import json
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final, cast

from wiggle_outside.core.activities import fits_time, season_allows
from wiggle_outside.core.types import (
    MAX_IDEAS,
    MAX_REASONS,
    MAX_TAGS,
    Activity,
    AgeBand,
    Energy,
    InterestOutcome,
    Interests,
    InterestStatus,
    InterestTag,
    Pair,
    Pick,
)
from wiggle_outside.core.weather import DRY_MM, DRY_WINDOW_MAX_PCT, Samples, is_dry_window

if TYPE_CHECKING:
    from wiggle_outside.core.places import PairCandidate

# hooks.toml: "straight-line distance is 1 km or less".
CLOSE_BY_MAX_M: Final = 1000
# "two or more age bands were selected and the activity lists all of them".
ALL_AGES_MIN_BANDS: Final = 2

REASON_CLOSE_BY: Final = "close_by"
REASON_FITS_TIME: Final = "fits_time"
REASON_MATCHES_ENERGY: Final = "matches_energy"
REASON_DRY_WINDOW: Final = "dry_window"
REASON_RAIN_ALLOWED: Final = "rain_allowed"
REASON_ALL_AGES: Final = "all_ages"
REASON_IN_SEASON: Final = "in_season"


@dataclass(frozen=True, slots=True)
class ReasonContext:
    """What the reason conditions need from one run besides the pair itself."""

    budget_min: int
    energy: Energy
    age_bands: frozenset[AgeBand]
    samples: Samples
    local_date: date
    lat: float


def rain_is_likely(samples: Samples) -> bool:
    """Say whether some hour is wetter than the dry-window rule (its complement)."""
    return any(
        interval.probability > DRY_WINDOW_MAX_PCT or interval.precipitation_mm > DRY_MM
        for interval in samples.intervals
    )


def allowed_reason_ids(candidate: PairCandidate, context: ReasonContext) -> frozenset[str]:
    """Return the reason IDs whose `when` holds for this pair. Code decides, never the model."""
    activity = candidate.activity
    conditions = {
        REASON_CLOSE_BY: candidate.distance_m is not None
        and candidate.distance_m <= CLOSE_BY_MAX_M,
        REASON_FITS_TIME: fits_time(
            activity, budget_min=context.budget_min, travel_min=candidate.travel_min
        ),
        REASON_MATCHES_ENERGY: context.energy in activity.energy,
        REASON_DRY_WINDOW: is_dry_window(context.samples),
        REASON_RAIN_ALLOWED: activity.rain_ok and rain_is_likely(context.samples),
        REASON_ALL_AGES: len(context.age_bands) >= ALL_AGES_MIN_BANDS
        and context.age_bands <= activity.ages,
        REASON_IN_SEASON: bool(activity.seasons)
        and season_allows(activity.seasons, context.local_date, context.lat),
    }
    return frozenset(reason_id for reason_id, holds in conditions.items() if holds)


def matched_interests(activity: Activity, tags: tuple[InterestTag, ...]) -> tuple[InterestTag, ...]:
    """Return the validated tags this entry carries, in tag order (computed, not stored)."""
    return tuple(tag for tag in tags if tag in activity.interests)


# --- Model output -----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Selection:
    """What survived validation. `dropped` counts the picks that did not (never hidden)."""

    picks: tuple[Pick, ...]
    interests: Interests
    dropped: int


NOT_APPLIED: Final = Interests(tags=(), outcome=InterestOutcome.NOT_APPLIED)


def parse_selection(payload: str, pairs: tuple[Pair, ...]) -> Selection | None:
    """Validate one model output against the pairs it was offered (selection.v2).

    None means the output is off-schema as a whole (not an object, or `picks` missing or
    not a list): the planner then goes straight to the labelled fallback. Otherwise every
    pick is checked on its own: an unknown pair, a hook or reason the pair does not allow,
    duplicate reasons, too many reasons or a repeated activity drops that pick and keeps the
    rest (partial success, D44). An interests block that fails validation is reported as
    NOT_APPLIED: the picks still count, the interpretation does not.
    """
    try:
        decoded: object = json.loads(payload)
    except ValueError:
        return None
    if not isinstance(decoded, dict):
        return None
    fields = {str(key): value for key, value in cast("dict[object, object]", decoded).items()}
    raw_picks = fields.get("picks")
    if not isinstance(raw_picks, list):
        return None
    by_id = {pair.pair_id: pair for pair in pairs}
    picks: list[Pick] = []
    used: set[str] = set()
    dropped = 0
    for raw in cast("list[object]", raw_picks)[:MAX_IDEAS]:
        pick = _pick(raw, by_id)
        if pick is None or by_id[pick.pair_id].activity_id in used:
            dropped += 1  # D36: a repeated activity keeps the higher-ranked pick only
            continue
        used.add(by_id[pick.pair_id].activity_id)
        picks.append(pick)
    dropped += max(0, len(raw_picks) - MAX_IDEAS)
    interests = _interests(fields.get("interests"), fields.get("interest_status"))
    return Selection(picks=tuple(picks), interests=interests, dropped=dropped)


def _pick(raw: object, by_id: dict[str, Pair]) -> Pick | None:
    if not isinstance(raw, dict):
        return None
    entry = {str(key): value for key, value in cast("dict[object, object]", raw).items()}
    pair_id = entry.get("pair_id")
    hook_id = entry.get("hook_id")
    if not isinstance(pair_id, str) or not isinstance(hook_id, str):
        return None
    pair = by_id.get(pair_id)
    if pair is None or hook_id not in pair.allowed_hook_ids:
        return None
    reasons = _strings(entry.get("reason_ids"))
    if reasons is None or len(reasons) > MAX_REASONS or len(set(reasons)) != len(reasons):
        return None
    if any(reason not in pair.allowed_reason_ids for reason in reasons):
        return None
    return Pick(pair_id=pair_id, hook_id=hook_id, reason_ids=reasons)


def _interests(raw_tags: object, raw_status: object) -> Interests:
    if not isinstance(raw_status, str):
        return NOT_APPLIED
    try:
        status = InterestStatus(raw_status)
    except ValueError:
        return NOT_APPLIED
    names = _strings(raw_tags)
    if names is None or len(names) > MAX_TAGS or len(set(names)) != len(names):
        return NOT_APPLIED
    try:
        tags = tuple(InterestTag(name) for name in names)
    except ValueError:
        return NOT_APPLIED
    outcome = InterestOutcome(status.value)
    if outcome is InterestOutcome.MATCHED and not tags:
        # "Matched" with nothing to show is not an interpretation we can display.
        return Interests(tags=(), outcome=InterestOutcome.UNCLEAR)
    # Tags are shown only for a match (CONTRACTS section 2: empty unless MATCHED).
    return Interests(tags=tags if outcome is InterestOutcome.MATCHED else (), outcome=outcome)


def _strings(raw: object) -> tuple[str, ...] | None:
    if not isinstance(raw, list):
        return None
    items = cast("list[object]", raw)
    if any(not isinstance(item, str) for item in items):
        return None
    return tuple(item for item in items if isinstance(item, str))
