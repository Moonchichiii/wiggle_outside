"""GET /static/{hashed} (CONTRACTS section 5).

Content-hashed names never change meaning, so they carry a one-year immutable cache.
Nothing outside the static root is servable, and the only font files are the two named
faces, which may be absent (TC-007) and then 404 cleanly.
"""

from typing import TYPE_CHECKING

from starlette.responses import FileResponse, Response

from wiggle_outside.web.routes.assets import resolve_static
from wiggle_outside.web.security import (
    HTTP_NOT_FOUND,
    STATIC_CACHE_CONTROL,
    security_headers,
)

# FastAPI resolves a handler's annotations when the route is registered, so Request
# and Response stay runtime imports: under TYPE_CHECKING it reads `request` as a
# query parameter and answers 422.

if TYPE_CHECKING:
    from fastapi import APIRouter

    from wiggle_outside.web.routes.support import WebContext


def register(router: APIRouter, context: WebContext) -> None:
    """Register the static mount on `router`."""
    headers = {"Cache-Control": STATIC_CACHE_CONTROL} | security_headers(context.settings.mode)

    @router.get("/static/{hashed:path}")
    async def static(hashed: str) -> Response:
        found = resolve_static(hashed, context.static_root, context.fonts_root)
        if found is None:
            return Response(status_code=HTTP_NOT_FOUND, headers=headers)
        return FileResponse(found.path, media_type=found.media_type, headers=headers)
