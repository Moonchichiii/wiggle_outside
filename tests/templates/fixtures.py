"""Fixture view models for the form page states (DESIGN-SPEC section 12).

CONTRACTS section 8 says the shared fixtures live in `tests/fixtures/`; WP0 has not
created them yet, so WP8 keeps its own here and will move to the shared ones when they
land. The data is the WALKTHROUGH.md journey: Bergby, Uppsala lan, Sweden.
"""

from datetime import UTC, datetime
from typing import Final

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import (
    AgeBand,
    Answers,
    AnswersSummary,
    Coordinates,
    Energy,
    LocationCandidate,
    LocationCandidates,
    TimeBudget,
    TypedPlace,
    Who,
)
from wiggle_outside.web.views import AssetRef, SessionView

SESSION: Final = SessionView(
    csrf_token="csrf-fixture-token",  # noqa: S106 - a fixture token, not a credential.
    idempotency_key="idem-fixture-key",
)

# d39_enabled is a positional flag in the CONTRACTS section 8 signature; naming the two
# values keeps the calls readable.
D39_ON: Final = True
D39_OFF: Final = False

BERGBY: Final = Coordinates(lat=60.42, lon=17.31)

CARRIED_ANSWERS: Final = AnswersSummary(
    who=Who.KIDS,
    age_bands=frozenset({AgeBand.B3_5, AgeBand.B6_9}),
    time_budget=TimeBudget.H1,
    energy=Energy.MODERATE,
    location=BERGBY,
    location_label="Bergby, Uppsala lan, Sweden",
    stroller=False,
    step_free=True,
)

# The approved error mock: ages missing and no location given.
FORM_ERRORS: Final[dict[str, ErrorCode]] = {
    "age_band": ErrorCode.INPUT_INVALID,
    "place": ErrorCode.INPUT_INVALID,
}

_AMBIGUOUS_ANSWERS: Final = Answers(
    who=Who.KIDS,
    age_bands=frozenset({AgeBand.B3_5, AgeBand.B6_9}),
    time_budget=TimeBudget.H1,
    energy=Energy.MODERATE,
    location=TypedPlace(text="Bergby"),
    stroller=False,
    step_free=False,
)

CANDIDATES: Final = LocationCandidates(
    candidates=(
        LocationCandidate(
            candidate_id="c1",
            label="Bergby, Gavleborg, Sweden",
            coords=Coordinates(lat=60.72, lon=17.08),
        ),
        LocationCandidate(
            candidate_id="c2",
            label="Bergby, Uppsala lan, Sweden",
            coords=BERGBY,
        ),
        LocationCandidate(
            candidate_id="c3",
            label="Bergby, Aland, Finland",
            coords=Coordinates(lat=60.18, lon=20.37),
        ),
    ),
    answers=_AMBIGUOUS_ANSWERS,
    expires_at=datetime(2026, 10, 10, 10, 41, tzinfo=UTC),
)

# A stand-in build manifest: the real one arrives with the Bun build (WP9b).
STYLESHEET: Final[dict[str, AssetRef]] = {"app.css": AssetRef(url="/static/app.css", integrity="")}
