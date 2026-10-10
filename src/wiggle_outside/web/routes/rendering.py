"""The seam between a route and the pages it renders.

The routes gather the CONTRACTS section 8 arguments into one carrier each and hand them
to a `Pages` implementation. The protocol is owned here, by the consumer
(PLAN section 7), so WP8's presenters can replace the interim renderer below without a
route changing.

`InterimPages` renders the real form page through `present_form`, and the result, detail
and error pages through small templates of its own, because `present_result`,
`present_detail` and `present_error` and their templates are WP8's and do not exist yet.
Everything it emits is escaped once, by Jinja autoescape; no inline script or style.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol

from jinja2 import DictLoader, Environment, StrictUndefined

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import (
    AnswersSummary,
    DeploymentMode,
    Idea,
    PlanResult,
)
from wiggle_outside.web import copy
from wiggle_outside.web.presenters import build_environment, present_form, render_form
from wiggle_outside.web.views import AssetRef, FormContext, SessionView

# --- What a page needs (CONTRACTS section 8) ----------------------------------------


@dataclass(frozen=True, slots=True)
class ResultContext:
    """The arguments of `present_result`, in one carrier."""

    result: PlanResult
    now: datetime
    session: SessionView
    mode: DeploymentMode
    d39_enabled: bool
    assets: Mapping[str, AssetRef]


@dataclass(frozen=True, slots=True)
class DetailContext:
    """The arguments of `present_detail`, in one carrier."""

    result: PlanResult
    idea_id: str
    now: datetime
    mode: DeploymentMode
    assets: Mapping[str, AssetRef]


@dataclass(frozen=True, slots=True)
class ErrorContext:
    """The arguments of `present_error`, in one carrier.

    `active_url` is not in the CONTRACTS section 8 signature; the REQUEST_BUSY row needs
    an error page "linking to the active result" (CONTRACTS section 3) and
    `present_error(code, reference, form)` has nowhere to put it. Raised as a
    contract-change proposal; carried here meanwhile.
    """

    code: ErrorCode
    reference: str | None
    form: FormContext | None
    mode: DeploymentMode
    assets: Mapping[str, AssetRef]
    active_url: str | None = None


class Pages(Protocol):
    """Turn one request's values into one complete HTML page. Never a fragment."""

    def form(self, context: FormContext) -> str: ...

    def result(self, context: ResultContext) -> str: ...

    def detail(self, context: DetailContext) -> str: ...

    def error(self, context: ErrorContext) -> str: ...


# --- The interim renderer -------------------------------------------------------------

_SHELL: Final = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
{% for name, asset in assets.items() %}
{% if name.endswith(".css") %}
<link rel="stylesheet" href="{{ asset.url }}"
{%- if asset.integrity %} integrity="{{ asset.integrity }}"{% endif %}>
{% endif %}
{% endfor %}
</head>
<body class="wo-body">
<div class="wo-page">
<header class="wo-masthead"><h1 class="wo-title">{{ heading }}</h1></header>
<main class="wo-column" id="main">
{% block main %}{% endblock %}
</main>
</div>
</body>
</html>
"""

_RESULTS: Final = """{% extends "shell" %}
{% block main %}
{% for notice in notices %}
<p class="wo-notice" role="status">{{ notice }}</p>
{% endfor %}
{% if weather %}
<p class="wo-weather">{{ weather }}</p>
{% endif %}
{% if ideas %}
<ul class="wo-ideas">
{% for idea in ideas %}
<li class="wo-card">
<h2>{{ idea.title }}</h2>
<p>{{ idea.place }}</p>
<p>{{ idea.times }}</p>
<p><a href="{{ idea.url }}">Idea details</a></p>
</li>
{% endfor %}
</ul>
{% endif %}
<h2>{{ answers_heading }}</h2>
<ul class="wo-answers">
{% for line in answers %}
<li>{{ line }}</li>
{% endfor %}
</ul>
<p><a href="/">{{ change_label }}</a></p>
{% endblock %}
"""

_DETAIL: Final = """{% extends "shell" %}
{% block main %}
<h2>{{ idea.title }}</h2>
<p>{{ idea.place }}</p>
<p>{{ idea.times }}</p>
{% if historical %}
<p class="wo-notice" role="status">{{ historical }}</p>
{% endif %}
<p><a href="{{ back_url }}">{{ back_label }}</a></p>
{% endblock %}
"""

_ERROR: Final = """{% extends "shell" %}
{% block main %}
<p class="wo-notice" role="alert">{{ message }}</p>
{% if reference %}
<p class="wo-reference">{{ reference_label }}</p>
{% endif %}
{% if active_url %}
<p><a href="{{ active_url }}">{{ active_label }}</a></p>
{% endif %}
{% if change_label %}
<p><a href="/">{{ change_label }}</a></p>
{% else %}
<p><a href="/">{{ start_label }}</a></p>
{% endif %}
{% endblock %}
"""

START_AGAIN: Final = "Start a new search"
ACTIVE_RESULT: Final = "Go to the outing we are already finding"
BACK_TO_RESULTS: Final = "Back to the ideas"
ANSWERS_HEADING: Final = "Your answers"
HISTORICAL: Final = "This result is from an earlier search."
IDEA_DETAILS_TITLE: Final = "Idea details"
REFERENCE_LABEL: Final = "Reference: {reference}"
# The daily allowance rolls over at 00:00 UTC (DEPLOYMENT section 2.3).
MIDNIGHT_UTC: Final = "00:00 UTC"


@dataclass(frozen=True, slots=True)
class _Card:
    title: str
    place: str
    times: str
    url: str


def _card(idea: Idea, job_id: str) -> _Card:
    place = idea.pair.place
    where = place.name if place is not None else "No particular place needed"
    distance = f", about {idea.pair.distance_m} m away" if idea.pair.distance_m else ""
    return _Card(
        # The activity title comes from the catalogue, which WP2 owns and which is not
        # wired yet, so the interim card shows the stable activity ID instead.
        title=idea.pair.activity_id,
        place=f"{where}{distance}",
        times=(f"{idea.pair.travel_min} min there and back, {idea.pair.duration_min} min activity"),
        url=f"/results/{job_id}/ideas/{idea.pair.idea_id}",
    )


def _answer_lines(answers: AnswersSummary) -> tuple[str, ...]:
    lines = [
        f"{copy.WHO_LEGEND} {copy.WHO_LABELS[answers.who]}",
        f"{copy.TIME_LEGEND}: {copy.TIME_LABELS[answers.time_budget]}",
        f"{copy.ENERGY_LEGEND} {copy.ENERGY_LABELS[answers.energy]}",
        f"{copy.WHERE_LEGEND} {answers.location_label}",
    ]
    if answers.age_bands:
        bands = ", ".join(copy.AGE_LABELS[band] for band in sorted(answers.age_bands))
        lines.insert(1, f"{copy.AGES_LEGEND}: {bands}")
    if answers.stroller:
        lines.append(copy.STROLLER_LABEL)
    if answers.step_free:
        lines.append(copy.STEP_FREE_LABEL)
    return tuple(lines)


class _Params(dict[str, object]):
    """Leave a copy placeholder we have no value for visible rather than crash."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def message_for(code: ErrorCode, **params: object) -> str:
    """Fill the approved copy for a code with the placeholder values we have."""
    return copy.ERROR_MESSAGES[code].format_map(_Params(params))


def _notice_lines(result: PlanResult) -> tuple[str, ...]:
    codes = [code for code in result.notices if isinstance(code, ErrorCode)]
    if result.error is not None and result.error not in codes:
        codes.insert(0, result.error)
    return tuple(
        message_for(code, count=len(result.ideas)) for code in codes if code in copy.ERROR_MESSAGES
    )


def _weather_line(result: PlanResult) -> str | None:
    weather = result.weather
    if weather is None:
        return None
    return (
        f"{weather.condition.value.replace('_', ' ')}, "
        f"{weather.temp_min_c} to {weather.temp_max_c} C, "
        f"up to {weather.max_precip_probability}% chance of rain"
    )


class InterimPages:
    """Renders real pages until WP8's `present_result`/`present_detail`/`present_error`.

    Swap this for a WP8-backed implementation of `Pages` by passing it to
    `build_router`; nothing in a route changes.
    """

    def __init__(self) -> None:
        self._form_env = build_environment()
        self._env = Environment(
            loader=DictLoader(
                {
                    "shell": _SHELL,
                    "results": _RESULTS,
                    "detail": _DETAIL,
                    "error": _ERROR,
                }
            ),
            autoescape=True,
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def form(self, context: FormContext) -> str:
        return render_form(self._form_env, present_form(context))

    def result(self, context: ResultContext) -> str:
        result = context.result
        return self._env.get_template("results").render(
            title=copy.PAGE_TITLE,
            heading=copy.RESULTS_HEADING,
            assets=context.assets,
            notices=_notice_lines(result),
            weather=_weather_line(result),
            ideas=tuple(_card(idea, result.job_id) for idea in result.ideas),
            answers=_answer_lines(result.answers),
            answers_heading=ANSWERS_HEADING,
            change_label=copy.CHANGE_ANSWERS,
        )

    def detail(self, context: DetailContext) -> str:
        result = context.result
        idea = next(one for one in result.ideas if one.pair.idea_id == context.idea_id)
        return self._env.get_template("detail").render(
            title=copy.PAGE_TITLE,
            heading=IDEA_DETAILS_TITLE,
            assets=context.assets,
            idea=_card(idea, result.job_id),
            historical=HISTORICAL if context.now >= result.valid_until else None,
            back_url=f"/results/{result.job_id}",
            back_label=BACK_TO_RESULTS,
        )

    def error(self, context: ErrorContext) -> str:
        # `context.form` reaches WP8's `present_error`, which re-renders the kept answers
        # under the notice. The interim page can only offer the way back to them.
        return self._env.get_template("error").render(
            title=copy.PAGE_TITLE,
            heading=copy.ERROR_HEADINGS.get(context.code, copy.PAGE_TITLE),
            assets=context.assets,
            message=message_for(
                context.code,
                reference=context.reference or "",
                reset_time=MIDNIGHT_UTC,
            ),
            reference=context.reference,
            reference_label=REFERENCE_LABEL.format(reference=context.reference),
            active_url=context.active_url,
            active_label=ACTIVE_RESULT,
            start_label=START_AGAIN,
            change_label=copy.CHANGE_ANSWERS if context.form is not None else None,
        )
