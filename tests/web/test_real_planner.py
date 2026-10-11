"""The real planner behind the real routes, with fake providers.

The route tests run against a scripted PlannerService; this mounts `planner.jobs.Planner`
over scripted *providers* instead, so the whole no-JavaScript journey - form, POST, 303,
results page with the fallback label, detail page - is exercised end to end with zero
sockets. The ambiguous-place branch checks that the planner's candidates reach the
session the web layer reads them from.
"""

import json
import re
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Final

import pytest
from tests_planner_bridge import Rig, ambiguous_rig, budgets, plain_rig
from web_support import Harness, build_harness

from wiggle_outside.core.result import Ok
from wiggle_outside.planner.jobs import Planner
from wiggle_outside.planner.ports import RawSelection
from wiggle_outside.web.security import SessionStore

if TYPE_CHECKING:
    from wiggle_outside.core.types import LocationCandidates, Pair

DETAIL_URL: Final = re.compile(r'href="(/results/[^"]+/ideas/[^"]+)"')
DETAIL_IDEA_ID: Final = re.compile(r'href="/results/[^"/]+/ideas/([^"]+)"')
CARD_TITLE: Final = re.compile(r'class="[^"]*wo-card-title[^"]*"[^>]*>(.*?)</h3>', re.DOTALL)
CANDIDATE: Final = re.compile(r'name="candidate_id" value="([^"]+)"')


def mounted(build: Callable[[], Rig]) -> Iterator[Harness]:
    rig = build()
    sessions = SessionStore()

    def publish(session_id: str, held: LocationCandidates) -> None:
        # What main.py wires: the planner's candidates land in the session the routes read.
        session = sessions.get(session_id)
        if session is not None:
            session.candidates = held

    planner = Planner(rig.ports, budgets(), deadline_s=18.0, publish_candidates=publish)
    yield from build_harness(planner, sessions=sessions)


@pytest.fixture
def real() -> Iterator[Harness]:
    yield from mounted(plain_rig)


@pytest.fixture
def ambiguous() -> Iterator[Harness]:
    yield from mounted(ambiguous_rig)


class _RepeatingModel:
    """Pick the same entry three ways: twice by the same pair, once at another place.

    Then one pick with a hook the pair does not allow and one with an unknown pair.
    Valid output under the sent schema now that `uniqueItems` is not sent (TC-010).
    """

    async def __call__(
        self, pairs: tuple[Pair, ...], _text: str | None, _deadline: float
    ) -> Ok[RawSelection]:
        first, twin = _twins(pairs)
        other = next(p for p in pairs if p.activity_id != first.activity_id)
        picks = [
            {"pair_id": first.pair_id, "hook_id": min(first.allowed_hook_ids), "reason_ids": []},
            {"pair_id": first.pair_id, "hook_id": min(first.allowed_hook_ids), "reason_ids": []},
            {"pair_id": twin.pair_id, "hook_id": min(twin.allowed_hook_ids), "reason_ids": []},
            {"pair_id": other.pair_id, "hook_id": "no-such-hook", "reason_ids": []},
            {"pair_id": "p99", "hook_id": min(other.allowed_hook_ids), "reason_ids": []},
        ]
        return Ok(RawSelection(payload=json.dumps({"picks": picks})))


def _twins(pairs: tuple[Pair, ...]) -> tuple[Pair, Pair]:
    """Return an entry offered at two places; failing that, the first pair twice."""
    for first in pairs:
        for twin in pairs:
            if twin.pair_id != first.pair_id and twin.activity_id == first.activity_id:
                return first, twin
    return pairs[0], pairs[0]


def repeating_rig() -> Rig:
    built = plain_rig()
    built.model = _RepeatingModel()  # type: ignore[assignment]  the callable shape is all that counts
    return built


@pytest.fixture
def repeating() -> Iterator[Harness]:
    yield from mounted(repeating_rig)


def test_duplicate_and_invalid_picks_never_reach_the_cards(repeating: Harness) -> None:
    posted = repeating.plan()
    shown = repeating.client.get(posted.headers["location"])

    assert shown.status_code == 200
    assert "AI selection isn" not in shown.text, "the model's valid pick counts: no fallback"
    titles = CARD_TITLE.findall(shown.text)
    assert len(titles) == 1, titles
    assert len(set(DETAIL_IDEA_ID.findall(shown.text))) == 1
    detail = DETAIL_URL.search(shown.text)
    assert detail is not None
    assert repeating.client.get(detail.group(1)).status_code == 200


def test_the_journey_reaches_a_labelled_fallback_result(real: Harness) -> None:
    posted = real.plan()
    assert posted.status_code == 303

    shown = real.client.get(posted.headers["location"])
    assert shown.status_code == 200
    assert "AI selection isn" in shown.text  # MODEL_FALLBACK, said plainly (D44)
    assert "Bergby, G" in shown.text  # the geocoder's label, not the typed text
    assert "Example forecast" not in shown.text  # the real path carries no fixture label

    detail = DETAIL_URL.search(shown.text)
    assert detail is not None
    assert real.client.get(detail.group(1)).status_code == 200


def test_the_same_form_again_joins_the_same_job(real: Harness) -> None:
    tokens = real.start()
    first = real.post("/plan", real.body(tokens))
    second = real.post("/plan", real.body(tokens))
    assert first.headers["location"] == second.headers["location"]


def test_an_ambiguous_place_offers_the_choice_and_the_choice_plans(ambiguous: Harness) -> None:
    posted = ambiguous.plan()
    choice_page = ambiguous.client.get(posted.headers["location"])

    assert choice_page.status_code == 200
    candidates = CANDIDATE.findall(choice_page.text)
    assert len(candidates) == 3, "the three distinguishable hits, as radios"

    tokens = ambiguous.start()
    chosen = ambiguous.post(
        "/location-choice", {"csrf_token": tokens["csrf_token"], "candidate_id": candidates[0]}
    )
    assert chosen.status_code == 303
    result = ambiguous.client.get(chosen.headers["location"])
    assert result.status_code == 200
    assert "AI selection isn" in result.text
