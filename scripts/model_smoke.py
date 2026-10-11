"""PLAN section 15 step 3: the hosted model smoke, on controlled input, against OpenRouter.

    uv run python scripts/model_smoke.py [--typical-only] [--generic-only]

Two real calls through the real adapter: a typical request (the WALKTHROUGH family, four
places) and the largest contracted one (twelve pairs, 120 characters of interest text).
Each answer is validated by `core.ideas.parse_selection` exactly as a run would validate
it. The script prints, and writes to `docs/evidence/model-smoke.md`, the pairs offered,
the validated picks, the serving provider, usage, reasoning tokens, finish reason, the
latency and the request size. Controlled input only: no visitor data exists here. The key
is read from the environment by `Settings` and is never printed or written.
"""

import asyncio
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import httpx

from wiggle_outside.core.activities import fits_time
from wiggle_outside.core.answers import allowed_energies
from wiggle_outside.core.ideas import (
    REASON_ALL_AGES,
    REASON_CLOSE_BY,
    REASON_FITS_TIME,
    REASON_MATCHES_ENERGY,
    Selection,
    parse_selection,
)
from wiggle_outside.core.places import PairCandidate, PairPlan, pair_candidates, to_pairs
from wiggle_outside.core.result import Ok
from wiggle_outside.core.types import AgeBand, Coordinates, Energy, Pair, Place, Who
from wiggle_outside.integrations import openrouter
from wiggle_outside.planner.catalogue import load_catalogue
from wiggle_outside.planner.prompting import build_request, user_message
from wiggle_outside.settings import Settings

EVIDENCE_DIR: Final = Path(__file__).resolve().parent.parent / "docs" / "evidence"
# `--generic-only`: the pairs a run builds when places are unavailable (no place at
# all), to show whether the model picks among them (select.v2 rule 1). Its evidence
# goes to its own file so the typical smoke stays as recorded.
GENERIC_ONLY: Final = "--generic-only" in sys.argv
EVIDENCE: Final = EVIDENCE_DIR / ("model-smoke-generic.md" if GENERIC_ONLY else "model-smoke.md")
ORIGIN: Final = Coordinates(lat=60.93, lon=17.04)  # the WALKTHROUGH fixture origin
AGES: Final = frozenset({AgeBand.B3_5, AgeBand.B6_9})
ENERGY: Final = Energy.MODERATE
BUDGET_MIN: Final = 60
MODEL_DEADLINE_S: Final = 9.0
CLOSE_BY_MAX_M: Final = 1000
TEXT_MAX: Final = 120
TYPICAL_TEXT: Final = "birds and puddles"
LARGEST_TEXT: Final = (
    "they love spotting birds, jumping in puddles, collecting sticks and "
    "looking at clouds and bugs under logs!!"
)[:TEXT_MAX]
_COUNTER: Final = {"n": 0}


def _place(place_id: str, name: str, kind: str, lat: float, lon: float) -> Place:
    return Place(
        place_id=place_id,
        name=name,
        kind=kind,
        coords=Coordinates(lat=lat, lon=lon),
        fee="unknown",
        osm_access="unknown",
    )


# The WALKTHROUGH places (hand-built fixtures, as in tests/planner), plus four more for
# the largest request.
TYPICAL_PLACES: Final = (
    _place("osm:1", "Linden Park", "park", 60.935, 17.045),
    _place("osm:2", "Birchwood Nature Area", "nature_reserve", 60.938, 17.04),
    _place("osm:3", "Oak Lane Park", "park", 60.933, 17.038),
    _place("osm:4", "Elm & Oak Playground", "playground", 60.928, 17.042),
)
MORE_PLACES: Final = (
    _place("osm:5", "Mill Meadow", "park", 60.925, 17.03),
    _place("osm:6", "Pine Ridge Wood", "forest", 60.94, 17.06),
    _place("osm:7", "Riverside Picnic Site", "picnic_site", 60.92, 17.05),
    _place("osm:8", "Station Playground", "playground", 60.931, 17.05),
)


def _new_id() -> str:
    _COUNTER["n"] += 1
    return f"idea-{_COUNTER['n']}"


def _reasons(candidate: PairCandidate) -> frozenset[str]:
    """Return the controlled reason set: four of the conditions core.ideas evaluates."""
    activity = candidate.activity
    holds = {
        REASON_CLOSE_BY: candidate.distance_m is not None
        and candidate.distance_m <= CLOSE_BY_MAX_M,
        REASON_FITS_TIME: fits_time(
            activity, budget_min=BUDGET_MIN, travel_min=candidate.travel_min
        ),
        REASON_MATCHES_ENERGY: ENERGY in activity.energy,
        REASON_ALL_AGES: activity.ages >= AGES,
    }
    return frozenset(reason for reason, ok in holds.items() if ok)


def controlled_pairs(places: tuple[Place, ...]) -> tuple[Pair, ...]:
    catalogue = load_catalogue()
    activities = tuple(
        a
        for a in catalogue.activities()
        if a.who is Who.KIDS and a.ages >= AGES and allowed_energies(ENERGY) & a.energy
    )
    plan = PairPlan(origin=ORIGIN, budget_min=BUDGET_MIN, with_kids=True, prefer_step_free=False)
    return to_pairs(pair_candidates(activities, places, plan), catalogue.hooks(), _new_id, _reasons)


@dataclass(slots=True)
class Call:
    name: str
    pairs: tuple[Pair, ...]
    text: str
    served: list[openrouter.Served] = field(default_factory=list)
    elapsed_s: float = 0.0
    request_bytes: int = 0
    outcome: str = ""
    selection: Selection | None = None
    payload: str = ""


async def run(call: Call, ranker: openrouter.OpenRouterRanker) -> None:
    request = build_request(call.pairs, load_catalogue(), call.text, d39_enabled=True)
    body = openrouter.request_body(ranker.model_id, request)
    call.request_bytes = len(openrouter.serialise(body))
    started = time.monotonic()
    outcome = await ranker.select(request, time.monotonic() + MODEL_DEADLINE_S)
    call.elapsed_s = time.monotonic() - started
    call.outcome = type(outcome).__name__
    if isinstance(outcome, Ok):
        call.payload = outcome.value.payload
        call.selection = parse_selection(outcome.value.payload, call.pairs)


def _pair_line(pair: Pair) -> str:
    kind = pair.place.kind if pair.place else "none"
    distance = pair.distance_m if pair.distance_m is not None else "-"
    hooks = ", ".join(sorted(pair.allowed_hook_ids))
    reasons = ", ".join(sorted(pair.allowed_reason_ids))
    return f"| {pair.pair_id} | {pair.activity_id} | {kind} | {distance} | {hooks} | {reasons} |"


def _served_lines(call: Call) -> list[str]:
    if not call.served:
        return []
    s = call.served[0]
    return [
        "",
        (
            "| served by | model | prompt tokens | completion tokens | reasoning tokens | "
            "finish | adapter latency |"
        ),
        "|---|---|---|---|---|---|---|",
        (
            f"| {s.provider} | {s.model} | {s.prompt_tokens} | {s.completion_tokens} | "
            f"{s.reasoning_tokens} | {s.finish_reason} | {s.latency_s:.2f} s |"
        ),
    ]


def _validation_lines(call: Call) -> list[str]:
    sel = call.selection
    if sel is None:
        return [
            "",
            (
                "Validation: **off-schema as a whole** (parse_selection returned None) -> "
                "labelled fallback."
            ),
        ]
    tags = [t.value for t in sel.interests.tags]
    lines = [
        "",
        (
            f"Validation: {len(sel.picks)} pick(s) kept, {sel.dropped} dropped; interests "
            f"{sel.interests.outcome.value} {tags}"
        ),
        "",
        "| pick | pair | activity | hook | reasons |",
        "|---|---|---|---|---|",
    ]
    by_id = {p.pair_id: p for p in call.pairs}
    for i, pick in enumerate(sel.picks, start=1):
        activity = by_id[pick.pair_id].activity_id
        lines.append(
            f"| {i} | {pick.pair_id} | {activity} | {pick.hook_id} | {', '.join(pick.reason_ids)} |"
        )
    return lines


def report(call: Call) -> str:
    lines = [
        f"### {call.name}",
        "",
        f"Controlled interest text: `{call.text}`",
        "",
        (
            "Pairs offered (exactly what the model saw, plus the straight-line distance for "
            "the reader):"
        ),
        "",
        "| pair | activity | place kind | distance m | allowed hooks | allowed reasons |",
        "|---|---|---|---|---|---|",
    ]
    lines += [_pair_line(pair) for pair in call.pairs]
    lines += [
        "",
        f"Request size: {call.request_bytes} bytes (cap {openrouter.MAX_REQUEST_BYTES}).",
        f"Adapter outcome: `{call.outcome}` in {call.elapsed_s:.2f} s (no queue: direct call).",
    ]
    lines += _served_lines(call)
    if call.payload:
        lines += ["", "Raw answer (schema-constrained JSON):", "", "```json", call.payload, "```"]
    lines += _validation_lines(call)
    return "\n".join(lines) + "\n"


def _header(settings: Settings) -> str:
    return (
        "# Hosted model smoke (PLAN section 15 step 3)\n\n"
        f"Run on {datetime.now(UTC):%Y-%m-%d %H:%M} UTC with `scripts/model_smoke.py`. Model "
        f"`{settings.model_id}` through OpenRouter, routing `provider.only` = "
        f"{list(openrouter.APPROVED_PROVIDERS)}, `require_parameters` true, fallbacks within "
        f"the list, `max_tokens` {openrouter.MAX_TOKENS}, reasoning effort none, strict "
        "`json_schema` `selection.v2`, prompt `select.v2`. Controlled input: fixture places "
        "and a fixed interest text; no visitor data. The key is never written.\n\n"
    )


async def main() -> int:
    settings = Settings.from_env()
    async with httpx.AsyncClient(follow_redirects=False) as client:
        ranker = openrouter.from_settings(client, settings)
        if ranker is None:
            print("OPENROUTER_API_KEY is not set; nothing was called.")
            return 2
        calls = [
            Call(
                "Generic-only request (places unavailable: no place in any pair)",
                controlled_pairs(()),
                TYPICAL_TEXT,
            )
            if GENERIC_ONLY
            else Call(
                "Typical request (WALKTHROUGH family, 4 places)",
                controlled_pairs(TYPICAL_PLACES),
                TYPICAL_TEXT,
            )
        ]
        if "--typical-only" not in sys.argv and not GENERIC_ONLY:
            calls.append(
                Call(
                    "Largest contracted request (12 pairs, 120-character text)",
                    controlled_pairs(TYPICAL_PLACES + MORE_PLACES),
                    LARGEST_TEXT,
                )
            )
        for call in calls:
            logged = openrouter.OpenRouterRanker(
                client=client,
                url=ranker.url,
                api_key=ranker.api_key,
                model_id=ranker.model_id,
                on_served=call.served.append,
            )
            await run(call, logged)
    body = _header(settings) + "\n".join(report(c) for c in calls)
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(body, encoding="utf-8")
    typical = build_request(calls[0].pairs, load_catalogue(), TYPICAL_TEXT, d39_enabled=True)
    shown = user_message(typical)
    text = f"{body}\nwritten: {EVIDENCE}\nuser message of the typical request:\n{shown}\n"
    sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
