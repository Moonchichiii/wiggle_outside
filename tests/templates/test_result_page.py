"""The results page rendered from fixture view models (DESIGN-SPEC section 12).

Covers results with 0, 1, 2 and 3 ideas, the fallback label, the gentler notice, the
uncertainty labels, the historical view, the D39 label states, both daylight pages and the
weather-unavailable page.

Accessibility is not claimed from these checks: axe, the contrast script and the keyboard,
screen-reader, forced-colours and zoom walkthroughs are WP9b's and have not run.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING

import pytest
from markupsafe import escape

from checks import assert_page_is_sound
from fixtures import (
    CATALOGUE,
    D39_OFF,
    D39_ON,
    LATER,
    NOW,
    RESULT,
    RESULT_AMPERSAND,
    RESULT_FALLBACK,
    RESULT_GENERIC,
    RESULT_GENTLER,
    RESULT_NIGHT,
    RESULT_NO_MATCH,
    RESULT_NO_WEATHER,
    RESULT_NONE,
    RESULT_NOT_APPLIED,
    RESULT_ONE,
    RESULT_TOO_SHORT,
    RESULT_TWO,
    RESULT_UNCLEAR,
    SESSION,
    STYLESHEET,
)
from parse import read
from wiggle_outside.core.errors import ErrorCode, NoticeId
from wiggle_outside.core.types import DeploymentMode, PlanResult
from wiggle_outside.web import copy
from wiggle_outside.web.presenters import (
    build_environment,
    present_result,
    render_result,
    with_assets,
)

if TYPE_CHECKING:
    from wiggle_outside.web.views import ResultPage

MODE = DeploymentMode.HOSTED_LIVE

# The separators the copy table uses, named here so no expected string in this file
# contains an ambiguous character of its own (copy.py says why).
DASH = copy.EN_DASH
DOT = copy.ANSWERS_JOIN

# Every state in the DESIGN-SPEC section 12 checklist that renders a results page.
STATES: Mapping[str, tuple[PlanResult, bool]] = {
    "three": (RESULT, D39_ON),
    "two": (RESULT_TWO, D39_ON),
    "one": (RESULT_ONE, D39_ON),
    "none": (RESULT_NONE, D39_ON),
    "fallback": (RESULT_FALLBACK, D39_ON),
    "gentler": (RESULT_GENTLER, D39_ON),
    "generic": (RESULT_GENERIC, D39_ON),
    "ampersand": (RESULT_AMPERSAND, D39_ON),
    "no-match": (RESULT_NO_MATCH, D39_ON),
    "unclear": (RESULT_UNCLEAR, D39_ON),
    "not-applied": (RESULT_NOT_APPLIED, D39_ON),
    "night": (RESULT_NIGHT, D39_ON),
    "too-short": (RESULT_TOO_SHORT, D39_ON),
    "no-weather": (RESULT_NO_WEATHER, D39_ON),
    "no-d39": (RESULT, D39_OFF),
}


def esc(text: str) -> str:
    """Return copy as it appears in the HTML: autoescape has run over it once."""
    return str(escape(text))


def view(result: PlanResult, *, d39: bool = True, historical: bool = False) -> ResultPage:
    return present_result(result, CATALOGUE, LATER if historical else NOW, SESSION, MODE, d39)


@pytest.fixture(scope="module")
def pages() -> Mapping[str, ResultPage]:
    return {name: view(result, d39=d39) for name, (result, d39) in STATES.items()}


@pytest.fixture(scope="module")
def rendered(pages: Mapping[str, ResultPage]) -> Mapping[str, str]:
    env = build_environment()
    return {name: render_result(env, with_assets(page, STYLESHEET)) for name, page in pages.items()}


# --- Every state is structurally sound ------------------------------------------------


def test_every_state_renders_sound_markup(rendered: Mapping[str, str]) -> None:
    for name, html in rendered.items():
        assert_page_is_sound(name, html)


def test_the_page_links_its_stylesheet(rendered: Mapping[str, str]) -> None:
    assert '<link rel="stylesheet" href="/static/app.css"' in rendered["three"]


# --- No padding and no empty slots (DESIGN-SPEC section 12) ---------------------------


@pytest.mark.parametrize(("state", "count"), [("three", 3), ("two", 2), ("one", 1), ("none", 0)])
def test_ideas_are_never_padded(
    pages: Mapping[str, ResultPage], rendered: Mapping[str, str], state: str, count: int
) -> None:
    assert len(pages[state].ideas) == count
    assert rendered[state].count('<article class="wo-card') == count


def test_a_result_with_no_ideas_renders_no_card_markup(rendered: Mapping[str, str]) -> None:
    html = rendered["none"]
    assert "wo-cards" not in html
    assert esc(copy.ERROR_MESSAGES[ErrorCode.NO_MATCHES]) in html


def test_fewer_matches_counts_what_is_actually_shown(pages: Mapping[str, ResultPage]) -> None:
    template = copy.ERROR_MESSAGES[ErrorCode.FEWER_MATCHES]
    assert template.format(count=2) in [n.body for n in pages["two"].notices]
    assert template.format(count=1) in [n.body for n in pages["one"].notices]
    # No unfilled placeholder ever reaches a page.
    for page in pages.values():
        for item in page.notices:
            assert "{" not in item.body


# --- The approved card line and the shared weather line -------------------------------


def test_the_card_facts_match_the_approved_board(rendered: Mapping[str, str]) -> None:
    # The approved board (visual-direction-v2.png) gives each fact its own row with its
    # own icon: where, then how long. Same words and same order as mock 03's single
    # line, which the board supersedes as the visual target.
    flat = rendered["three"].replace("\n", "")

    assert "<strong>Linden Park</strong> · park · about 0.6 km away" in flat
    assert "24 min there and back · 36 min activity" in flat
    # One place row and one time row per card, not a merged sentence.
    assert flat.count('class="wo-card-practical"') == 2 * 3


def test_the_weather_line_is_shown_once_and_never_per_card(
    pages: Mapping[str, ResultPage], rendered: Mapping[str, str]
) -> None:
    weather = pages["three"].weather
    assert weather is not None
    # The en dash and the degree sign come from the copy table, so the expected string
    # carries no ambiguous character of its own (see copy.py's note on the linter).
    assert weather.line == (
        f"Forecast for 10:31{DASH}11:31, checked at 10:31: cloudy with showers possible "
        f"(up to 40 %), 11{DASH}12 {copy.DEGREE}C, wind up to 18 km/h."
    )
    assert rendered["three"].count(esc(weather.line)) == 1


def test_times_are_in_the_locations_timezone(pages: Mapping[str, ResultPage]) -> None:
    # The fixture window is 08:31-09:31 UTC, which is 10:31-11:31 in Europe/Stockholm.
    weather = pages["three"].weather
    assert weather is not None
    assert weather.window == f"10:31{DASH}11:31"
    assert weather.checked_at == "10:31"
    assert "08:31" not in weather.line


def test_the_answers_summary_matches_the_approved_mock(pages: Mapping[str, ResultPage]) -> None:
    lines = pages["three"].answers.lines
    assert lines[0] == (
        f"Me and the kids (3{DASH}5, 6{DASH}9){DOT}1 hour{DOT}Moderate"
        f"{DOT}near Bergby, Uppsala lan, Sweden"
    )
    # D42: the step-free preference was given, the stroller was not.
    assert copy.STEP_FREE_LABEL in lines
    assert copy.STROLLER_LABEL not in lines
    assert pages["three"].answers.change_label == copy.CHANGE_ANSWERS


def test_change_answers_holds_the_prefilled_form(rendered: Mapping[str, str]) -> None:
    html = rendered["three"]
    assert esc(copy.CHANGE_ANSWERS) in html
    assert '<details class="wo-change">' in html
    assert 'method="post" action="/plan"' in html
    # D46: the carried coordinates travel with the form, so no new geocode is needed.
    assert 'name="location_mode" value="coords"' in html
    assert 'name="lat" value="60.42"' in html
    assert esc(copy.CARRIED_LOCATION_SUFFIX) in html


# --- Labels only when true (DESIGN-SPEC section 12) -----------------------------------


def test_uncertainty_labels_are_only_the_ones_that_apply(pages: Mapping[str, ResultPage]) -> None:
    puddles, bingo, leaves = pages["three"].ideas
    assert puddles.place.uncertainty == (copy.FEE_UNKNOWN, copy.STEP_FREE_UNKNOWN)
    assert bingo.place.uncertainty == (copy.FEE_REPORTED_FREE, copy.STEP_FREE_UNKNOWN)
    assert leaves.place.uncertainty == (copy.FEE_UNKNOWN, copy.STEP_FREE_REPORTED)


def test_a_generic_pair_has_no_place_name_distance_or_uncertainty(
    pages: Mapping[str, ResultPage],
) -> None:
    (idea,) = pages["generic"].ideas
    assert idea.place.name is None
    assert idea.place.distance is None
    assert idea.place.uncertainty == ()
    assert idea.place.kind_label == copy.PLACE_KIND_GENERIC


def test_the_gentler_notice_appears_only_when_it_is_true(
    pages: Mapping[str, ResultPage],
) -> None:
    gentler = copy.NOTICE_MESSAGES[NoticeId.GENTLER_THAN_ASKED]
    assert gentler == "These suggestions are gentler than the energy level you selected."
    assert gentler in [n.body for n in pages["gentler"].notices]
    assert gentler not in [n.body for n in pages["three"].notices]


def test_the_fallback_label_appears_only_for_a_fallback_result(
    pages: Mapping[str, ResultPage], rendered: Mapping[str, str]
) -> None:
    label = copy.ERROR_MESSAGES[ErrorCode.MODEL_FALLBACK]
    assert pages["fallback"].source_label == label
    assert pages["three"].source_label is None
    assert esc(label) in rendered["fallback"]
    assert esc(label) not in rendered["three"]
    # The label is said once, not repeated as a notice as well.
    assert rendered["fallback"].count(esc(label)) == 1


def test_the_interest_match_line_uses_the_results_own_tags(
    pages: Mapping[str, ResultPage],
) -> None:
    puddles, bingo, leaves = pages["three"].ideas
    assert puddles.interest_match == "Matches the interests: puddles."
    assert bingo.interest_match == "Matches the interests: birds."
    # Leaf colour hunt is tagged colours and trees: neither tag matched, so no line.
    assert leaves.interest_match is None


def test_the_match_line_is_not_on_the_card(rendered: Mapping[str, str]) -> None:
    # 8.12: reasons and the match line live on the detail page, not on the card.
    assert "Matches the interests" not in rendered["three"]
    assert esc("It's close by.") not in rendered["three"]


# --- D39 labels, no match, unclear, not applied (PRODUCT-FIT 3.4) ---------------------


def test_interest_labels_are_plain_text_and_not_controls(
    pages: Mapping[str, ResultPage], rendered: Mapping[str, str]
) -> None:
    view_model = pages["three"].interests
    assert view_model is not None
    assert view_model.heading == "We think they're into:"
    assert view_model.labels == ("birds", "puddles")
    assert view_model.note == ('To change these, edit "What are they into?" under Change answers.')
    interests_box = rendered["three"].split('class="wo-interests"')[1].split("</div>")[0]
    assert "<button" not in interests_box
    assert "<input" not in interests_box


@pytest.mark.parametrize(
    ("state", "notice_id"),
    [
        ("no-match", NoticeId.INTEREST_NO_MATCH),
        ("unclear", NoticeId.INTEREST_UNCLEAR),
        ("not-applied", NoticeId.INTEREST_NOT_APPLIED),
    ],
)
def test_a_failed_interpretation_shows_a_notice_and_no_labels(
    pages: Mapping[str, ResultPage], state: str, notice_id: NoticeId
) -> None:
    page = pages[state]
    assert page.interests is None, f"{state}: labels shown for an invalid interpretation"
    assert copy.NOTICE_MESSAGES[notice_id] in [n.body for n in page.notices]


def test_a_fallback_that_used_valid_interests_says_so(pages: Mapping[str, ResultPage]) -> None:
    # PRODUCT-FIT 3.4: valid interpretation, failed selection.
    page = pages["fallback"]
    assert page.interests is not None
    assert copy.NOTICE_MESSAGES[NoticeId.INTERESTS_USED_BY_FALLBACK] in [
        n.body for n in page.notices
    ]


def test_d39_off_shows_no_interest_labels(
    pages: Mapping[str, ResultPage], rendered: Mapping[str, str]
) -> None:
    assert pages["no-d39"].interests is None
    assert "We think they're into" not in rendered["no-d39"]


# --- The daylight pages (DESIGN-SPEC section 12, TC-002) ------------------------------


@pytest.mark.parametrize(
    ("state", "code"),
    [("night", ErrorCode.DAYLIGHT_NIGHT), ("too-short", ErrorCode.DAYLIGHT_TOO_SHORT)],
)
def test_the_daylight_pages_show_the_fixed_copy_in_the_heading_position(
    pages: Mapping[str, ResultPage], rendered: Mapping[str, str], state: str, code: ErrorCode
) -> None:
    page = pages[state]
    html = rendered[state]
    assert page.heading == copy.ERROR_HEADINGS[code]
    assert f'id="results-heading" tabindex="-1">{esc(copy.ERROR_HEADINGS[code])}</h2>' in html
    # The body is the TC-002 wording, as a sentence under its heading, not in a box.
    assert f'<p class="wo-lede">{esc(copy.ERROR_MESSAGES[code])}</p>' in html


@pytest.mark.parametrize("state", ["night", "too-short"])
def test_the_daylight_pages_keep_the_answers_and_promise_no_weather(
    pages: Mapping[str, ResultPage], rendered: Mapping[str, str], state: str
) -> None:
    page = pages[state]
    assert page.ideas == ()
    assert page.weather is None
    assert page.interests is None
    html = rendered[state]
    assert "wo-cards" not in html
    assert "Forecast for" not in html
    # The answers summary and "Change answers" stay (mock 05-night.html).
    assert page.answers.lines[0].startswith("Me and the kids")
    assert esc(copy.CHANGE_ANSWERS) in html
    assert 'method="post" action="/plan"' in html


def test_the_too_short_copy_promises_a_recheck_and_offers_no_shorter_outing(
    pages: Mapping[str, ResultPage],
) -> None:
    # TC-002: the weather limits were never evaluated on this run, so the copy promises a
    # re-check and never presents a shorter outing as the fix.
    body = pages["too-short"].notices[0].body
    assert "check the daylight and the weather again" in body
    assert "shorter" not in body


# --- Failure states (DESIGN-SPEC section 7) -------------------------------------------


def test_weather_unavailable_shows_no_card_of_any_kind(
    pages: Mapping[str, ResultPage], rendered: Mapping[str, str]
) -> None:
    page = pages["no-weather"]
    assert page.ideas == ()
    assert page.weather is None
    assert [n.body for n in page.notices] == [copy.ERROR_MESSAGES[ErrorCode.WEATHER_UNAVAILABLE]]
    assert "wo-cards" not in rendered["no-weather"]


# --- The historical view (BACKEND-CONTRACT section 2) ---------------------------------


def test_the_historical_view_says_it_is_no_longer_current() -> None:
    page = view(RESULT, historical=True)
    assert page.is_historical
    assert page.historical_text == (
        f"This information is no longer current. Planned for Sat 10 Oct 2026, "
        f"10:31{DASH}11:31, forecast checked at 10:31. Plan again for fresh ideas."
    )
    assert page.plan_again.label == copy.PLAN_AGAIN
    assert page.plan_again.method == "get"
    html = render_result(build_environment(), with_assets(page, STYLESHEET))
    assert_page_is_sound("historical", html)
    assert esc(page.historical_text) in html
    assert esc(copy.PLAN_AGAIN) in html


def test_a_current_result_is_not_historical(pages: Mapping[str, ResultPage]) -> None:
    assert not pages["three"].is_historical
    assert pages["three"].historical_text is None


# --- Escaping (BACKEND-CONTRACT section 7, WALKTHROUGH step 11) -----------------------


def test_an_osm_name_with_an_ampersand_is_escaped_exactly_once(
    rendered: Mapping[str, str],
) -> None:
    html = rendered["ampersand"]
    assert html.count("Elm &amp; Oak Playground") == 1
    assert "Elm & Oak" not in html
    assert "&amp;amp;" not in html
    # The same, in the answers summary, where the line is assembled from four parts and
    # then split again for the emphasis the approved mock shows.
    assert "Oak &amp; Elm &lt;b&gt;" in html
    assert "<b>" not in html


# --- TC-001 ---------------------------------------------------------------------------


def test_no_rendered_results_page_shows_the_word_energetic(rendered: Mapping[str, str]) -> None:
    for name, html in rendered.items():
        assert "Energetic" not in html, name


# --- Order on the page (DESIGN-SPEC section 6) ----------------------------------------


def test_the_page_order_is_heading_answers_weather_notices_interests_cards(
    rendered: Mapping[str, str],
) -> None:
    html = rendered["gentler"]
    positions = [
        html.index('id="results-heading"'),
        html.index('class="wo-answers"'),
        html.index('class="wo-weather"'),
        html.index("wo-notice-text"),
        html.index('class="wo-interests"'),
        html.index('class="wo-cards"'),
    ]
    assert positions == sorted(positions)


def test_each_card_names_its_own_link(rendered: Mapping[str, str]) -> None:
    doc = read(rendered["three"])
    assert rendered["three"].count(esc(copy.CARD_LINK)) == 3
    for title in ("Puddle jumping championship", "Nature bingo", "Leaf colour hunt"):
        assert esc(copy.CARD_LINK_CONTEXT.format(title=title)) in rendered["three"]
    assert "idea-i1-title" in doc.ids
