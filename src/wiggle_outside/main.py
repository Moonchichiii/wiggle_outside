"""Build the services and own their lifecycle (PLAN section 6).

Dependencies are passed in; this module assembles them. It is the only module that may
import integrations or storage (import-linter contracts 5 and 6).
"""

import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from wiggle_outside.core.types import DeploymentMode
from wiggle_outside.planner.ports import Ranker
from wiggle_outside.settings import Settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

PROCESS_KEY_BYTES: Final = 32


def readiness_body(state: AppState) -> str:
    """Compose the /readyz body. App and model readiness are reported separately."""
    return "\n".join(("app: ready", f"model: {state.model_status}", ""))


@dataclass(slots=True)
class AppState:
    """Everything built at startup and closed at shutdown.

    One httpx client, one SQLite connection on its own thread, one model client and one
    generation semaphore of size 1 (PLAN section 6). Those arrive with WP3-WP5; at M0
    only the settings and the per-process fingerprint key exist.
    """

    settings: Settings
    # 32 random bytes made at startup and never stored (CONTRACTS section 7).
    process_key: bytes
    # None until WP5 wires a model adapter. /readyz reports readiness from this, not from
    # configuration, so it cannot claim a model the process does not have.
    ranker: Ranker | None = None

    @property
    def model_status(self) -> str:
        """What /readyz reports for the model (PLAN section 6: reported separately)."""
        if self.ranker is None:
            return "unavailable"
        if (
            self.settings.mode is DeploymentMode.HOSTED_LIVE
            and self.settings.openrouter_api_key is None
        ):
            return "unavailable"
        return "ready"


def build_state(settings: Settings | None = None) -> AppState:
    return AppState(
        settings=settings or Settings.from_env(),
        process_key=secrets.token_bytes(PROCESS_KEY_BYTES),
        ranker=None,  # WP5 supplies the adapter; until then the app serves fallbacks.
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    state = build_state(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.wiggle = state
        yield
        # Resources are closed here once WP3-WP5 add them.

    app = FastAPI(
        title="Wiggle Outside",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # WP7 owns web/routes/**; it registers the CONTRACTS section 5 table here. Until then
    # only the two endpoints the host needs exist, so the app starts and reports honestly.
    @app.get("/healthz", response_class=PlainTextResponse)
    async def healthz() -> str:
        return "ok"

    @app.get("/readyz", response_class=PlainTextResponse)
    async def readyz() -> str:
        return f"app: ready\nmodel: {state.model_status}\n"

    return app
