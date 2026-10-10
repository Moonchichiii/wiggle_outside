"""The form page rendered from fixture view models (DESIGN-SPEC section 12).

Covers the empty, filled (carried answers, D46), error and ambiguous-town states, the
TC-001 energy labels, the no-inline-anything rule and the labelling of every control.
Accessibility is not claimed from these checks: axe, contrast and the keyboard and
screen-reader walkthroughs are WP9b's and have not run.
"""

import re
from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING

import pytest
from markupsafe import escape

from fixtures import CANDIDATES, CARRIED_ANSWERS, D39_OFF, D39_ON, FORM_ERRORS, SESSION
from parse import Document, read
from wiggle_outside.core.types import DeploymentMode, Energy
from wiggle_outside.web import copy
from wiggle_outside.web.presenters import build_environment, present_form, render_form
from wiggle_outside.web.views import FormContext

if TYPE_CHECKING:
    from wiggle_outside.web.views import FormPage

MODE = DeploymentMode.HOSTED_LIVE

# An inline event handler: on<name>= but not a legitimate attribute that merely starts
# with "on" (there is none in these templates).
INLINE_HANDLER = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
INLINE_STYLE = re.compile(r"\sstyle\s*=", re.IGNORECASE)


def _states() -> dict[str, FormPage]:
    return {
        "empty": present_form(FormContext(session=SESSION, mode=MODE, d39_enabled=D39_ON)),
        "filled": present_form(
            FormContext(session=SESSION, mode=MODE, d39_enabled=D39_ON, answers=CARRIED_ANSWERS)
        ),
        "errors": present_form(
            FormContext(session=SESSION, mode=MODE, d39_enabled=D39_ON, errors=FORM_ERRORS)
        ),
        "ambiguous": present_form(
            FormContext(session=SESSION, mode=MODE, d39_enabled=D39_ON, candidates=CANDIDATES)
        ),
        "no-d39": present_form(FormContext(session=SESSION, mode=MODE, d39_enabled=D39_OFF)),
    }


@pytest.fixture(scope="module")
def rendered() -> Mapping[str, str]:
    env = build_environment()
    return {name: render_form(env, page) for name, page in _states().items()}


@pytest.fixture(scope="module")
def documents(rendered: Mapping[str, str]) -> Mapping[str, Document]:
    return {name: read(html) for name, html in rendered.items()}


def _every(rendered: Mapping[str, str]) -> Iterator[tuple[str, str]]:
    return iter(rendered.items())


def esc(text: str) -> str:
    """Copy as it appears in the HTML: Jinja autoescape has run over it once."""
    return str(escape(text))


# --- TC-001 ---------------------------------------------------------------------------


def test_energy_options_render_the_values_as_gentle_moderate_high(
    documents: Mapping[str, Document],
) -> None:
    labels = {
        value: text
        for value, text in documents["empty"].option_labels
        if value in {e.value for e in Energy}
    }
    assert labels == {"gentle": "Gentle", "moderate": "Moderate", "energetic": "High"}


def test_the_word_energetic_appears_in_no_rendered_page(rendered: Mapping[str, str]) -> None:
    # TC-001: `energetic` is the submitted value; "Energetic" is never shown.
    for name, html in _every(rendered):
        assert "Energetic" not in html, name


def test_the_word_energetic_appears_in_no_copy_string() -> None:
    strings = [v for v in vars(copy).values() if isinstance(v, str)]
    strings += [
        text
        for value in vars(copy).values()
        if isinstance(value, Mapping)
        for text in value.values()
        if isinstance(text, str)
    ]
    assert strings, "no copy strings were collected"
    assert not [s for s in strings if "Energetic" in s]


def test_moderate_is_the_only_default(documents: Mapping[str, Document]) -> None:
    # DESIGN-SPEC section 6: defaults only where decided (D18).
    checked = [c.attrs.get("value") for c in documents["empty"].controls if "checked" in c.attrs]
    assert checked == ["moderate"]


# --- No inline script, style or handler (DESIGN-SPEC section 11) -------------------------


def test_no_inline_script_style_or_handler(rendered: Mapping[str, str]) -> None:
    for name, html in _every(rendered):
        assert "<script" not in html.lower(), name
        assert not INLINE_STYLE.search(html), name
        assert not INLINE_HANDLER.search(html), name
        assert "javascript:" not in html.lower(), name


def test_no_safe_filter_or_double_escaping(rendered: Mapping[str, str]) -> None:
    for name, html in _every(rendered):
        assert "&amp;amp;" not in html, name


def test_text_is_escaped_exactly_once() -> None:
    # BACKEND-CONTRACT section 7: "Oak & Elm <b>" renders once-escaped, never twice.
    hostile = CARRIED_ANSWERS.__class__(
        who=CARRIED_ANSWERS.who,
        age_bands=CARRIED_ANSWERS.age_bands,
        time_budget=CARRIED_ANSWERS.time_budget,
        energy=CARRIED_ANSWERS.energy,
        location=CARRIED_ANSWERS.location,
        location_label="Oak & Elm <b>",
        stroller=CARRIED_ANSWERS.stroller,
        step_free=CARRIED_ANSWERS.step_free,
    )
    html = render_form(
        build_environment(),
        present_form(FormContext(session=SESSION, mode=MODE, d39_enabled=D39_ON, answers=hostile)),
    )
    assert "Oak &amp; Elm &lt;b&gt;" in html
    assert "<b>" not in html
    assert "&amp;amp;" not in html


# --- Labelling ----------------------------------------------------------------------------


def test_every_visible_input_has_a_label(documents: Mapping[str, Document]) -> None:
    for name, doc in documents.items():
        for control in doc.controls:
            if control.tag != "input" or control.attrs.get("type") == "hidden":
                continue
            labelled = control.in_label or control.attrs.get("id") in doc.label_targets
            assert labelled, f"{name}: unlabelled input {control.attrs}"


def test_buttons_have_a_visible_label(documents: Mapping[str, Document]) -> None:
    for name, doc in documents.items():
        buttons = [c for c in doc.controls if c.tag == "button"]
        assert buttons, name
        for button in buttons:
            assert "aria-label" not in button.attrs, f"{name}: a button hides its label"


def test_ids_are_unique(documents: Mapping[str, Document]) -> None:
    for name, doc in documents.items():
        assert len(doc.ids) == len(set(doc.ids)), f"{name}: duplicate id"


def test_every_reference_resolves(documents: Mapping[str, Document]) -> None:
    for name, doc in documents.items():
        known = set(doc.ids)
        for target in doc.described_by:
            assert target in known, f"{name}: aria-describedby points at a missing {target}"
        for target in doc.label_targets:
            assert target in known, f"{name}: label points at a missing {target}"
        for target in doc.fragment_links:
            assert target in known, f"{name}: link points at a missing #{target}"


# --- Order and structure -------------------------------------------------------------------


def test_keyboard_order(documents: Mapping[str, Document]) -> None:
    # DESIGN-SPEC section 12: who, ages, time, energy, where, location, interests, submit.
    doc = documents["empty"]
    order: list[str] = []
    for control in doc.controls:
        key = control.attrs.get("name") or control.attrs.get("type", control.tag)
        if control.attrs.get("type") == "hidden" or control.attrs.get("tabindex") == "-1":
            continue
        if not order or order[-1] != key:
            order.append(key)
    assert order == [
        "who",
        "age_band",
        "time",
        "energy",
        "button",
        "place",
        "interests_text",
        "stroller",
        "step_free",
        "submit",
    ]


def test_the_form_posts_to_plan_and_carries_the_session(rendered: Mapping[str, str]) -> None:
    html = rendered["empty"]
    assert 'method="post" action="/plan"' in html
    assert f'name="csrf_token" value="{SESSION.csrf_token}"' in html
    assert f'name="idempotency_key" value="{SESSION.idempotency_key}"' in html


def test_the_honeypot_is_present_and_hidden(rendered: Mapping[str, str]) -> None:
    # D49: present in every plan form, hidden from keyboard and screen readers.
    for name, html in _every(rendered):
        assert 'name="hp_note"' in html, name
        assert 'tabindex="-1"' in html, name
        assert 'aria-hidden="true"><label for="hp_note">' in html, name


# --- States --------------------------------------------------------------------------------


def test_the_filled_state_carries_the_answers(
    documents: Mapping[str, Document], rendered: Mapping[str, str]
) -> None:
    doc = documents["filled"]
    checked = {
        c.attrs.get("name"): c.attrs.get("value") for c in doc.controls if "checked" in c.attrs
    }
    assert checked["who"] == "kids"
    assert checked["time"] == "60"
    assert checked["energy"] == "moderate"
    assert checked["step_free"] == "1"
    assert [c.attrs["value"] for c in doc.named("age_band") if "checked" in c.attrs] == [
        "3-5",
        "6-9",
    ]
    # D46: the rounded coordinates travel with the form, so no new geocode is needed.
    assert 'name="location_mode" value="coords"' in rendered["filled"]
    assert 'name="lat" value="60.42"' in rendered["filled"]
    assert esc(copy.CARRIED_LOCATION_SUFFIX) in rendered["filled"]


def test_the_error_state_matches_the_approved_mock(rendered: Mapping[str, str]) -> None:
    html = rendered["errors"]
    assert esc(copy.ERROR_SUMMARY_HEADING) in html
    assert 'role="alert" tabindex="-1" id="error-summary"' in html
    assert esc(copy.FIELD_INVALID_SUMMARY["age_band"]) in html
    assert esc(copy.FIELD_INVALID_SUMMARY["place"]) in html
    assert esc(copy.FIELD_INVALID["age_band"]) in html
    assert esc(copy.FIELD_INVALID["place"]) in html
    assert 'aria-invalid="true"' in html
    # The summary comes before the first fieldset it links to.
    assert html.index("error-summary") < html.index('id="age-first"')


def test_the_error_summary_is_in_keyboard_order() -> None:
    page = present_form(
        FormContext(session=SESSION, mode=MODE, d39_enabled=D39_ON, errors=FORM_ERRORS)
    )
    assert [item.field for item in page.summary] == ["age_band", "place"]
    assert [item.anchor for item in page.summary] == ["age-first", "place"]


def test_the_empty_state_shows_no_error_summary(rendered: Mapping[str, str]) -> None:
    assert "error-summary" not in rendered["empty"]
    assert esc(copy.ERROR_SUMMARY_HEADING) not in rendered["empty"]


def test_d39_off_removes_the_interests_field(
    documents: Mapping[str, Document], rendered: Mapping[str, str]
) -> None:
    assert not documents["no-d39"].named("interests_text")
    assert esc(copy.INTERESTS_HINT) not in rendered["no-d39"]
    assert esc(copy.INTERESTS_HINT) in rendered["empty"]


def test_the_ambiguous_state_lists_the_candidates(
    documents: Mapping[str, Document], rendered: Mapping[str, str]
) -> None:
    values = [c.attrs["value"] for c in documents["ambiguous"].named("candidate_id")]
    assert values == ["c1", "c2", "c3"]
    assert 'action="/location-choice"' in rendered["ambiguous"]
    # BACKEND-CONTRACT section 3: the town field stays editable, so focus is not trapped.
    assert documents["ambiguous"].named("place")


def test_the_place_hint_is_the_disclosed_wording(rendered: Mapping[str, str]) -> None:
    assert esc(copy.PLACE_HINT_BY_MODE[MODE]) in rendered["empty"]
    assert "30 days" in rendered["empty"]


def test_the_busy_note_is_static_markup(rendered: Mapping[str, str]) -> None:
    # D43: no stage messages, no Stop button, no polling.
    html = rendered["empty"]
    assert esc(copy.BUSY_NOTE) in html
    assert 'aria-live="polite"' in html
    assert "Stop" not in html
