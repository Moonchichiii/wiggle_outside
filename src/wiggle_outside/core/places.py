"""Candidate places, distance and place ranking.

Distance, travel and duration follow BACKEND-CONTRACT section 8; the caps (8 places,
12 pairs) are PLAN section 3. Step-free access ranks, never filters (D42 P).
"""

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from wiggle_outside.core.types import (
    MAX_PAIRS,
    MAX_PLACES,
    Activity,
    Coordinates,
    Pair,
    Place,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

EARTH_RADIUS_M: Final = 6_371_008.8
WALK_KMH_WITH_KIDS: Final = 3.0
WALK_KMH_ALONE: Final = 4.5
METRES_PER_KM: Final = 1000.0
MINUTES_PER_HOUR: Final = 60.0
ANY_PLACE_KIND: Final = "any"
GENERIC_TRAVEL_MIN: Final = 0


@dataclass(frozen=True, slots=True)
class PairPlan:
    """What pairing needs besides the catalogue entries and the candidate places."""

    origin: Coordinates
    budget_min: int
    with_kids: bool
    prefer_step_free: bool


@dataclass(frozen=True, slots=True)
class PairCandidate:
    """One (activity, place) combination that fits the budget. `place` None = generic."""

    activity: Activity
    place: Place | None
    distance_m: int | None
    travel_min: int
    duration_min: int


def distance_m(origin: Coordinates, destination: Coordinates) -> int:
    """Straight-line distance in whole metres; the card always labels it as such."""
    lat1, lon1 = math.radians(origin.lat), math.radians(origin.lon)
    lat2, lon2 = math.radians(destination.lat), math.radians(destination.lon)
    half_chord = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return round(EARTH_RADIUS_M * 2 * math.asin(math.sqrt(half_chord)))


def walking_speed_kmh(*, with_kids: bool) -> float:
    return WALK_KMH_WITH_KIDS if with_kids else WALK_KMH_ALONE


def travel_min(metres: int, *, with_kids: bool) -> int:
    """`travel = 2 x distance / speed`, rounded up: the estimate covers both ways."""
    hours = 2 * (metres / METRES_PER_KM) / walking_speed_kmh(with_kids=with_kids)
    return math.ceil(hours * MINUTES_PER_HOUR)


def fits_budget(*, budget_min: int, travel: int, minutes_min: int) -> bool:
    """BACKEND-CONTRACT section 8: the pair qualifies only if travel + min <= budget."""
    return travel + minutes_min <= budget_min


def selected_duration(*, budget_min: int, travel: int, minutes_min: int, minutes_max: int) -> int:
    """`selected_duration = clamp(budget - travel, min, max)`."""
    return max(minutes_min, min(budget_min - travel, minutes_max))


def is_usable(place: Place) -> bool:
    """D37 (b): a place tagged `fee=yes` is excluded; an unknown fee is kept, labelled."""
    return place.fee != "yes"


def reports_step_free(place: Place) -> bool:
    """OpenStreetMap reports step-free access. Reported, never verified (D42 P)."""
    return place.osm_access == "yes"


def place_kind_matches(activity: Activity, place: Place) -> bool:
    return ANY_PLACE_KIND in activity.place_kinds or place.kind in activity.place_kinds


def rank_places(places: tuple[Place, ...], plan: PairPlan) -> tuple[Place, ...]:
    """Rank usable places and cap them at 8. Step-free only ever moves a place up."""
    # The key ends in the opaque place ID, so no two places share one and the order is stable.
    by_key = {_place_key(place, plan): place for place in places if is_usable(place)}
    return tuple(by_key[key] for key in sorted(by_key)[:MAX_PLACES])


def pair_candidates(
    activities: tuple[Activity, ...],
    places: tuple[Place, ...],
    plan: PairPlan,
) -> tuple[PairCandidate, ...]:
    """Build at most 12 pairs from already-eligible entries, generic when no place is left."""
    ranked = rank_places(places, plan)
    if not ranked:
        return tuple(_generic_candidates(activities, plan))[:MAX_PAIRS]
    return tuple(_place_candidates(activities, ranked, plan))[:MAX_PAIRS]


def to_pairs(
    candidates: tuple[PairCandidate, ...],
    new_idea_id: Callable[[], str],
    allowed: Callable[[PairCandidate], tuple[frozenset[str], frozenset[str]]],
) -> tuple[Pair, ...]:
    """Return one `Pair` per candidate, numbered `p1`..`p12`, with an injected `idea_id`."""
    pairs: list[Pair] = []
    for index, candidate in enumerate(candidates, start=1):
        hook_ids, reason_ids = allowed(candidate)
        pairs.append(
            Pair(
                pair_id=f"p{index}",
                idea_id=new_idea_id(),
                activity_id=candidate.activity.activity_id,
                place=candidate.place,
                distance_m=candidate.distance_m,
                travel_min=candidate.travel_min,
                duration_min=candidate.duration_min,
                allowed_hook_ids=hook_ids,
                allowed_reason_ids=reason_ids,
            )
        )
    return tuple(pairs)


def _place_key(place: Place, plan: PairPlan) -> tuple[int, int, str]:
    step_free_first = 0 if plan.prefer_step_free and reports_step_free(place) else 1
    return (step_free_first, distance_m(plan.origin, place.coords), place.place_id)


def _generic_candidates(
    activities: tuple[Activity, ...], plan: PairPlan
) -> Iterator[PairCandidate]:
    for activity in activities:
        if not activity.generic_ok:
            continue
        if fits_budget(
            budget_min=plan.budget_min,
            travel=GENERIC_TRAVEL_MIN,
            minutes_min=activity.duration_min,
        ):
            yield PairCandidate(
                activity=activity,
                place=None,
                distance_m=None,
                travel_min=GENERIC_TRAVEL_MIN,
                duration_min=activity.duration_min,
            )


def _place_candidates(
    activities: tuple[Activity, ...],
    ranked: tuple[Place, ...],
    plan: PairPlan,
) -> Iterator[PairCandidate]:
    # One round per place keeps the 12 pairs spread over places and entries.
    by_place = {place.place_id: _for_place(activities, place, plan) for place in ranked}
    depth = max(len(by_place[place.place_id]) for place in ranked)
    for index in range(depth):
        for place in ranked:
            found = by_place[place.place_id]
            if index < len(found):
                yield found[index]


def _for_place(
    activities: tuple[Activity, ...],
    place: Place,
    plan: PairPlan,
) -> tuple[PairCandidate, ...]:
    metres = distance_m(plan.origin, place.coords)
    travel = travel_min(metres, with_kids=plan.with_kids)
    return tuple(
        PairCandidate(
            activity=activity,
            place=place,
            distance_m=metres,
            travel_min=travel,
            # One value until the catalogue carries `minutes = [min, max]` (CC-002):
            # with a min and a max this is `selected_duration(...)`.
            duration_min=activity.duration_min,
        )
        for activity in activities
        if place_kind_matches(activity, place)
        and fits_budget(
            budget_min=plan.budget_min,
            travel=travel,
            minutes_min=activity.duration_min,
        )
    )
