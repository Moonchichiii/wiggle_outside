"""GET / and the result and detail pages (CONTRACTS section 5).

Thin: parse the URL, read the owned job, render. A GET never starts work, and an unowned
or unknown job is the same 404 (BACKEND-CONTRACT section 5).
"""

from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

# FastAPI resolves a handler's annotations when the route is registered, so Request
# and Response stay runtime imports: under TYPE_CHECKING it reads `request` as a
# query parameter and answers 422.
from starlette.requests import Request  # noqa: TC002
from starlette.responses import Response

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import JobState, PlanResult
from wiggle_outside.planner.ports import NotFound
from wiggle_outside.web.routes.rendering import DetailContext, ResultContext
from wiggle_outside.web.routes.status import Outcome, PageKind, outcome_for
from wiggle_outside.web.routes.support import (
    ErrorOutcome,
    WebContext,
    error_page,
    form_context,
    new_reference,
    render_form_page,
    session_view,
)
from wiggle_outside.web.security import (
    HTTP_BAD_REQUEST,
    HTTP_NOT_FOUND,
    SESSION_COOKIE,
    Session,
    host_allowed,
    html_page,
    page_headers,
    see_other,
    set_session_cookie,
)

if TYPE_CHECKING:
    from fastapi import APIRouter

# Non-terminal states: the GET waits for the job's own deadline (CONTRACTS section 3).
_RUNNING = frozenset({JobState.RUNNING, JobState.WAITING, JobState.GENERATING, JobState.CANCELLING})


def _not_found(context: WebContext) -> Response:
    """404, with the same body for an unknown, unowned and removed ID."""
    return Response(
        status_code=HTTP_NOT_FOUND,
        headers=page_headers(context.settings.mode),
    )


def register(router: APIRouter, context: WebContext) -> None:
    """Register the GET pages on `router`."""

    @router.get("/")
    async def form(request: Request) -> Response:
        return _render_form(context, request)

    @router.get("/results/{job_id}")
    async def results(request: Request, job_id: str) -> Response:
        owned = await _owned(context, request, job_id)
        if isinstance(owned, Response):
            return owned
        session, result = owned
        return _render_result(context, session, result)

    @router.get("/results/{job_id}/ideas/{idea_id}")
    async def detail(request: Request, job_id: str, idea_id: str) -> Response:
        owned = await _owned(context, request, job_id)
        if isinstance(owned, Response):
            return owned
        _, result = owned
        return _render_detail(context, result, idea_id)


def _render_form(context: WebContext, request: Request) -> Response:
    """Render the form page, opening a session when the request has none."""
    if not host_allowed(request, context.policy):
        return error_page(context, ErrorOutcome(ErrorCode.INPUT_INVALID, HTTP_BAD_REQUEST))
    session = context.sessions.get(request.cookies.get(SESSION_COOKIE))
    if session is None:
        session = context.sessions.create()
    response = render_form_page(context, form_context(context, session))
    set_session_cookie(response, session.session_id)
    return response


def _render_detail(context: WebContext, result: PlanResult, idea_id: str) -> Response:
    """Render one idea, or the uniform 404 for an idea this result does not carry."""
    now = datetime.now(UTC)
    known = any(idea.pair.idea_id == idea_id for idea in result.ideas)
    if not known or now >= result.retain_until:
        return _not_found(context)
    body = context.pages.detail(
        DetailContext(
            result=result,
            idea_id=idea_id,
            now=now,
            mode=context.settings.mode,
            assets=context.assets,
        )
    )
    return html_page(body, context.settings.mode)


async def _owned(
    context: WebContext, request: Request, job_id: str
) -> tuple[Session, PlanResult] | Response:
    """Return this session's job in a terminal state, or the uniform 404."""
    if not host_allowed(request, context.policy):
        return error_page(context, ErrorOutcome(ErrorCode.INPUT_INVALID, HTTP_BAD_REQUEST))
    session = context.sessions.get(request.cookies.get(SESSION_COOKIE))
    if session is None:
        return _not_found(context)
    result = context.planner.get(session.session_id, job_id)
    if result is None:
        return _not_found(context)
    if result.state in _RUNNING:
        # Waiting on an existing job is not starting work (CONTRACTS section 5).
        try:
            result = await context.planner.wait(session.session_id, job_id)
        except NotFound:
            return _not_found(context)
    return session, result


def _render_result(context: WebContext, session: Session, result: PlanResult) -> Response:
    """Answer a terminal result per the CONTRACTS section 3 GET table."""
    if result.state is JobState.NEEDS_LOCATION_CHOICE:
        started = session.latest_candidate_job()
        if started is not None:
            # Consumed: the back button never offers a stale choice as new.
            return see_other(f"/results/{started}", context.settings.mode)
    outcome = outcome_for(result)
    if outcome.kind is PageKind.MISSING:
        return _not_found(context)
    if outcome.kind is PageKind.RESULTS:
        body = context.pages.result(
            ResultContext(
                result=result,
                now=datetime.now(UTC),
                session=session_view(session, with_key=True),
                mode=context.settings.mode,
                d39_enabled=context.settings.d39_enabled,
                assets=context.assets,
            )
        )
        return html_page(body, context.settings.mode, outcome.status)
    return _render_notice(context, session, result, outcome)


def _render_notice(
    context: WebContext, session: Session, result: PlanResult, outcome: Outcome
) -> Response:
    """Render a notice, a choice page or a 422 form, keeping the answers."""
    kept = replace(
        form_context(context, session),
        answers=result.answers,
        interests=result.interests,
        submitted=fields_from_answers_summary(result),
        errors={} if outcome.code is None else {"place": outcome.code},
    )
    if outcome.kind is PageKind.CHOICE:
        return render_form_page(
            context,
            replace(
                kept,
                errors={},
                candidates=session.candidates,
                candidates_tz=result.weather.tz if result.weather else None,
            ),
            outcome.status,
        )
    if outcome.kind is PageKind.FORM:
        return render_form_page(context, kept, outcome.status)
    reference = new_reference() if outcome.code is ErrorCode.UNEXPECTED_FAILURE else None
    return error_page(
        context,
        ErrorOutcome(
            code=outcome.code or ErrorCode.UNEXPECTED_FAILURE,
            status=outcome.status,
            form=replace(kept, errors={}),
            reference=reference,
        ),
    )


def fields_from_answers_summary(result: PlanResult) -> dict[str, str]:
    """Render a result's answers as form values, so a re-render keeps them (D46)."""
    summary = result.answers
    sent = {
        "who": summary.who.value,
        "time": str(int(summary.time_budget)),
        "energy": summary.energy.value,
        "location_mode": "coords",
        "lat": f"{summary.location.lat}",
        "lon": f"{summary.location.lon}",
        "location_label": summary.location_label,
    }
    if summary.age_bands:
        sent["age_band"] = ",".join(band.value for band in sorted(summary.age_bands))
    if summary.stroller:
        sent["stroller"] = "1"
    if summary.step_free:
        sent["step_free"] = "1"
    return sent
