"""What every route in this package shares: its dependencies, and the refusals.

`WebContext` is the one carrier the factory builds; every dependency in it is an explicit
value, so no route reaches for a global (PLAN section 7). The admission chain below is
the order CONTRACTS section 3 refuses a POST in, and it is the only place that order is
written down.
"""

import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from starlette.responses import Response

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.planner.ports import PlannerService
from wiggle_outside.settings import Settings
from wiggle_outside.web.routes.parsing import parse_body
from wiggle_outside.web.routes.rendering import ErrorContext, Pages
from wiggle_outside.web.security import (
    HTTP_BAD_REQUEST,
    HTTP_CONTENT_TOO_LARGE,
    HTTP_FORBIDDEN,
    HTTP_OK,
    HTTP_UNSUPPORTED_MEDIA_TYPE,
    SESSION_COOKIE,
    OriginPolicy,
    Session,
    SessionStore,
    csrf_ok,
    declared_too_large,
    host_allowed,
    html_page,
    media_type_allowed,
    origin_allowed,
    read_limited,
    set_session_cookie,
)
from wiggle_outside.web.views import AssetRef, FormContext, SessionView

if TYPE_CHECKING:
    from starlette.requests import Request

REFERENCE_BYTES: Final = 8


@dataclass(frozen=True, slots=True)
class WebContext:
    """Everything the routes need, passed in rather than looked up."""

    planner: PlannerService
    settings: Settings
    process_key: bytes
    sessions: SessionStore
    pages: Pages
    policy: OriginPolicy
    assets: Mapping[str, AssetRef]
    static_root: Path
    fonts_root: Path
    # What /readyz reports for the model; main.py owns the adapter, so it owns the answer.
    readiness: Callable[[], str]


@dataclass(frozen=True, slots=True)
class ErrorOutcome:
    """One refusal: its code, its status, and what the page may keep."""

    code: ErrorCode
    status: int
    form: FormContext | None = None
    reference: str | None = None
    extra: Mapping[str, str] | None = None
    active_url: str | None = None


def new_reference() -> str:
    """Make an opaque correlation reference; never a result-access token."""
    return secrets.token_hex(REFERENCE_BYTES)


def session_view(session: Session, *, with_key: bool) -> SessionView:
    """Build the session view, with a fresh key where a plan form needs one."""
    return SessionView(
        csrf_token=session.csrf_token,
        idempotency_key=session.new_key() if with_key else None,
    )


def form_context(context: WebContext, session: Session) -> FormContext:
    """Build a bare form context; the caller adds what the page keeps."""
    return FormContext(
        session=session_view(session, with_key=True),
        mode=context.settings.mode,
        d39_enabled=context.settings.d39_enabled,
        assets=context.assets,
    )


def render_form_page(context: WebContext, form: FormContext, status: int = HTTP_OK) -> Response:
    return html_page(context.pages.form(form), context.settings.mode, status)


def error_page(context: WebContext, outcome: ErrorOutcome) -> Response:
    """Render an error page: full page, approved copy, every security header."""
    body = context.pages.error(
        ErrorContext(
            code=outcome.code,
            reference=outcome.reference,
            form=outcome.form,
            mode=context.settings.mode,
            assets=context.assets,
            active_url=outcome.active_url,
        )
    )
    return html_page(body, context.settings.mode, outcome.status, outcome.extra)


# --- Admitting a POST (CONTRACTS section 3, in order) -------------------------------


@dataclass(frozen=True, slots=True)
class Admitted:
    session: Session
    values: dict[str, list[str]]


def _refuse(context: WebContext, code: ErrorCode, status: int) -> Response:
    return error_page(context, ErrorOutcome(code=code, status=status))


def refuse_session(context: WebContext, *, fresh: bool) -> Response:
    """403 SESSION_INVALID. An unknown session ID is never adopted; a new one is issued."""
    response = _refuse(context, ErrorCode.SESSION_INVALID, HTTP_FORBIDDEN)
    if fresh:
        set_session_cookie(response, context.sessions.create().session_id)
    return response


async def _transport(context: WebContext, request: Request) -> bytes | Response:
    """Host, content type and body size, before anything is parsed."""
    if not host_allowed(request, context.policy):
        return _refuse(context, ErrorCode.INPUT_INVALID, HTTP_BAD_REQUEST)
    if not media_type_allowed(request):
        return _refuse(context, ErrorCode.INPUT_INVALID, HTTP_UNSUPPORTED_MEDIA_TYPE)
    if declared_too_large(request):
        return _refuse(context, ErrorCode.REQUEST_TOO_LARGE, HTTP_CONTENT_TOO_LARGE)
    body = await read_limited(request)
    if body is None:
        return _refuse(context, ErrorCode.REQUEST_TOO_LARGE, HTTP_CONTENT_TOO_LARGE)
    return body


async def admit_post(context: WebContext, request: Request) -> Admitted | Response:
    """Refuse a POST that fails any transport, origin, session or CSRF check."""
    body = await _transport(context, request)
    if isinstance(body, Response):
        return body
    values = parse_body(body)
    if values is None:
        return _refuse(context, ErrorCode.INPUT_INVALID, HTTP_BAD_REQUEST)
    if not origin_allowed(request, context.policy):
        return refuse_session(context, fresh=False)
    session = context.sessions.get(request.cookies.get(SESSION_COOKIE))
    if session is None:
        return refuse_session(context, fresh=True)
    tokens = values.get("csrf_token", [])
    if not csrf_ok(session.csrf_token, tokens[0] if tokens else None):
        return refuse_session(context, fresh=False)
    return Admitted(session=session, values=values)
