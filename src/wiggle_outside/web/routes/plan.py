"""POST /plan and POST /location-choice (CONTRACTS section 3 and section 5).

Both are plain-form POST-redirect-GET (D43): wait for the terminal state, then 303 to
`/results/{job_id}`, so the outcome's own status is on the GET. Every other row of the
POST table is refused here, before any provider or model call.
"""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Final

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import Response

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import Answers, LocationCandidate
from wiggle_outside.planner.ports import Busy, Conflict, NotFound
from wiggle_outside.web.forms import candidate_key, fingerprint
from wiggle_outside.web.routes.parsing import (
    FORM_ANCHOR,
    fields_from_answers,
    read_choice,
    read_plan,
    submitted_fields,
)
from wiggle_outside.web.routes.support import (
    Admitted,
    ErrorOutcome,
    WebContext,
    admit_post,
    error_page,
    form_context,
    new_reference,
    render_form_page,
)
from wiggle_outside.web.views import FormContext
from wiggle_outside.web.security import (
    HTTP_CONFLICT,
    HTTP_SERVER_ERROR,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_UNPROCESSABLE,
    Session,
    see_other,
)

# The honeypot is hidden from keyboard and screen readers, so anything in it is a bot.
HONEYPOT: Final = "hp_note"


def register(router: APIRouter, context: WebContext) -> None:
    """Register the POST routes on `router`."""

    @router.post("/plan")
    async def plan(request: Request) -> Response:
        admitted = await admit_post(context, request)
        if isinstance(admitted, Response):
            return admitted
        return await _plan(context, admitted)

    @router.post("/location-choice")
    async def location_choice(request: Request) -> Response:
        admitted = await admit_post(context, request)
        if isinstance(admitted, Response):
            return admitted
        return await _choose(context, admitted)


# --- /plan --------------------------------------------------------------------------


async def _plan(context: WebContext, admitted: Admitted) -> Response:
    session, values = admitted.session, admitted.values
    if any(value.strip() for value in values.get(HONEYPOT, ())):
        return _honeypot(context, admitted)
    # The honeypot is never echoed: `submitted_fields` carries answer fields only.
    kept = replace(form_context(context, session), submitted=submitted_fields(values))
    parse = read_plan(values, d39_enabled=context.settings.d39_enabled)
    if parse.answers is None:
        return render_form_page(
            context, replace(kept, errors=parse.errors), HTTP_UNPROCESSABLE
        )
    digest = fingerprint(context.process_key, values)
    refused = _register_key(context, session, parse.key, digest, kept)
    if refused is not None:
        return refused
    started = await _start(context, session, parse.key, parse.answers, kept)
    if isinstance(started, Response):
        return started
    return await _settle(context, session, started)


def _honeypot(context: WebContext, admitted: Admitted) -> Response:
    """422 with the answers kept, the honeypot cleared, and no planner call (D49)."""
    return render_form_page(
        context,
        replace(
            form_context(context, admitted.session),
            submitted=submitted_fields(admitted.values),
            errors={FORM_ANCHOR: ErrorCode.INPUT_INVALID},
        ),
        HTTP_UNPROCESSABLE,
    )


# --- /location-choice ---------------------------------------------------------------


async def _choose(context: WebContext, admitted: Admitted) -> Response:
    session = admitted.session
    now = datetime.now(UTC)
    candidate = session.live_candidate(read_choice(admitted.values) or "", now)
    if candidate is None:
        return _choice_expired(context, session, now)
    if candidate.job_id is not None:
        # A repeat of an already consumed, owned candidate: the same job, no new work.
        return see_other(f"/results/{candidate.job_id}", context.settings.mode)
    return await _start_choice(context, session, candidate)


async def _start_choice(
    context: WebContext, session: Session, candidate: LocationCandidate
) -> Response:
    key = candidate_key(candidate.candidate_id)
    # CONTRACTS section 7: for /location-choice the fingerprint is the candidate ID.
    refused = _register_key(context, session, key, candidate.candidate_id)
    if refused is not None:
        return refused
    try:
        ref = await context.planner.choose_location(session.session_id, candidate.candidate_id)
    except NotFound:
        return _choice_expired(context, session, datetime.now(UTC))
    except Conflict:
        return _conflict(context)
    except Busy as busy:
        return _busy(context, session, busy.retry_after_s)
    session.consume_candidate(candidate.candidate_id, ref.job_id)
    return await _settle(context, session, ref.job_id)


def _choice_expired(context: WebContext, session: Session, now: datetime) -> Response:
    """The uniform 422 for any candidate not in this session's live set."""
    live = session.live_set(now)
    kept = form_context(context, session)
    if live is not None:
        kept = replace(kept, submitted=fields_from_answers(live.answers))
    return render_form_page(
        context,
        replace(kept, errors={"place": ErrorCode.LOCATION_CHOICE_EXPIRED}),
        HTTP_UNPROCESSABLE,
    )


# --- Shared ------------------------------------------------------------------------


def _register_key(
    context: WebContext,
    session: Session,
    key: str,
    digest: str,
    kept: FormContext | None = None,
) -> Response | None:
    """Record the submission under its key, and apply the submission rate limits."""
    fresh = key not in session.keys
    if not session.remember(key, digest):
        return _conflict(context)
    # Deduplication is not rate limiting: only a new key spends a token.
    if fresh and not context.sessions.admit_submission(session):
        return _busy(context, session, None, kept)
    return None


async def _start(
    context: WebContext,
    session: Session,
    key: str,
    answers: Answers,
    kept: FormContext | None = None,
) -> str | Response:
    try:
        ref = await context.planner.start_or_join(session.session_id, key, answers)
    except Conflict:
        return _conflict(context)
    except Busy as busy:
        return _busy(context, session, busy.retry_after_s, kept)
    except NotFound:
        return error_page(
            context,
            ErrorOutcome(
                code=ErrorCode.UNEXPECTED_FAILURE,
                status=HTTP_SERVER_ERROR,
                reference=new_reference(),
            ),
        )
    session.last_job_id = ref.job_id
    return ref.job_id


async def _settle(context: WebContext, session: Session, job_id: str) -> Response:
    """Wait for the terminal state, then redirect (D43). The status is on the GET."""
    try:
        await context.planner.wait(session.session_id, job_id)
    except NotFound:
        # The result went while we waited; the GET answers the uniform 404.
        pass
    return see_other(f"/results/{job_id}", context.settings.mode)


def _conflict(context: WebContext) -> Response:
    return error_page(
        context,
        ErrorOutcome(code=ErrorCode.REQUEST_CONFLICT, status=HTTP_CONFLICT),
    )


def _busy(
    context: WebContext,
    session: Session,
    retry_after_s: float | None,
    kept: FormContext | None = None,
) -> Response:
    """429 REQUEST_BUSY, with Retry-After only when the delay is actually known."""
    extra = {"Retry-After": str(int(retry_after_s))} if retry_after_s is not None else None
    active = session.active_job
    return error_page(
        context,
        ErrorOutcome(
            code=ErrorCode.REQUEST_BUSY,
            status=HTTP_TOO_MANY_REQUESTS,
            extra=extra,
            active_url=f"/results/{active}" if active else None,
            form=kept,
        ),
    )
