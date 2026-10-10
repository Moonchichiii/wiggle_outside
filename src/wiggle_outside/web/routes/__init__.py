"""The router factory: the one thing main.py mounts.

Every dependency is an explicit parameter, so nothing in this package reaches for a
global (PLAN section 7). `build_router` is the convenience shape; `build` takes the whole
`WebContext` when the caller has more to say, such as the real model readiness.
"""

from typing import TYPE_CHECKING, Final

from fastapi import APIRouter

from wiggle_outside.planner.catalogue import load_catalogue
from wiggle_outside.web.routes import health, pages, plan, static
from wiggle_outside.web.routes.assets import REPO_FONTS_DIR, STATIC_DIR, build_manifest
from wiggle_outside.web.routes.rendering import JinjaPages, Pages
from wiggle_outside.web.routes.support import WebContext
from wiggle_outside.web.security import SessionStore, origin_policy

if TYPE_CHECKING:
    from wiggle_outside.planner.ports import PlannerService
    from wiggle_outside.settings import Settings

MODEL_UNAVAILABLE: Final = "unavailable"

__all__ = ["WebContext", "build", "build_router"]


def build_router(
    planner: PlannerService,
    settings: Settings,
    process_key: bytes,
    sessions: SessionStore,
    pages_impl: Pages | None = None,
) -> APIRouter:
    """Build the CONTRACTS section 5 router.

    `pages_impl` is the renderer; left out, it is `JinjaPages` over the reviewed
    catalogue, which is WP8's four presenters and their four templates.
    """
    return build(
        WebContext(
            planner=planner,
            settings=settings,
            process_key=process_key,
            sessions=sessions,
            pages=pages_impl or JinjaPages(load_catalogue()),
            policy=origin_policy(settings),
            assets=build_manifest(),
            static_root=STATIC_DIR,
            fonts_root=REPO_FONTS_DIR,
            readiness=lambda: MODEL_UNAVAILABLE,
        )
    )


def build(context: WebContext) -> APIRouter:
    """Register every route in CONTRACTS section 5 on one router, and nothing else."""
    router = APIRouter()
    pages.register(router, context)
    plan.register(router, context)
    health.register(router, context)
    static.register(router, context)
    return router
