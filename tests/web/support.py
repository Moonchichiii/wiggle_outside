"""Harness for the WP7 route tests.

The router is mounted on a bare FastAPI app, so these tests exercise WP7's own routes
and nothing main.py adds. The client speaks https to `testserver` because the session
cookie is `__Host-` prefixed and therefore Secure, and a cookie jar will not send a
Secure cookie over http.
"""

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from wiggle_outside.core.types import DeploymentMode
from wiggle_outside.planner.ports import PlannerService
from wiggle_outside.settings import Settings
from wiggle_outside.web.routes import WebContext, build
from wiggle_outside.web.routes.assets import REPO_FONTS_DIR, STATIC_DIR
from wiggle_outside.web.routes.rendering import InterimPages
from wiggle_outside.web.security import SessionStore, origin_policy

HOST: Final = "testserver"
BASE_URL: Final = f"https://{HOST}"
ORIGIN: Final = BASE_URL
FOREIGN_ORIGIN: Final = "https://evil.example"
PROCESS_KEY: Final = b"\x00" * 32

# A complete, valid set of answers (CONTRACTS section 7).
ANSWERS: Final[Mapping[str, str]] = {
    "who": "kids",
    "age_band": "3-5",
    "time": "60",
    "energy": "moderate",
    "location_mode": "typed",
    "place": "Bergby",
}

_HIDDEN: Final = re.compile(r'name="([a-z_]+)" value="([^"]*)"')


def harness_settings(**overrides: object) -> Settings:
    """Settings for the harness: local mode on the https test host."""
    base = replace(
        Settings.from_env(),
        mode=DeploymentMode.LOCAL,
        host=HOST,
        port=443,
        d39_enabled=True,
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


@dataclass(slots=True)
class Harness:
    """One app, its client, and the objects the routes were given."""

    client: TestClient
    planner: PlannerService
    sessions: SessionStore
    settings: Settings

    def start(self) -> dict[str, str]:
        """GET the form page and return its hidden fields (CSRF and the fresh key)."""
        page = self.client.get("/")
        if page.status_code != 200:  # noqa: PLR2004  the form page is a 200 or nothing
            msg = f"the form page answered {page.status_code}"
            raise AssertionError(msg)
        return dict(_HIDDEN.findall(page.text))

    def post(self, url: str, data: Mapping[str, str], **extra: str) -> httpx.Response:
        return self.client.post(
            url,
            data=dict(data),
            headers={"Origin": ORIGIN, **extra},
            follow_redirects=False,
        )

    def plan(self, **overrides: str) -> httpx.Response:
        """Submit a complete, valid plan form."""
        tokens = self.start()
        return self.post("/plan", self.body(tokens, **overrides))

    def body(self, tokens: Mapping[str, str], **overrides: str) -> dict[str, str]:
        return {
            "csrf_token": tokens["csrf_token"],
            "idempotency_key": tokens["idempotency_key"],
            **ANSWERS,
            **overrides,
        }


def build_harness(
    planner: PlannerService,
    settings: Settings | None = None,
    sessions: SessionStore | None = None,
    static_root: Path = STATIC_DIR,
) -> Iterator[Harness]:
    """Mount the WP7 router on a bare app and hand back a client for it."""
    chosen = settings or harness_settings()
    store = sessions if sessions is not None else SessionStore()
    context = WebContext(
        planner=planner,
        settings=chosen,
        process_key=PROCESS_KEY,
        sessions=store,
        pages=InterimPages(),
        policy=origin_policy(chosen),
        assets={},
        static_root=static_root,
        fonts_root=REPO_FONTS_DIR,
        readiness=lambda: "unavailable",
    )
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(build(context))
    with TestClient(app, base_url=BASE_URL) as client:
        yield Harness(client=client, planner=planner, sessions=store, settings=chosen)
