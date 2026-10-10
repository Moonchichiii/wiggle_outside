"""A PlannerService backed by fixtures, so the form can post and show a result.

DELETE THIS FILE when WP6 lands. It is integration scaffolding, not a package: the real
planner runs the ARCHITECTURE section 3 workflow under one absolute deadline, calls
providers and the model, and enforces the request budget. This calls nothing, waits for
nothing and decides nothing — it hands back a prepared result so the web layer and the
templates can be exercised end to end before the planner exists.

What it does honour, because getting these wrong would teach the web layer the wrong
shape: results are immutable (D46), a repeat of the same key with the same fingerprint
joins rather than starting again, a different fingerprint on the same key is a Conflict,
and ownership failures raise NotFound rather than returning someone else's result.
"""

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Final

from wiggle_outside.core.errors import ErrorCode, NoticeId
from wiggle_outside.core.types import (
    AgeBand,
    Answers,
    AnswersSummary,
    Coordinates,
    Energy,
    Idea,
    InterestOutcome,
    Interests,
    InterestTag,
    JobState,
    Pair,
    Place,
    PlanResult,
    Source,
    TimeBudget,
    TypedPlace,
    WeatherCondition,
    WeatherSummary,
    Who,
)
from wiggle_outside.planner.ports import Conflict, JobRef, NotFound

ID_BYTES: Final = 16
VALID_FOR: Final = timedelta(minutes=5)
RETAIN_FOR: Final = timedelta(hours=1)

# Three places near the WALKTHROUGH fixture location, so the cards have real-looking
# distances and names that exercise escaping ("Elm & Oak").
_PLACES: Final = (
    Place(
        place_id="pl-1",
        name="Bergby Park",
        kind="park",
        coords=Coordinates(lat=60.12, lon=17.9),
        fee="no",
        osm_access="yes",
    ),
    Place(
        place_id="pl-2",
        name="Elm & Oak Playground",
        kind="playground",
        coords=Coordinates(lat=60.13, lon=17.91),
        fee="unknown",
        osm_access="unknown",
    ),
    Place(
        place_id="pl-3",
        name="Norra Skogen",
        kind="forest",
        coords=Coordinates(lat=60.11, lon=17.88),
        fee="unknown",
        osm_access="limited",
    ),
)

_ACTIVITY_IDS: Final = ("nature-bingo", "leaf-colour-hunt", "puddle-jumping")
_HOOK_IDS: Final = ("expedition", "secret-spot", "pocket-adventure")
_REASON_IDS: Final = (("close_by", "fits_time"), ("fits_time",), ("matches_energy",))


def _summary(answers: Answers, label: str) -> AnswersSummary:
    location = answers.location
    coords = location if isinstance(location, Coordinates) else Coordinates(lat=60.12, lon=17.9)
    return AnswersSummary(
        who=answers.who,
        age_bands=answers.age_bands,
        time_budget=answers.time_budget,
        energy=answers.energy,
        location=coords,
        location_label=label,
        stroller=answers.stroller,
        step_free=answers.step_free,
    )


def _weather(now: datetime, end: datetime) -> WeatherSummary:
    return WeatherSummary(
        fetched_at=now,
        tz="Europe/Stockholm",
        window_start=now,
        window_end=end,
        condition=WeatherCondition.SHOWERS_POSSIBLE,
        temp_min_c=11,
        temp_max_c=12,
        max_precip_probability=40,
        max_wind_kmh=18,
    )


def _ideas(count: int, travel_base: int) -> tuple[Idea, ...]:
    ideas: list[Idea] = []
    for index in range(count):
        place = _PLACES[index % len(_PLACES)]
        ideas.append(
            Idea(
                pair=Pair(
                    pair_id=f"p{index + 1}",
                    idea_id=secrets.token_urlsafe(ID_BYTES),
                    activity_id=_ACTIVITY_IDS[index % len(_ACTIVITY_IDS)],
                    place=place,
                    distance_m=400 + index * 200,
                    travel_min=travel_base + index * 2,
                    duration_min=36,
                    allowed_hook_ids=frozenset(_HOOK_IDS),
                    allowed_reason_ids=frozenset({"close_by", "fits_time", "matches_energy"}),
                ),
                hook_id=_HOOK_IDS[index % len(_HOOK_IDS)],
                reason_ids=_REASON_IDS[index % len(_REASON_IDS)],
            )
        )
    return tuple(ideas)


def _fingerprint(answers: Answers) -> str:
    """Discriminate two submissions, interest text included.

    `Answers.interest_text` is excluded from repr, hash and comparison so it cannot leak,
    so `repr()` would make two submissions that differ only in their interests look
    identical. CONTRACTS section 7 requires the opposite. The real fingerprint is
    `web.forms.fingerprint` over the canonical form; WP6 stores and compares it.
    """
    return repr(
        (
            answers.who,
            sorted(answers.age_bands),
            answers.time_budget,
            answers.energy,
            answers.location,
            answers.stroller,
            answers.step_free,
            answers.interest_text,
        )
    )


@dataclass(frozen=True, slots=True)
class _Job:
    result: PlanResult
    fingerprint: str
    session_id: str


@dataclass(slots=True)
class PreviewPlanner:
    """Hands back a prepared result. Wired by main.py until WP6 exists.

    `ideas` chooses how many cards the result carries, so the 0, 1, 2 and 3-idea layouts
    and the daylight and no-match notices can all be looked at without a planner.
    """

    ideas: int = 3
    outcome: ErrorCode | None = None
    source: Source = Source.FALLBACK
    _jobs: dict[str, _Job] = field(default_factory=dict, init=False)
    _by_key: dict[tuple[str, str], str] = field(default_factory=dict, init=False)

    def _build(self, answers: Answers) -> PlanResult:
        now = datetime.now(UTC)
        end = now + timedelta(minutes=int(answers.time_budget))
        label = (
            answers.location.text if isinstance(answers.location, TypedPlace) else "Your location"
        )
        blocked = self.outcome in {
            ErrorCode.DAYLIGHT_NIGHT,
            ErrorCode.DAYLIGHT_TOO_SHORT,
            ErrorCode.NO_MATCHES,
            ErrorCode.WEATHER_RESTRICTED,
        }
        notices: tuple[NoticeId | ErrorCode, ...] = ()
        if self.source is Source.FALLBACK and not blocked:
            # The label is not decoration: a fallback result must say so (D44).
            notices = (ErrorCode.MODEL_FALLBACK,)
        return PlanResult(
            job_id=secrets.token_urlsafe(ID_BYTES),
            state=JobState.FALLBACK if not blocked else JobState.COMPLETE,
            source=self.source,
            ideas=() if blocked else _ideas(self.ideas, travel_base=12),
            notices=notices,
            interests=(
                Interests(tags=(InterestTag.BIRDS,), outcome=InterestOutcome.MATCHED)
                if answers.interest_text
                else None
            ),
            answers=_summary(answers, label),
            weather=None if blocked else _weather(now, end),
            planned_start=now,
            planned_end=end,
            valid_until=now + VALID_FOR,
            retain_until=now + RETAIN_FOR,
            error=self.outcome,
        )

    async def start_or_join(self, session_id: str, key: str, answers: Answers) -> JobRef:
        fingerprint = _fingerprint(answers)
        existing = self._by_key.get((session_id, key))
        if existing is not None:
            job = self._jobs[existing]
            if job.fingerprint != fingerprint:
                # Same key, different answers: a new search needs a new key (CONTRACTS 7).
                raise Conflict
            return JobRef(job_id=existing, joined=True)

        result = self._build(answers)
        self._jobs[result.job_id] = _Job(result, fingerprint, session_id)
        self._by_key[(session_id, key)] = result.job_id
        return JobRef(job_id=result.job_id, joined=False)

    async def choose_location(self, session_id: str, candidate_id: str) -> JobRef:  # noqa: ARG002  the PlannerService protocol fixes this signature
        # The preview never returns ambiguous candidates, so nothing can be chosen.
        raise NotFound

    async def wait(self, session_id: str, job_id: str) -> PlanResult:
        result = self.get(session_id, job_id)
        if result is None:
            raise NotFound
        return result

    def get(self, session_id: str, job_id: str) -> PlanResult | None:
        job = self._jobs.get(job_id)
        if job is None or job.session_id != session_id:
            # Ownership failure is indistinguishable from an unknown id (CONTRACTS 3).
            return None
        return job.result


SAMPLE_ANSWERS: Final = Answers(
    who=Who.KIDS,
    age_bands=frozenset({AgeBand.B3_5, AgeBand.B6_9}),
    time_budget=TimeBudget.H1,
    energy=Energy.MODERATE,
    location=TypedPlace(text="Bergby"),
    stroller=False,
    step_free=False,
)
