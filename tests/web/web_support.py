"""Harness for the WP7 route tests.

The router is mounted on a bare FastAPI app, so these tests exercise WP7's own routes
and nothing main.py adds. The client speaks https to `testserver` because the session
cookie is `__Host-` prefixed and therefore Secure, and a cookie jar will not send a
Secure cookie over http.
"""

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Final

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from wiggle_outside.core.types import (
    AgeBand,
    Answers,
    AnswersSummary,
    Coordinates,
    DeploymentMode,
    Energy,
    Idea,
    JobState,
    Pair,
    PlanResult,
    Source,
    TimeBudget,
    Who,
)
from wiggle_outside.planner.ports import Busy, Conflict, JobRef, NotFound, PlannerService
from wiggle_outside.settings import Settings
from wiggle_outside.web.routes import WebContext, build
from wiggle_outside.web.routes.assets import REPO_FONTS_DIR, STATIC_DIR, build_manifest
from wiggle_outside.web.routes.rendering import InterimPages
from wiggle_outside.web.security import SessionStore, origin_policy

if TYPE_CHECKING:
    import httpx

    from wiggle_outside.core.errors import ErrorCode

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
    """Build settings for the harness: local mode on the https test host."""
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
    app: FastAPI
    router: APIRouter
    planner: PlannerService
    sessions: SessionStore
    settings: Settings

    def start(self) -> dict[str, str]:
        """GET the form page and return its hidden fields (CSRF and the fresh key)."""
        page = self.client.get("/")
        if page.status_code != 200:
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


def plan_result(
    job_id: str = "job-1",
    state: JobState = JobState.COMPLETE,
    error: ErrorCode | None = None,
    ideas: tuple[Idea, ...] = (),
    retained: bool = True,  # noqa: FBT001, FBT002  a fixture switch, not a flag argument
) -> PlanResult:
    """Build a terminal result with the fields a status decision reads.

    Validity is relative to now, so a test does not depend on the wall clock;
    `retained=False` puts the result past its `retain_until` instead.
    """
    now = datetime.now(UTC)
    if not retained:
        now -= timedelta(hours=4)
    return PlanResult(
        job_id=job_id,
        state=state,
        source=Source.FALLBACK,
        ideas=ideas,
        notices=(),
        interests=None,
        answers=AnswersSummary(
            who=Who.KIDS,
            age_bands=frozenset({AgeBand.B3_5}),
            time_budget=TimeBudget.H1,
            energy=Energy.MODERATE,
            location=Coordinates(lat=60.12, lon=17.9),
            location_label="Bergby",
            stroller=False,
            step_free=False,
        ),
        weather=None,
        planned_start=now,
        planned_end=now + timedelta(hours=1),
        valid_until=now + timedelta(hours=1),
        retain_until=now + timedelta(hours=2),
        error=error,
    )


def one_idea(idea_id: str = "idea-1") -> Idea:
    """One generic idea, enough for a card and a detail URL."""
    return Idea(
        pair=Pair(
            pair_id="p1",
            idea_id=idea_id,
            activity_id="nature-bingo",
            place=None,
            distance_m=None,
            travel_min=10,
            duration_min=30,
            allowed_hook_ids=frozenset({"expedition"}),
            allowed_reason_ids=frozenset({"close_by"}),
        ),
        hook_id="expedition",
        reason_ids=("close_by",),
    )


@dataclass(slots=True)
class FixedPlanner:
    """A PlannerService that hands back one prepared result, or one prepared refusal."""

    result: PlanResult = field(default_factory=plan_result)
    busy: Busy | None = None
    conflict: bool = False
    choice: PlanResult | None = None
    owner: str | None = None
    calls: list[str] = field(default_factory=list)

    # The PlannerService protocol fixes these signatures; the fake reads only what it
    # needs to decide ownership.
    async def start_or_join(
        self,
        session_id: str,
        key: str,  # noqa: ARG002
        answers: Answers,  # noqa: ARG002
    ) -> JobRef:
        self.calls.append("start_or_join")
        if self.conflict:
            raise Conflict
        if self.busy is not None:
            raise self.busy
        self.owner = session_id
        return JobRef(job_id=self.result.job_id, joined=False)

    async def choose_location(
        self,
        session_id: str,
        candidate_id: str,  # noqa: ARG002
    ) -> JobRef:
        self.calls.append("choose_location")
        if self.busy is not None:
            raise self.busy
        if self.conflict:
            raise Conflict
        if self.choice is None:
            raise NotFound
        self.owner = session_id
        return JobRef(job_id=self.choice.job_id, joined=False)

    async def wait(self, session_id: str, job_id: str) -> PlanResult:
        self.calls.append("wait")
        found = self.get(session_id, job_id)
        if found is None:
            raise NotFound
        return found

    def get(self, session_id: str, job_id: str) -> PlanResult | None:
        if session_id != self.owner:
            return None
        for candidate in (self.result, self.choice):
            if candidate is not None and candidate.job_id == job_id:
                return candidate
        return None


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
        assets=build_manifest(static_root) if static_root.is_dir() else {},
        static_root=static_root,
        fonts_root=REPO_FONTS_DIR,
        readiness=lambda: "unavailable",
    )
    router = build(context)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(router)
    with TestClient(app, base_url=BASE_URL) as client:
        yield Harness(
            client=client,
            app=app,
            router=router,
            planner=planner,
            sessions=store,
            settings=chosen,
        )
