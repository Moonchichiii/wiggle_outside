"""The seam between a route and the pages it renders.

The routes gather the CONTRACTS section 8 arguments into one carrier each and hand them
to a `Pages` implementation. The protocol is owned here, by the consumer
(PLAN section 7), so a route never reaches into `presenters.py` itself and a test can
render through a stub.

`JinjaPages` is the real one: WP8's four presenters and their four templates, with the
build manifest attached afterwards, because only `present_form` takes it (CC-B).
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import DeploymentMode, PlanResult
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
from wiggle_outside.web.views import (
    ActionView,
    AssetRef,
    ErrorPage,
    FormContext,
    SessionView,
)

if TYPE_CHECKING:
    from jinja2 import Environment

    from wiggle_outside.planner.ports import Catalogue

# The label on the 429 link to the job the session already has in flight.
ACTIVE_RESULT = "Go to the outing we are already finding"


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

    `active_url` is not one of them. The REQUEST_BUSY row needs an error page "linking to
    the active result" (CONTRACTS section 3) and `present_error(code, reference, form)`
    has nowhere to put it, so the route carries it here and the link is added to the
    notice afterwards. Raised as a contract-change proposal.
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


class JinjaPages:
    """WP8's presenters and templates behind the `Pages` protocol.

    A class rather than functions because it owns two things for the life of the app: the
    Jinja environment and the catalogue the result and detail pages read activity text
    from (CONTRACTS section 8).
    """

    def __init__(self, catalogue: Catalogue, env: Environment | None = None) -> None:
        self._catalogue = catalogue
        self._env = env if env is not None else build_environment()

    def form(self, context: FormContext) -> str:
        return render_form(self._env, present_form(context))

    def result(self, context: ResultContext) -> str:
        page = present_result(
            context.result,
            self._catalogue,
            context.now,
            context.session,
            context.mode,
            context.d39_enabled,
        )
        return render_result(self._env, with_assets(page, context.assets))

    def detail(self, context: DetailContext) -> str:
        page = present_detail(context.result, context.idea_id, self._catalogue, context.now)
        return render_detail(self._env, with_assets(page, context.assets))

    def error(self, context: ErrorContext) -> str:
        kept = present_form(context.form) if context.form is not None else None
        page = _linking_to_active(
            present_error(context.code, context.reference, kept),
            context.active_url,
        )
        return render_error(self._env, with_assets(page, context.assets))


def _linking_to_active(page: ErrorPage, active_url: str | None) -> ErrorPage:
    """Offer the job already in flight, which is the only action a 429 has."""
    if active_url is None:
        return page
    link = ActionView(label=ACTIVE_RESULT, url=active_url, method="get", csrf_token=None)
    return replace(page, notice=replace(page.notice, actions=(link, *page.notice.actions)))
