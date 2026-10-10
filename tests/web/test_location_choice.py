"""POST /location-choice: one job per candidate, and one uniform 422 for everything else.

CONTRACTS section 3: unknown, forged, from another session, expired or already removed
all answer the same 422 LOCATION_CHOICE_EXPIRED with the manual-entry form, so nothing
about another session is revealed. A POST here never answers 404.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final

import pytest
from web_support import FixedPlanner, Harness, build_harness, one_idea, plan_result

from wiggle_outside.core.types import (
    AgeBand,
    Answers,
    Energy,
    JobState,
    LocationCandidate,
    LocationCandidates,
    TimeBudget,
    TypedPlace,
    Who,
)

if TYPE_CHECKING:
    import httpx

    from wiggle_outside.web.security import Session

ANSWERS: Final = Answers(
    who=Who.KIDS,
    age_bands=frozenset({AgeBand.B3_5}),
    time_budget=TimeBudget.H1,
    energy=Energy.MODERATE,
    location=TypedPlace(text="Bergby"),
    stroller=False,
    step_free=False,
)


def _candidates(*, minutes: int = 10) -> LocationCandidates:
    return LocationCandidates(
        candidates=(
            LocationCandidate(candidate_id="cand-1", label="Bergby, Uppsala", coords=_at()),
            LocationCandidate(candidate_id="cand-2", label="Bergby, Gavle", coords=_at()),
        ),
        answers=ANSWERS,
        expires_at=datetime.now(UTC) + timedelta(minutes=minutes),
    )


def _at() -> object:
    from wiggle_outside.core.types import Coordinates  # noqa: PLC0415

    return Coordinates(lat=60.12, lon=17.9)


@pytest.fixture
def ambiguous() -> Iterator[Harness]:
    """Build a session whose job needs a location choice, with a live set."""
    planner = FixedPlanner(
        result=plan_result(job_id="job-amb", state=JobState.NEEDS_LOCATION_CHOICE),
        choice=plan_result(job_id="job-choice", ideas=(one_idea(),)),
    )
    yield from build_harness(planner)


def _session(harness: Harness) -> Session:
    return next(iter(harness.sessions))


def _choose(harness: Harness, candidate_id: str) -> httpx.Response:
    tokens = harness.start()
    return harness.post(
        "/location-choice",
        {"csrf_token": tokens["csrf_token"], "candidate_id": candidate_id},
    )


def test_choosing_a_live_candidate_starts_one_job(ambiguous: Harness) -> None:
    ambiguous.plan()
    _session(ambiguous).candidates = _candidates()

    chosen = _choose(ambiguous, "cand-1")

    assert chosen.status_code == 303
    assert chosen.headers["location"] == "/results/job-choice"


def test_repeating_a_consumed_candidate_returns_the_same_job_with_no_new_work(
    ambiguous: Harness,
) -> None:
    ambiguous.plan()
    _session(ambiguous).candidates = _candidates()
    first = _choose(ambiguous, "cand-1")
    calls = len(ambiguous.planner.calls)  # type: ignore[attr-defined]

    second = _choose(ambiguous, "cand-1")

    assert second.status_code == 303
    assert second.headers["location"] == first.headers["location"]
    assert len(ambiguous.planner.calls) == calls  # type: ignore[attr-defined]


def test_a_consumed_choice_redirects_the_original_result(ambiguous: Harness) -> None:
    ambiguous.plan()
    _session(ambiguous).candidates = _candidates()
    _choose(ambiguous, "cand-1")

    shown = ambiguous.client.get("/results/job-amb", follow_redirects=False)

    assert shown.status_code == 303
    assert shown.headers["location"] == "/results/job-choice"


def test_an_unconsumed_choice_shows_the_choice_page(ambiguous: Harness) -> None:
    ambiguous.plan()
    _session(ambiguous).candidates = _candidates()

    shown = ambiguous.client.get("/results/job-amb")

    assert shown.status_code == 200
    assert "Bergby, Uppsala" in shown.text
    assert 'action="/location-choice"' in shown.text


# --- The uniform 422 ----------------------------------------------------------------


def test_an_unknown_candidate_is_a_422_with_the_manual_entry_form(
    ambiguous: Harness,
) -> None:
    ambiguous.plan()
    _session(ambiguous).candidates = _candidates()

    refused = _choose(ambiguous, "cand-9")

    assert refused.status_code == 422
    assert 'action="/plan"' in refused.text
    assert "Bergby" in refused.text  # the other answers are retained


def test_an_expired_candidate_set_is_the_same_422(ambiguous: Harness) -> None:
    ambiguous.plan()
    _session(ambiguous).candidates = _candidates(minutes=-1)

    refused = _choose(ambiguous, "cand-1")

    assert refused.status_code == 422


def test_a_candidate_from_another_session_is_the_same_422(ambiguous: Harness) -> None:
    ambiguous.plan()
    _session(ambiguous).candidates = _candidates()
    ambiguous.client.cookies.clear()

    refused = _choose(ambiguous, "cand-1")  # a new session, which owns no candidates

    assert refused.status_code == 422


def test_every_non_live_candidate_answers_the_same_way(ambiguous: Harness) -> None:
    ambiguous.plan()
    bodies: set[int] = set()
    for candidate_id in ("", "cand-9", "../../etc", "x" * 200):
        _session(ambiguous).candidates = _candidates()
        refused = _choose(ambiguous, candidate_id)
        assert refused.status_code == 422
        bodies.add(len(refused.text))

    assert len(bodies) == 1, "the 422 bodies differ, so they reveal which case it was"


def test_a_candidate_with_no_set_at_all_is_the_same_422(ambiguous: Harness) -> None:
    ambiguous.plan()

    refused = _choose(ambiguous, "cand-1")

    assert refused.status_code == 422


def test_an_unknown_field_in_a_choice_is_refused(ambiguous: Harness) -> None:
    ambiguous.plan()
    _session(ambiguous).candidates = _candidates()
    tokens = ambiguous.start()

    refused = ambiguous.post(
        "/location-choice",
        {
            "csrf_token": tokens["csrf_token"],
            "candidate_id": "cand-1",
            "idempotency_key": "client-supplied",
        },
    )

    assert refused.status_code == 422


def test_a_choice_needs_the_csrf_token(ambiguous: Harness) -> None:
    ambiguous.plan()
    _session(ambiguous).candidates = _candidates()

    refused = ambiguous.post("/location-choice", {"candidate_id": "cand-1"})

    assert refused.status_code == 403


def test_a_different_candidate_from_the_same_set_starts_its_own_job(
    ambiguous: Harness,
) -> None:
    ambiguous.plan()
    _session(ambiguous).candidates = _candidates()
    _choose(ambiguous, "cand-1")

    second = _choose(ambiguous, "cand-2")

    assert second.status_code == 303
    assert ambiguous.planner.calls.count("choose_location") == 2  # type: ignore[attr-defined]
