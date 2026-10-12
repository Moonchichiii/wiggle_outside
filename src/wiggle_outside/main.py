"""Build the services and own their lifecycle (PLAN section 6).

Dependencies are passed in; this module assembles them. It is the only module that may
import integrations or storage (import-linter contracts 5 and 6).
"""

import logging
import secrets
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final

import httpx
from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from wiggle_outside.core.types import DeploymentMode, LocationCandidates
from wiggle_outside.integrations import nominatim, open_meteo, openrouter, overpass
from wiggle_outside.planner.catalogue import load_catalogue
from wiggle_outside.planner.jobs import Planner
from wiggle_outside.planner.model_stage import ModelWiring, model_stage
from wiggle_outside.planner.plan_outing import AllowanceOutcome, Budgets, Ports
from wiggle_outside.planner.ports import PlannerService, Ranker
from wiggle_outside.settings import (
    GEOCODE_BUDGET_S,
    MODEL_BUDGET_S,
    PROVIDERS_BUDGET_S,
    RENDER_RESERVE_S,
    Settings,
)
from wiggle_outside.storage.cache import SqliteCache
from wiggle_outside.storage.counters import LogCounters
from wiggle_outside.storage.flight import MemorySingleFlight
from wiggle_outside.storage.gate import MemoryGate
from wiggle_outside.storage.providers import cached_geocoder, cached_places, cached_weather
from wiggle_outside.storage.quota import DailyAllowance, LimitReached, Reserved
from wiggle_outside.storage.sqlite import MEMORY_PATH, Database
from wiggle_outside.web.routes import WebContext, build
from wiggle_outside.web.routes.assets import REPO_FONTS_DIR, STATIC_DIR, build_manifest
from wiggle_outside.web.routes.rendering import JinjaPages
from wiggle_outside.web.security import HTTP_SERVER_ERROR, SessionStore, origin_policy, page_headers

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from starlette.requests import Request

log = logging.getLogger(__name__)

PROCESS_KEY_BYTES: Final = 32
LOG_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s: %(message)s"
# Libraries whose INFO lines would carry request URLs: coordinates, the typed town.
QUIET_LOGGERS: Final = ("httpx", "httpcore")


def configure_logging(level: int = logging.INFO, root: logging.Logger | None = None) -> bool:
    """Send the application's log lines to stdout, once (TC-011).

    uvicorn configures only its own loggers, so without this the root logger has no
    handler and every `wiggle_outside.*` INFO line (counters, which provider served a
    request, how each search ended) is dropped in production. A root handler that is
    already there (a test runner, an operator's log config) is left alone. The lines
    themselves carry counts, timings and names only: never interest text, coordinates
    or the key (PLAN section 5). Returns whether a handler was added. `root` is for
    tests; the process root logger otherwise.
    """
    if root is None:
        root = logging.getLogger()
    # httpx logs every request URL at INFO, and those URLs carry the rounded coordinates
    # and the typed town. Those never reach a log (PLAN section 5), whoever owns the root.
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    if root.handlers:
        return False
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)
    root.setLevel(level)
    return True


def _uniform_http_error(
    mode: DeploymentMode,
) -> Callable[[Request, Exception], Awaitable[Response]]:
    """Build the handler for the framework's own 404 and 405 (and any other HTTPException).

    The body is empty, like the app's uniform 404 for an unknown or unowned result, so an
    unknown path and an unknown result are indistinguishable; the status and any `Allow`
    header the framework set are kept, and the page headers are added.
    """

    async def handle(request: Request, exc: Exception) -> Response:  # noqa: ARG001  the signature Starlette calls
        status = exc.status_code if isinstance(exc, StarletteHTTPException) else HTTP_SERVER_ERROR
        extra = dict(exc.headers or {}) if isinstance(exc, StarletteHTTPException) else {}
        return Response(status_code=status, headers=page_headers(mode) | extra)

    return handle


def readiness_body(state: AppState) -> str:
    """Compose the /readyz body. App and model readiness are reported separately."""
    return "\n".join(("app: ready", f"model: {state.model_status}", ""))


class SystemClock:
    """The one real clock (CONTRACTS section 4): aware UTC wall time and monotonic seconds."""

    @staticmethod
    def now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def monotonic() -> float:
        return time.monotonic()


class _AllowancePort:
    """Adapt the SQLite daily allowance to the planner's three-way answer."""

    def __init__(self, allowance: DailyAllowance) -> None:
        self._allowance = allowance

    async def reserve(self, now: datetime) -> AllowanceOutcome:
        reserved = await self._allowance.reserve(now)
        if isinstance(reserved, Reserved):
            return "reserved"
        if isinstance(reserved, LimitReached):
            return "limit_reached"
        log.error("daily allowance storage failed; the run is refused (DEPLOYMENT 2.3)")
        return "unavailable"


@dataclass(slots=True)
class Resources:
    """What the planner needs opened before the first request and closed at shutdown.

    One httpx client, one SQLite connection on its own thread, the in-memory gate and
    single flight, and the hosted daily allowance (PLAN section 6).
    """

    client: httpx.AsyncClient
    db: Database
    allowance: DailyAllowance | None
    planner: Planner
    # The hosted model adapter, or None without a key (then every run is a fallback).
    ranker: Ranker | None = None

    async def open(self) -> None:
        await self.db.open()
        if self.allowance is not None:
            await self.allowance.prepare()

    async def close(self) -> None:
        # Stop admission first (the server has already stopped routing), then the owned
        # tasks, then the HTTP client, then the database on its own thread
        # (BACKEND-CONTRACT section 10).
        await self.planner.close()
        await self.client.aclose()
        await self.db.close()


@dataclass(slots=True)
class AppState:
    """Everything built at startup and closed at shutdown."""

    settings: Settings
    # 32 random bytes made at startup and never stored (CONTRACTS section 7).
    process_key: bytes
    # The wired adapter, or None. /readyz reports readiness from this, not from
    # configuration, so it cannot claim a model the process does not have.
    ranker: Ranker | None = None
    resources: Resources | None = None

    @property
    def model_status(self) -> str:
        """What /readyz reports for the model (PLAN section 6: reported separately)."""
        return "unavailable" if self.ranker is None else "ready"


def build_state(settings: Settings | None = None) -> AppState:
    return AppState(
        settings=settings or Settings.from_env(),
        process_key=secrets.token_bytes(PROCESS_KEY_BYTES),
        ranker=None,  # set by _wire once the resources exist
    )


def build_resources(settings: Settings, sessions: SessionStore) -> Resources:
    """Assemble the real planner: adapters, wrapped by the cache, gate and single flight."""
    clock = SystemClock()
    counters = LogCounters()
    client = httpx.AsyncClient(follow_redirects=False)
    if settings.db_path != MEMORY_PATH:
        Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    db = Database(settings.db_path)
    store = SqliteCache(db, counters, clock)
    gate = MemoryGate(clock)
    flight = MemorySingleFlight(counters, clock)
    allowance = (
        DailyAllowance(db, settings.daily_run_limit)
        if settings.mode is DeploymentMode.HOSTED_LIVE
        else None
    )
    catalogue = load_catalogue()
    # TC-010: the hosted model whenever a key is present, in any mode; without one the
    # app serves the labelled fallback and /readyz says so.
    ranker = openrouter.from_settings(client, settings)
    model = (
        model_stage(
            ModelWiring(
                ranker=ranker,
                catalogue=catalogue,
                gate=gate,
                counters=counters,
                clock=clock,
                d39_enabled=settings.d39_enabled,
            )
        )
        if ranker is not None
        else None
    )

    def publish(session_id: str, candidates: LocationCandidates) -> None:
        # The web layer renders and validates the choice from the session's own copy
        # (BACKEND-CONTRACT section 3); the planner keeps the one that starts the job.
        session = sessions.get(session_id)
        if session is not None:
            session.candidates = candidates

    ports = Ports(
        geocoder=cached_geocoder(
            nominatim.from_settings(client, settings), store, gate, flight, counters, clock
        ),
        places=cached_places(
            overpass.from_settings(client, settings),
            store,
            gate,
            flight,
            counters,
            clock,
            fallback=overpass.fallback_from_settings(client, settings),
        ),
        weather=cached_weather(
            open_meteo.from_settings(client, settings), store, gate, flight, counters, clock
        ),
        catalogue=catalogue,
        clock=clock,
        counters=counters,
        allowance=_AllowancePort(allowance) if allowance is not None else None,
        model=model,
    )
    planner = Planner(
        ports,
        Budgets(geocode_s=GEOCODE_BUDGET_S, providers_s=PROVIDERS_BUDGET_S, model_s=MODEL_BUDGET_S),
        # D32: the user-visible budget, less the reserve for fallback assembly and rendering.
        deadline_s=max(1.0, settings.deadline_seconds - RENDER_RESERVE_S),
        publish_candidates=publish,
    )
    return Resources(client=client, db=db, allowance=allowance, planner=planner, ranker=ranker)


def _wire(state: AppState, planner: PlannerService | None) -> tuple[PlannerService, SessionStore]:
    """Return the planner the routes use and the one session store it shares with them.

    The planner publishes location candidates into the store, and a session that ends
    takes everything it owned with it (BACKEND-CONTRACT sections 2 and 3). The planner
    is built after the store, so the end-of-session hook reaches it through a holder.
    An injected `planner` (tests, previews) brings no resources and no hook.
    """
    built: list[Planner] = []

    def session_ended(session_id: str) -> None:
        for real in built:
            real.forget_session(session_id)

    sessions = SessionStore(on_end=session_ended)
    if planner is not None:
        return planner, sessions
    resources = build_resources(state.settings, sessions)
    built.append(resources.planner)
    state.resources = resources
    state.ranker = resources.ranker
    return resources.planner, sessions


def create_app(settings: Settings | None = None, planner: PlannerService | None = None) -> FastAPI:
    """Build the app. An injected `planner` replaces the real one (tests, previews)."""
    configure_logging()
    state = build_state(settings)
    planner, sessions = _wire(state, planner)
    resources = state.resources

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.wiggle = state
        if resources is not None:
            await resources.open()
        try:
            yield
        finally:
            if resources is not None:
                await resources.close()

    app = FastAPI(
        title="Wiggle Outside",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    # A path or method the router does not own gets the app's own uniform answer with
    # every security header, never the framework's JSON (PLAN section 9: every response).
    app.add_exception_handler(StarletteHTTPException, _uniform_http_error(state.settings.mode))

    app.include_router(
        build(
            WebContext(
                planner=planner,
                settings=state.settings,
                process_key=state.process_key,
                sessions=sessions,
                pages=JinjaPages(load_catalogue()),
                policy=origin_policy(state.settings),
                assets=build_manifest(),
                static_root=STATIC_DIR,
                fonts_root=REPO_FONTS_DIR,
                # The honest answer, which the router cannot see for itself.
                readiness=lambda: state.model_status,
            )
        )
    )
    return app
