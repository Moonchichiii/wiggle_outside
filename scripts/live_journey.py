"""A real search through the real app, with real providers and the hosted model.

    uv run python scripts/live_journey.py [place] [--no-warm] [--no-shots]

Three steps, each timed per stage from the planner's own stage counters and with every
provider call counted from the counter log: a cold search (fresh database, nothing
cached), an identical resubmission (must join: zero calls), and a new search on the
same place and time budget that differs only in a ranking preference (cached place
data). The app is the real `create_app()` with the real adapters, served by uvicorn
over https on 127.0.0.1:8453 (the dev certificate in `out/devcert`) in a thread of
this process, so the counter log is read in-process while every request is a real
request. Controlled input: a fixed family and a fixed interest text; no visitor exists.
Results pages are saved under `out/` as HTML and, with Playwright, as screenshots.
"""

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
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
OUT: Final = ROOT / "out"
CERT_DIR: Final = OUT / "devcert"
ARGS: Final = [a for a in sys.argv[1:] if not a.startswith("--")]
PLACE: Final = ARGS[0] if ARGS else "Växjö"
NO_WARM: Final = "--no-warm" in sys.argv
NO_SHOTS: Final = "--no-shots" in sys.argv
TEXT: Final = "birds and puddles"
HOST: Final = "127.0.0.1"
PORT: Final = 8453
ORIGIN: Final = f"https://{HOST}:{PORT}"
HIDDEN: Final = re.compile(r'name="([a-z_]+)" value="([^"]*)"')
CANDIDATE: Final = re.compile(r'name="candidate_id" value="([^"]+)"')
CARD_TITLE: Final = re.compile(
    r'<h3[^>]*class="[^"]*wo-card-title[^"]*"[^>]*>(.*?)</h3>', re.DOTALL
)
TAG: Final = re.compile(r"<[^>]+>")
COUNTERS_LOG: Final = "wiggle_outside.counters"
MODEL_LOG: Final = "wiggle_outside.integrations.openrouter"
STARTUP_WAIT_S: Final = 15.0
WIDTHS: Final = (390, 1440)

# A fresh database so the first search is cold; the port so the origin policy allows it.
os.environ["WO_DB_PATH"] = str(Path(tempfile.mkdtemp(prefix="wo-journey-")) / "wiggle.sqlite")
os.environ.setdefault("WO_MODE", "local")
os.environ["WO_PORT"] = str(PORT)

import httpx  # noqa: E402
import uvicorn  # noqa: E402

from wiggle_outside.core.types import Source  # noqa: E402
from wiggle_outside.main import create_app  # noqa: E402
from wiggle_outside.web.security import session_cookie_name  # noqa: E402


@dataclass(slots=True)
class Step:
    name: str
    started: float = 0.0
    finished: float = 0.0
    stage_times: dict[str, float] = field(default_factory=dict)
    calls: dict[str, int] = field(default_factory=dict)
    model_lines: list[str] = field(default_factory=list)
    status: str = ""
    job_id: str = ""
    url: str = ""
    source: str = ""
    cards: list[str] = field(default_factory=list)
    page_notes: list[str] = field(default_factory=list)
    html_path: str = ""
    shots: list[str] = field(default_factory=list)


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
        "who": "kids",
        "age_band": "3-5",
        "time": "60",
        "energy": "moderate",
        "location_mode": "typed",
        "place": PLACE,
        "interests_text": TEXT,
    }
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
    step.source = (
        f"{result.source.value} ({result.state.value}, {len(result.ideas)} ideas, "
        f"error={result.error.value if result.error else None}, "
        f"near {result.answers.location_label!r})"
    )
    step.page_notes.append("internal picks: " + "; ".join(_idea_line(i) for i in result.ideas))
    if result.source is Source.MODEL:
        step.page_notes.append("source=MODEL: the cards above are the model's validated picks")


def _run(journey: Journey, step: Step, tokens: dict[str, str], *, step_free: bool) -> None:
    client, capture = journey.client, journey.capture
    mark = len(capture.records)
    step.started = time.monotonic()
    posted = client.post(
        "/plan", data=_body(tokens, step_free=step_free), headers={"Origin": ORIGIN}
    )
    location = posted.headers.get("location", "")
    page = client.get(location) if location else posted
    ambiguous = CANDIDATE.search(page.text) if location else None
    if ambiguous is not None:
        # An ambiguous place: take the first candidate, as a person would.
        chosen = client.post(
            "/location-choice",
            data={"csrf_token": tokens["csrf_token"], "candidate_id": ambiguous.group(1)},
            headers={"Origin": ORIGIN},
        )
        location = chosen.headers.get("location", "")
        page = client.get(location)
        step.page_notes.append("the place was ambiguous; the first candidate was chosen")
    step.finished = time.monotonic()
    step.status = f"POST {posted.status_code}, GET {page.status_code}"
    step.url = location
    step.job_id = location.rsplit("/", 1)[-1]
    _attribute(step, capture.records[mark:])
    _describe(step, page.text, journey.planner)
    OUT.mkdir(exist_ok=True)
    path = OUT / f"live-{PLACE.lower()}-{step.name.split()[0].lower()}.html"
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
                shot = OUT / f"live-{PLACE.lower()}-{step.name.split()[0].lower()}-{width}.png"
                page.screenshot(path=str(shot), full_page=True)
                step.shots.append(str(shot.relative_to(ROOT)))
            context.close()
        browser.close()


def _row(s: Step) -> str:
    t = s.stage_times
    total = s.finished - s.started
    calls = ", ".join(f"{k} {v}" for k, v in sorted(s.calls.items())) or "none"
    model_calls = sum(1 for m in s.model_lines if m.startswith("model served by"))
    return (
        f"| {s.name} | {s.status} | {t.get('geocode', 0):.2f} s | "
        f"{t.get('weather_places', 0):.2f} s | {t.get('choosing', 0):.2f} s | "
        f"{t.get('render and transport', 0):.2f} s | **{total:.2f} s** | "
        f"{calls}; model {model_calls} |"
    )


def _report(steps: list[Step]) -> str:
    when = f"{datetime.now(UTC):%Y-%m-%d %H:%M} UTC"
    lines = [
        f"## Live search: {PLACE}, family with a 3-5 year old, 1 h, run {when}",
        "",
        (
            "| step | status | geocode | places+weather | model incl. queue | "
            "render+transport | total | calls |"
        ),
        "|---|---|---|---|---|---|---|---|",
    ]
    lines += [_row(s) for s in steps]
    for s in steps:
        lines += [
            "",
            f"### {s.name}",
            f"- job `{s.job_id[:8]}`, internal result: {s.source or 'joined, no new job'}",
            f"- cards: {s.cards}",
        ]
        lines += [f"- {note}" for note in s.page_notes]
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
    if not NO_WARM:
        tokens2 = _hidden(client.get("/").text)
        warm = Step("New search on cached places (step-free preference)")
        _run(journey, warm, tokens2, step_free=True)
        steps.append(warm)
    return steps


def main() -> int:
    capture = Capture()
    logging.basicConfig(level=logging.INFO, handlers=[capture])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    app = create_app()
    server = _serve(app)
    steps: list[Step] = []
    try:
        # The dev certificate is self-signed; a POST waits for the whole 20 s job.
        with httpx.Client(
            base_url=ORIGIN,
            verify=False,  # noqa: S501
            follow_redirects=False,
            timeout=30.0,
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
    (OUT / f"live-{PLACE.lower()}-report.md").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
