# Purpose-and-simplicity review — round 8.13

Status: DRAFT, 10 October 2026.

## Current state (binding for agents)

The owning documents (PLAN §0 decisions, BACKEND-CONTRACT, CONTRACTS, ARCHITECTURE)
already contain everything below; this section only summarises what changed.

### Decisions (Mats, round 8.11)

| Proposal | Decision | Recorded as |
|---|---|---|
| S1 progress stream and Stop | Accepted, with internal cancellation, cleanup, deadlines, duplicate protection and lost-response recovery kept; no polling | D43 |
| S3 repair attempt | Accepted; partial success kept; frequent invalid output is investigated, not hidden | D44 |
| S5 single flight and negative cache | **Rejected**; D33 kept in full, compactly in the provider wrapper | D45 |
| S7 re-sort | Accepted: display-only labels, resubmission through "Change answers", immutable results | D46 |
| S2, S4, S6 | Closed in 8.13 as routine engineering: keep the job states, cache and protocols as currently specified (no churn); revisit only with evidence | closed |

| Kind | Removed in 8.11 |
|---|---|
| Endpoints | `GET /results/{job_id}/events` (SSE), `POST /results/{job_id}/cancel`, `POST /results/{job_id}/interests` |
| Modules and templates | `web/events.py` (SSE encoding), `partials/progress.html`; the interests partial becomes plain labels |
| Planner interface | `PlannerService.observe`, `.cancel`, `.resort`; `PlannerEvent`; the per-job event buffer |
| Types and copy | `ProgressView`, `ChipView`, `IdeaSnapshot`; `Source.RESORTED`; job state `CANCELLED`; notices `RESORTED`, `NOT_IN_CURRENT_LIST`; error codes `PROGRESS_DISCONNECTED`, `JOB_CANCEL_REQUESTED`, `JOB_CANCELLED` marked "not in v1" |
| Forms | cancel and interests forms |
| Resource bounds | SSE subscribers (2 per session, 20 global), event buffer (16 per job), up to 12 idea snapshots per result |
| Behaviour | model repair attempt and the `Generating → Generating` loop; stage progress messages; Stop; chip removal and re-sort |
| Browser dependency | the htmx `hx-sse` extension (htmx core stays) |
| Mock screens | `02b-waiting-long`, `04b-detail-not-current` |

Kept on purpose: the deadline, the bounded model queue, internal cancellation and
cleanup at deadline and shutdown, model-slot ownership until inference ended or
cancellation is verified, duplicate-submission protection, lost-response recovery by
resubmission, single flight, the bounded negative cache, pacing and cooldowns (D45), and
the product scope and AI role. No Python runtime dependency changes.

## Historical review (round 8.10): background only, not instructions

This review checked every box and arrow in the ARCHITECTURE
diagrams (deployment §2, sequence §3, state §4, domain §5) and the CONTRACTS interfaces
against one test: **which requirement or concrete risk does it serve, and what would be
lost without it?** It traces the normal request and WALKTHROUGH.md through them.

Verdicts for S1, S3, S5 and S7 below show the decision Mats took in 8.11; where a 8.10
recommendation was rejected, the row says so. Agents follow the section above and the
owning documents, never a historical recommendation.

### Verdicts (updated with decisions)

| Component | Verdict | Requirement it serves, or reason |
|---|---|---|
| Plain form, POST then 303 then GET result | **Keep** | Core journey; works without JS; refresh never resubmits |
| Session, CSRF, origin check | **Keep** | Required security controls (D31) |
| Job registry with idempotency key, one active job per session | **Keep** | Double submits must not start a second model call (D33, mandatory) |
| Model slot, one generation at a time | **Keep** | One GPU; no overlapping inference |
| One absolute deadline | **Keep** | 20 s promise; every stage gets the remainder |
| Location candidates, one job per candidate | **Keep** | Never pick an ambiguous place silently; double clicks |
| Catalogue, hooks and reasons; Gemma picks IDs only | **Keep** | D4 safety boundary: no model text shown |
| Deterministic ranking (`core/ranking.py`) | **Keep** | Labelled fallback and the H1 baseline both need it |
| Provider gate: Nominatim pacing, cooldown on 429/503 | **Keep** | Provider policy; respecting `Retry-After` |
| Cache of geocode, places and weather | **Keep; table shape open** (S4) | Nominatim requires caching; the 30-day note promises it. One key/value table is enough |
| Places and weather in parallel | **Keep** | Latency budget. A weather failure wastes one places call, which is cheaper than serialising |
| Presenters plus view models | **Keep** | Escape once; WP7 and WP8 can build in parallel against fixtures |
| `PlannerService` and the three provider protocols | **Keep** | Real fakes in tests; parallel packages |
| `Catalogue` protocol | **Open** (S6) | Static data loaded once; a frozen value is enough |
| `Counters` protocol | **Open** (S6) | Duplicates the structured logs in ARCHITECTURE §10 |
| SSE progress, event buffer, subscriber limits, reconnects, the `/events` and `/cancel` routes, and the Stop button | **Removed** (S1 accepted → D43) | Shows stage messages and allows stopping. It is the largest optional machinery and already second on the PLAN §15 cut list |
| Job states `Waiting`, `Generating`, `Cancelling`, `Cancelled`, `Fallback` | **Open** (S2); `Cancelled` removed by D43 | Waiting and Generating only drive progress text; Fallback duplicates `source = fallback`; cancel states exist only for Stop |
| One model repair attempt | **Removed** (S3 accepted → D44) | Recovers some invalid outputs, but adds a second model call, a loop in the state machine and budget splitting. Schema-constrained output plus the labelled fallback may be enough; measure the invalid rate at the model smoke step |
| Single flight with waiter-cancellation rules | **Keep** (S5 rejected → D45; the 8.10 recommendation to remove it is withdrawn) | Guards against concurrent identical fetches. At 1 active job per session and 5 globally, plus the cache, that risk is small. It is the most intricate concurrency code in the plan |
| Negative cache, 60 s per key | **Keep** (S5 rejected → D45; written only after the final attempt) | The per-session rate limit (6/min), the global limit (30/min) and the provider cooldown already stop failure floods |
| `cached_*` wrappers in WP4 around WP3 adapters, four protocols | **Keep, compact** (D45: the controls stay together in the provider wrapper) | One shared policy helper (cache, gate, one retry) used by the three adapters removes cross-package coupling |
| D39 chip removal, re-sort, idea snapshots, `NOT_IN_CURRENT_LIST`, the interests route | **Removed** (S7 accepted → D46) | Lets parents drop a wrong tag without a model call. The reviewer accepted "explicit resubmission" as an alternative; with it, results are immutable and snapshots are unnecessary |
| Two model schemas, v1 and v2 | **Remove one after D39** | Keep only the one that matches the decision |
| D34 intent preloading | **Open** (recommend removing) | Optional; the form is one page |
| Replay demo routes `/examples` | **Decision needed** (D24) | Needed only if the public demo is replay |
| Quantisation comparison, pandas/Polars/DuckDB analysis | **Keep outside runtime, cut first** | Learning and evidence goals, not product; already on the cut list |
| Hermes build boundary in the deployment diagram | **Remove from this diagram** (done) | Workbench policy lives in HERMES-P0 since 8.8 |

### Trace findings (8.10)

1. **Normal request** (WALKTHROUGH steps 1–8): every call has a purpose. There is
   1 geocode, 1 places, 1 weather and 1 model call; the retry only happens after a
   transport failure.
2. **Duplicated state:** `JobState.FALLBACK` and `Source.FALLBACK` say the same thing
   (S2). `PlanResult.error` and the `Unavailable` state overlap; keep the error code and
   let the state be `Unavailable`.
3. **Retry owners:** after 8.9 there is one owner for provider retries, the wrapper.
   SSE reconnection is a second retry loop in the browser; it disappears with S1.
4. **Repeated transformations:** `Idea` → `IdeaSnapshot` → `IdeaView` exists only for
   the re-sort. With S7, it becomes `Idea` → `IdeaView`.
5. **Avoidable coupling:** WP4 wrapping WP3 through four protocols (S5); presenters
   needing a `Catalogue` protocol where a value would do (S6).
6. **Failure walkthrough** (steps 5b, 14–21): the states needed are Running,
   NeedsLocationChoice, Complete, Unavailable and Failed, plus removal at
   `retain_until`. The other five exist for Stop, progress text or the repair loop.

### Proposals as made in 8.10

| ID | Proposal | Amends | What is lost |
|---|---|---|---|
| S1 | v1 without SSE: htmx (or the plain form) posts and waits; the button shows "Finding outings…"; no Stop | ARCHITECTURE §4, CONTRACTS §5, DESIGN-SPEC §6, PLAN §15 cut list (moves SSE from "cut if behind" to "not in v1") | Stage messages and user cancellation. Closing the tab still detaches, and the deadline still bounds the work |
| S2 | Five job states: Running, NeedsLocationChoice, Complete (with `source`), Unavailable, Failed; removal at `retain_until` is not a state | ARCHITECTURE §4, CONTRACTS §2 | Nothing user-visible, given S1 |
| S3 | No repair attempt: an invalid model output goes straight to the labelled fallback | D4 ("at most one repair"), BACKEND-CONTRACT §7 | Some recoverable outputs; revisit if the smoke test shows a high invalid rate |
| S4 | One SQLite key/value cache table (`key`, `payload`, `expires_at`), no feedback table in v1 | D6 scope, ARCHITECTURE §7, §15 | Optional feedback storage (already first on the cut list) |
| S5 | Remove single flight and the negative cache; one policy helper per adapter call: cache → gate → attempt → one retry → cache | D33 (mandatory, so Mats decides), BACKEND-CONTRACT §6, CONTRACTS §4.1 | Protection against concurrent identical fetches, which the job limits already make rare |
| S6 | `Catalogue` as a frozen value, no `Counters` protocol (logs instead) | CONTRACTS §4, §8 | Nothing |
| S7 | D39 chips are informational; changing interests is an explicit resubmission through "Change answers". No re-sort, snapshots or interests route; results are immutable | PRODUCT-FIT §3.5, CONTRACTS §2, §5, BACKEND-CONTRACT §2 | Removing a wrong tag without another model call |

If all seven are accepted, these disappear: three routes (`/events`, `/cancel`,
`/interests`), six of the eleven job states, the `SingleFlight`, `Counters` and
`Catalogue` protocols, the event stream, the repair loop and the snapshot store. Nothing
else goes with them: and no approved safety,
privacy, accessibility or honesty control is weakened. Each proposal can be accepted on
its own.

### Diagram consistency fixes applied in 8.10

- ARCHITECTURE §2: the Hermes build subgraph was removed from the application deployment
  diagram, with a pointer to HERMES-P0.
- ARCHITECTURE §5: the domain diagram uses the CONTRACTS names (`Answers`,
  `WeatherSummary`, `Activity`, `Place`, `Pair`, `Pick`, `Idea`, `PlanResult`) instead of
  the older `Weather`, `Destination`, `EligiblePair`, `ModelPick` and `Card`.

A diagram box does not require a class, module or service. After the decisions above,
the build should still map several boxes onto a few plain functions.
