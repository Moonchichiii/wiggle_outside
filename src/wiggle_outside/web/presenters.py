"""Builds the CONTRACTS section 8 view models, and the Jinja environment.

Every input is an explicit parameter: no globals, no hidden settings or catalogue
lookups. Presenters return plain-text strings; escaping happens exactly once, by Jinja
autoescape at the HTML boundary (BACKEND-CONTRACT section 7). Nothing here renders
`|safe` markup.

Importing this module has no side effects: `build_environment()` is called explicitly.
"""

from collections.abc import Mapping
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
    FormContext,
    FormPage,
    Option,
    PageMeta,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import datetime
from zoneinfo import ZoneInfo

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


def _submitted_coords(sent: Mapping[str, str]) -> tuple[str, str] | None:
    lat, lon = sent.get("lat"), sent.get("lon")
    return (lat, lon) if lat and lon else None


def _submitted_flag(sent: Mapping[str, str], name: str, fallback: bool) -> bool:  # noqa: FBT001
    return sent[name] == "1" if name in sent else fallback


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


def _expires_at(candidates: LocationCandidates | None, tz: str | None) -> str | None:
    """Candidate expiry in the planned location's timezone (CONTRACTS 8, CC-D).

    With no timezone the moment is rendered in whatever it carries, and the caller is
    told to pass one rather than the presenter guessing.
    """
    if candidates is None:
        return None
    moment = candidates.expires_at
    if tz is not None:
        moment = moment.astimezone(ZoneInfo(tz))
    return _hhmm(moment)


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
def _enum_opt[E](raw: str | None, parse: Callable[[str], E], fallback: E | None) -> E | None:
    """Parse a submitted value, falling back when it is absent or not a legal value.

    A 422 re-render must echo what the person chose, but an illegal value is exactly what
    made it a 422, so it cannot be preselected.
    """
    if not raw:
        return fallback
    try:
        return parse(raw)
    except ValueError:
        return fallback


def _enum_or[E](raw: str | None, parse: Callable[[str], E], fallback: E) -> E:
    """As _enum_opt, but with a real default, so the result is never None."""
    parsed = _enum_opt(raw, parse, fallback)
    return parsed if parsed is not None else fallback


def _submitted_ages(raw: str) -> frozenset[AgeBand]:
    bands = []
    for part in raw.split(","):
        try:
            bands.append(AgeBand(part.strip()))
        except ValueError:
            continue
    return frozenset(bands)


def _interests_prefill(context: FormContext) -> str | None:
    """Prefill the interests field with the recognised tag labels (D46, CC-C).

    Never the original free text: the labels are what we actually understood.
    """
    if not context.d39_enabled:
        return None
    submitted = context.submitted.get("interests_text")
    if submitted is not None:
        return submitted
    tags = context.interests.tags if context.interests else ()
    return ", ".join(copy.INTEREST_TAG_LABELS[tag] for tag in tags)


def present_form(context: FormContext) -> FormPage:
    """Build the form view model (CONTRACTS section 8).

    `context.answers` carries a previous result's answers (D46); `context.submitted`
    carries what was actually typed, which may be partial or ungeocodable, and wins field
    by field so a 422 keeps it (ERROR-HANDLING section 2). Energy defaults to Moderate
    (D18); nothing else is preselected.
    """
    values = context.answers
    sent = context.submitted
    coords = _submitted_coords(sent) or _coords(values)
    return FormPage(
        meta=PageMeta(
            title=copy.FORM_PAGE_TITLE,
            assets=dict(context.assets),
            demo_mode=context.mode is DeploymentMode.REPLAY,
        ),
        session=context.session,
        intro=copy.INTRO,
        who=_who_options(_enum_or(sent.get("who"), Who, values.who if values else None)),
        ages=_age_options(
            _submitted_ages(sent["age_band"])
            if "age_band" in sent
            else (values.age_bands if values else frozenset())
        ),
        time=_time_options(
            _enum_opt(
                sent.get("time"),
                lambda raw: TimeBudget(int(raw)),
                values.time_budget if values else None,
            )
        ),
        energy=_energy_options(
            _enum_or(sent.get("energy"), Energy, values.energy if values else DEFAULT_ENERGY)
            or DEFAULT_ENERGY
        ),
        location_mode=sent.get("location_mode", "coords" if coords else DEFAULT_LOCATION_MODE),
        # A typed town that failed to geocode is echoed back so it can be corrected.
        place=sent.get("place", ""),
        coords=coords,
        location_label=sent.get("location_label", values.location_label if values else None),
        place_hint=copy.PLACE_HINT_BY_MODE[context.mode],
        stroller=_submitted_flag(sent, "stroller", values.stroller if values else False),
        step_free=_submitted_flag(sent, "step_free", values.step_free if values else False),
        interests_text=_interests_prefill(context),
        field_errors=_field_errors(context.errors),
        summary=_error_summary(context.errors),
        candidates=_candidate_options(context.candidates),
        candidates_expire_at=_expires_at(context.candidates, context.candidates_tz),
    )


def with_assets(page: FormPage, assets: Mapping[str, AssetRef]) -> FormPage:
    """Attach a build manifest to an already-built page.

    Kept for a caller that builds a page before it knows its manifest. `FormContext`
    carries `assets`, so `present_form` no longer needs this (CC-B).
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
