"""The error page rendered from fixture view models (DESIGN-SPEC sections 7 and 12).

One case per failure state in DESIGN-SPEC section 7, plus the 422 re-render that keeps the
answers. Recommendations are blocked everywhere: an error page never carries a card.

Accessibility is not claimed from these checks: axe, the contrast script and the keyboard
and screen-reader walkthroughs are WP9b's and have not run.
"""

from collections.abc import Mapping

import pytest
from markupsafe import escape

from checks import assert_page_is_sound
from fixtures import D39_ON, FORM_ERRORS, SESSION, STYLESHEET
from wiggle_outside.core.errors import NOT_IN_V1, ErrorCode
from wiggle_outside.core.types import DeploymentMode
from wiggle_outside.web import copy
from wiggle_outside.web.presenters import (
    build_environment,
    present_error,
    present_form,
    render_error,
    with_assets,
)
from wiggle_outside.web.views import FormContext, FormPage

MODE = DeploymentMode.HOSTED_LIVE
REFERENCE = "ref-9f3c21"

# One code per row of the DESIGN-SPEC section 7 failure table that reaches an error page.
CODES: tuple[ErrorCode, ...] = (
    ErrorCode.INPUT_INVALID,
    ErrorCode.LOCATION_DENIED,
    ErrorCode.LOCATION_UNAVAILABLE,
    ErrorCode.LOCATION_AMBIGUOUS,
    ErrorCode.LOCATION_CHOICE_EXPIRED,
    ErrorCode.LOCATION_NOT_FOUND,
    ErrorCode.GEOCODER_UNAVAILABLE,
    ErrorCode.WEATHER_UNAVAILABLE,
    ErrorCode.WEATHER_RESTRICTED,
    ErrorCode.PLACES_UNAVAILABLE,
    ErrorCode.NO_MATCHES,
    ErrorCode.SERVICE_LIMIT_REACHED,
    ErrorCode.SERVICE_UNAVAILABLE,
    ErrorCode.REQUEST_BUSY,
    ErrorCode.CONNECTION_FAILED,
    ErrorCode.REQUEST_CONFLICT,
    ErrorCode.SESSION_INVALID,
    ErrorCode.REQUEST_TOO_LARGE,
    ErrorCode.UNEXPECTED_FAILURE,
)


def esc(text: str) -> str:
    """Return copy as it appears in the HTML: autoescape has run over it once."""
    return str(escape(text))


def kept_answers() -> FormPage:
    """Build the answer-keeping form a 422 re-renders (ERROR-HANDLING section 2)."""
    return present_form(
        FormContext(session=SESSION, mode=MODE, d39_enabled=D39_ON, errors=FORM_ERRORS)
    )


@pytest.fixture(scope="module")
def rendered() -> Mapping[str, str]:
    env = build_environment()
    pages = {code.value: present_error(code, REFERENCE, None) for code in CODES}
    pages["with-form"] = present_error(ErrorCode.INPUT_INVALID, None, kept_answers())
    return {name: render_error(env, with_assets(page, STYLESHEET)) for name, page in pages.items()}


def test_every_failure_state_renders_sound_markup(rendered: Mapping[str, str]) -> None:
    for name, html in rendered.items():
        assert_page_is_sound(name, html)


def test_the_codes_covered_are_the_v1_error_page_codes() -> None:
    # Every code this page can be asked for is a v1 code; the daylight codes and the
    # result notices are a results page, not an error page.
    assert not set(CODES) & NOT_IN_V1
    assert not set(CODES) & {ErrorCode.DAYLIGHT_NIGHT, ErrorCode.DAYLIGHT_TOO_SHORT}


@pytest.mark.parametrize("code", CODES)
def test_each_code_renders_its_reviewed_copy_with_no_placeholder_left(code: ErrorCode) -> None:
    page = present_error(code, REFERENCE, None)
    assert "{" not in page.notice.body, f"{code}: an unfilled placeholder reached the page"
    assert page.notice.kind == "alert"
    assert page.notice.body
    assert page.reference == REFERENCE
    html = render_error(build_environment(), with_assets(page, STYLESHEET))
    assert esc(page.notice.body) in html


@pytest.mark.parametrize("code", CODES)
def test_no_error_page_carries_a_recommendation(
    rendered: Mapping[str, str], code: ErrorCode
) -> None:
    # DESIGN-SPEC section 7: recommendations are blocked in every failure state.
    html = rendered[code.value]
    assert "wo-card" not in html
    assert "wo-cards" not in html
    assert esc(copy.CARD_LINK) not in html


def test_the_reference_is_in_the_message_and_is_not_a_token(rendered: Mapping[str, str]) -> None:
    page = present_error(ErrorCode.UNEXPECTED_FAILURE, REFERENCE, None)
    assert page.notice.body == (
        f"We couldn't finish that request. Please try again. Reference: {REFERENCE}."
    )
    html = rendered[ErrorCode.UNEXPECTED_FAILURE.value]
    assert html.count(REFERENCE) == 1
    # No traceback, provider response or job identifier reaches the browser.
    assert "Traceback" not in html
    assert "job_id" not in html


def test_the_service_limit_names_the_reset_it_actually_has() -> None:
    # D49, DEPLOYMENT section 2.3: the allowance rolls over at 00:00 UTC. No countdown is
    # invented, and the sentence never promises anything else.
    page = present_error(ErrorCode.SERVICE_LIMIT_REACHED, None, None)
    assert page.notice.body.endswith("Please try again after 00:00 UTC.")


def test_the_service_unavailable_copy_never_mentions_midnight() -> None:
    # ERROR-HANDLING section 2: quota storage failed, so the run is refused; this is not
    # the daily limit and must not be described as one.
    page = present_error(ErrorCode.SERVICE_UNAVAILABLE, None, None)
    assert "midnight" not in page.notice.body
    assert "00:00" not in page.notice.body
    assert "Your answers are kept" in page.notice.body


def test_a_page_without_a_form_offers_one_action_that_works(rendered: Mapping[str, str]) -> None:
    page = present_error(ErrorCode.CONNECTION_FAILED, None, None)
    assert [action.label for action in page.notice.actions] == [copy.RETURN_TO_FORM]
    assert page.notice.actions[0].url == "/"
    assert page.notice.actions[0].method == "get"
    assert esc(copy.RETURN_TO_FORM) in rendered[ErrorCode.CONNECTION_FAILED.value]


def test_the_422_rerender_keeps_the_answers_and_links_every_field(
    rendered: Mapping[str, str],
) -> None:
    html = rendered["with-form"]
    # ERROR-HANDLING section 2: inline field explanations plus a linked error summary.
    assert esc(copy.ERROR_MESSAGES[ErrorCode.INPUT_INVALID]) in html
    assert esc(copy.ERROR_SUMMARY_HEADING) in html
    assert esc(copy.FIELD_INVALID_SUMMARY["age_band"]) in html
    assert esc(copy.FIELD_INVALID["place"]) in html
    assert 'aria-invalid="true"' in html
    assert 'method="post" action="/plan"' in html


def test_the_422_page_announces_once(rendered: Mapping[str, str]) -> None:
    # ERROR-HANDLING section 5: the form's error summary is the one thing that takes
    # focus; the notice above it is plain text, not a second live region.
    html = rendered["with-form"]
    # The form's error summary is the only alert region, and the only thing on the page
    # that script can focus (the honeypot's tabindex="-1" takes it out of the tab order,
    # it does not make it a focus target).
    assert html.count('role="alert"') == 1
    assert 'role="alert" tabindex="-1" id="error-summary"' in html
    assert 'id="page-error"' not in html
    # Without a form the notice itself is the message, so it is the focus target.
    assert 'id="page-error" tabindex="-1"' in rendered[ErrorCode.CONNECTION_FAILED.value]


def test_a_page_with_a_form_offers_no_second_action(rendered: Mapping[str, str]) -> None:
    page = present_error(ErrorCode.INPUT_INVALID, None, kept_answers())
    assert page.notice.actions == ()
    assert esc(copy.RETURN_TO_FORM) not in rendered["with-form"]


def test_no_rendered_error_page_shows_the_word_energetic(rendered: Mapping[str, str]) -> None:
    for name, html in rendered.items():
        assert "Energetic" not in html, name
