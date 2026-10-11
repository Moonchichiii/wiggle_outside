"""The detail and print views rendered from fixture view models (DESIGN-SPEC section 12).

Covers the bingo activity and one without a card, "Why this idea", the full weather line,
the dated print context, the historical detail, the no-JavaScript print route and the
section 10 print rules.

Accessibility is not claimed from these checks: axe, the contrast script, Playwright and
the print-preview review are WP9b's and have not run.
"""

import dataclasses
from collections.abc import Mapping
from typing import TYPE_CHECKING

import pytest
from markupsafe import escape

from checks import assert_nothing_inline, assert_page_is_sound
from fixtures import CATALOGUE, LATER, NOW, RESULT, STYLESHEET
from parse import read
from wiggle_outside.core.types import CARD_ITEMS
from wiggle_outside.web import copy
from wiggle_outside.web.presenters import (
    build_environment,
    present_detail,
    render_detail,
    with_assets,
)
from wiggle_outside.web.views import AssetRef

if TYPE_CHECKING:
    from wiggle_outside.web.views import DetailPage

# i4 is Nature bingo, which has a 3 x 3 card; i1 is Puddle jumping, which has none.
BINGO = "i4"
NO_BINGO = "i1"


def esc(text: str) -> str:
    """Return copy as it appears in the HTML: autoescape has run over it once."""
    return str(escape(text))


@pytest.fixture(scope="module")
def pages() -> Mapping[str, DetailPage]:
    return {
        "bingo": present_detail(RESULT, BINGO, CATALOGUE, NOW),
        "no-bingo": present_detail(RESULT, NO_BINGO, CATALOGUE, NOW),
        "historical": present_detail(RESULT, BINGO, CATALOGUE, LATER),
    }


@pytest.fixture(scope="module")
def rendered(pages: Mapping[str, DetailPage]) -> Mapping[str, str]:
    env = build_environment()
    return {name: render_detail(env, with_assets(page, STYLESHEET)) for name, page in pages.items()}


def test_every_state_renders_sound_markup(rendered: Mapping[str, str]) -> None:
    for name, html in rendered.items():
        assert_page_is_sound(name, html)


def test_an_unknown_idea_id_is_a_lookup_failure() -> None:
    # CONTRACTS section 5: the route turns this into a 404, indistinguishable from an
    # unknown job. The presenter never invents a page for an idea the result does not have.
    with pytest.raises(KeyError):
        present_detail(RESULT, "not-in-this-result", CATALOGUE, NOW)


# --- The catalogue text, verbatim -----------------------------------------------------


def test_the_detail_page_renders_the_catalogue_text_verbatim(
    pages: Mapping[str, DetailPage], rendered: Mapping[str, str]
) -> None:
    page = pages["bingo"]
    html = rendered["bingo"]
    assert page.idea.title == "Nature bingo"
    assert page.idea.intro == "The explorer club meets here today."
    assert page.activity.steps[0] == "Look at the nine things on the card together."
    assert page.activity.adapt.startswith("Swap any item")
    assert page.activity.safety.startswith("Look and point")
    assert page.activity.ask == "What did you spot that wasn't on the card?"
    for text in (page.idea.title, page.idea.intro, page.activity.adapt, page.activity.safety):
        assert esc(text) in html
    for step in page.activity.steps:
        assert esc(step) in html
    for item in page.activity.optional:
        assert esc(item) in html


def test_why_this_idea_carries_the_reasons_and_the_match_line(
    pages: Mapping[str, DetailPage], rendered: Mapping[str, str]
) -> None:
    page = pages["bingo"]
    assert page.idea.reasons == (
        "Estimated to fit your time, including travel.",
        "It matches the energy you asked for.",
    )
    assert page.idea.interest_match == "Matches the interests: birds."
    html = rendered["bingo"]
    assert esc(copy.DETAIL_WHY) in html
    for reason in page.idea.reasons:
        assert esc(reason) in html
    assert esc(page.idea.interest_match) in html


def test_the_detail_page_states_the_straight_line_distance_and_the_estimates(
    rendered: Mapping[str, str],
) -> None:
    html = rendered["bingo"].replace("\n", "")
    assert (
        "<strong>Birchwood Nature Area</strong> · nature area · "
        "about 0.9 km away in a straight line"
    ) in html
    assert "About 36 min there and back · 24 min activity (estimates)" in html


# --- The bingo card (DESIGN-SPEC sections 2, 6 and 12) --------------------------------


def test_the_bingo_card_is_a_three_by_three_grid(
    pages: Mapping[str, DetailPage], rendered: Mapping[str, str]
) -> None:
    card = pages["bingo"].activity.card
    assert card is not None
    assert card.heading == copy.BINGO_HEADING
    assert len(card.items) == CARD_ITEMS
    html = rendered["bingo"]
    assert html.count("<tr>") == 3
    assert html.count("<td>") == CARD_ITEMS
    assert 'aria-labelledby="bingo-heading"' in html
    for item in card.items:
        assert esc(item) in html


def test_an_activity_without_a_card_renders_no_grid(
    pages: Mapping[str, DetailPage], rendered: Mapping[str, str]
) -> None:
    assert pages["no-bingo"].activity.card is None
    assert "<table" not in rendered["no-bingo"]
    assert esc(copy.BINGO_HEADING) not in rendered["no-bingo"]


# --- The print view (DESIGN-SPEC section 10) ------------------------------------------


def test_the_print_context_carries_the_date_timezone_and_place(
    pages: Mapping[str, DetailPage], rendered: Mapping[str, str]
) -> None:
    printed = pages["bingo"].print
    assert printed.context_line == (
        f"Planned for Sat 10 Oct 2026, 10:31{copy.EN_DASH}11:31 (Europe/Stockholm), "
        f"near Bergby, Uppsala lan, Sweden."
    )
    assert printed.weather_line == (
        "Forecast checked at 10:31 on Sat 10 Oct 2026; times are estimates."
    )
    assert printed.source_line == (
        "Place data © OpenStreetMap contributors; weather from Open-Meteo."
    )
    assert printed.note == "Check the forecast again before you go if plans change."
    html = rendered["bingo"]
    for line in (printed.context_line, printed.weather_line, printed.source_line, printed.note):
        assert esc(line) in html


def test_the_full_weather_line_is_on_the_detail_page(pages: Mapping[str, DetailPage]) -> None:
    expected = f"Forecast for today, 10:31{copy.EN_DASH}11:31, checked at 10:31"
    assert pages["bingo"].weather.line.startswith(expected)


def test_printing_works_without_javascript(rendered: Mapping[str, str]) -> None:
    html = rendered["bingo"]
    # No script is emitted at all unless the build manifest actually carries one.
    assert "<script" not in html
    # The print button is hidden until a script unhides it: a control that cannot work is
    # not offered (ERROR-HANDLING section 5).
    assert 'type="button" data-wo-print hidden' in html
    # The plain-browser route is named in words, always.
    assert esc(copy.PRINT_HELP) in html
    assert esc(copy.BACK_TO_RESULTS) in html


def test_the_print_script_is_external_and_integrity_pinned_when_the_build_has_one() -> None:
    page = with_assets(
        present_detail(RESULT, BINGO, CATALOGUE, NOW),
        {
            "app.css": AssetRef(url="/static/app.css", integrity=""),
            "print.js": AssetRef(url="/static/print.abc123.js", integrity="sha384-fixture"),
        },
    )
    html = render_detail(build_environment(), page)
    assert (
        '<script src="/static/print.abc123.js" integrity="sha384-fixture" defer></script>' in html
    )
    # Still no inline script, style or handler, and the script has no body.
    assert "<script>" not in html
    assert ">window.print" not in html


# --- The historical detail (BACKEND-CONTRACT section 2) ------------------------------


def test_the_historical_detail_says_it_is_no_longer_current(
    pages: Mapping[str, DetailPage], rendered: Mapping[str, str]
) -> None:
    page = pages["historical"]
    assert page.is_historical
    assert len(page.notices) == 1
    assert page.notices[0].body.startswith("This information is no longer current.")
    assert esc(page.notices[0].body) in rendered["historical"]
    # Immutable results (D46): the content is the same as the current view.
    assert page.idea == pages["bingo"].idea
    assert page.print == pages["bingo"].print


def test_a_current_detail_shows_no_historical_notice(pages: Mapping[str, DetailPage]) -> None:
    assert not pages["bingo"].is_historical
    assert pages["bingo"].notices == ()


# --- Structure ------------------------------------------------------------------------


def test_the_back_link_points_at_the_result(
    pages: Mapping[str, DetailPage], rendered: Mapping[str, str]
) -> None:
    assert pages["bingo"].back_url == "/results/J2"
    assert rendered["bingo"].count('href="/results/J2"') == 2  # the top link and the button


def test_the_page_has_one_heading_per_section_and_no_duplicate_ids(
    rendered: Mapping[str, str],
) -> None:
    doc = read(rendered["bingo"])
    assert "detail-title" in doc.ids
    assert "bingo-heading" in doc.ids
    assert_nothing_inline("bingo", rendered["bingo"])


def test_no_rendered_detail_page_shows_the_word_energetic(rendered: Mapping[str, str]) -> None:
    for name, html in rendered.items():
        assert "Energetic" not in html, name


def test_a_close_by_place_gets_no_straight_line_suffix_on_the_detail_page() -> None:
    idea = RESULT.ideas[0]
    near = dataclasses.replace(idea, pair=dataclasses.replace(idea.pair, distance_m=30))
    result = dataclasses.replace(RESULT, ideas=(near, *RESULT.ideas[1:]))
    page = present_detail(result, idea.pair.idea_id, CATALOGUE, NOW)
    html = render_detail(build_environment(), with_assets(page, STYLESHEET)).replace("\n", "")

    assert "0.0 km" not in html
    assert f"{copy.PRACTICAL_JOIN}close by</p>" in html
    assert "close by in a straight line" not in html
