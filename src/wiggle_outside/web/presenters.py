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

from wiggle_outside.core.errors import ErrorCode, NoticeId
from wiggle_outside.core.types import (
    COORD_DP,
    AgeBand,
    AnswersSummary,
    DeploymentMode,
    Energy,
    InterestOutcome,
    LocationCandidates,
    Source,
    TimeBudget,
    Who,
)
from wiggle_outside.web import copy
from wiggle_outside.web.forms import DEFAULT_ENERGY, DEFAULT_LOCATION_LABEL, DEFAULT_LOCATION_MODE
from wiggle_outside.web.views import (
    ActionView,
    ActivityView,
    AnswersView,
    AssetRef,
    BingoView,
    DetailPage,
    ErrorPage,
    FieldError,
    FormContext,
    FormPage,
    IdeaVariant,
    IdeaView,
    InterestsView,
    NoticeKind,
    NoticeView,
    Option,
    PageMeta,
    PlaceView,
    PrintView,
    ResultPage,
    SessionView,
    WeatherView,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import datetime

    from wiggle_outside.core.types import (
        Activity,
        Idea,
        Interests,
        InterestTag,
        Pair,
        Place,
        PlanResult,
        WeatherSummary,
    )
    from wiggle_outside.planner.ports import Catalogue
from zoneinfo import ZoneInfo

TEMPLATES_DIR: Final = Path(__file__).parent / "templates"
# Below this a distance rounds to 0.0 km; the card then says "close by" (copy).
CLOSE_BY_MAX_M: Final = 50
METRES_PER_KM: Final = 1000

# Card colour by position (CONTRACTS section 8: `variant`, from the idea's position).
IDEA_VARIANTS: Final[tuple[IdeaVariant, ...]] = ("sage", "peach", "butter")

# The two codes that replace the results heading with fixed copy and show no cards and no
# weather promise (BACKEND-CONTRACT section 1, DESIGN-SPEC section 12, TC-002).
DAYLIGHT_CODES: Final[frozenset[ErrorCode]] = frozenset(
    {ErrorCode.DAYLIGHT_NIGHT, ErrorCode.DAYLIGHT_TOO_SHORT}
)

# Codes a results page does not render as a notice.
# MODEL_FALLBACK is the result's source label (`ResultPage.source_label`), so repeating it
# as a notice would say the same sentence twice.
# PLACES_CACHED needs the age of the cached place data ("last checked {age} ago"), and no
# view model or presenter parameter carries it, so it is raised as a contract change
# rather than rendered with an unfilled placeholder.
NOT_A_RESULT_NOTICE: Final[frozenset[ErrorCode]] = frozenset(
    {ErrorCode.MODEL_FALLBACK, ErrorCode.PLACES_CACHED}
)

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
            icon=None,  # the board's time tiles are control + label only
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


def with_assets[P: FormPage | ResultPage | DetailPage | ErrorPage](
    page: P, assets: Mapping[str, AssetRef]
) -> P:
    """Attach a build manifest to an already-built page.

    `FormContext` carries `assets`, so `present_form` no longer needs this (CC-B). The
    other three presenters have no assets parameter in their CONTRACTS section 8
    signature and a presenter must never reach for the manifest, so this is how the
    caller, which knows it, hands it over.
    """
    return replace(page, meta=replace(page.meta, assets=dict(assets)))


# --- Times, dates and places -------------------------------------------------------------


def _at(moment: datetime, tz: str) -> datetime:
    """Convert a moment to the planned location's timezone, never the server's."""
    return moment.astimezone(ZoneInfo(tz))


def _time(moment: datetime, tz: str) -> str:
    return _hhmm(_at(moment, tz))


def _date(moment: datetime, tz: str) -> str:
    """Render a date as Sat 10 Oct 2026 (CONTRACTS 8), from fixed names, not the locale."""
    local = _at(moment, tz)
    weekday = copy.WEEKDAYS[local.weekday()]
    return f"{weekday} {local.day} {copy.MONTHS[local.month - 1]} {local.year}"


def _kind_label(place: Place | None) -> str:
    if place is None:
        return copy.PLACE_KIND_GENERIC
    return copy.PLACE_KIND_LABELS.get(place.kind, place.kind.replace("_", " "))


def _uncertainty(place: Place | None) -> tuple[str, ...]:
    """Return the fee and access labels that apply, and only those (D37, D42 P)."""
    if place is None:
        return ()
    labels: list[str] = []
    if place.fee == "unknown":
        labels.append(copy.FEE_UNKNOWN)
    elif place.fee == "no":
        labels.append(copy.FEE_REPORTED_FREE)
    labels.append(copy.STEP_FREE_REPORTED if place.osm_access == "yes" else copy.STEP_FREE_UNKNOWN)
    return tuple(labels)


def _km(metres: int) -> str:
    return f"{metres / METRES_PER_KM:.1f}"


def _distance(metres: int | None) -> str | None:
    """Say the distance to one decimal of a kilometre, or "close by" below that precision."""
    if metres is None:
        return None
    if metres < CLOSE_BY_MAX_M:
        return copy.DISTANCE_CLOSE_BY
    return copy.DISTANCE.format(km=_km(metres))


def _place_view(pair: Pair) -> PlaceView:
    distance = _distance(pair.distance_m)
    return PlaceView(
        name=pair.place.name if pair.place is not None else None,
        kind_label=_kind_label(pair.place),
        distance=distance,
        uncertainty=_uncertainty(pair.place),
    )


# --- The shared weather line ---------------------------------------------------------------


def _temperature(weather: WeatherSummary) -> str:
    if weather.temp_min_c == weather.temp_max_c:
        return copy.WEATHER_TEMPERATURE_ONE.format(value=weather.temp_min_c)
    return copy.WEATHER_TEMPERATURE_RANGE.format(low=weather.temp_min_c, high=weather.temp_max_c)


def _forecast(weather: WeatherSummary) -> str:
    # No "(up to 0 %)": a zero probability is not worth a clause.
    rain = (
        copy.WEATHER_RAIN.format(percent=weather.max_precip_probability)
        if weather.max_precip_probability > 0
        else ""
    )
    return copy.WEATHER_SUMMARY.format(
        condition=copy.WEATHER_CONDITIONS[weather.condition],
        rain=rain,
        temperature=_temperature(weather),
        wind=weather.max_wind_kmh,
    )


def _weather_view(weather: WeatherSummary, *, example: bool = False) -> WeatherView:
    window = copy.WEATHER_WINDOW.format(
        start=_time(weather.window_start, weather.tz),
        end=_time(weather.window_end, weather.tz),
    )
    checked_at = _time(weather.fetched_at, weather.tz)
    return WeatherView(
        icon=copy.WEATHER_ICONS[weather.condition],
        line=copy.WEATHER_LINE.format(window=window, time=checked_at, summary=_forecast(weather)),
        checked_at=checked_at,
        window=window,
        example=copy.EXAMPLE_FORECAST if example else None,
        example_note=copy.EXAMPLE_NOTE if example else None,
    )


# --- The answers summary and the interest labels -------------------------------------------


def _near(label: str) -> str:
    """Say where, mid-sentence: the device label reads "near your location" (TC-011)."""
    if label == DEFAULT_LOCATION_LABEL:
        return copy.ANSWERS_NEAR_YOUR_LOCATION
    return copy.ANSWERS_NEAR.format(label=label)


def _answers_view(answers: AnswersSummary) -> AnswersView:
    ages = copy.AGES_JOIN.join(
        copy.AGE_LABELS[band] for band in AgeBand if band in answers.age_bands
    )
    who = copy.WHO_LABELS[answers.who]
    summary = copy.ANSWERS_JOIN.join(
        (
            copy.ANSWERS_WITH_AGES.format(who=who, ages=ages) if ages else who,
            copy.TIME_LABELS[answers.time_budget],
            copy.ENERGY_LABELS[answers.energy],
            _near(answers.location_label),
        )
    )
    # D42: two answers with different effects, each shown only when it was given.
    extras = [
        label
        for given, label in (
            (answers.stroller, copy.STROLLER_LABEL),
            (answers.step_free, copy.STEP_FREE_LABEL),
        )
        if given
    ]
    return AnswersView(lines=(summary, *extras), change_label=copy.CHANGE_ANSWERS)


def _matched_interests(
    activity: Activity, tags: tuple[InterestTag, ...]
) -> tuple[InterestTag, ...]:
    """Return the tags this activity covers, in the result's own tag order.

    This is `core.ideas.matched_interests` (CONTRACTS section 2, PRODUCT-FIT section 3.3),
    which WP1 has not implemented yet: `core/ideas.py` is still a stub. The same
    intersection is computed here so the match line is never stale, and this helper is
    deleted in favour of the core function as soon as it lands.
    """
    return tuple(tag for tag in tags if tag in activity.interests)


def _interest_match(activity: Activity, interests: Interests | None) -> str | None:
    """Build the match line from the result's own validated tags (PRODUCT-FIT 3.3)."""
    if interests is None or interests.outcome is not InterestOutcome.MATCHED:
        return None
    matched = _matched_interests(activity, interests.tags)
    if not matched:
        return None
    labels = copy.INTERESTS_LIST_JOIN.join(copy.INTEREST_TAG_LABELS[tag] for tag in matched)
    return copy.INTEREST_MATCH.format(tags=labels)


def _interests_view(result: PlanResult, *, d39_enabled: bool) -> InterestsView | None:
    """Build the plain labels, and only when the interpretation was valid (PRODUCT-FIT 3.4)."""
    interests = result.interests
    if not d39_enabled or interests is None:
        return None
    if interests.outcome is not InterestOutcome.MATCHED or not interests.tags:
        return None
    who = result.answers.who
    return InterestsView(
        heading=copy.INTERESTS_HEADING_BY_WHO[who],
        labels=tuple(copy.INTEREST_TAG_LABELS[tag] for tag in interests.tags),
        note=copy.INTERESTS_NOTE.format(legend=copy.INTERESTS_LEGEND_BY_WHO[who]),
    )


# --- Ideas and notices -----------------------------------------------------------------------


def _idea_views(result: PlanResult, catalogue: Catalogue) -> tuple[IdeaView, ...]:
    """One view per idea, in the result's display order. Never padded (0-3, FEWER_MATCHES).

    Titles, hooks and reasons are catalogue text, rendered verbatim; the model contributes
    only the IDs that select them (PLAN section 3).
    """
    activities = {entry.activity_id: entry for entry in catalogue.activities()}
    hooks = {hook.hook_id: hook.text for hook in catalogue.hooks()}
    reasons = {reason.reason_id: reason.text for reason in catalogue.reasons()}
    views: list[IdeaView] = []
    for index, idea in enumerate(result.ideas):
        activity = activities[idea.pair.activity_id]
        views.append(
            IdeaView(
                idea_id=idea.pair.idea_id,
                variant=IDEA_VARIANTS[index % len(IDEA_VARIANTS)],
                title=activity.title,
                intro=hooks[idea.hook_id],
                reasons=tuple(reasons[reason_id] for reason_id in idea.reason_ids),
                interest_match=_interest_match(activity, result.interests),
                place=_place_view(idea.pair),
                times=copy.TIMES.format(
                    travel=idea.pair.travel_min, duration=idea.pair.duration_min
                ),
                detail_url=f"/results/{result.job_id}/ideas/{idea.pair.idea_id}",
                illustration=copy.ACTIVITY_ILLUSTRATIONS.get(
                    activity.activity_id, copy.DEFAULT_ILLUSTRATION
                ),
            )
        )
    return tuple(views)


def _notice_body(code: NoticeId | ErrorCode, idea_count: int) -> str | None:
    """Return the reviewed text for one notice, or None when there is none to render."""
    if isinstance(code, NoticeId):
        # REPLAY has no reviewed copy: the replay demo is inactive (D24, D48).
        return copy.NOTICE_MESSAGES.get(code)
    if code is ErrorCode.FEWER_MATCHES:
        return copy.ERROR_MESSAGES[code].format(count=idea_count)
    if code in NOT_A_RESULT_NOTICE:
        return None
    return copy.ERROR_MESSAGES[code]


def _notice_views(result: PlanResult) -> tuple[NoticeView, ...]:
    """Build the notices, the result's own error first, each as plain reviewed text.

    On a DAYLIGHT_NIGHT or DAYLIGHT_TOO_SHORT page the first notice is the fixed body copy
    that belongs under the heading, which is why the error comes first.
    """
    bodies: list[tuple[NoticeKind, str]] = []
    error = result.error
    if error is not None and error not in NOT_A_RESULT_NOTICE:
        # The daylight copy is calm, deliberate guidance, not an alert (ERROR-HANDLING 1).
        kind: NoticeKind = "info" if error in DAYLIGHT_CODES else "alert"
        error_body = _notice_body(error, len(result.ideas))
        if error_body is not None:
            bodies.append((kind, error_body))
    for code in result.notices:
        if code == error:
            continue
        body = _notice_body(code, len(result.ideas))
        if body is not None:
            bodies.append(("info", body))
    return tuple(
        NoticeView(kind=kind, heading=None, body=body, actions=()) for kind, body in bodies
    )


def _historical_text(result: PlanResult) -> str | None:
    """Build the "no longer current" wording, dated in the planned location's timezone.

    Without a weather summary there is no such timezone, and CONTRACTS section 8 forbids
    showing the server's; such a result has no ideas to date either, and its own notice
    already says what happened, so the dated sentence is simply not shown.
    """
    weather = result.weather
    if weather is None:
        return None
    return copy.HISTORICAL.format(
        date=_date(result.planned_start, weather.tz),
        start=_time(result.planned_start, weather.tz),
        end=_time(result.planned_end, weather.tz),
        time=_time(weather.fetched_at, weather.tz),
    )


# --- The results page ---------------------------------------------------------------------


# CONTRACTS section 8 fixes this signature and WP7 calls it positionally, so the
# argument-count and boolean-flag rules are suppressed rather than the contract bent.
def present_result(  # noqa: PLR0913, PLR0917
    result: PlanResult,
    catalogue: Catalogue,
    now: datetime,
    session: SessionView,
    mode: DeploymentMode,
    d39_enabled: bool,  # noqa: FBT001
) -> ResultPage:
    """Build the results view model (CONTRACTS section 8).

    Times and dates are rendered in `WeatherSummary.tz`, the timezone of the planned
    location. Ideas are never padded. The DAYLIGHT_NIGHT and DAYLIGHT_TOO_SHORT pages put
    their fixed heading in the results heading position and show no cards and no weather
    promise, while keeping the answers summary and "Change answers" (TC-002).
    """
    fixed_copy = result.error in DAYLIGHT_CODES
    heading = (
        copy.ERROR_HEADINGS[result.error]
        if fixed_copy and result.error is not None
        else copy.RESULTS_HEADING
    )
    weather = (
        None
        if fixed_copy or result.weather is None
        else _weather_view(result.weather, example=NoticeId.REPLAY in result.notices)
    )
    is_historical = now > result.valid_until
    return ResultPage(
        meta=PageMeta(
            title=copy.PAGE_TITLE,
            assets={},
            demo_mode=mode is DeploymentMode.REPLAY,
        ),
        session=session,
        heading=heading,
        answers=_answers_view(result.answers),
        edit_form=present_form(
            FormContext(
                session=session,
                mode=mode,
                d39_enabled=d39_enabled,
                answers=result.answers,
                interests=result.interests,
            )
        ),
        weather=weather,
        ideas=() if fixed_copy else _idea_views(result, catalogue),
        notices=_notice_views(result),
        interests=None if fixed_copy else _interests_view(result, d39_enabled=d39_enabled),
        # A daylight page shows no picks, so there is nothing for the label to describe.
        source_label=(
            copy.ERROR_MESSAGES[ErrorCode.MODEL_FALLBACK]
            if result.source is Source.FALLBACK and not fixed_copy
            else None
        ),
        is_historical=is_historical,
        historical_text=_historical_text(result) if is_historical else None,
        plan_again=ActionView(label=copy.PLAN_AGAIN, url="/", method="get", csrf_token=None),
    )


# --- The detail page ------------------------------------------------------------------------


def _find_index(result: PlanResult, idea_id: str) -> int:
    for index, idea in enumerate(result.ideas):
        if idea.pair.idea_id == idea_id:
            return index
    # CONTRACTS section 5: an idea_id that is not in the result is a 404. The caller turns
    # this lookup failure into one; a presenter never invents a page for an unknown idea.
    raise KeyError(idea_id)


def _activity_view(activity: Activity) -> ActivityView:
    card = BingoView(heading=copy.BINGO_HEADING, items=activity.card) if activity.card else None
    return ActivityView(
        steps=activity.steps,
        optional=activity.optional,
        adapt=activity.adapt,
        ask=activity.ask,
        safety=activity.safety,
        card=card,
    )


def _print_location(label: str) -> str:
    return "your location" if label == DEFAULT_LOCATION_LABEL else label


def _print_view(result: PlanResult, weather: WeatherSummary) -> PrintView:
    """Build the dated context a printed card keeps for as long as it exists (section 10)."""
    return PrintView(
        context_line=copy.PRINT_CONTEXT.format(
            date=_date(result.planned_start, weather.tz),
            start=_time(result.planned_start, weather.tz),
            end=_time(result.planned_end, weather.tz),
            tz=weather.tz,
            location=_print_location(result.answers.location_label),
        ),
        weather_line=copy.PRINT_WEATHER.format(
            time=_time(weather.fetched_at, weather.tz),
            date=_date(weather.fetched_at, weather.tz),
        ),
        source_line=copy.PRINT_SOURCE,
        note=copy.PRINT_NOTE,
    )


def _detail_activity(catalogue: Catalogue, idea: Idea) -> ActivityView:
    activities = {entry.activity_id: entry for entry in catalogue.activities()}
    return _activity_view(activities[idea.pair.activity_id])


def present_detail(
    result: PlanResult, idea_id: str, catalogue: Catalogue, now: datetime
) -> DetailPage:
    """Build one idea's detail and print view (CONTRACTS section 8).

    The result is immutable (D46), so this page shows the same content for as long as the
    result is retained; past `valid_until` it renders the historical view.
    """
    index = _find_index(result, idea_id)
    idea = result.ideas[index]
    weather = result.weather
    if weather is None:
        # An idea only exists when the weather was checked (D16), so this cannot happen
        # for a real result; failing here is better than inventing a weather line.
        msg = "a result with ideas has a weather summary"
        raise ValueError(msg)
    is_historical = now > result.valid_until
    historical = _historical_text(result) if is_historical else None
    return DetailPage(
        meta=PageMeta(title=copy.PAGE_TITLE, assets={}, demo_mode=False),
        idea=_idea_views(result, catalogue)[index],
        activity=_detail_activity(catalogue, idea),
        weather=_weather_view(weather),
        print=_print_view(result, weather),
        notices=(
            (NoticeView(kind="alert", heading=None, body=historical, actions=()),)
            if historical is not None
            else ()
        ),
        is_historical=is_historical,
        back_url=f"/results/{result.job_id}",
        print_label=copy.PRINT_LABEL,
    )


# --- The error page -------------------------------------------------------------------------


def _error_body(code: ErrorCode, reference: str | None) -> str:
    """ERROR-HANDLING section 2 copy with its placeholders filled, never left showing."""
    message = copy.ERROR_MESSAGES[code]
    if code is ErrorCode.UNEXPECTED_FAILURE:
        return message.format(reference=reference or "")
    if code is ErrorCode.SERVICE_LIMIT_REACHED:
        # D49: the daily allowance rolls over at 00:00 UTC and nothing else resets it.
        return message.format(reset_time=copy.SERVICE_RESET_TIME)
    return message


def present_error(code: ErrorCode, reference: str | None, form: FormPage | None) -> ErrorPage:
    """Build the error page (CONTRACTS section 8).

    `form` is the re-rendered, answer-keeping form a 422 shows; when it is present the
    page offers no separate action, because the form's own submit is the recovery
    (ERROR-HANDLING section 5: an action only when it can work). `reference` is required
    for UNEXPECTED_FAILURE, whose reviewed copy names it.
    """
    actions = (
        ()
        if form is not None
        else (ActionView(label=copy.RETURN_TO_FORM, url="/", method="get", csrf_token=None),)
    )
    return ErrorPage(
        meta=PageMeta(title=copy.PAGE_TITLE, assets={}, demo_mode=False),
        notice=NoticeView(
            kind="alert",
            heading=copy.ERROR_HEADINGS.get(code),
            body=_error_body(code, reference),
            actions=actions,
        ),
        reference=reference,
        form=form,
    )


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


def render_result(env: Environment, page: ResultPage) -> str:
    """Render the results page, including the daylight pages (DESIGN-SPEC section 12)."""
    return env.get_template("pages/results.html").render(page=page, copy=copy)


def render_detail(env: Environment, page: DetailPage) -> str:
    """Render one idea's detail and print view."""
    return env.get_template("pages/detail.html").render(page=page, copy=copy)


def render_error(env: Environment, page: ErrorPage) -> str:
    """Render the error page, with the answer-keeping form when there is one."""
    return env.get_template("pages/error.html").render(page=page, copy=copy)
