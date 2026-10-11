"""TC-011 round 1: "Use my location" as an enhancement, the choice page, the brand link.

Rendered from fixture view models, like the other template tests. The browser behaviour
of the location script is tests/web/test_browser_location.py.
"""

import dataclasses
from collections.abc import Mapping
from typing import TYPE_CHECKING

import pytest
from markupsafe import escape

from fixtures import (
    CANDIDATES,
    CATALOGUE,
    D39_ON,
    FORM_ERRORS,
    NOW,
    RESULT,
    SESSION,
    STYLESHEET,
)
from parse import read
from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import DeploymentMode
from wiggle_outside.web import copy
from wiggle_outside.web.forms import DEFAULT_LOCATION_LABEL
from wiggle_outside.web.presenters import (
    build_environment,
    present_detail,
    present_error,
    present_form,
    present_result,
    render_detail,
    render_error,
    render_form,
    render_result,
    with_assets,
)
from wiggle_outside.web.views import AssetRef, FormContext

if TYPE_CHECKING:
    from wiggle_outside.web.views import FormPage

MODE = DeploymentMode.HOSTED_LIVE
BINGO = RESULT.ideas[0].pair.idea_id
WITH_SCRIPT = {
    **STYLESHEET,
    "location.js": AssetRef(url="/static/location.abc123.js", integrity="sha384-fixture"),
}


def esc(text: str) -> str:
    return str(escape(text))


def _form(**extra: object) -> FormPage:
    return present_form(FormContext(session=SESSION, mode=MODE, d39_enabled=D39_ON, **extra))  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def rendered() -> Mapping[str, str]:
    env = build_environment()
    return {
        "form": render_form(env, _form()),
        "ambiguous": render_form(env, _form(candidates=CANDIDATES)),
        "form-with-script": render_form(env, with_assets(_form(), WITH_SCRIPT)),
        "result": render_result(
            env,
            with_assets(present_result(RESULT, CATALOGUE, NOW, SESSION, MODE, D39_ON), WITH_SCRIPT),
        ),
        "detail": render_detail(
            env, with_assets(present_detail(RESULT, BINGO, CATALOGUE, NOW), STYLESHEET)
        ),
        "error": render_error(
            env,
            with_assets(
                present_error(ErrorCode.INPUT_INVALID, None, _form(errors=FORM_ERRORS)),
                WITH_SCRIPT,
            ),
        ),
    }


# --- 1. "Use my location" is offered only when a script can serve it -------------------


def test_the_location_button_is_hidden_until_the_script_unhides_it(
    rendered: Mapping[str, str],
) -> None:
    html = rendered["form"]
    assert 'type="button" data-wo-locate aria-describedby="locate-status" hidden>' in html
    assert esc(copy.USE_MY_LOCATION) in html
    # The status line is a polite live region that carries its own wording, so the
    # script holds no copy and nothing is inlined.
    assert 'id="locate-status" role="status" data-wo-locate-status' in html
    for text in (
        copy.LOCATION_ASKING,
        copy.LOCATION_USING,
        copy.LOCATION_DENIED,
        copy.LOCATION_FAILED,
    ):
        assert esc(text) in html


def test_the_location_script_is_external_integrity_pinned_and_deferred(
    rendered: Mapping[str, str],
) -> None:
    tag = '<script src="/static/location.abc123.js" integrity="sha384-fixture" defer></script>'
    for name in ("form-with-script", "result", "error"):
        assert tag in rendered[name], name
        assert "<script>" not in rendered[name], name
    # Without a build there is no script at all, and the detail page never needs this one.
    assert "<script" not in rendered["form"]
    assert "location." not in rendered["detail"]


def test_the_status_line_describes_the_button(rendered: Mapping[str, str]) -> None:
    doc = read(rendered["form"])
    assert "locate-status" in doc.ids
    assert "locate-status" in doc.described_by


# --- 2. The choice page is unambiguous -----------------------------------------------


def test_the_candidates_have_their_own_heading_and_button(rendered: Mapping[str, str]) -> None:
    html = rendered["ambiguous"]
    heading = esc(copy.LOCATION_CHOICE_HEADING)
    assert f'<h2 class="wo-choice-heading" id="choice-heading">{heading}</h2>' in html
    assert esc(copy.LOCATION_CHOICE_INTRO) in html
    assert 'action="/location-choice" aria-labelledby="choice-heading"' in html
    # The list's button says what it does; the form below keeps its own.
    choice_end = html.index("</form>")
    choice = html[:choice_end]
    assert esc(copy.USE_THIS_PLACE) in choice
    assert esc(copy.SUBMIT) not in choice
    rest = html[choice_end:]
    assert esc(copy.SUBMIT) in rest
    assert esc(copy.USE_THIS_PLACE) not in rest
    assert 'action="/plan"' in rest


def test_the_choice_page_still_lets_the_answers_be_changed(rendered: Mapping[str, str]) -> None:
    doc = read(rendered["ambiguous"])
    assert [c.attrs["value"] for c in doc.named("candidate_id")] == ["c1", "c2", "c3"]
    assert doc.named("place")
    assert doc.named("who")


def test_the_form_page_without_candidates_has_no_choice_heading(
    rendered: Mapping[str, str],
) -> None:
    assert esc(copy.LOCATION_CHOICE_HEADING) not in rendered["form"]
    assert esc(copy.USE_THIS_PLACE) not in rendered["form"]


# --- 3. The brand is the way home ------------------------------------------------------


@pytest.mark.parametrize("name", ["form", "ambiguous", "result", "detail", "error"])
def test_the_brand_links_home_on_every_page(rendered: Mapping[str, str], name: str) -> None:
    html = rendered[name]
    start = html.index('<a class="wo-brand" href="/" rel="home">')
    end = html.index("</a>", start)
    link = html[start:end]
    # The accessible name is the product name; the leaf is decorative.
    assert link.startswith(f'<a class="wo-brand" href="/" rel="home">{esc(copy.PAGE_TITLE)}')
    assert 'aria-hidden="true"' in link
    assert html.count('class="wo-brand"') == 1


# --- 7. The page description ---------------------------------------------------------


@pytest.mark.parametrize("name", ["form", "ambiguous", "result", "detail", "error"])
def test_every_page_carries_the_one_description(rendered: Mapping[str, str], name: str) -> None:
    html = rendered[name]
    tag = f'<meta name="description" content="{esc(copy.PAGE_DESCRIPTION)}">'
    assert html.count('<meta name="description"') == 1
    assert tag in html
    # Inside <head>, and the exact approved sentence.
    assert html.index(tag) < html.index("</head>")
    assert copy.PAGE_DESCRIPTION == (
        "Weather, nearby places and a little inspiration in one short search. "
        "Up to three outdoor ideas for right now, chosen with Gemma."
    )


# --- Round 2, copy: "near your location" ----------------------------------------------------


def test_the_device_label_reads_lower_case_mid_sentence() -> None:
    located = dataclasses.replace(
        RESULT, answers=dataclasses.replace(RESULT.answers, location_label=DEFAULT_LOCATION_LABEL)
    )
    page = present_result(located, CATALOGUE, NOW, SESSION, MODE, D39_ON)
    html = render_result(build_environment(), with_assets(page, STYLESHEET))
    detail = present_detail(located, BINGO, CATALOGUE, NOW)

    assert page.answers.lines[0].endswith(copy.ANSWERS_NEAR_YOUR_LOCATION)
    assert "near your location" in html
    assert "near Your location" not in html
    assert detail.print is not None
    assert detail.print.context_line.endswith("near your location.")
    # A geocoded place keeps its own name, capitals and all.
    assert (
        present_result(RESULT, CATALOGUE, NOW, SESSION, MODE, D39_ON)
        .answers.lines[0]
        .endswith(copy.ANSWERS_NEAR.format(label=RESULT.answers.location_label))
    )
