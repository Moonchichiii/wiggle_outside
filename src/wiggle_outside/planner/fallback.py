"""Deterministic ideas with template wording, and the notices a result carries.

The fallback is the labelled path of D44: the same eligible pairs, ranked by
`core.ranking`, with the first allowed hook and the first two true reasons in the
catalogue's own order (CONTRACTS section 4.2). It runs only on valid weather and eligible
pairs; the planner never reaches it otherwise.
"""

from typing import TYPE_CHECKING

from wiggle_outside.core.answers import is_gentler_than_asked
from wiggle_outside.core.errors import ErrorCode, NoticeId
from wiggle_outside.core.ranking import RankingInputs, deterministic_ideas, rank, select
from wiggle_outside.core.types import MAX_IDEAS, Energy, Idea, InterestOutcome, Interests, Pair

if TYPE_CHECKING:
    from collections.abc import Mapping

    from wiggle_outside.core.types import Activity
    from wiggle_outside.planner.ports import Catalogue


def hook_order(catalogue: Catalogue) -> tuple[str, ...]:
    return tuple(hook.hook_id for hook in catalogue.hooks())


def reason_order(catalogue: Catalogue) -> tuple[str, ...]:
    return tuple(reason.reason_id for reason in catalogue.reasons())


def fallback_ideas(
    pairs: tuple[Pair, ...], inputs: RankingInputs, catalogue: Catalogue
) -> tuple[Idea, ...]:
    """Rank, take at most three distinct activities, and give each its deterministic words."""
    chosen = select(rank(pairs, inputs), inputs, MAX_IDEAS)
    return deterministic_ideas(chosen, hook_order(catalogue), reason_order(catalogue))


def interest_notice(interests: Interests | None) -> NoticeId | None:
    """Return the one notice an interest outcome adds (DESIGN-SPEC section 6)."""
    if interests is None:
        return None
    by_outcome = {
        InterestOutcome.NO_MATCH: NoticeId.INTEREST_NO_MATCH,
        InterestOutcome.UNCLEAR: NoticeId.INTEREST_UNCLEAR,
        InterestOutcome.NOT_APPLIED: NoticeId.INTEREST_NOT_APPLIED,
    }
    return by_outcome.get(interests.outcome)


def result_notices(
    ideas: tuple[Idea, ...],
    activities: Mapping[str, Activity],
    requested: Energy,
    interests: Interests | None,
    *,
    fallback: bool,
) -> tuple[NoticeId | ErrorCode, ...]:
    """Return the notices a result with ideas carries, in display order."""
    notices: list[NoticeId | ErrorCode] = []
    if fallback:
        notices.append(ErrorCode.MODEL_FALLBACK)
        if interests is not None and interests.outcome is InterestOutcome.MATCHED:
            notices.append(NoticeId.INTERESTS_USED_BY_FALLBACK)
    if 0 < len(ideas) < MAX_IDEAS:
        notices.append(ErrorCode.FEWER_MATCHES)
    if any(_gentler(activities[idea.pair.activity_id], requested) for idea in ideas):
        notices.append(NoticeId.GENTLER_THAN_ASKED)
    extra = interest_notice(interests)
    if extra is not None:
        notices.append(extra)
    return tuple(notices)


def _gentler(activity: Activity, requested: Energy) -> bool:
    """D18: a pick is gentler than asked when the entry does not list the level asked for."""
    if requested in activity.energy:
        return False
    return any(is_gentler_than_asked(requested, level) for level in activity.energy)
