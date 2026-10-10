"""Quiz values and the constraints derived from them.

Pure derivations only (PLAN section 3): the outing window, the energy ceiling (D18) and
the who/age-band invariant. Nothing here reads a clock.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import AgeBand, Answers, Energy, TimeBudget, Who

# D18: the quiz value is a ceiling, so every weaker level is allowed too.
ENERGY_CEILING: Final[tuple[Energy, ...]] = (Energy.GENTLE, Energy.MODERATE, Energy.ENERGETIC)


@dataclass(frozen=True, slots=True)
class OutingWindow:
    """The outing itself: leave at `start`, be back by `end` (BACKEND-CONTRACT 2)."""

    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return round((self.end - self.start).total_seconds() / timedelta(minutes=1).total_seconds())


@dataclass(frozen=True, slots=True)
class Constraints:
    """What the eligibility and pairing rules need from one set of answers."""

    window: OutingWindow
    budget_min: int
    age_bands: frozenset[AgeBand]
    energy: Energy
    with_kids: bool
    stroller: bool
    # D42 P: step-free is a ranking preference, never a filter.
    prefer_step_free: bool


def outing_window(planned_start: datetime, budget: TimeBudget) -> OutingWindow:
    """Return the window a budget covers from its admission time (D35: half day = 4 h)."""
    return OutingWindow(planned_start, planned_start + timedelta(minutes=budget.value))


def allowed_energies(requested: Energy) -> frozenset[Energy]:
    """Return the requested level and every gentler one (D18)."""
    ceiling = ENERGY_CEILING.index(requested)
    return frozenset(ENERGY_CEILING[: ceiling + 1])


def is_gentler_than_asked(requested: Energy, offered: Energy) -> bool:
    """Say whether a pick is below the level asked for (notice GENTLER_THAN_ASKED)."""
    return ENERGY_CEILING.index(offered) < ENERGY_CEILING.index(requested)


def answers_outcome(answers: Answers) -> ErrorCode | None:
    """Return INPUT_INVALID when an invariant of `Answers` is broken (CONTRACTS section 2)."""
    with_kids = answers.who is Who.KIDS
    # Age bands are empty if and only if the run is solo.
    if with_kids != bool(answers.age_bands):
        return ErrorCode.INPUT_INVALID
    return None


def constraints(answers: Answers, planned_start: datetime) -> Constraints:
    """Turn answers plus the job's admission time into the constraints the rules use."""
    return Constraints(
        window=outing_window(planned_start, answers.time_budget),
        budget_min=answers.time_budget.value,
        age_bands=answers.age_bands,
        energy=answers.energy,
        with_kids=answers.who is Who.KIDS,
        stroller=answers.stroller,
        prefer_step_free=answers.step_free,
    )
