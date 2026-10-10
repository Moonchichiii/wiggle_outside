"""Build the services and own their lifecycle (PLAN section 6).

Dependencies are passed in; this module assembles them. It is the only module that may
import integrations or storage (import-linter contracts 5 and 6).
"""

import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

from wiggle_outside.core.types import DeploymentMode
from wiggle_outside.planner.ports import Ranker
from wiggle_outside.settings import Settings
from wiggle_outside.web.presenters import (
    build_environment,
    present_form,
    render_form,
    with_assets,
)
from wiggle_outside.web.views import AssetRef, SessionView

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

    # BOOTSTRAP PREVIEW, replaced by WP7.
    #
    # CONTRACTS section 5 gives GET / to web/routes/**, which WP7 owns and has not built.
    # This serves WP8's form template so the page can be looked at, and it is deliberately
    # not the real route: no session, no CSRF token, no security headers, no CSP, and the
    # form posts nowhere. WP7 deletes this and registers the real table.
    @app.get("/", response_class=HTMLResponse)
    async def preview_form() -> str:
        return render_form(
            build_environment(),
            with_assets(
                present_form(
                    values=None,
                    errors={},
                    session=SessionView(
                        # Placeholders, not secrets: the real session and token are WP7's.
                        csrf_token="preview-not-a-real-token",  # noqa: S106
                        idempotency_key="preview-not-a-real-key",
                    ),
                    candidates=None,
                    mode=state.settings.mode,
                    d39_enabled=state.settings.d39_enabled,
                ),
                {"css": AssetRef(url="/preview/app.css", integrity="")},
            ),
        )

    @app.get("/preview/app.css", include_in_schema=False)
    async def preview_css() -> FileResponse:
        built = Path(__file__).parent / "web" / "static" / "app.css"
        return FileResponse(built, media_type="text/css")

    @app.get("/healthz", response_class=PlainTextResponse)
    async def healthz() -> str:
        return "ok"

    @app.get("/readyz", response_class=PlainTextResponse)
    async def readyz() -> str:
        return readiness_body(state)

    return app
