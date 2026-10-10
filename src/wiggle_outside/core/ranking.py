"""Deterministic ranking (fallback and the H1 baseline).

Interest preference, energy match, distance and variety (PRODUCT-FIT section 3, D36), plus
the deterministic hook and reasons: the first allowed ID in the catalogue's own order.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from wiggle_outside.core.types import (
    MAX_IDEAS,
    MAX_REASONS,
    Activity,
    Energy,
    Idea,
    InterestTag,
    Pick,
)

if TYPE_CHECKING:
    from wiggle_outside.core.types import Pair

# Sort keys are "lower is better", so a match scores 0 and everything else 1.
PREFERRED: Final = 0
NOT_PREFERRED: Final = 1
GENERIC_DISTANCE_M: Final = 0


@dataclass(frozen=True, slots=True)
class RankingInputs:
    """What the ranking compares pairs against. Empty tags mean no interest preference."""

    activities: Mapping[str, Activity]
    energy: Energy
    tags: tuple[InterestTag, ...] = ()


def matches_tags(activity: Activity, tags: tuple[InterestTag, ...]) -> bool:
    """Say whether an entry carries any of the inferred tags (ranking only, never a filter)."""
    return any(tag in activity.interests for tag in tags)


def rank(pairs: tuple[Pair, ...], inputs: RankingInputs) -> tuple[Pair, ...]:
    """Order the eligible pairs deterministically. Equal pairs keep their build order."""
    by_key = {(*_key(pair, inputs), index): pair for index, pair in enumerate(pairs)}
    return tuple(by_key[key] for key in sorted(by_key))


def select(
    pairs: tuple[Pair, ...], inputs: RankingInputs, limit: int = MAX_IDEAS
) -> tuple[Pair, ...]:
    """Take the best pairs, never two with the same activity (D36). Fewer is allowed."""
    chosen: list[Pair] = []
    used: set[str] = set()
    for pair in rank(pairs, inputs):
        if pair.activity_id in used:
            continue
        chosen.append(pair)
        used.add(pair.activity_id)
        if len(chosen) == limit:
            break
    return tuple(chosen)


def first_allowed(ordered: tuple[str, ...], allowed: frozenset[str]) -> str | None:
    """Return the first ID the catalogue lists that this pair allows."""
    return next((value for value in ordered if value in allowed), None)


def allowed_in_order(
    ordered: tuple[str, ...], allowed: frozenset[str], limit: int
) -> tuple[str, ...]:
    return tuple(value for value in ordered if value in allowed)[:limit]


def deterministic_pick(
    pair: Pair,
    hook_order: tuple[str, ...],
    reason_order: tuple[str, ...],
) -> Pick | None:
    """Choose the hook and reasons code would choose. None when no hook is allowed."""
    hook_id = first_allowed(hook_order, pair.allowed_hook_ids)
    if hook_id is None:
        return None
    return Pick(
        pair_id=pair.pair_id,
        hook_id=hook_id,
        reason_ids=allowed_in_order(reason_order, pair.allowed_reason_ids, MAX_REASONS),
    )


def deterministic_ideas(
    pairs: tuple[Pair, ...],
    hook_order: tuple[str, ...],
    reason_order: tuple[str, ...],
) -> tuple[Idea, ...]:
    """Build the fallback ideas from already-ranked pairs, dropping any pair with no hook."""
    ideas: list[Idea] = []
    for pair in pairs:
        pick = deterministic_pick(pair, hook_order, reason_order)
        if pick is not None:
            ideas.append(Idea(pair=pair, hook_id=pick.hook_id, reason_ids=pick.reason_ids))
    return tuple(ideas)


def _key(pair: Pair, inputs: RankingInputs) -> tuple[int, int, int]:
    # PRODUCT-FIT names distance, energy match, season and variety but not their
    # order. This order is WP1's choice, pending review; season is already an
    # eligibility filter and variety is applied in `select`.
    activity = inputs.activities[pair.activity_id]
    interest = PREFERRED if matches_tags(activity, inputs.tags) else NOT_PREFERRED
    energy = PREFERRED if inputs.energy in activity.energy else NOT_PREFERRED
    # Generic pairs carry no destination, and they never share a run with placed pairs.
    distance = pair.distance_m if pair.distance_m is not None else GENERIC_DISTANCE_M
    return (interest, energy, distance)
