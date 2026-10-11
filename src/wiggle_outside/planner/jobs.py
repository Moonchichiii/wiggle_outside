"""Job registry, idempotency, admission and lifecycle (ARCHITECTURE section 4).

`Planner` is the PlannerService the web layer depends on (CONTRACTS section 4.2). It owns
the jobs: one running task per admitted key, bounded admission, same key and same
fingerprint joins while a different fingerprint is a Conflict, ownership failures that
look like unknown IDs, immutable results kept until `retain_until`, and the one
candidate set a session may hold for an ambiguous place (BACKEND-CONTRACT sections 2-4).

Everything lives in process memory for the documented lifecycle and nowhere else.
"""

import asyncio
import contextlib
import hashlib
import logging
import secrets
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import (
    Answers,
    Coordinates,
    JobState,
    LocationCandidate,
    LocationCandidates,
    PlanResult,
    Source,
)
from wiggle_outside.planner.plan_outing import (
    Budgets,
    LocationChoiceNeeded,
    Ports,
    Run,
    plan_outing,
    typed_summary,
)
from wiggle_outside.planner.ports import Busy, Conflict, JobRef, NotFound

if TYPE_CHECKING:
    from collections.abc import Callable

log = logging.getLogger(__name__)

ID_BYTES: Final = 16
CANDIDATES_TTL: Final = timedelta(minutes=10)
# BACKEND-CONTRACT section 10: cancel owned tasks at shutdown and wait at most 5 s.
SHUTDOWN_WAIT_S: Final = 5.0
# A running job's placeholder is never rendered; it only tells the web layer to wait.
RUNNING_RETENTION: Final = timedelta(hours=1)
# ARCHITECTURE section 4: the serialised result cap. A result over it is never stored.
RESULT_CAP_BYTES: Final = 32 * 1024
# The workflow bounds every stage at its deadline; this guard is the last resort if it
# did not, so no job can outlive its deadline by more than this.
DEADLINE_GRACE_S: Final = 1.0

type PublishCandidates = Callable[[str, LocationCandidates], None]


@dataclass(frozen=True, slots=True)
class Limits:
    """BACKEND-CONTRACT section 4, starting values. One active job per session always."""

    active_global: int = 5
    terminal_records: int = 100


DEFAULT_LIMITS: Final = Limits()


def submission_fingerprint(answers: Answers) -> str:
    """Discriminate two submissions, interest text included (CONTRACTS section 7).

    `Answers.interest_text` is excluded from repr, hash and comparison so it cannot leak,
    so a plain repr would make two submissions that differ only in their interests look
    the same. The web layer compares the HMAC fingerprint of the canonical form before
    calling; this is the registry's own check over the answers it was handed.

    A SHA-256 digest, never the canonical text itself (TC-011, privacy fix): the
    fingerprint lives in the registry until `retain_until`, and the contract says the raw
    interest text is discarded once the job has run. The registry has no secret of its
    own, so this is a plain digest, not an HMAC; it is compared in memory only and never
    stored, rendered or logged.
    """
    canonical = repr(
        (
            answers.who,
            sorted(answers.age_bands),
            answers.time_budget,
            answers.energy,
            answers.location,
            answers.stroller,
            answers.step_free,
            answers.interest_text,
            answers.location_label,
        )
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def serialized_size(result: PlanResult) -> int:
    """Measure a result as the bytes of its canonical repr (the one serialisation)."""
    return len(repr(result).encode("utf-8"))


@dataclass(slots=True)
class _Job:
    job_id: str
    session_id: str
    key: str
    fingerprint: str
    placeholder: PlanResult
    done: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None
    result: PlanResult | None = None

    @property
    def active(self) -> bool:
        return self.result is None


@dataclass(slots=True)
class _CandidateSet:
    job_id: str
    candidates: LocationCandidates


class Planner:
    """PlannerService over the plan_outing workflow."""

    def __init__(
        self,
        ports: Ports,
        budgets: Budgets,
        *,
        deadline_s: float,
        publish_candidates: PublishCandidates | None = None,
        limits: Limits = DEFAULT_LIMITS,
    ) -> None:
        self._ports = ports
        self._budgets = budgets
        self._deadline_s = deadline_s
        self._publish = publish_candidates
        self._limits = limits
        self._jobs: dict[str, _Job] = {}
        self._by_key: dict[tuple[str, str], str] = {}
        self._candidates: dict[str, _CandidateSet] = {}

    # --- PlannerService -------------------------------------------------------------

    async def start_or_join(self, session_id: str, key: str, answers: Answers) -> JobRef:
        self.sweep()
        fingerprint = submission_fingerprint(answers)
        joined = self._join(session_id, key, fingerprint)
        if joined is not None:
            return joined
        self._admit(session_id)
        job = self._start(session_id, key, fingerprint, answers, origin=None, label=None)
        return JobRef(job_id=job.job_id, joined=False)

    async def choose_location(self, session_id: str, candidate_id: str) -> JobRef:
        self.sweep()
        held = self._candidates.get(session_id)
        if held is None:
            raise NotFound
        candidate = _candidate(held, candidate_id)
        if candidate is None:
            raise NotFound
        if candidate.job_id is not None:
            # Idempotent per candidate: the same owned candidate returns the same job
            # until that job's retain_until (BACKEND-CONTRACT section 3).
            if candidate.job_id in self._jobs:
                return JobRef(job_id=candidate.job_id, joined=True)
            raise NotFound
        if held.candidates.expires_at <= self._now():
            raise NotFound
        self._admit(session_id)
        job = self._start(
            session_id,
            f"candidate:{candidate_id}",
            candidate_id,
            held.candidates.answers,
            origin=candidate.coords,
            label=candidate.label,
        )
        held.candidates = _consume(held.candidates, candidate_id, job.job_id)
        return JobRef(job_id=job.job_id, joined=False)

    async def wait(self, session_id: str, job_id: str) -> PlanResult:
        job = self._owned(session_id, job_id)
        if job is None:
            raise NotFound
        await job.done.wait()
        if job.result is None or self._jobs.get(job_id) is not job:
            raise NotFound  # removed while waiting
        return job.result

    def get(self, session_id: str, job_id: str) -> PlanResult | None:
        self.sweep()
        job = self._owned(session_id, job_id)
        if job is None:
            return None
        return job.result if job.result is not None else job.placeholder

    # --- Lifecycle ----------------------------------------------------------------------

    def forget_session(self, session_id: str) -> None:
        """Remove everything a session owned, together (BACKEND-CONTRACT section 2)."""
        for job_id, job in tuple(self._jobs.items()):
            if job.session_id == session_id:
                self._remove(job_id)
        self._candidates.pop(session_id, None)

    def sweep(self) -> None:
        """Remove results past `retain_until` and candidate sets past their TTL."""
        now = self._now()
        for job_id, job in tuple(self._jobs.items()):
            if job.result is not None and job.result.retain_until <= now:
                self._remove(job_id)
        for session_id, held in tuple(self._candidates.items()):
            if held.candidates.expires_at <= now:
                self._expire_candidates(session_id, held)

    def _expire_candidates(self, session_id: str, held: _CandidateSet) -> None:
        """Drop the unconsumed entries and the set's answers; a consumed entry lives on.

        It lives until its job's retain_until (BACKEND-CONTRACT section 3).
        """
        consumed = tuple(c for c in held.candidates.candidates if c.job_id in self._jobs)
        if not consumed:
            del self._candidates[session_id]
        elif len(consumed) != len(held.candidates.candidates):
            held.candidates = replace(held.candidates, candidates=consumed)

    def active_jobs(self) -> int:
        return sum(1 for job in self._jobs.values() if job.active)

    async def close(self) -> None:
        """Cancel owned work at shutdown and wait a bounded time for it to stop."""
        tasks = [job.task for job in self._jobs.values() if job.task is not None and job.active]
        for task in tasks:
            task.cancel()
        if tasks:
            with contextlib.suppress(TimeoutError):
                async with asyncio.timeout(SHUTDOWN_WAIT_S):
                    await asyncio.gather(*tasks, return_exceptions=True)

    # --- Internals ----------------------------------------------------------------------

    def _join(self, session_id: str, key: str, fingerprint: str) -> JobRef | None:
        job_id = self._by_key.get((session_id, key))
        if job_id is None:
            return None
        job = self._jobs.get(job_id)
        if job is None:
            del self._by_key[(session_id, key)]
            return None
        if job.fingerprint != fingerprint:
            raise Conflict  # same key, different answers (CONTRACTS section 7)
        return JobRef(job_id=job_id, joined=True)

    def _admit(self, session_id: str) -> None:
        active = [job for job in self._jobs.values() if job.active]
        if any(job.session_id == session_id for job in active):
            raise Busy(retry_after_s=None)  # the web links to the active result
        if len(active) >= self._limits.active_global:
            raise Busy(retry_after_s=self._deadline_s)
        if self._terminal_count() >= self._limits.terminal_records:
            self._evict_terminal()
        if self._terminal_count() >= self._limits.terminal_records:
            raise Busy(retry_after_s=None)  # bounded storage cannot take another record

    def _terminal_count(self) -> int:
        return sum(1 for job in self._jobs.values() if not job.active)

    def _evict_terminal(self) -> None:
        """Evict results past `valid_until` first, oldest first; never active work."""
        now = self._now()
        # A stable sort over insertion order: equal validity evicts the older record.
        stale = sorted(
            (
                job
                for job in self._jobs.values()
                if job.result is not None and job.result.valid_until <= now
            ),
            key=lambda job: job.result.valid_until if job.result is not None else now,
        )
        excess = self._terminal_count() - self._limits.terminal_records + 1
        for job in stale[: max(1, excess)]:
            self._remove(job.job_id)

    def _start(  # noqa: PLR0913, PLR0917
        self,
        session_id: str,
        key: str,
        fingerprint: str,
        answers: Answers,
        origin: Coordinates | None,
        label: str | None,
    ) -> _Job:
        planned_start = self._now()
        job_id = secrets.token_urlsafe(ID_BYTES)
        run = Run(
            job_id=job_id,
            answers=answers,
            planned_start=planned_start,
            deadline=self._ports.clock.monotonic() + self._deadline_s,
            origin=origin,
            label=label,
        )
        job = _Job(
            job_id=job_id,
            session_id=session_id,
            key=key,
            fingerprint=fingerprint,
            placeholder=_placeholder(run),
        )
        self._jobs[job_id] = job
        self._by_key[(session_id, key)] = job_id
        job.task = asyncio.create_task(self._run(job, run), name=f"wo-plan-{job_id[:8]}")
        return job

    async def _run(self, job: _Job, run: Run) -> None:
        started = self._ports.clock.monotonic()
        grace = max(0.0, run.deadline - started) + DEADLINE_GRACE_S
        try:
            async with asyncio.timeout(grace):
                planned = await plan_outing(self._ports, run, self._budgets)
        except TimeoutError:
            log.error("job %s overran its deadline and was cancelled", job.job_id[:8])  # noqa: TRY400  no traceback wanted
            self._finish(job, _failed(job.placeholder), started)
            return
        except asyncio.CancelledError:
            self._finish(job, _failed(job.placeholder), started)
            raise
        except Exception:
            log.exception("job %s failed", job.job_id[:8])
            self._finish(job, _failed(job.placeholder), started)
            return
        if isinstance(planned, LocationChoiceNeeded):
            self._hold_candidates(job, run, planned)
            self._finish(job, planned.result, started)
            return
        self._finish(job, planned, started)

    def _finish(self, job: _Job, result: PlanResult, started: float) -> None:
        _finish(job, result)
        # TC-011: one operator line per search. Names, counts and timings only: never
        # the answers, the interest text or coordinates (PLAN section 5).
        done = job.result if job.result is not None else result
        log.info(
            "job %s finished: state=%s source=%s ideas=%d error=%s elapsed=%.2fs",
            job.job_id[:8],
            done.state.value,
            done.source.value,
            len(done.ideas),
            done.error.value if done.error is not None else "-",
            self._ports.clock.monotonic() - started,
        )

    def _hold_candidates(self, job: _Job, run: Run, planned: LocationChoiceNeeded) -> None:
        held = LocationCandidates(
            candidates=planned.candidates,
            answers=run.answers,
            expires_at=self._now() + CANDIDATES_TTL,
        )
        # One set per session: the newest replaces the older one (BACKEND-CONTRACT 4).
        self._candidates[job.session_id] = _CandidateSet(job_id=job.job_id, candidates=held)
        if self._publish is not None:
            self._publish(job.session_id, held)

    def _owned(self, session_id: str, job_id: str) -> _Job | None:
        job = self._jobs.get(job_id)
        if job is None or job.session_id != session_id:
            return None  # an ownership failure looks like an unknown ID (CONTRACTS 3)
        return job

    def _remove(self, job_id: str) -> None:
        job = self._jobs.pop(job_id, None)
        if job is None:
            return
        self._by_key.pop((job.session_id, job.key), None)
        if job.task is not None and not job.task.done():
            job.task.cancel()
        job.done.set()

    def _now(self) -> datetime:
        now = self._ports.clock.now()
        return now if now.tzinfo is not None else now.replace(tzinfo=UTC)


def _candidate(held: _CandidateSet, candidate_id: str) -> LocationCandidate | None:
    return next((c for c in held.candidates.candidates if c.candidate_id == candidate_id), None)


def _consume(held: LocationCandidates, candidate_id: str, job_id: str) -> LocationCandidates:
    return replace(
        held,
        candidates=tuple(
            replace(c, job_id=job_id) if c.candidate_id == candidate_id else c
            for c in held.candidates
        ),
    )


def _finish(job: _Job, result: PlanResult) -> None:
    if serialized_size(result) > RESULT_CAP_BYTES:
        # Bounded storage never takes an oversized record (ARCHITECTURE section 4).
        log.error("job %s produced a result over %d bytes", job.job_id[:8], RESULT_CAP_BYTES)
        result = _failed(job.placeholder)
    job.result = result
    job.done.set()


def _placeholder(run: Run) -> PlanResult:
    """Build what `get` returns while the job runs. Never rendered: the web layer waits."""
    summary = typed_summary(run.answers)
    if run.origin is not None:
        summary = replace(summary, location=run.origin, location_label=run.label or "")
    end = run.planned_start + timedelta(minutes=run.answers.time_budget.value)
    return PlanResult(
        job_id=run.job_id,
        state=JobState.RUNNING,
        source=Source.FALLBACK,
        ideas=(),
        notices=(),
        interests=None,
        answers=summary,
        weather=None,
        planned_start=run.planned_start,
        planned_end=end,
        valid_until=run.planned_start + RUNNING_RETENTION,
        retain_until=run.planned_start + RUNNING_RETENTION,
        error=None,
    )


def _failed(placeholder: PlanResult) -> PlanResult:
    """Build the result of an unexpected exception or a cancellation: a safe message only."""
    return replace(placeholder, state=JobState.FAILED, error=ErrorCode.UNEXPECTED_FAILURE)
