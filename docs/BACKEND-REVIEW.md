# Touchgrass backend review — round 8.4 review candidate

Date: 10 October 2026, Europe/Stockholm. Reviewer: Codex.
Input: the updated round 8.3 ZIP delivered by Codex, with nine verified document checksums.
Scope: three document-review passes, not three independent reviewers or executed app tests.
No repository, application code, dependency installation or build approval is included.

## Verdict and authority

The architecture is viable, but the previous claim that only runtime proofs remain is too strong.
There are concrete contract gaps to close before backend implementation. This report supersedes
the readiness verdict in REVIEW-RESULT.md; it does not approve proposed decisions or change
the catalogue. The bundled round 8.3 documents remain the baseline for reconciliation.

Use this bounded findings list for the next revision. Do not add frameworks or redesign the
product. Fix repeated rules at their owning contract and reconcile summaries/diagrams. Mark a
finding text-resolved only when all affected documents agree; runtime evidence remains pending.

## What was checked

1. Correctness: quiz through geocoding, weather, places, eligibility, model validation, fallback,
   result reuse; catalogue and hook schemas and known edge cases.
2. Boundaries: sessions/CSRF, admission, task ownership, privacy, external data, model service,
   build and CI trust, audit and release order.
3. Consistency: decisions, prose, diagrams, error contract, runtime bounds and proof order.

Static checks completed: all nine input checksums pass; TOML parses; 28 unique activity IDs,
8 unique hook IDs, 7 unique reason IDs and one notice; ordered positive duration ranges;
all 28 generic_ok flags are booleans, five true. Hook placeholders are activity/distance/place.
These checks establish structural consistency, not suitability or safety of the activities.

## Findings and minimum fixes

### B01 — High: weather freshness contradicts the failure policy

Location: PLAN sections 2.2, 4 and 5; ARCHITECTURE sections 14–15.
Failure: a 45-minute-old forecast can pass PLAN's 60-minute rule but fail the 30-minute
cache contract. A result card still permits “weather not checked,” despite D16 forbidding it.
Fix: use the existing 30-minute policy as the single freshness limit, reject at expiry, and
remove the unchecked-weather recommendation-card alternative. Distinguish cache-fetch time,
forecast validity and any available model issue time; never invent a provider issue time.
Check: 29:59/30:00/30:01 age boundaries; every unavailable path produces zero model calls.
Blocks: backend contract lock. Owner: Claude reconciles; no weaker policy is proposed.

### B02 — High: forecast samples are not interchangeable time intervals

Location: PLAN sections 3/5; ARCHITECTURE sections 5/7; hooks dry_window.
Failure: an outing from 10:40–11:10 can miss rain if code checks only timestamps falling
inside that interval. Open-Meteo precipitation and probability describe the preceding hour;
is_day is an instantaneous value [S1]. A daylight sample is not proof of daylight throughout.
Fix: normalize times to aware UTC internally; define each variable's sample/interval mapping,
include every overlapping interval and required boundary sample. Define sunset handling
(daily sunrise/sunset in the same weather request, or a conservative documented bound).
Specify missing/null/non-finite values, unequal array lengths, unknown codes and missing units:
required uncertainty fails closed. Define rain_ok=false, max_rain_pct, min/max temperature
variables and severe-code sets as explicit predicates. “Half day” needs a numeric duration;
meteorological-season scope needs an equatorial boundary or explicit supported geography.
Check: partial hours, midnight, DST, sunset mid-outing, malformed arrays and each code/limit.
Blocks: eligibility implementation. Owner: Claude; product thresholds need Mats's review.

### B03 — High: result retention is not weather validity

Location: ARCHITECTURE sections 4/14/15; ERROR-HANDLING RESULT_EXPIRED.
Failure: a result created just before weather expiry can be redisplayed for five minutes
as current, although its weather has expired; a delayed start also changes the outing window.
Fix: retain the original planned start/end and derive valid_until from the stricter result
TTL and weather freshness/coverage. Reopening must not silently change “leave now.” Once
invalid, show an expired/historical card and require explicit new submission; no background
refetch. An already loaded/printed card stays readable with its original time context.
Check: result at forecast expiry minus one second; revisit across sunset/expiry; zero hidden calls.
Blocks: result lifecycle. Owner: Claude.

### B04 — High: ambiguous geocoding has no complete continuation contract

Location: ERROR-HANDLING LOCATION_AMBIGUOUS; ARCHITECTURE state machine/transport.
Failure: the person needs time to choose among five matches, but the only job has a 20-second
deadline. It is unclear whether selecting a match repeats geocoding or trusts client coordinates.
Fix: terminate the lookup as a needs-location-choice outcome. Keep a short-lived, session-owned
candidate set; selecting a valid candidate explicitly starts a new planning attempt with a new
key/deadline and reuses that candidate without another geocode. Reject tampered/expired IDs.
Bound candidate storage within the session budget. Support the same form flow without JS.
Check: deliberate 60-second human pause, forged candidate, expired choice, zero second geocode.
Blocks: backend journey contract. Owner: Claude; this is an implementation recommendation.

### B05 — High: bound the whole session and admission surface

Location: ARCHITECTURE sections 4/13.2; PLAN security table.
Failure: five admitted jobs and 100 terminal records do not bound sessions created by page
loads, SSE subscribers, pending SQLite submissions, or per-key fetch bookkeeping. New keys
also bypass duplicate suppression; deduplication is not rate limiting.
Fix: one resource table naming limits, expiry, owner and overflow response for sessions,
candidate sets, active jobs, terminal records, SSE subscribers/event buffers, provider in-flight
keys and DB queue. Rate-limit valid new submissions per session and globally before work;
use a global budget even when users can create new sessions. Reject overload without queuing
unbounded tasks. Review model context/output limits, not just wall-clock timeout.
Check: many sessions, distinct keys, subscriber floods and a stalled SQLite worker remain bounded.
Blocks: backend lock; exact capacities are proposed until load-tested. Owner: Claude/Mats.

### B06 — High: session security needs a complete endpoint contract

Location: D31; ARCHITECTURE section 13.2; PLAN section 9.
Failure: “Origin checked” leaves missing/null origins, proxy trust, cancellation, session expiry
and caching of CSRF-bearing HTML undefined.
Fix: exact configured allowed hosts/origins (including scheme/port), trusted proxy list, explicit
missing/null Origin handling with no automatic bypass, cryptographically random bounded tokens,
server expiry and ownership on every job/status/cancel endpoint. Never let GET initiate/cancel
work. Set private no-store on session/form/result/error/SSE responses; immutable public caching
only for appropriate static assets. Ensure fragments and full pages cannot cross-contaminate
through a proxy cache. Reject unknown client session IDs rather than adopting them. Decide how
multiple tabs and session expiry affect in-flight work. Keep localhost cookie proof pending.
Check: session A cannot read/cancel B, CSRF/referrer edge cases, forged Host/forwarding headers,
expired session and cached form replay. OWASP distinguishes missing origins from trusted ones [S2].
Blocks: web boundary implementation. Owner: Claude. No custom signing algorithm is requested.

### B07 — High: shared fetch deadlines and negative caching need ownership rules

Location: ARCHITECTURE sections 7/14/15.
Failure: inheriting the first waiter's timeout can cancel work for another user; an unbounded
cache-owned task can outlive all users. Per-key failure caching does not protect a provider
from thousands of different keys, and a fixed 60 seconds may conflict with Retry-After.
Fix: a provider fetch has one bounded deadline and bounded waiter set. Each waiter retains its
own deadline; joining never resets the fetch deadline. Detach independently, cancel when no
waiters remain, and always remove finished entries. Cancelled callers do not poison the cache.
Distinguish transport failures, valid empty results, malformed data and quota responses. Apply
provider-wide cooldown for 429/unavailability where appropriate, honoring Retry-After beyond
the per-key default; do not hold user requests during a long cooldown. Put coalescing/pacing
outside persistent-cache success so a disk failure cannot cause a request stampede.
Check: staggered callers, last waiter leaves, 429 with 120-second delay, disk failure, unique keys.
Blocks: caching implementation. Owner: Claude.

### B08 — High: model cancellation proof and endpoint permissions are incomplete

Location: REVIEW-RESULT R12; ARCHITECTURE sections 4/9; HERMES-P0 model connection.
Failure: ollama ps reports loaded models [S3], so a model remaining listed does not prove
inference is running or stopped. A port-only allowlist also permits more than generation.
Fix: demonstrate request completion/cancellation and no overlapping work using runtime evidence;
GPU utilization is corroboration only. Keep the existing fail-closed slot rule when uncertain.
Specify allowed model API methods/paths, fixed model digest, context/output bounds and queue
settings; deny management/pull/delete/arbitrary-model requests from the untrusted runner.
Use a constrained proxy or equivalently scoped isolated runtime; do not modify the shared
workbench service silently. Record how application shutdown deals with outstanding inference.
Check: cancel mid-generation then immediately submit; blocked model-management requests;
no automatic model downloads; runtime proof on the actual GPU. Blocks: model milestone.
Owner: Claude proposes mechanism; Mats supplies workbench inventory/approval.

### B09 — Medium: complete input and output validation, including pair diversity

Location: PLAN section 3/9; ARCHITECTURE dependency and HTTP contracts.
Fix: enumerate accepted content types, body/field limits before expensive parsing, unknown
fields, repeated scalar fields, finite coordinates, age-band combinations and parameterized
SQL. Reject uploaded files. Construct provider queries from bounded typed values, never raw
query-language input; disable redirects or validate every destination, retain TLS verification.
For model output: specify empty output, surplus fields, duplicate reasons and invalid-pick
policy (drop versus one repair versus whole fallback). Three different pairs can still be the
same activity at three parks: recommend unique activity IDs across cards; repeated destinations
may remain allowed. Preserve escaping after hook substitution and after validation failures.
Check: malformed/oversized/compressed upstream data, repeated form keys, hostile OSM labels,
extra JSON fields, duplicates and empty selections. Blocks: adapters/model validator.
Owner: Claude; unique-activity recommendation remains a product choice, not silently approved.

### B10 — Medium: source data does not prove free, open or accessible

Location: D2; PLAN sections 2/5; core destination eligibility.
Failure: a matching park kind can have fee=yes, access=private/no or known closure tags;
straight-line proximity does not prove an entrance or walkable route.
Fix: define explicit exclusion/unknown policies for fees, access, lifecycle and usable centre
coordinates. Exclude explicit incompatibility; do not present missing tags as verified free/open.
If verified-free admission is mandatory, unknown fees must fail that rule; Mats must choose
between verified-free-only and free-intended with explicit uncertainty. Stroller activity fit
must remain distinct from route/site accessibility. Keep travel estimates qualified and ensure
the shown duration fits the same total-time predicate used to qualify the pair.
Check: private/paid/closed destinations, missing tags, centroid across a river and stroller case.
Blocks: place contract. Owner: Claude, with Mats choosing unknown-fee policy.

### B11 — Medium: catalogue contracts need a small human reconciliation

Location: drafts/activities.toml, drafts/hooks.toml, PLAN sections 2/3.
Observed: shape-safari has a 15-minute minimum but its steps prescribe ten minutes then
another round. A 15-minute fit can therefore contradict its instructions. Leaf colour hunt
and stick houses move natural material while the shared preamble forbids moving it. Some
optional items have no stated alternative despite the all-items rule. The generic hook says
“wherever your walk takes you,” broader than the path/traffic rules. tree-twins says skip windy
days without a matching defined predicate. Five-senses permits darkness but lacks a lit-path
condition. These are content/contract inconsistencies, not a medical safety certification.
Fix: align minimum/maximum durations with literal steps; select either non-moving activities
or a precise shared-material rule; reconcile optional equipment, generic wording and wind/darkness
conditions. Define one selected duration if the displayed range exceeds the user's budget.
Evidence: all four child age bands share only picnic-adventure; ages 0–2 plus 6–9 have zero
generic activities. Honest no-results is correct; do not weaken age checks to fill the list.
Blocks: catalogue approval, not infrastructure. Owner: Claude drafts; Mats reviews every change.

### B12 — High: GitHub needs the same trust separation as the local build

Location: PLAN section 8; HERMES-P0; CLAUDE-REVIEW build track.
Failure: branch checks alone do not stop a PR weakening its own gate/configuration, and
least-privilege language alone does not isolate credentials from arbitrary build/test code.
Fix: map events, source refs, secrets, token permissions, runner type and artifact consumers.
No privileged pull_request_target job executes PR source; also inspect workflow_run consumers
and cache/artifact provenance [S4]. Do not run untrusted PRs on the workbench host. Define the
independent approved-gate check and protected-change approval mechanism, including solo-author
constraints and first-repository bootstrap. Required gate outcomes bind to the exact source
and approved gate version; a success uploaded by a changed gate is not sufficient evidence.
Check: a PR deleting tests/changing workflow or config cannot satisfy the approved policy;
untrusted builds lack deploy credentials and cannot contaminate the release artifact.
Blocks: CI/bootstrap. Owner: Claude; actual repository settings must later be demonstrated.

### B13 — High: image audit must bind to the artifact actually deployed

Location: ARCHITECTURE 13.3; PLAN release order; HERMES-P0 audit inputs.
Failure: all merge checks include Trivy image scanning, but the release image is built only
afterwards. The plan does not explicitly require scanning that new digest before deployment.
Fix: distinguish dependency/PR-image checks from release-image verification. Build the release
artifact once, record digest and source/config provenance, scan that exact image archive,
then deploy candidate, verify and promote the same digest. If the deployed mode has no image,
name the applicable platform/OS evidence rather than inventing a container scan. Fresh release
audits still block on every known advisory. Document legitimate marker/platform exclusions
and unsupported package formats rather than treating package counts as coverage.
The hashed pip-audit procedure is supported in principle [S5], but tools are not yet pinned or
executed. Define database freshness and who provisions scanner/tool inputs without project code.
Check: image B cannot inherit image A's pass; unsupported/partial inventory fails verification.
Blocks: release workflow design. Owner: Claude.

### B14 — Medium: persisted geocoding and service policy need explicit disclosure

Location: PLAN privacy; ARCHITECTURE cache keys; Nominatim integration.
Failure: typed location is a quiz answer, yet it is persisted as a 30-day cache key while
the privacy summary says answers are not persisted. Free text may contain a home address.
Fix: distinguish cached public town lookup data from session answers, bound and minimize
stored search terms, explain the actual retention and clearing behaviour. Request towns/areas,
not personal addresses; validation cannot guarantee arbitrary text contains no personal data.
Review the public Nominatim policy deliberately: app-wide pacing, identification, attribution,
no autocomplete, caching, switchable configured service, and no personal/confidential input [S6].
Do not infer public-service scalability from cache hits. Record policy/licence checks for all
providers and model/assets; integration tests obey the same provider budgets as production.
Check: cache/log inspection shows the documented data only; provider switching remains fixed
trusted configuration, never a user-supplied URL. Blocks: privacy/provider contract. Owner: Claude/Mats.

### B15 — Medium: state machine and startup/shutdown omit terminal cases

Location: ARCHITECTURE sections 4/7; ERROR-HANDLING matrix; PLAN lifespan.
Failure: diagram lacks location-choice and unexpected-failure transitions; startup policy
does not distinguish invalid catalogue from unavailable cache/model. Thread work can outlive
an awaiting coroutine; “bounded shutdown” alone does not specify resource ownership.
Fix: add typed terminal failure and location-choice outcomes; define admission rejection outside
accepted-job lifecycle. Invalid catalogue/hooks/config fail readiness and prevent planning;
cache failure may degrade, model failure may use eligible fallback. Stop admission, detach/close
subscribers, cancel/drain owned tasks, close HTTP resources and drain/close SQLite on its owner
thread. Bound statement/busy time and queue; no work may use a closed connection. Define process
exit escalation without killing unrelated host workloads. Health requests never call providers/model.
Check: corrupt catalogue, missing assets, disk-full, blocked DB, shutdown during generation,
unexpected adapter exception, and restart returning truthful expired/unavailable state.
Blocks: lifespan implementation. Owner: Claude.

### B16 — Medium: remaining summaries and timing are not fully reconciled

Location: PLAN timeline/evidence register; REVIEW-RESULT decisions/proof order; COMPETITION 14.4.
Fix: replace elapsed Saturday slots with dependency order, incorporating Mats's design-before-repo
instruction. Keep no repo/app code before approval; any pre-build fixture execution needs its
own authorized boundary. Model smoke order differs between plan and report: select one.
D25/evidence register require quantization comparison but the cut list permits dropping it:
mark conditional evidence honestly. D17's alternative Python versions must defer to whichever
pin Mats accepts. Reviewer's “Accept” is a recommendation, not user approval. COMPETITION's
wording about AI personalizing text should explicitly mean choosing reviewed hooks/reasons.
Rule check today confirms the entry window, new project/repository, one entry, open AI core,
demo/repository and explanation requirements [S7]. It does not certify entrant eligibility,
all general terms, licence compliance or a future finished entry.
Blocks: planning handoff consistency. Owner: Claude.

## Lean resolution order

1. Claude reconciles B01–B07 and B15 into a single backend contract: weather, sessions,
   location-choice, state transitions, cache/task ownership and finite budgets.
2. Complete B08–B14 at the model/provider/build boundaries. Keep explicit product choices
   proposed; no security downgrade or new service is automatically authorized.
3. Apply B16, then review only those diffs. Preserve stable D1–D34 IDs; allocate fresh IDs
   to actual new decisions, not one ID per paragraph. No broad rewrite or new framework.
4. Once text blockers are closed, proceed to design discussion. Runtime proofs remain
   gated for the authorized build; there is no reason to pretend they can run on paper.

## Facts/approvals still required

- Demo hostname and replay/live-fixture choice; D20 remains unchanged pending D27.
- Read-only Hermes capability inventory, its real governance and the four P0 confirmations.
- App name, age bands, 20-second budget and proposed D29–D32 parameters.
- Catalogue/hooks and provisional weather thresholds; fee-unknown policy from B10.
- Numeric resource/retention limits and any API/data/host constraints chosen during reconciliation.

## Runtime evidence still pending

Actual isolation/gate tamper tests; exact dependency versions and complete vulnerability audits;
GPU inference and cancellation; provider parsing/pacing; session/CSRF on supported browsers;
concurrency/cache failure/load tests; CSP/error journeys; same-digest deployed checks.
No installed packages, running app or source repo exists in this review, so no claim of
zero CVEs, working isolation, measured latency or production capacity is made.

## Primary sources checked 10 October 2026

- S1: https://open-meteo.com/en/docs — hourly variable time semantics and daylight field.
- S2: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html — origin and token handling.
- S3: https://docs.ollama.com/faq — loaded-model reporting, parallelism and queue configuration; https://docs.ollama.com/api/generate — generation API.
- S4: https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target — untrusted code and privileged workflows.
- S5: https://github.com/pypa/pip-audit — hashed inventory and disable-pip; https://docs.astral.sh/uv/reference/cli/ — export flags and mutually conflicting extras.
- S6: https://operations.osmfoundation.org/policies/nominatim/ — public service conditions.
- S7: https://dev.to/page/hacktoberfest-week1-2026-10-05-contest-rules — contest-specific requirements.
- Model identity cross-check: https://ai.google.dev/gemma/docs/core — E4B exists; selected runtime/backend compatibility still requires proof.

Recommendations above are design judgments derived from the documents and these sources;
they are not claims that the absent implementation has demonstrated an exploit.

## Delivery instruction to Claude

Return one complete versioned ZIP containing the reconciled set, updated findings/status and
SHA256SUMS.txt. No side files. Keep the change summary brief. Retain source attribution and
distinguish text-resolved, user-approved and runtime-proven. Do not reopen settled scope or
begin repository/app implementation without Mats's explicit authorization.

## Reconciliation status — round 8.5 (Claude, 10 October 2026)

"Text-resolved" means every affected document now agrees; nothing is runtime-proven.

| ID | Status | Where it now lives | Still needed |
|---|---|---|---|
| B01 | Text-resolved | BACKEND-CONTRACT §1; PLAN §2.2, §4, §5 | Boundary tests at 29:59 / 30:00 / 30:01 |
| B02 | Text-resolved; code set proposed | BACKEND-CONTRACT §1; D35 half day | Mats reviews thresholds and severe codes |
| B03 | Text-resolved | BACKEND-CONTRACT §2; ARCHITECTURE state diagram | Tests at expiry minus one second |
| B04 | Text-resolved | BACKEND-CONTRACT §3; ERROR-HANDLING new LOCATION_CHOICE_EXPIRED | 60-second pause, forged and expired choice tests |
| B05 | Text-resolved; numbers proposed | BACKEND-CONTRACT §4 | Load test before lock |
| B06 | Text-resolved | BACKEND-CONTRACT §5 | Localhost cookie proof; cross-session tests |
| B07 | Text-resolved | BACKEND-CONTRACT §6; ARCHITECTURE §15 | Staggered-waiter, 429 and disk-failure tests |
| B08 | Text-resolved; mechanism open | HERMES-P0 §4; D38 | Mats chooses D38; runtime cancellation evidence |
| B09 | Text-resolved; D36 proposed | BACKEND-CONTRACT §7 | Adapter and validator tests |
| B10 | Text-resolved; fee policy open | BACKEND-CONTRACT §8; PLAN §5; D37 | Mats chooses D37 |
| B11 | Text-resolved | Catalogue and hooks | Mats reviews every changed line |
| B12 | Text-resolved | PLAN §8 CI trust model | Repository settings demonstrated at bootstrap |
| B13 | Text-resolved | PLAN §8 release gate; ARCHITECTURE 13.3 | Pinned tools, executed release scan |
| B14 | Text-resolved | BACKEND-CONTRACT §9; PLAN §5 privacy | Cache and log inspection |
| B15 | Text-resolved | BACKEND-CONTRACT §10; ARCHITECTURE state diagram | Corrupt-catalogue, disk-full and shutdown tests |
| B16 | Text-resolved | PLAN §15 dependency order; D17, D25; COMPETITION 14.4 | None in text |

Catalogue changes (B11): shared rule now allows moving loose fallen leaves and sticks a short
way and never stones or logs; `shape-safari` minimum 20 min; `tree-twins` wind limit 25 km/h
instead of prose; `five-senses` lit-path note after dark; every optional item names an
alternative; generic hook reads "on paths near you". Age-band gaps (all four bands share only
`picnic-adventure`; 0–2 with 6–9 has no generic activity) are left as honest no-results.
