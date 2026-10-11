"""Every row of the CONTRACTS section 3 GET table, as a status and as a response.

The mapping is a pure function, so the table is checked twice: once against the document
itself, so a drift in either direction fails, and once over HTTP, so the route really
answers what the mapping says.
"""

import re
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import pytest
from web_support import FixedPlanner, Harness, build_harness, one_idea, plan_result

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import JobState
from wiggle_outside.web.routes.status import PageKind, outcome_for

CODE: Final = re.compile(r"\b([A-Z][A-Z_]{3,})\b")
STATUS: Final = re.compile(r"\b(200|303|404|422|500|503)\b")

# CONTRACTS section 3, GET table: code -> status, as the route must answer it.
ROWS: Final = (
    (JobState.COMPLETE, None, True, 200),
    (JobState.FALLBACK, ErrorCode.MODEL_FALLBACK, True, 200),
    (JobState.COMPLETE, ErrorCode.FEWER_MATCHES, True, 200),
    (JobState.COMPLETE, ErrorCode.PLACES_CACHED, True, 200),
    (JobState.COMPLETE, ErrorCode.PLACES_UNAVAILABLE, True, 200),
    (JobState.COMPLETE, ErrorCode.PLACES_UNAVAILABLE, False, 503),
    (JobState.COMPLETE, ErrorCode.NO_MATCHES, False, 200),
    (JobState.COMPLETE, ErrorCode.WEATHER_RESTRICTED, False, 200),
    (JobState.COMPLETE, ErrorCode.DAYLIGHT_NIGHT, False, 200),
    (JobState.COMPLETE, ErrorCode.DAYLIGHT_TOO_SHORT, False, 200),
    (JobState.COMPLETE, ErrorCode.LOCATION_NOT_FOUND, False, 422),
    (JobState.UNAVAILABLE, ErrorCode.WEATHER_UNAVAILABLE, False, 503),
    (JobState.UNAVAILABLE, ErrorCode.GEOCODER_UNAVAILABLE, False, 503),
    (JobState.UNAVAILABLE, ErrorCode.SERVICE_LIMIT_REACHED, False, 503),
    (JobState.UNAVAILABLE, ErrorCode.SERVICE_UNAVAILABLE, False, 503),
    (JobState.NEEDS_LOCATION_CHOICE, None, False, 200),
    (JobState.FAILED, None, False, 500),
    (JobState.EXPIRED, None, False, 404),
)


def _harness(state: JobState, code: ErrorCode | None, *, ideas: bool) -> Iterator[Harness]:
    result = plan_result(
        state=state,
        error=code,
        ideas=(one_idea(),) if ideas else (),
    )
    yield from build_harness(FixedPlanner(result=result))


@pytest.mark.parametrize(("state", "code", "ideas", "status"), ROWS)
def test_the_mapping_matches_the_table(
    state: JobState,
    code: ErrorCode | None,
    ideas: bool,  # noqa: FBT001  a parametrized table column
    status: int,
) -> None:
    result = plan_result(state=state, error=code, ideas=(one_idea(),) if ideas else ())

    assert outcome_for(result).status == status


@pytest.mark.parametrize(("state", "code", "ideas", "status"), ROWS)
def test_the_route_answers_what_the_mapping_says(
    state: JobState,
    code: ErrorCode | None,
    ideas: bool,  # noqa: FBT001  a parametrized table column
    status: int,
) -> None:
    for harness in _harness(state, code, ideas=ideas):
        posted = harness.plan()
        assert posted.status_code == 303

        shown = harness.client.get(posted.headers["location"], follow_redirects=False)

        assert shown.status_code == status
        # A full page, with the headers, on every status (CONTRACTS section 3).
        assert "content-security-policy" in shown.headers
        break


@pytest.mark.contract
def test_every_code_in_the_document_maps_to_the_status_it_names(docs_dir: Path) -> None:
    text = (docs_dir / "CONTRACTS.md").read_text(encoding="utf-8")
    table = text[
        text.index("**GET `/results/{job_id}`**") : text.index(
            "**GET `/results/{job_id}/ideas/{idea_id}`**"
        )
    ]
    checked = 0
    for line in table.splitlines():
        cells = line.split("|")
        if len(cells) < 3:
            continue
        found = STATUS.search(cells[2])
        if found is None:
            continue
        status = int(found.group(1))
        ideas = "with generic ideas" in cells[1] or (
            "ideas" in cells[1] and "without" not in cells[1]
        )
        for name in CODE.findall(cells[1]):
            if name not in ErrorCode.__members__:
                continue
            result = plan_result(error=ErrorCode[name], ideas=(one_idea(),) if ideas else ())
            assert outcome_for(result).status == status, f"{name} should be {status}"
            checked += 1

    assert checked >= 10, "the GET table did not parse"


def test_a_choice_page_is_the_form_with_the_candidates() -> None:
    for harness in _harness(JobState.NEEDS_LOCATION_CHOICE, None, ideas=False):
        shown = harness.client.get(harness.plan().headers["location"])

        assert shown.status_code == 200
        assert 'action="/plan"' in shown.text
        break


def test_a_location_not_found_result_re_renders_the_form_with_the_answers() -> None:
    for harness in _harness(JobState.COMPLETE, ErrorCode.LOCATION_NOT_FOUND, ideas=False):
        shown = harness.client.get(harness.plan().headers["location"])

        assert shown.status_code == 422
        assert 'action="/plan"' in shown.text
        assert "Bergby" in shown.text  # the answers are kept
        break


def test_a_failed_job_carries_an_opaque_reference_and_no_detail() -> None:
    for harness in _harness(JobState.FAILED, None, ideas=False):
        shown = harness.client.get(harness.plan().headers["location"])

        assert shown.status_code == 500
        assert "Reference:" in shown.text
        for leaked in ("Traceback", "wiggle_outside", "sqlite"):
            assert leaked not in shown.text
        break


def test_the_notice_page_kinds_are_the_ones_the_table_names() -> None:
    choice = plan_result(state=JobState.NEEDS_LOCATION_CHOICE)
    form = plan_result(error=ErrorCode.LOCATION_NOT_FOUND)

    assert outcome_for(choice).kind is PageKind.CHOICE
    assert outcome_for(form).kind is PageKind.FORM
    assert outcome_for(plan_result(ideas=(one_idea(),))).kind is PageKind.RESULTS
    assert outcome_for(plan_result(state=JobState.EXPIRED)).kind is PageKind.MISSING


def test_a_result_past_valid_until_but_retained_is_the_historical_view() -> None:
    """BACKEND-CONTRACT section 2: between valid_until and retain_until, with real time."""
    now = datetime.now(UTC)
    result = replace(
        plan_result(ideas=(one_idea(),)),
        valid_until=now - timedelta(minutes=1),
        retain_until=now + timedelta(minutes=30),
    )
    for harness in build_harness(FixedPlanner(result=result)):
        posted = harness.plan()
        assert posted.status_code == 303
        shown = harness.client.get(posted.headers["location"], follow_redirects=False)

        assert shown.status_code == 200
        assert "no longer current" in shown.text
        detail = re.search(r'href="(/results/[^"]+/ideas/[^"]+)"', shown.text)
        assert detail is not None
        assert harness.client.get(detail.group(1)).status_code == 200
        break
