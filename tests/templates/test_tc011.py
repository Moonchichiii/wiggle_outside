"""TC-011 round 1: "Use my location" as an enhancement, the choice page, the brand link.

Rendered from fixture view models, like the other template tests. The browser behaviour
of the location script is tests/web/test_browser_location.py.
"""

import dataclasses
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest
from markupsafe import escape

from fixtures import (
    CANDIDATES,
    CATALOGUE,
    D39_ON,
    FORM_ERRORS,
    NOW,
    RESULT,
    RESULT_GENERIC,
    RESULT_NO_MATCH,
    RESULT_NONE,
    RESULT_ONE,
    RESULT_TWO,
    SESSION,
    STYLESHEET,
)
from parse import read
from wiggle_outside.core.errors import ErrorCode, NoticeId
from wiggle_outside.core.packing import PackingItem, Snack
from wiggle_outside.core.types import (
    AgeBand,
    DeploymentMode,
    InterestOutcome,
    Interests,
    PlanResult,
    TimeBudget,
    Who,
)
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


# --- Round 2: the morning notice ------------------------------------------------------------

STOCKHOLM = ZoneInfo("Europe/Stockholm")


def _morning_result(searched_at: datetime, morning: datetime) -> PlanResult:
    assert RESULT.weather is not None
    return dataclasses.replace(
        RESULT,
        notices=(NoticeId.PLANNED_FOR_MORNING,),
        planned_start=morning.astimezone(UTC),
        planned_end=(morning + timedelta(hours=1)).astimezone(UTC),
        weather=dataclasses.replace(
            RESULT.weather,
            fetched_at=searched_at.astimezone(UTC),
            window_start=morning.astimezone(UTC),
            window_end=(morning + timedelta(hours=1)).astimezone(UTC),
        ),
    )


def test_the_morning_notice_says_tomorrow_and_the_window_in_the_places_time() -> None:
    result = _morning_result(
        datetime(2026, 10, 11, 21, 0, tzinfo=STOCKHOLM),
        datetime(2026, 10, 12, 9, 0, tzinfo=STOCKHOLM),
    )
    page = present_result(result, CATALOGUE, NOW, SESSION, MODE, D39_ON)
    html = render_result(build_environment(), with_assets(page, STYLESHEET))

    window = f"Tomorrow, 09:00{copy.EN_DASH}10:00."
    expected = f"It's dark now, so here are ideas for tomorrow morning. {window}"
    assert [n.body for n in page.notices] == [expected]
    assert esc(expected) in html
    assert page.heading == copy.RESULTS_HEADING
    assert page.ideas


def test_the_morning_notice_says_this_morning_after_the_lock() -> None:
    result = _morning_result(
        datetime(2026, 10, 12, 4, 31, tzinfo=STOCKHOLM),
        datetime(2026, 10, 12, 9, 0, tzinfo=STOCKHOLM),
    )
    page = present_result(result, CATALOGUE, NOW, SESSION, MODE, D39_ON)

    window = f"This morning, 09:00{copy.EN_DASH}10:00."
    assert page.notices[0].body == f"It's dark now, so here are ideas for this morning. {window}"


def test_the_morning_notice_without_a_forecast_is_the_plain_sentence() -> None:
    result = dataclasses.replace(RESULT, notices=(NoticeId.PLANNED_FOR_MORNING,), weather=None)
    page = present_result(result, CATALOGUE, NOW, SESSION, MODE, D39_ON)

    assert page.notices[0].body == copy.NOTICE_MESSAGES[NoticeId.PLANNED_FOR_MORNING]


# --- The loader (TC-011) ----------------------------------------------------------------------


@pytest.mark.parametrize("name", ["form", "ambiguous", "result", "error"])
def test_every_search_form_carries_a_hidden_loader(rendered: Mapping[str, str], name: str) -> None:
    html = rendered[name]
    forms = html.count("data-wo-pending")
    assert forms == html.count('<div class="wo-busy wo-loader" data-wo-loader hidden>')
    assert forms == (2 if name == "ambiguous" else 1)
    # Decorative badge and bar; an empty status region that the script fills once.
    assert f'<p class="wo-loader-badge" aria-hidden="true">{esc(copy.LOADER_BADGE)}</p>' in html
    assert (
        '<div class="wo-loader-track" aria-hidden="true"><div class="wo-loader-bar"></div></div>'
        in html
    )
    assert (
        '<p class="wo-loader-text" role="status" aria-live="polite" data-wo-loader-status '
        f'data-message="{esc(copy.LOADER_TEXT)}"></p>'
    ) in html
    assert "%" not in copy.LOADER_TEXT
    assert copy.LOADER_TEXT.endswith(copy.BUSY_NOTE)


# --- Five fixes from the live site (TC-011) ----------------------------------------------------


def test_a_place_free_idea_is_timed_without_a_journey() -> None:
    page = present_result(RESULT_GENERIC, CATALOGUE, NOW, SESSION, MODE, D39_ON)
    (idea,) = page.ideas
    assert idea.times == copy.TIMES_ACTIVITY_ONLY.format(
        duration=idea_pair_duration(RESULT_GENERIC)
    )
    assert "there and back" not in idea.times
    assert idea.times.startswith("Start nearby")
    detail = present_detail(RESULT_GENERIC, RESULT_GENERIC.ideas[0].pair.idea_id, CATALOGUE, NOW)
    assert "there and back" not in detail.idea.times_detail
    assert detail.idea.times_detail == copy.DETAIL_TIMES_ACTIVITY_ONLY.format(
        duration=idea_pair_duration(RESULT_GENERIC)
    )
    detail_html = render_detail(build_environment(), with_assets(detail, STYLESHEET))
    assert esc(detail.idea.times_detail) in detail_html
    assert "there and back" not in detail_html
    # A placed idea keeps the journey.
    placed = present_result(RESULT, CATALOGUE, NOW, SESSION, MODE, D39_ON).ideas[0]
    assert "min there and back" in placed.times


def idea_pair_duration(result: PlanResult) -> int:
    return result.ideas[0].pair.duration_min


def test_a_window_on_a_later_local_date_says_tomorrow() -> None:
    result = _morning_result(
        datetime(2026, 10, 11, 21, 0, tzinfo=STOCKHOLM),
        datetime(2026, 10, 12, 9, 0, tzinfo=STOCKHOLM),
    )
    now = datetime(2026, 10, 11, 21, 5, tzinfo=STOCKHOLM)
    page = present_result(result, CATALOGUE, now, SESSION, MODE, D39_ON)
    assert page.weather is not None
    assert page.weather.line.startswith(
        f"Forecast for tomorrow, 09:00{copy.EN_DASH}10:00, checked at 21:00"
    )
    detail = present_detail(result, BINGO, CATALOGUE, now)
    assert detail.weather.line.startswith(f"Forecast for tomorrow, 09:00{copy.EN_DASH}10:00")
    # Seen the next morning, the same window is no longer "tomorrow".
    later = present_result(
        result, CATALOGUE, datetime(2026, 10, 12, 8, 0, tzinfo=STOCKHOLM), SESSION, MODE, D39_ON
    )
    assert later.weather is not None
    assert later.weather.line.startswith(f"Forecast for today, 09:00{copy.EN_DASH}10:00")
    # Looked at days later, the line carries the date instead.
    days_later = present_result(
        result, CATALOGUE, datetime(2026, 10, 14, 8, 0, tzinfo=STOCKHOLM), SESSION, MODE, D39_ON
    )
    assert days_later.weather is not None
    line = days_later.weather.line
    assert line.startswith("Forecast for Mon 12 Oct 2026, ")


def test_the_fewer_matches_line_is_gone_for_one_and_two_ideas() -> None:
    # TC-012 replaced TC-011's singular: the count is on the page, the line is not.
    for result in (RESULT_ONE, RESULT_TWO):
        page = present_result(result, CATALOGUE, NOW, SESSION, MODE, D39_ON)
        assert not [n for n in page.notices if "matching idea" in n.body]


def test_an_interests_notice_never_shows_without_an_interpretation() -> None:
    # Belt and braces: even if a result carried the notice with no interpretation (no text
    # was given, or the outcome is not_provided), nothing is rendered for it.
    for interests in (None, Interests(tags=(), outcome=InterestOutcome.NOT_PROVIDED)):
        carried = dataclasses.replace(
            RESULT, interests=interests, notices=(NoticeId.INTEREST_NO_MATCH,)
        )
        page = present_result(carried, CATALOGUE, NOW, SESSION, MODE, D39_ON)
        assert copy.NOTICE_MESSAGES[NoticeId.INTEREST_NO_MATCH] not in [
            n.body for n in page.notices
        ]
    # With text that matched nothing, the notice stays.
    page = present_result(RESULT_NO_MATCH, CATALOGUE, NOW, SESSION, MODE, D39_ON)
    assert copy.NOTICE_MESSAGES[NoticeId.INTEREST_NO_MATCH] in [n.body for n in page.notices]


def test_the_loader_sits_in_the_actions_place(rendered: Mapping[str, str]) -> None:
    html = rendered["form"]
    actions = html.index('<div class="wo-actions">')
    loader = html.index('<div class="wo-busy wo-loader" data-wo-loader hidden>')
    assert actions < loader
    assert "</form>" not in html[actions:loader]  # the same form, right after the button


# --- TC-012 part A: the model's choices on the card, one notice box ------------------------------


def test_every_card_renders_without_model_text() -> None:
    page = present_result(RESULT, CATALOGUE, NOW, SESSION, MODE, D39_ON)
    html = render_result(build_environment(), with_assets(page, STYLESHEET))
    # TC-012 clarification: part B was dropped; nothing on a card is model-written.
    assert "Gemma's note" not in html
    assert "wo-card-note" not in html


def test_the_card_shows_at_most_two_reasons_and_the_match() -> None:
    page = present_result(RESULT, CATALOGUE, NOW, SESSION, MODE, D39_ON)
    html = render_result(build_environment(), with_assets(page, STYLESHEET))
    for idea in page.ideas:
        for reason in idea.reasons[:2]:
            assert f"<span>{esc(reason)}</span>" in html
        if idea.match_labels:
            assert esc(copy.CARD_MATCH.format(tags=idea.match_labels)) in html
            assert idea.interest_match == copy.INTEREST_MATCH.format(tags=idea.match_labels)
    assert any(idea.match_labels for idea in page.ideas), "the fixture matches birds"
    assert html.count('<ul class="wo-card-reasons">') == len([i for i in page.ideas if i.reasons])


def test_the_notices_are_one_box_with_the_lead_first() -> None:
    result = dataclasses.replace(
        _morning_result(
            datetime(2026, 10, 11, 21, 0, tzinfo=STOCKHOLM),
            datetime(2026, 10, 12, 9, 0, tzinfo=STOCKHOLM),
        ),
        notices=(
            ErrorCode.PLACES_UNAVAILABLE,
            NoticeId.PLANNED_FOR_MORNING,
            NoticeId.GENTLER_THAN_ASKED,
        ),
        error=ErrorCode.PLACES_UNAVAILABLE,
    )
    page = present_result(result, CATALOGUE, NOW, SESSION, MODE, D39_ON)
    html = render_result(build_environment(), with_assets(page, STYLESHEET))

    bodies = [n.body for n in page.notices]
    assert bodies[0].startswith("It's dark now")
    assert copy.ERROR_MESSAGES[ErrorCode.PLACES_UNAVAILABLE] in bodies[1:]
    assert copy.NOTICE_MESSAGES[NoticeId.GENTLER_THAN_ASKED] in bodies[1:]
    assert html.count('class="wo-notice wo-notice-') == 1 + (1 if page.source_label else 0)
    assert 'wo-notices" aria-labelledby="notices-heading"' in html
    assert html.index(esc(bodies[0])) < html.index(esc(bodies[1]))
    assert '<ul class="wo-notice-list wo-notice-secondary">' in html


# --- TC-012 part D: directions to the place, never from the visitor ---------------------


def _with_place_ids(*ids: str) -> PlanResult:
    """Give the fixture's placed ideas these OSM identities, in order."""
    ideas = []
    todo = list(ids)
    for original in RESULT.ideas:
        idea = original
        if idea.pair.place is not None and todo:
            place = dataclasses.replace(idea.pair.place, place_id=todo.pop(0))
            idea = dataclasses.replace(idea, pair=dataclasses.replace(idea.pair, place=place))
        ideas.append(idea)
    return dataclasses.replace(RESULT, ideas=tuple(ideas))


@pytest.mark.parametrize(
    ("place_id", "expected"),
    [
        ("node:123", "https://www.openstreetmap.org/node/123"),
        ("way:4567", "https://www.openstreetmap.org/way/4567"),
        ("relation:89", "https://www.openstreetmap.org/relation/89"),
    ],
)
def test_a_placed_idea_links_its_own_osm_page(place_id: str, expected: str) -> None:
    result = _with_place_ids(place_id)
    page = present_result(result, CATALOGUE, NOW, SESSION, MODE, D39_ON)
    html = render_result(build_environment(), with_assets(page, STYLESHEET))
    first = page.ideas[0]
    assert first.place.directions_url == expected
    context = f'<span class="wo-vh"> {esc(copy.DIRECTIONS_CONTEXT)}</span>'
    tag = (
        f'<a href="{expected}" target="_blank" rel="noopener noreferrer">'
        f"{esc(copy.DIRECTIONS_LABEL)}{context}</a>"
    )
    assert tag in html
    # No coordinate and no route in any link.
    assert "mlat=" not in html
    assert "directions" not in html.lower()
    detail = present_detail(result, first.idea_id, CATALOGUE, NOW)
    detail_html = render_detail(build_environment(), with_assets(detail, STYLESHEET))
    assert expected in detail_html


@pytest.mark.parametrize("place_id", ["linden", "node:abc", "nodes:1", "node:", ":12", "way:1:2"])
def test_a_place_without_a_usable_osm_id_gets_no_link(place_id: str) -> None:
    result = _with_place_ids(place_id)
    page = present_result(result, CATALOGUE, NOW, SESSION, MODE, D39_ON)
    html = render_result(build_environment(), with_assets(page, STYLESHEET))
    assert page.ideas[0].place.directions_url is None
    # The other placed ideas keep their fixture ids, so the page carries no link at all.
    assert "openstreetmap.org/" not in html.replace("OpenStreetMap", "")
    detail = present_detail(result, page.ideas[0].idea_id, CATALOGUE, NOW)
    detail_html = render_detail(build_environment(), with_assets(detail, STYLESHEET))
    assert esc(copy.DIRECTIONS_LABEL) not in detail_html


def test_a_place_free_idea_has_no_directions_link() -> None:
    page = present_result(RESULT_GENERIC, CATALOGUE, NOW, SESSION, MODE, D39_ON)
    html = render_result(build_environment(), with_assets(page, STYLESHEET))
    assert page.ideas[0].place.directions_url is None
    assert "openstreetmap.org/" not in html.replace("OpenStreetMap", "")


# --- TC-012 part E: "Before you go" --------------------------------------------------------------

FORBIDDEN_SNACK_WORDS = ("grape", "nut", "popcorn")


def test_the_packing_box_renders_three_groups_with_tickable_boxes_and_the_reminder() -> None:
    page = present_result(RESULT, CATALOGUE, NOW, SESSION, MODE, D39_ON)
    html = render_result(build_environment(), with_assets(page, STYLESHEET))
    assert page.packing is not None
    assert page.packing.heading == copy.PACKING_HEADING
    # Weather and essentials before optional extras: the weather group leads when present,
    # and the ideas' optional items come last.
    assert page.packing.groups[-1].heading == copy.PACKING_GROUP_IDEAS
    assert copy.PACKING_GROUP_IDEAS in [g.heading for g in page.packing.groups]
    assert sum(len(g.items) for g in page.packing.groups) <= 10
    assert '<section class="wo-packing" aria-labelledby="packing-heading">' in html
    boxes = html.count('<label class="wo-checkrow"><input type="checkbox"><span>')
    assert boxes == sum(len(g.items) for g in page.packing.groups)
    assert esc(copy.PACKING_REMINDER) in html
    assert f"<strong>{esc(copy.PACKING_SNACK_LABEL)}:</strong>" in html
    # Under the cards, above the end of the results section.
    assert html.index('<div class="wo-cards">') < html.index('<section class="wo-packing"')


def test_with_the_youngest_the_snack_line_is_the_neutral_one_and_nothing_else() -> None:
    long_with_baby = dataclasses.replace(
        RESULT,
        answers=dataclasses.replace(
            RESULT.answers,
            age_bands=frozenset({AgeBand.B0_2, AgeBand.B6_9}),
            time_budget=TimeBudget.H2,
        ),
    )
    page = present_result(long_with_baby, CATALOGUE, NOW, SESSION, MODE, D39_ON)
    assert page.packing is not None
    assert page.packing.snack == copy.SNACKS[Snack.YOUNGEST]
    little = next(g for g in page.packing.groups if g.heading == copy.PACKING_GROUP_LITTLE_ONES)
    assert little.items[0] == copy.PACKING_ITEMS[PackingItem.NAPPIES]
    assert "Baby" not in " ".join(little.items)
    assert "usual snack" not in " ".join(little.items).lower()


def test_without_the_youngest_a_long_outing_adds_a_sandwich() -> None:
    long_one = dataclasses.replace(
        RESULT, answers=dataclasses.replace(RESULT.answers, time_budget=TimeBudget.H2)
    )
    page = present_result(long_one, CATALOGUE, NOW, SESSION, MODE, D39_ON)
    assert page.packing is not None
    assert page.packing.snack.endswith(copy.SNACK_SANDWICH)


def test_no_snack_or_packing_copy_names_grapes_nuts_or_popcorn() -> None:
    texts = [
        *copy.SNACKS.values(),
        copy.SNACK_SANDWICH,
        *copy.PACKING_ITEMS.values(),
    ]
    for text in texts:
        for word in FORBIDDEN_SNACK_WORDS:
            assert word not in text.lower(), (text, word)


def test_solo_gets_the_weather_group_and_coffee_only() -> None:
    solo = dataclasses.replace(
        RESULT,
        answers=dataclasses.replace(RESULT.answers, who=Who.SOLO, age_bands=frozenset()),
    )
    page = present_result(solo, CATALOGUE, NOW, SESSION, MODE, D39_ON)
    assert page.packing is not None
    headings = [g.heading for g in page.packing.groups]
    assert copy.PACKING_GROUP_LITTLE_ONES not in headings
    assert copy.PACKING_ITEMS[PackingItem.CHARGED_PHONE] in page.packing.groups[0].items
    assert page.packing.snack == copy.SNACKS[Snack.SOLO]


def test_a_result_without_ideas_has_no_packing_box() -> None:
    page = present_result(RESULT_NONE, CATALOGUE, NOW, SESSION, MODE, D39_ON)
    html = render_result(build_environment(), with_assets(page, STYLESHEET))
    assert page.packing is None
    assert "wo-packing" not in html
