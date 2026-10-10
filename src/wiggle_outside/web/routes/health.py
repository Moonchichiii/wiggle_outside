"""GET /healthz and GET /readyz (CONTRACTS section 5).

Liveness, app readiness and model readiness stay distinct: an unavailable model does not
make working deterministic functionality a crash (ERROR-HANDLING section 3). Neither
checks the Host header: a platform health check addresses the instance, not the public
host name, and `/healthz` is never counted against a rate limit.
"""

from fastapi import APIRouter
from starlette.responses import Response

from wiggle_outside.web.routes.support import WebContext
from wiggle_outside.web.security import plain_text

LIVE = "ok"


def readiness_body(model_status: str) -> str:
    """App and model readiness, reported separately (PLAN section 6)."""
    return "\n".join(("app: ready", f"model: {model_status}", ""))


def register(router: APIRouter, context: WebContext) -> None:
    """Register the health endpoints on `router`."""

    @router.get("/healthz")
    async def healthz() -> Response:
        return plain_text(LIVE, context.settings.mode)

    @router.get("/readyz")
    async def readyz() -> Response:
        return plain_text(readiness_body(context.readiness()), context.settings.mode)
