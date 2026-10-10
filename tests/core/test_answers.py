"""The constraints derived from the answers: window (D35), energy ceiling (D18), invariants."""

import dataclasses
import itertools
from datetime import UTC, datetime, timedelta

import pytest
from support import ALL_BANDS, ALL_ENERGIES, KIDS_ANSWERS, SOLO_ANSWERS

from wiggle_outside.core.answers import (
    OutingWindow,
    allowed_energies,
    answers_outcome,
    constraints,
    is_gentler_than_asked,
    outing_window,
)
from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import AgeBand, Energy, TimeBudget, Who

PLANNED_START = datetime(2026, 10, 10, 8, 31, tzinfo=UTC)


def band_sets() -> list[frozenset[AgeBand]]:
    """Every non-empty combination of age bands (15 of them)."""
    return [
        frozenset(combination)
        for size in range(1, len(ALL_BANDS) + 1)
        for combination in itertools.combinations(ALL_BANDS, size)
    ]


# --- the outing window --------------------------------------------------------------


@pytest.mark.parametrize(
    ("budget", "minutes"),
    [(TimeBudget.M30, 30), (TimeBudget.H1, 60), (TimeBudget.H2, 120), (TimeBudget.HALF_DAY, 240)],
)
def test_the_window_is_the_budget_from_the_admission_time(budget: TimeBudget, minutes: int) -> None:
    window = outing_window(PLANNED_START, budget)
    assert window.start == PLANNED_START
    assert window.end == PLANNED_START + timedelta(minutes=minutes)
    assert window.minutes == minutes


def test_half_a_day_is_four_hours() -> None:
    # D35, accepted: nothing else may stand in for "half day".
    assert TimeBudget.HALF_DAY.value == 240
    assert outing_window(PLANNED_START, TimeBudget.HALF_DAY).minutes == 4 * 60


def test_window_minutes_rounds_to_whole_minutes() -> None:
    window = OutingWindow(start=PLANNED_START, end=PLANNED_START + timedelta(seconds=90))
    assert window.minutes == 2


# --- the energy ceiling (D18) -------------------------------------------------------


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        (Energy.GENTLE, {Energy.GENTLE}),
        (Energy.MODERATE, {Energy.GENTLE, Energy.MODERATE}),
        (Energy.ENERGETIC, {Energy.GENTLE, Energy.MODERATE, Energy.ENERGETIC}),
    ],
)
def test_the_requested_level_is_a_ceiling(requested: Energy, expected: set[Energy]) -> None:
    assert allowed_energies(requested) == expected


@pytest.mark.parametrize("requested", ALL_ENERGIES)
def test_the_requested_level_is_always_allowed(requested: Energy) -> None:
    assert requested in allowed_energies(requested)
    assert not is_gentler_than_asked(requested, requested)


@pytest.mark.parametrize(("weaker", "stronger"), list(itertools.combinations(ALL_ENERGIES, 2)))
def test_a_weaker_level_is_gentler_than_asked(weaker: Energy, stronger: Energy) -> None:
    assert is_gentler_than_asked(stronger, weaker)
    assert not is_gentler_than_asked(weaker, stronger)
    assert weaker in allowed_energies(stronger)
    assert stronger not in allowed_energies(weaker)


# --- the who / age-band invariant ---------------------------------------------------


@pytest.mark.parametrize("bands", band_sets())
def test_kids_with_any_band_combination_are_valid(bands: frozenset[AgeBand]) -> None:
    answers = dataclasses.replace(KIDS_ANSWERS, age_bands=bands)
    assert answers_outcome(answers) is None


def test_kids_without_a_band_are_invalid() -> None:
    answers = dataclasses.replace(KIDS_ANSWERS, age_bands=frozenset())
    assert answers_outcome(answers) is ErrorCode.INPUT_INVALID


@pytest.mark.parametrize("bands", band_sets())
def test_solo_with_any_band_is_invalid(bands: frozenset[AgeBand]) -> None:
    answers = dataclasses.replace(SOLO_ANSWERS, age_bands=bands)
    assert answers_outcome(answers) is ErrorCode.INPUT_INVALID


def test_solo_without_bands_is_valid() -> None:
    assert answers_outcome(SOLO_ANSWERS) is None


# --- the whole derivation -----------------------------------------------------------


def test_constraints_carry_the_answers_through() -> None:
    answers = dataclasses.replace(KIDS_ANSWERS, stroller=True, step_free=True)
    derived = constraints(answers, PLANNED_START)
    assert derived.window == outing_window(PLANNED_START, answers.time_budget)
    assert derived.budget_min == answers.time_budget.value
    assert derived.age_bands == answers.age_bands
    assert derived.energy is answers.energy
    assert derived.with_kids
    assert derived.stroller
    # D42 P: step-free travels as a preference, never as a filter.
    assert derived.prefer_step_free


def test_a_solo_run_is_not_with_kids() -> None:
    derived = constraints(SOLO_ANSWERS, PLANNED_START)
    assert not derived.with_kids
    assert derived.age_bands == frozenset()
    assert SOLO_ANSWERS.who is Who.SOLO
