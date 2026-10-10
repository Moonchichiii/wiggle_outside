"""What CC-A, CC-B, CC-C and CC-D unblocked.

Each of these states was unrepresentable before `FormContext`, so each is asserted here
rather than left to the route tests that will eventually exercise them end to end.
"""

from datetime import UTC, datetime
from typing import Final

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import (
    AgeBand,
    Answers,
    AnswersSummary,
    Coordinates,
    DeploymentMode,
    Energy,
    InterestOutcome,
    Interests,
    InterestTag,
    LocationCandidate,
    LocationCandidates,
    TimeBudget,
    TypedPlace,
    Who,
)
from wiggle_outside.web.presenters import present_form
from wiggle_outside.web.views import AssetRef, FormContext, SessionView

SESSION: Final = SessionView(csrf_token="t", idempotency_key="k")  # noqa: S106


def _context(**kwargs: object) -> FormContext:
    """Build a context with the three required values plus whatever the test varies."""
    base: dict[str, object] = {
        "session": SESSION,
        "mode": DeploymentMode.LOCAL,
        "d39_enabled": True,
    }
    base.update(kwargs)
    return FormContext(**base)  # type: ignore[arg-type]


ANSWERS: Final = Answers(
    who=Who.KIDS,
    age_bands=frozenset({AgeBand.B3_5}),
    time_budget=TimeBudget.H1,
    energy=Energy.MODERATE,
    location=TypedPlace(text="Bergby"),
    stroller=False,
    step_free=False,
)

CARRIED: Final = AnswersSummary(
    who=Who.KIDS,
    age_bands=frozenset({AgeBand.B3_5}),
    time_budget=TimeBudget.H1,
    energy=Energy.MODERATE,
    location=Coordinates(lat=60.12, lon=17.9),
    location_label="Bergby",
    stroller=False,
    step_free=False,
)


# --- CC-A: a partial submission survives a re-render ------------------------------


def test_a_partial_submission_is_echoed_back() -> None:
    # ERROR-HANDLING section 2: a 422 keeps the answers that were given. Here "who" and
    # "time" were answered and the age bands were not, which is what made it a 422.
    page = present_form(
        _context(
            submitted={"who": "kids", "time": "120"},
            errors={"age_band": ErrorCode.INPUT_INVALID},
        )
    )
    assert [o.checked for o in page.who] == [False, True]
    assert [o.value for o in page.time if o.checked] == ["120"]
    assert not any(o.checked for o in page.ages)
    assert "age_band" in page.field_errors


def test_an_illegal_submitted_value_is_not_preselected() -> None:
    # The illegal value is why the request failed; echoing it as a checked control would
    # re-submit it. Nothing is selected, and the error is shown instead.
    page = present_form(
        _context(submitted={"who": "nobody"}, errors={"who": ErrorCode.INPUT_INVALID})
    )
    assert not any(o.checked for o in page.who)


def test_a_typed_place_that_failed_to_geocode_is_echoed() -> None:
    # Without this the field came back empty and the person had to retype the town.
    page = present_form(
        _context(
            submitted={"location_mode": "typed", "place": "Bergbyy"},
            errors={"place": ErrorCode.LOCATION_NOT_FOUND},
        )
    )
    assert page.place == "Bergbyy"
    assert page.location_mode == "typed"


def test_submitted_values_win_over_carried_answers() -> None:
    page = present_form(_context(answers=CARRIED, submitted={"time": "30"}))
    assert [o.value for o in page.time if o.checked] == ["30"]
    # Everything not resubmitted still comes from the carried result (D46).
    assert [o.checked for o in page.who] == [False, True]
    assert page.coords == ("60.12", "17.90")


def test_energy_defaults_to_moderate_with_nothing_submitted() -> None:
    page = present_form(_context())
    assert [o.value for o in page.energy if o.checked] == [Energy.MODERATE.value]


# --- CC-B: the asset manifest --------------------------------------------------------


def test_the_manifest_reaches_page_meta() -> None:
    assets = {"app.css": AssetRef(url="/static/app.abc123.css", integrity="sha384-x")}
    page = present_form(_context(assets=assets))
    assert page.meta.assets["app.css"].url == "/static/app.abc123.css"


# --- CC-C: the D39 tag prefill -------------------------------------------------------


def test_interests_prefill_uses_the_tag_labels_not_the_original_text() -> None:
    page = present_form(
        _context(
            interests=Interests(
                tags=(InterestTag.BIRDS, InterestTag.PUDDLES),
                outcome=InterestOutcome.MATCHED,
            )
        )
    )
    assert page.interests_text == "birds, puddles"


def test_interests_prefill_is_empty_when_nothing_matched() -> None:
    page = present_form(_context(interests=Interests(tags=(), outcome=InterestOutcome.NO_MATCH)))
    assert page.interests_text == ""


def test_the_interests_field_is_absent_when_d39_is_off() -> None:
    page = present_form(_context(d39_enabled=False))
    assert page.interests_text is None


# --- CC-D: candidate expiry in the location's timezone -------------------------------


def test_candidate_expiry_renders_in_the_given_timezone() -> None:
    candidates = LocationCandidates(
        candidates=(
            LocationCandidate(
                candidate_id="c1", label="Bergby", coords=Coordinates(lat=60.1, lon=17.9)
            ),
        ),
        answers=ANSWERS,
        expires_at=datetime(2026, 10, 10, 8, 35, tzinfo=UTC),
    )
    page = present_form(_context(candidates=candidates, candidates_tz="Europe/Stockholm"))
    # 08:35 UTC is 10:35 in Stockholm; the server's own zone never shows.
    assert page.candidates_expire_at == "10:35"
