"""Builds the CONTRACTS section 8 view models, and the Jinja environment.

Every input is an explicit parameter: no globals, no hidden settings or catalogue
lookups. Presenters return plain-text strings; escaping happens exactly once, by Jinja
autoescape at the HTML boundary (BACKEND-CONTRACT section 7). Nothing here renders
`|safe` markup.

Importing this module has no side effects: `build_environment()` is called explicitly.
"""

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Final

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import (
    COORD_DP,
    AgeBand,
    AnswersSummary,
    DeploymentMode,
    Energy,
    LocationCandidates,
    TimeBudget,
    Who,
)
from wiggle_outside.web import copy
from wiggle_outside.web.forms import DEFAULT_ENERGY, DEFAULT_LOCATION_MODE
from wiggle_outside.web.views import (
    AssetRef,
    FieldError,
    FormPage,
    Option,
    PageMeta,
    SessionView,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

TEMPLATES_DIR: Final = Path(__file__).parent / "templates"

# The keyboard and error-summary order (DESIGN-SPEC section 12).
FIELD_ORDER: Final[tuple[str, ...]] = (
    "who",
    "age_band",
    "time",
    "energy",
    "place",
    "interests_text",
)

_NO_ASSETS: Final[Mapping[str, AssetRef]] = {}


# --- Option builders ------------------------------------------------------------------


def _who_options(selected: Who | None) -> tuple[Option, ...]:
    return tuple(
        Option(
            value=who.value,
            label=copy.WHO_LABELS[who],
            icon=copy.WHO_ICONS[who],
            checked=who is selected,
        )
        for who in Who
    )


def _age_options(selected: frozenset[AgeBand]) -> tuple[Option, ...]:
    return tuple(
        Option(
            value=band.value,
            label=copy.AGE_LABELS[band],
            icon=None,
            checked=band in selected,
        )
        for band in AgeBand
    )


def _time_options(selected: TimeBudget | None) -> tuple[Option, ...]:
    return tuple(
        Option(
            value=str(budget.value),
            label=copy.TIME_LABELS[budget],
            icon=copy.TIME_ICONS[budget],
            checked=budget is selected,
        )
        for budget in TimeBudget
    )


def _energy_options(selected: Energy) -> tuple[Option, ...]:
    # TC-001: the value stays `energetic`, the label reads High.
    return tuple(
        Option(
            value=energy.value,
            label=copy.ENERGY_LABELS[energy],
            icon=copy.ENERGY_ICONS[energy],
            checked=energy is selected,
        )
        for energy in Energy
    )


def _candidate_options(candidates: LocationCandidates | None) -> tuple[Option, ...]:
    if candidates is None:
        return ()
    return tuple(
        Option(value=c.candidate_id, label=c.label, icon=None, checked=False)
        for c in candidates.candidates
    )


def _expires_at(candidates: LocationCandidates | None) -> str | None:
    if candidates is None:
        return None
    return _hhmm(candidates.expires_at)


def _hhmm(moment: datetime) -> str:
    return moment.strftime("%H:%M")


# --- Errors ---------------------------------------------------------------------------


def _message(field: str, code: ErrorCode) -> str:
    if code is ErrorCode.INPUT_INVALID and field in copy.FIELD_INVALID:
        return copy.FIELD_INVALID[field]
    return copy.ERROR_MESSAGES[code]


def _summary_message(field: str, code: ErrorCode) -> str:
    if code is ErrorCode.INPUT_INVALID and field in copy.FIELD_INVALID_SUMMARY:
        return copy.FIELD_INVALID_SUMMARY[field]
    label = copy.FIELD_LABELS.get(field, field)
    return f"{label}: {copy.ERROR_MESSAGES[code]}"


def _anchor(field: str) -> str:
    return copy.FIELD_ANCHORS.get(field, field)


def _field_errors(errors: Mapping[str, ErrorCode]) -> dict[str, FieldError]:
    return {
        field: FieldError(field=field, anchor=_anchor(field), message=_message(field, code))
        for field, code in errors.items()
    }


def _error_summary(errors: Mapping[str, ErrorCode]) -> tuple[FieldError, ...]:
    ordered = sorted(
        errors, key=lambda f: (FIELD_ORDER.index(f) if f in FIELD_ORDER else len(FIELD_ORDER), f)
    )
    return tuple(
        FieldError(
            field=field,
            anchor=_anchor(field),
            message=_summary_message(field, errors[field]),
        )
        for field in ordered
    )


# --- Location --------------------------------------------------------------------------


def _coords(values: AnswersSummary | None) -> tuple[str, str] | None:
    # D46: a carried result's coordinates, already rounded, so no new geocode is needed.
    if values is None:
        return None
    return (
        f"{values.location.lat:.{COORD_DP}f}",
        f"{values.location.lon:.{COORD_DP}f}",
    )


# --- The form page -----------------------------------------------------------------------


# CONTRACTS section 8 fixes this signature and WP7 calls it positionally; a package may
# not change a contract file (CONTRACTS section 10.1), so the argument-count and
# boolean-flag rules are suppressed here rather than the contract being bent to them.
def present_form(  # noqa: PLR0913, PLR0917
    values: AnswersSummary | None,
    errors: Mapping[str, ErrorCode],
    session: SessionView,
    candidates: LocationCandidates | None,
    mode: DeploymentMode,
    d39_enabled: bool,  # noqa: FBT001 - positional in the CONTRACTS section 8 signature.
) -> FormPage:
    """Build the form view model (CONTRACTS section 8).

    `values` is the carried answers summary of an earlier search (D46) or None for a
    first visit. Energy defaults to Moderate (D18); nothing else is preselected.
    """
    coords = _coords(values)
    return FormPage(
        meta=PageMeta(
            title=copy.FORM_PAGE_TITLE,
            assets=_NO_ASSETS,
            demo_mode=mode is DeploymentMode.REPLAY,
        ),
        session=session,
        intro=copy.INTRO,
        who=_who_options(values.who if values else None),
        ages=_age_options(values.age_bands if values else frozenset()),
        time=_time_options(values.time_budget if values else None),
        energy=_energy_options(values.energy if values else DEFAULT_ENERGY),
        location_mode="coords" if coords else DEFAULT_LOCATION_MODE,
        place="",
        coords=coords,
        location_label=values.location_label if values else None,
        place_hint=copy.PLACE_HINT_BY_MODE[mode],
        stroller=values.stroller if values else False,
        step_free=values.step_free if values else False,
        interests_text="" if d39_enabled else None,
        field_errors=_field_errors(errors),
        summary=_error_summary(errors),
        candidates=_candidate_options(candidates),
        candidates_expire_at=_expires_at(candidates),
    )


def with_assets(page: FormPage, assets: Mapping[str, AssetRef]) -> FormPage:
    """Attach a build manifest to a page.

    `present_form` has no manifest parameter (CONTRACTS section 8), so the caller that
    knows the manifest attaches it here rather than a presenter reaching for a global.
    """
    return replace(page, meta=replace(page.meta, assets=dict(assets)))


# --- Rendering ---------------------------------------------------------------------------


def build_environment(searchpath: Path = TEMPLATES_DIR) -> Environment:
    """Build a Jinja environment with autoescape on and undefined names fatal."""
    return Environment(
        loader=FileSystemLoader(searchpath),
        autoescape=select_autoescape(default=True, default_for_string=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def render_form(env: Environment, page: FormPage) -> str:
    """Render the form page. Templates see the view model and the copy table only."""
    return env.get_template("pages/form.html").render(page=page, copy=copy)
