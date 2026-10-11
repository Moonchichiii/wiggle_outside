"""A real search through the real app, with real providers and the hosted model.

    uv run python scripts/live_journey.py [place] [--no-warm] [--no-shots] [--fixture-places]

Three steps, each timed per stage from the planner's own stage counters and with every
provider call counted from the counter log: a cold search (fresh database, nothing
cached), an identical resubmission (must join: zero calls), and a new search on the
same place and time budget that differs only in a ranking preference (the geocode and
the forecast are cached; the places are cached only if the cold search obtained them).
The app is the real `create_app()` with the real adapters, served by uvicorn over https
on 127.0.0.1:8453 (the dev certificate in `out/devcert`) in a thread of this process,
so the counter log is read in-process while every request is a real request.
Controlled input: a fixed family and a fixed interest text; no visitor exists.
Results pages are saved under `out/` as HTML and, with Playwright, as screenshots.

`--fixture-places` replaces the Overpass adapter, and only it, with the WALKTHROUGH
fixture places translated to the geocoded origin: live geocode, live forecast, live
model, real routes and templates, fixture places. The report says so in its title.

The client only ever speaks to the loopback origin this script serves: certificate
verification is off, so any other host is refused before a request is made.
"""

import ipaddress
import logging
import os
import re
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final

ROOT: Final = Path(__file__).resolve().parent.parent
OUT: Final = ROOT / "out"
CERT_DIR: Final = OUT / "devcert"
ARGS: Final = [a for a in sys.argv[1:] if not a.startswith("--")]
PLACE: Final = ARGS[0] if ARGS else "Växjö"
NO_WARM: Final = "--no-warm" in sys.argv
NO_SHOTS: Final = "--no-shots" in sys.argv
FIXTURE_PLACES: Final = "--fixture-places" in sys.argv
# The outing: a 1 h family hour by default; `--time=30` and `--solo` for the evening
# runs, when a family outing would end after sunset and the rules say so.
TIME_MIN: Final = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--time=")), "60")
SOLO: Final = "--solo" in sys.argv
TEXT: Final = "birds and puddles"
HOST: Final = "127.0.0.1"
PORT: Final = 8453
ORIGIN: Final = f"https://{HOST}:{PORT}"
HIDDEN: Final = re.compile(r'name="([a-z_]+)" value="([^"]*)"')
CANDIDATE: Final = re.compile(r'name="candidate_id" value="([^"]+)"')
CARD_TITLE: Final = re.compile(
    r'<h3[^>]*class="[^"]*wo-card-title[^"]*"[^>]*>(.*?)</h3>', re.DOTALL
)
DETAIL_URL: Final = re.compile(r'href="/results/[^"/]+/ideas/([^"]+)"')
TAG: Final = re.compile(r"<[^>]+>")
COUNTERS_LOG: Final = "wiggle_outside.counters"
MODEL_LOG: Final = "wiggle_outside.integrations.openrouter"
STARTUP_WAIT_S: Final = 15.0
WIDTHS: Final = (390, 1440)
# The brief for the 11 October evening run: at most two Overpass attempts in total.
MAX_OVERPASS_ATTEMPTS: Final = 2
REDIRECT_HOPS: Final = 3
HTTP_SEE_OTHER: Final = 303
RUN_TAG: Final = f"{PLACE.lower().replace(' ', '-').replace(',', '')}"
RUN_TAG_FULL: Final = f"{RUN_TAG}{'-fixture' if FIXTURE_PLACES else ''}"

# A fresh database so the first search is cold; the port so the origin policy allows it.
os.environ["WO_DB_PATH"] = str(Path(tempfile.mkdtemp(prefix="wo-journey-")) / "wiggle.sqlite")
os.environ.setdefault("WO_MODE", "local")
os.environ["WO_PORT"] = str(PORT)

import httpx  # noqa: E402
import uvicorn  # noqa: E402

from wiggle_outside.core.errors import ErrorCode  # noqa: E402
from wiggle_outside.core.result import Ok, Outcome  # noqa: E402
from wiggle_outside.core.types import Coordinates, Place, Source  # noqa: E402
from wiggle_outside.integrations import overpass  # noqa: E402
from wiggle_outside.main import create_app  # noqa: E402
from wiggle_outside.planner import model_stage  # noqa: E402
from wiggle_outside.web.security import session_cookie_name  # noqa: E402

if TYPE_CHECKING:
    from wiggle_outside.core.types import Pair
    from wiggle_outside.planner.ports import Catalogue, ModelRequest


# --- Fixture places (route b): the WALKTHROUGH places around whatever origin was geocoded

FIXTURE_OFFSETS: Final = (
    ("fixture:1", "Linden Park", "park", 0.005, 0.005, "unknown", "unknown"),
    ("fixture:2", "Birchwood Nature Area", "nature_reserve", 0.008, 0.0, "no", "unknown"),
    ("fixture:3", "Oak Lane Park", "park", 0.003, -0.002, "unknown", "yes"),
    ("fixture:4", "Elm & Oak Playground", "playground", -0.002, 0.002, "unknown", "unknown"),
)


class FixturePlaces:
    """Stand in for Overpass only: four fixture places translated to the real origin."""

    async def nearby(
        self, at: Coordinates, radius_m: int, kinds: frozenset[str], deadline: float
    ) -> Outcome[tuple[Place, ...]]:
        del radius_m, kinds, deadline
        # The cache wrapper around this adapter counts the upstream call, as for Overpass.
        return Ok(
            tuple(
                Place(
                    place_id=place_id,
                    name=name,
                    kind=kind,
                    coords=Coordinates(lat=at.lat + dlat, lon=at.lon + dlon),
                    fee=fee,
                    osm_access=access,
                )
                for place_id, name, kind, dlat, dlon, fee, access in FIXTURE_OFFSETS
            )
        )


def _install_fixture_places() -> None:
    def fixture(client: object, settings: object) -> FixturePlaces:
        del client, settings
        return FixturePlaces()

    overpass.from_settings = fixture  # type: ignore[assignment]


# --- Recording what was sent to the model (controlled input only: the pairs) -------------

SENT: Final[list[list[str]]] = []
_build_request = model_stage.build_request


def _pair_sent(pair: Pair) -> str:
    where = pair.place.name if pair.place else "none"
    return (
        f"{pair.pair_id}={pair.activity_id}@{where} hooks={sorted(pair.allowed_hook_ids)} "
        f"reasons={sorted(pair.allowed_reason_ids)}"
    )


def _recording_build_request(
    pairs: tuple[Pair, ...], catalogue: Catalogue, text: str | None, *, d39_enabled: bool
) -> ModelRequest:
    SENT.append([_pair_sent(pair) for pair in pairs])
    return _build_request(pairs, catalogue, text, d39_enabled=d39_enabled)


model_stage.build_request = _recording_build_request  # type: ignore[assignment]


@dataclass(slots=True)
class Step:
    name: str
    started: float = 0.0
    finished: float = 0.0
    stage_times: dict[str, float] = field(default_factory=dict)
    calls: dict[str, int] = field(default_factory=dict)
    model_lines: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    job_id: str = ""
    url: str = ""
    source: str = ""
    error: str = ""
    cards: list[str] = field(default_factory=list)
    page_notes: list[str] = field(default_factory=list)
    pairs_sent: list[list[str]] = field(default_factory=list)
    html_path: str = ""
    shots: list[str] = field(default_factory=list)
    skipped: str = ""

    @property
    def status(self) -> str:
        return ", ".join(self.statuses)

    @property
    def overpass_attempts(self) -> int:
        return self.calls.get("places", 0) + self.calls.get("places retry", 0)


class Capture(logging.Handler):
    """Collect counter and model log lines with monotonic timestamps."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[tuple[float, str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append((time.monotonic(), record.name, record.getMessage()))


@dataclass(slots=True)
class Journey:
    """The one client, the planner it drives, and the log it reads."""

    client: httpx.Client
    planner: object
    capture: Capture


def _attribute(step: Step, records: list[tuple[float, str, str]]) -> None:
    previous = step.started
    for when, name, message in records:
        if name == MODEL_LOG:
            step.model_lines.append(message)
        elif name == COUNTERS_LOG:
            previous = _count(step, message, when, previous)
    step.stage_times["render and transport"] = step.finished - previous


def _count(step: Step, message: str, when: float, previous: float) -> float:
    stage, counter = message.split(" ", 1)
    counter_name = counter.split("=")[0]
    if counter_name == "stage_done":
        step.stage_times[stage] = when - previous
        return when
    if counter_name == "upstream_call":
        step.calls[stage] = step.calls.get(stage, 0) + 1
    elif counter_name == "upstream_retry":
        step.calls[f"{stage} retry"] = step.calls.get(f"{stage} retry", 0) + 1
    return previous


def _hidden(html: str) -> dict[str, str]:
    return dict(HIDDEN.findall(html))


def _body(tokens: dict[str, str], *, step_free: bool) -> dict[str, str]:
    body = {
        "csrf_token": tokens["csrf_token"],
        "idempotency_key": tokens["idempotency_key"],
        "who": "solo" if SOLO else "kids",
        "time": TIME_MIN,
        "energy": "moderate",
        "location_mode": "typed",
        "place": PLACE,
        "interests_text": TEXT,
    }
    if not SOLO:
        body["age_band"] = "3-5"
    if step_free:
        body["step_free"] = "1"  # a ranking preference: same eligibility, new fingerprint
    return body


def _text(fragment: str) -> str:
    return " ".join(TAG.sub(" ", fragment).split())


def _idea_line(idea: object) -> str:
    pair = idea.pair  # type: ignore[attr-defined]
    where = pair.place.name if pair.place else "generic"
    hook = idea.hook_id  # type: ignore[attr-defined]
    reasons = list(idea.reason_ids)  # type: ignore[attr-defined]
    return f"{pair.pair_id}={pair.activity_id}@{where} hook={hook} reasons={reasons}"


def _describe(step: Step, html: str, planner: object) -> None:
    step.cards = [_text(m) for m in CARD_TITLE.findall(html)]
    card_idea_ids = DETAIL_URL.findall(html)
    for needle, note in (
        ("AI selection isn", "page carries the MODEL_FALLBACK label"),
        ("We think they", "page shows inferred interests"),
        ("no longer current", "page shows the historical notice"),
        ("load nearby places", "page carries the PLACES_UNAVAILABLE notice"),
    ):
        if needle in html:
            step.page_notes.append(note)
    jobs = getattr(planner, "_jobs", {})  # the real registry, read for evidence only
    job = jobs.get(step.job_id)
    result = job.result if job is not None else None
    if result is None:
        return
    step.error = result.error.value if result.error else ""
    step.source = (
        f"{result.source.value} ({result.state.value}, {len(result.ideas)} ideas, "
        f"error={step.error or None}, near {result.answers.location_label!r})"
    )
    step.page_notes.append("internal picks: " + "; ".join(_idea_line(i) for i in result.ideas))
    idea_ids = [idea.pair.idea_id for idea in result.ideas]
    if idea_ids:
        same = sorted(idea_ids) == sorted(set(card_idea_ids))
        step.page_notes.append(
            f"cards link {len(set(card_idea_ids))} idea IDs; "
            f"{'identical to' if same else 'DIFFERENT from'} the result's {len(idea_ids)} picks"
        )
    if result.source is Source.MODEL:
        step.page_notes.append("source=MODEL: the cards above are the model's validated picks")


def _follow(client: httpx.Client, response: httpx.Response, step: Step) -> httpx.Response:
    """Follow 303s to the final page, bounded, recording every hop."""
    page = response
    for _ in range(REDIRECT_HOPS):
        location = page.headers.get("location", "")
        if page.status_code != HTTP_SEE_OTHER or not location:
            break
        page = client.get(location)
        step.statuses.append(f"GET {page.status_code}")
        step.url = location
    return page


def _run(journey: Journey, step: Step, tokens: dict[str, str], *, step_free: bool) -> None:
    client, capture = journey.client, journey.capture
    mark, sent_mark = len(capture.records), len(SENT)
    step.started = time.monotonic()
    posted = client.post(
        "/plan", data=_body(tokens, step_free=step_free), headers={"Origin": ORIGIN}
    )
    step.statuses.append(f"POST {posted.status_code}")
    page = _follow(client, posted, step)
    ambiguous = CANDIDATE.search(page.text) if step.url else None
    if ambiguous is not None:
        # An ambiguous place: take the first candidate, as a person would.
        chosen = client.post(
            "/location-choice",
            data={"csrf_token": tokens["csrf_token"], "candidate_id": ambiguous.group(1)},
            headers={"Origin": ORIGIN},
        )
        step.statuses.append(f"POST {chosen.status_code}")
        page = _follow(client, chosen, step)
        step.page_notes.append("the place was ambiguous; the first candidate was chosen")
    step.finished = time.monotonic()
    step.job_id = step.url.rsplit("/", 1)[-1]
    step.pairs_sent = SENT[sent_mark:]
    _attribute(step, capture.records[mark:])
    _describe(step, page.text, journey.planner)
    OUT.mkdir(exist_ok=True)
    path = OUT / f"live-{RUN_TAG_FULL}-{step.name.split()[0].lower()}.html"
    path.write_text(page.text, encoding="utf-8")
    step.html_path = str(path.relative_to(ROOT))


def _shoot(steps: list[Step], cookie_name: str, cookie_value: str) -> None:
    """Screenshot each result page in a real browser carrying the same session."""
    from playwright.sync_api import sync_playwright  # noqa: PLC0415  optional, dev-only

    with sync_playwright() as play:
        browser = play.chromium.launch()
        for width in WIDTHS:
            context = browser.new_context(
                viewport={"width": width, "height": 1100}, ignore_https_errors=True
            )
            context.add_cookies(
                [
                    {
                        "name": cookie_name,
                        "value": cookie_value,
                        "url": ORIGIN,
                        "secure": True,
                        "httpOnly": True,
                        "sameSite": "Lax",
                    }
                ]
            )
            page = context.new_page()
            for step in steps:
                if not step.url:
                    continue
                page.goto(ORIGIN + step.url)
                page.wait_for_load_state("networkidle")
                shot = OUT / f"live-{RUN_TAG_FULL}-{step.name.split()[0].lower()}-{width}.png"
                page.screenshot(path=str(shot), full_page=True)
                step.shots.append(str(shot.relative_to(ROOT)))
            context.close()
        browser.close()


def _row(s: Step) -> str:
    if s.skipped:
        return f"| {s.name} | skipped | | | | | | {s.skipped} |"
    t = s.stage_times
    total = s.finished - s.started
    calls = ", ".join(f"{k} {v}" for k, v in sorted(s.calls.items())) or "none"
    model_calls = sum(1 for m in s.model_lines if m.startswith("model served by"))
    return (
        f"| {s.name} | {s.status} | {t.get('geocode', 0):.2f} s | "
        f"{t.get('weather_places', 0):.2f} s | {t.get('choosing', 0):.2f} s | "
        f"{t.get('render and transport', 0):.2f} s | **{total:.2f} s** | "
        f"{calls}; model served {model_calls} |"
    )


def _title() -> str:
    places = (
        "FIXTURE PLACES translated to the geocoded origin; live geocode, forecast and model"
        if FIXTURE_PLACES
        else "live providers"
    )
    who = "solo adult" if SOLO else "family with a 3-5 year old"
    return f"## Live search: {PLACE}, {who}, {TIME_MIN} min ({places})"


def _report(steps: list[Step]) -> str:
    when = f"{datetime.now(UTC):%Y-%m-%d %H:%M} UTC"
    lines = [
        _title(),
        "",
        f"Run {when}. Interest text (controlled input): {TEXT!r}.",
        "",
        (
            "| step | status | geocode | places+weather | model incl. queue | "
            "render+transport | total | calls |"
        ),
        "|---|---|---|---|---|---|---|---|",
    ]
    lines += [_row(s) for s in steps]
    for s in steps:
        if s.skipped:
            continue
        lines += [
            "",
            f"### {s.name}",
            f"- job `{s.job_id[:8]}`, internal result: {s.source or 'joined, no new job'}",
            f"- cards: {s.cards}",
        ]
        lines += [f"- {note}" for note in s.page_notes]
        for sent in s.pairs_sent:
            lines.append(f"- pairs sent to the model ({len(sent)}):")
            lines += [f"    - {pair}" for pair in sent]
        lines += [f"- model log: {m}" for m in s.model_lines]
        lines.append(f"- page saved to `{s.html_path}`")
        lines += [f"- screenshot `{shot}`" for shot in s.shots]
    return "\n".join(lines) + "\n"


def _serve(app: object) -> uvicorn.Server:
    config = uvicorn.Config(
        app,  # type: ignore[arg-type]
        host=HOST,
        port=PORT,
        ssl_keyfile=str(CERT_DIR / "key.pem"),
        ssl_certfile=str(CERT_DIR / "cert.pem"),
        log_level="warning",
    )
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.monotonic() + STARTUP_WAIT_S
    while not server.started:
        if time.monotonic() > deadline:
            msg = "the server did not start"
            raise RuntimeError(msg)
        time.sleep(0.05)
    return server


def _steps(journey: Journey) -> list[Step]:
    """Run the cold search, the identical resubmission and, unless told not to, the warm one."""
    client = journey.client
    tokens = _hidden(client.get("/").text)
    cold = Step("Cold search (fresh database)")
    _run(journey, cold, tokens, step_free=False)
    again = Step("Identical resubmission (same key, same answers)")
    _run(journey, again, tokens, step_free=False)
    steps = [cold, again]
    if NO_WARM:
        return steps
    warm = Step("New search with cached geocode and weather (step-free preference)")
    spent = cold.overpass_attempts + again.overpass_attempts
    if cold.error == ErrorCode.PLACES_UNAVAILABLE.value and not FIXTURE_PLACES:
        # Without cached places the warm search would call Overpass again.
        warm.skipped = (
            f"places were not obtained by the cold search ({spent} of "
            f"{MAX_OVERPASS_ATTEMPTS} allowed Overpass attempts spent); not polling"
        )
    else:
        tokens2 = _hidden(client.get("/").text)
        _run(journey, warm, tokens2, step_free=True)
    steps.append(warm)
    return steps


def _loopback_only(request: httpx.Request) -> None:
    """Refuse any request that is not to the loopback origin this script serves."""
    host = request.url.host.strip("[]")
    if host != "localhost" and not ipaddress.ip_address(host).is_loopback:
        msg = f"refusing a request to {request.url.host}: only the loopback origin is allowed"
        raise RuntimeError(msg)


def main() -> int:
    _loopback_only(httpx.Request("GET", ORIGIN))  # the origin itself, before anything runs
    capture = Capture()
    logging.basicConfig(level=logging.INFO, handlers=[capture])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if FIXTURE_PLACES:
        _install_fixture_places()
    app = create_app()
    server = _serve(app)
    steps: list[Step] = []
    try:
        # The dev certificate is self-signed, so verification is off; the request hook
        # makes sure that only ever applies to the loopback origin.
        with httpx.Client(
            base_url=ORIGIN,
            verify=False,  # noqa: S501
            follow_redirects=False,
            timeout=30.0,
            event_hooks={"request": [_loopback_only]},
        ) as client:
            journey = Journey(
                client=client, planner=app.state.wiggle.resources.planner, capture=capture
            )
            steps = _steps(journey)
            cookie_name = session_cookie_name(app.state.wiggle.settings.mode)
            cookie_value = client.cookies.get(cookie_name) or ""
        if not NO_SHOTS and cookie_value:
            _shoot(steps, cookie_name, cookie_value)
    finally:
        server.should_exit = True
    report = _report(steps)
    sys.stdout.buffer.write(report.encode("utf-8"))
    (OUT / f"live-{RUN_TAG_FULL}-report.md").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
