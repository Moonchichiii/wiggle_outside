"""The outing workflow under one absolute deadline (ARCHITECTURE section 3).

Geocode the typed place if there is one, then places and weather together, then the
pure rules in BACKEND-CONTRACT section 1 order - validated weather, the family daylight
rule, the run-wide severe and heat rules, per-entry eligibility - then pairs, then one
model call if a model stage is wired, else the labelled deterministic fallback (D44).

Every stage gets only what remains of the one monotonic deadline; adapters answer
`TransportFailure` when nothing remains, and the workflow cancels any call that is
still running at its stage deadline (`_bounded`), so the absolute deadline holds even if
an adapter overran its own bound. Provider failures are outcomes, never exceptions;
cancellation propagates. Nothing here stores a verdict: a resubmission is a new run and
re-evaluates everything (TC-002).
"""

import asyncio
import secrets
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta, tzinfo
from functools import partial
from typing import TYPE_CHECKING, Final, Literal, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from wiggle_outside.core.activities import Conditions, eligible
from wiggle_outside.core.answers import Constraints, answers_outcome, constraints
from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.ideas import ReasonContext, allowed_reason_ids, parse_selection
from wiggle_outside.core.places import ANY_PLACE_KIND, PairPlan, pair_candidates, to_pairs
from wiggle_outside.core.ranking import RankingInputs
from wiggle_outside.core.result import Empty, Ok, Outcome, TransportFailure
from wiggle_outside.core.types import (
    MAX_CANDIDATES,
    Activity,
    Answers,
    AnswersSummary,
    Coordinates,
    GeocodeHit,
    GeocodeHits,
    Idea,
    InterestOutcome,
    Interests,
    JobState,
    LocationCandidate,
    Pair,
    PlanResult,
    Source,
    WeatherSummary,
    Who,
)
from wiggle_outside.core.weather import (
    Samples,
    daylight_outcome,
    is_in_daylight,
    run_weather_outcome,
    summarise,
    used_samples,
)
from wiggle_outside.planner.fallback import fallback_ideas, result_notices
from wiggle_outside.planner.ports import (
    Catalogue,
    Clock,
    Counters,
    Geocoder,
    PlacesProvider,
    RawSelection,
    WeatherProvider,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from wiggle_outside.core.places import PairCandidate
    from wiggle_outside.core.types import Place, WeatherWindow

ID_BYTES: Final = 16
# BACKEND-CONTRACT section 2.
VALID_AFTER_CREATION: Final = timedelta(minutes=5)
WEATHER_USABLE_FOR: Final = timedelta(minutes=30)
VALID_AFTER_START: Final = timedelta(minutes=10)
RETAIN_AFTER_VALID: Final = timedelta(minutes=60)
# The place radius: as far as the outing can walk out and back in half the budget, within
# the Overpass template's bounds (integrations.overpass; repeated here because the planner
# never imports an adapter).
MIN_RADIUS_M: Final = 100
MAX_RADIUS_M: Final = 3000
WALK_KMH_WITH_KIDS: Final = 3.0
WALK_KMH_ALONE: Final = 4.5
METRES_PER_KM: Final = 1000
MINUTES_PER_HOUR: Final = 60
YOUR_LOCATION: Final = "Your location"
# The daylight pages make no weather promise (BACKEND-CONTRACT section 1).
DAYLIGHT_CODES: Final[frozenset[ErrorCode]] = frozenset(
    {ErrorCode.DAYLIGHT_NIGHT, ErrorCode.DAYLIGHT_TOO_SHORT}
)
# Stage names for the counters (ARCHITECTURE section 14): counts only, never answers.
STAGE_DONE: Final = "stage_done"
# A call cancelled at its stage deadline (ARCHITECTURE section 4: Generating -> Cancelling).
STAGE_TIMEOUT: Final = "stage_timeout"

type AllowanceOutcome = Literal["reserved", "limit_reached", "unavailable"]
type ModelStage = Callable[[tuple[Pair, ...], str | None, float], Awaitable[Outcome[RawSelection]]]


class Allowance(Protocol):
    """The hosted daily run allowance (DEPLOYMENT section 2.3), charged once per run."""

    async def reserve(self, now: datetime) -> AllowanceOutcome: ...


@dataclass(frozen=True, slots=True)
class Ports:
    """Everything the workflow calls. The cached wrappers are invisible (CONTRACTS 4.1)."""

    geocoder: Geocoder
    places: PlacesProvider
    weather: WeatherProvider
    catalogue: Catalogue
    clock: Clock
    counters: Counters
    allowance: Allowance | None = None
    # One model call per run, built and parsed by WP5; None means the labelled fallback.
    model: ModelStage | None = None


@dataclass(frozen=True, slots=True)
class Budgets:
    """Stage budgets inside the one deadline (settings: D32 split)."""

    geocode_s: float
    providers_s: float
    model_s: float


@dataclass(frozen=True, slots=True)
class Run:
    """One admitted job: the answers, when it was admitted, and its absolute deadline."""

    job_id: str
    answers: Answers
    planned_start: datetime
    deadline: float
    # Set when the location is already known: device coordinates, or a chosen candidate.
    origin: Coordinates | None = None
    label: str | None = None


@dataclass(frozen=True, slots=True)
class LocationChoiceNeeded:
    """An ambiguous place: the job ends here and the person picks (BACKEND-CONTRACT 3)."""

    result: PlanResult
    candidates: tuple[LocationCandidate, ...]


type Planned = PlanResult | LocationChoiceNeeded


@dataclass(frozen=True, slots=True)
class _Located:
    origin: Coordinates
    label: str


@dataclass(frozen=True, slots=True)
class _Evaluated:
    """Valid weather and the pure rules, applied to one run."""

    samples: Samples
    summary: WeatherSummary
    constraints: Constraints
    conditions: Conditions
    activities: tuple[Activity, ...]


# --- The workflow -----------------------------------------------------------------------


async def plan_outing(ports: Ports, run: Run, budgets: Budgets) -> Planned:
    """Run one job to its terminal result."""
    if answers_outcome(run.answers) is not None:
        return _failed(ports, run, ErrorCode.INPUT_INVALID)
    located = await _locate(ports, run, budgets)
    if not isinstance(located, _Located):
        return located
    return await _plan_from(ports, run, budgets, located)


async def _plan_from(ports: Ports, run: Run, budgets: Budgets, located: _Located) -> PlanResult:
    """Run the expensive stage and everything after it, once the location is known."""
    summary = _summary(run.answers, located)
    charged = await _charge(ports)
    if charged is not None:
        return _failed(ports, run, charged, summary)
    places, weather = await _fetch(ports, run, located, budgets)
    evaluated = _evaluate(ports, run, located, weather)
    if not isinstance(evaluated, _Evaluated):
        return _failed(ports, run, evaluated, summary)
    if not evaluated.activities:
        return _failed(ports, run, ErrorCode.NO_MATCHES, summary, evaluated.summary)
    pairs = _pairs(ports, located, places, evaluated)
    if not pairs:
        code = ErrorCode.PLACES_UNAVAILABLE if _unavailable(places) else ErrorCode.NO_MATCHES
        return _failed(ports, run, code, summary, evaluated.summary)
    return await _choose(ports, run, budgets, summary, evaluated, pairs, places)


# --- Location -------------------------------------------------------------------------


async def _locate(ports: Ports, run: Run, budgets: Budgets) -> _Located | Planned:
    if run.origin is not None:
        return _Located(origin=run.origin, label=run.label or YOUR_LOCATION)
    location = run.answers.location
    if isinstance(location, Coordinates):
        # CC-004: a "Change answers" form carries the earlier label with its coordinates.
        label = run.label or run.answers.location_label or YOUR_LOCATION
        return _Located(origin=location, label=label)
    deadline = _stage_deadline(ports, run, budgets.geocode_s)
    found = await _bounded(
        ports, "geocode", partial(ports.geocoder.resolve, location, deadline), deadline
    )
    ports.counters.incr(STAGE_DONE, "geocode")
    return _from_hits(ports, run, found)


def _from_hits(ports: Ports, run: Run, found: Outcome[GeocodeHits]) -> _Located | Planned:
    if isinstance(found, Empty):
        return _failed(ports, run, ErrorCode.LOCATION_NOT_FOUND)
    if not isinstance(found, Ok):
        return _failed(ports, run, ErrorCode.GEOCODER_UNAVAILABLE)
    hits = _distinct(found.value.hits)
    if not hits:
        return _failed(ports, run, ErrorCode.LOCATION_NOT_FOUND)
    if len(hits) == 1:
        return _Located(origin=hits[0].coords, label=hits[0].label)
    return _choice(ports, run, hits)


def _distinct(hits: tuple[GeocodeHit, ...]) -> tuple[GeocodeHit, ...]:
    """Keep hits a person could tell apart: one per label and one per rounded point."""
    seen_labels: set[str] = set()
    seen_points: set[Coordinates] = set()
    kept: list[GeocodeHit] = []
    for hit in hits:
        if hit.label in seen_labels or hit.coords in seen_points:
            continue
        seen_labels.add(hit.label)
        seen_points.add(hit.coords)
        kept.append(hit)
    return tuple(kept[:MAX_CANDIDATES])


def _choice(ports: Ports, run: Run, hits: tuple[GeocodeHit, ...]) -> LocationChoiceNeeded:
    candidates = tuple(
        LocationCandidate(candidate_id=_new_id(), label=hit.label, coords=hit.coords)
        for hit in hits
    )
    result = replace(
        _base(ports, run, typed_summary(run.answers)),
        state=JobState.NEEDS_LOCATION_CHOICE,
        error=ErrorCode.LOCATION_AMBIGUOUS,
    )
    return LocationChoiceNeeded(result=result, candidates=candidates)


# --- Allowance, places and weather ------------------------------------------------------


async def _charge(ports: Ports) -> ErrorCode | None:
    """Reserve the hosted daily run, once, just before the expensive stage."""
    if ports.allowance is None:
        return None
    reserved = await ports.allowance.reserve(_now(ports))
    if reserved == "reserved":
        return None
    if reserved == "limit_reached":
        return ErrorCode.SERVICE_LIMIT_REACHED
    return ErrorCode.SERVICE_UNAVAILABLE


async def _fetch(
    ports: Ports, run: Run, located: _Located, budgets: Budgets
) -> tuple[Outcome[tuple[Place, ...]], Outcome[WeatherWindow]]:
    """Fetch places and weather concurrently, each on the same bounded stage deadline."""
    deadline = _stage_deadline(ports, run, budgets.providers_s)
    window = constraints(run.answers, run.planned_start).window
    # Each call is bounded on its own, so a hanging weather call cannot lose the places.
    places, weather = await asyncio.gather(
        _bounded(
            ports,
            "places",
            partial(
                ports.places.nearby,
                located.origin,
                radius_m(run.answers),
                place_kinds(ports.catalogue.activities()),
                deadline,
            ),
            deadline,
        ),
        _bounded(
            ports,
            "weather",
            partial(ports.weather.window, located.origin, window.start, window.end, deadline),
            deadline,
        ),
    )
    ports.counters.incr(STAGE_DONE, "weather_places")
    return places, weather


def radius_m(answers: Answers) -> int:
    """Reach as far as the outing can walk out and back in half the budget, bounded."""
    speed = WALK_KMH_WITH_KIDS if answers.who is Who.KIDS else WALK_KMH_ALONE
    half_budget_h = answers.time_budget.value / 2 / MINUTES_PER_HOUR
    return max(MIN_RADIUS_M, min(MAX_RADIUS_M, round(speed * METRES_PER_KM * half_budget_h)))


def place_kinds(activities: tuple[Activity, ...]) -> frozenset[str]:
    """Return every concrete place kind the catalogue can use (`any` is not a query)."""
    return frozenset(
        kind for activity in activities for kind in activity.place_kinds if kind != ANY_PLACE_KIND
    )


# --- The pure rules, in contract order ---------------------------------------------------


def _evaluate(
    ports: Ports, run: Run, located: _Located, weather: Outcome[WeatherWindow]
) -> _Evaluated | ErrorCode:
    if not isinstance(weather, Ok):
        return ErrorCode.WEATHER_UNAVAILABLE
    window = weather.value
    rules = constraints(run.answers, run.planned_start)
    samples = used_samples(window, rules.window)
    if samples is None or _now(ports) - window.fetched_at >= WEATHER_USABLE_FOR:
        return ErrorCode.WEATHER_UNAVAILABLE
    if rules.with_kids:
        # The family daylight rule decides the run before any activity is checked, and
        # before the severe and heat rules (BACKEND-CONTRACT section 1).
        blocked = daylight_outcome(rules.window, window.sunrise, window.sunset)
        if blocked is not None:
            return blocked
    restricted = run_weather_outcome(samples, with_kids=rules.with_kids)
    if restricted is not None:
        return restricted
    conditions = Conditions(
        samples=samples,
        local_date=_local_date(run.planned_start, window.tz),
        lat=located.origin.lat,
        in_daylight=is_in_daylight(rules.window, window.sunrise, window.sunset),
    )
    return _Evaluated(
        samples=samples,
        summary=summarise(window, rules.window, samples),
        constraints=rules,
        conditions=conditions,
        activities=eligible(ports.catalogue.activities(), rules, conditions),
    )


def _local_date(moment: datetime, tz: str) -> date:
    zone: tzinfo
    try:
        zone = ZoneInfo(tz)
    except ZoneInfoNotFoundError, ValueError:
        zone = UTC
    return moment.astimezone(zone).date()


def _pairs(
    ports: Ports,
    located: _Located,
    places: Outcome[tuple[Place, ...]],
    evaluated: _Evaluated,
) -> tuple[Pair, ...]:
    found = places.value if isinstance(places, Ok) else ()
    plan = PairPlan(
        origin=located.origin,
        budget_min=evaluated.constraints.budget_min,
        with_kids=evaluated.constraints.with_kids,
        prefer_step_free=evaluated.constraints.prefer_step_free,
    )
    candidates = pair_candidates(evaluated.activities, found, plan)
    context = ReasonContext(
        budget_min=evaluated.constraints.budget_min,
        energy=evaluated.constraints.energy,
        age_bands=evaluated.constraints.age_bands,
        samples=evaluated.samples,
        local_date=evaluated.conditions.local_date,
        lat=located.origin.lat,
    )

    def reasons(candidate: PairCandidate) -> frozenset[str]:
        return allowed_reason_ids(candidate, context)

    return to_pairs(candidates, ports.catalogue.hooks(), _new_id, reasons)


def _unavailable(places: Outcome[tuple[Place, ...]]) -> bool:
    return not isinstance(places, Ok | Empty)


# --- Choosing: one model call, or the labelled fallback ---------------------------------


async def _choose(  # noqa: PLR0913, PLR0917
    ports: Ports,
    run: Run,
    budgets: Budgets,
    summary: AnswersSummary,
    evaluated: _Evaluated,
    pairs: tuple[Pair, ...],
    places: Outcome[tuple[Place, ...]],
) -> PlanResult:
    by_id = {activity.activity_id: activity for activity in ports.catalogue.activities()}
    interests = _no_model_interests(run.answers.interest_text)
    chosen: tuple[Idea, ...] = ()
    if ports.model is not None:
        chosen, interests = await _ask_model(ports, run, budgets, pairs, interests)
    source = Source.MODEL if chosen else Source.FALLBACK
    if not chosen:
        inputs = RankingInputs(
            activities=by_id,
            energy=run.answers.energy,
            tags=interests.tags if interests is not None else (),
        )
        chosen = fallback_ideas(pairs, inputs, ports.catalogue)
    notices = result_notices(
        chosen, by_id, run.answers.energy, interests, fallback=source is Source.FALLBACK
    )
    places_down = _unavailable(places)
    if places_down:
        notices = (ErrorCode.PLACES_UNAVAILABLE, *notices)
    created = _now(ports)
    valid_until = min(
        created + VALID_AFTER_CREATION,
        evaluated.summary.fetched_at + WEATHER_USABLE_FOR,
        run.planned_start + VALID_AFTER_START,
    )
    return replace(
        _base(ports, run, summary, created=created),
        state=JobState.COMPLETE if source is Source.MODEL else JobState.FALLBACK,
        source=source,
        ideas=chosen,
        notices=notices,
        interests=interests,
        weather=evaluated.summary,
        valid_until=valid_until,
        retain_until=valid_until + RETAIN_AFTER_VALID,
        error=ErrorCode.PLACES_UNAVAILABLE if places_down else None,
    )


async def _ask_model(
    ports: Ports,
    run: Run,
    budgets: Budgets,
    pairs: tuple[Pair, ...],
    interests: Interests | None,
) -> tuple[tuple[Idea, ...], Interests | None]:
    """Make exactly one call per run, validated once, never repaired (D44)."""
    model = ports.model
    if model is None:
        return (), interests
    text = run.answers.interest_text
    deadline = _stage_deadline(ports, run, budgets.model_s)
    raw = await _bounded(ports, "choosing", partial(model, pairs, text, deadline), deadline)
    ports.counters.incr(STAGE_DONE, "choosing")
    if not isinstance(raw, Ok):
        return (), interests
    selection = parse_selection(raw.value.payload, pairs)
    if selection is None:
        return (), interests
    by_pair = {pair.pair_id: pair for pair in pairs}
    ideas = tuple(
        Idea(pair=by_pair[pick.pair_id], hook_id=pick.hook_id, reason_ids=pick.reason_ids)
        for pick in selection.picks
    )
    return ideas, (selection.interests if text else interests)


def _no_model_interests(text: str | None) -> Interests | None:
    """Report text that was given but not interpreted, when no model ran (PRODUCT-FIT 3.4)."""
    if not text:
        return None
    return Interests(tags=(), outcome=InterestOutcome.NOT_APPLIED)


# --- Results --------------------------------------------------------------------------


def _base(
    ports: Ports, run: Run, summary: AnswersSummary, created: datetime | None = None
) -> PlanResult:
    created = created or _now(ports)
    window = constraints(run.answers, run.planned_start).window
    valid_until = min(created + VALID_AFTER_CREATION, run.planned_start + VALID_AFTER_START)
    return PlanResult(
        job_id=run.job_id,
        state=JobState.UNAVAILABLE,
        source=Source.FALLBACK,
        ideas=(),
        notices=(),
        interests=None,
        answers=summary,
        weather=None,
        planned_start=run.planned_start,
        planned_end=window.end,
        valid_until=valid_until,
        retain_until=valid_until + RETAIN_AFTER_VALID,
        error=None,
    )


def _failed(
    ports: Ports,
    run: Run,
    code: ErrorCode,
    summary: AnswersSummary | None = None,
    weather: WeatherSummary | None = None,
) -> PlanResult:
    """Build an evaluated or unavailable outcome: no ideas, no fallback label, the code."""
    return replace(
        _base(ports, run, summary or typed_summary(run.answers)),
        weather=None if code in DAYLIGHT_CODES else weather,
        error=code,
    )


def _summary(answers: Answers, located: _Located) -> AnswersSummary:
    return AnswersSummary(
        who=answers.who,
        age_bands=answers.age_bands,
        time_budget=answers.time_budget,
        energy=answers.energy,
        location=located.origin,
        location_label=located.label,
        stroller=answers.stroller,
        step_free=answers.step_free,
    )


def typed_summary(answers: Answers) -> AnswersSummary:
    """Summarise answers before (or without) a location: the typed text as the label."""
    location = answers.location
    if isinstance(location, Coordinates):
        label = answers.location_label or YOUR_LOCATION
        return _summary(answers, _Located(origin=location, label=label))
    return _summary(answers, _Located(origin=Coordinates(lat=0.0, lon=0.0), label=location.text))


# --- Small helpers ----------------------------------------------------------------------


def _now(ports: Ports) -> datetime:
    now = ports.clock.now()
    return now if now.tzinfo is not None else now.replace(tzinfo=UTC)


def _stage_deadline(ports: Ports, run: Run, budget_s: float) -> float:
    """Give each stage only the remaining budget, capped at its own share."""
    return min(run.deadline, ports.clock.monotonic() + budget_s)


async def _bounded[T](
    ports: Ports, stage: str, call: Callable[[], Awaitable[Outcome[T]]], deadline: float
) -> Outcome[T]:
    """Run one provider or model call, cancelling it at the stage deadline.

    Adapters bound themselves; this is the outer guard (ARCHITECTURE section 4) so that
    a call that overruns its own bound is cancelled rather than the deadline missed.
    The cancelled call answers like a transport failure and the run goes on to its
    labelled fallback or its honest unavailable page. A cancellation from outside
    (shutdown) is not a timeout and propagates. The call is created inside the guard,
    so a job cancelled before this point leaves no coroutine behind.
    """
    remaining = deadline - ports.clock.monotonic()
    try:
        async with asyncio.timeout(max(0.0, remaining)):
            return await call()
    except TimeoutError:
        ports.counters.incr(STAGE_TIMEOUT, stage)
        return TransportFailure()


def _new_id() -> str:
    return secrets.token_urlsafe(ID_BYTES)
