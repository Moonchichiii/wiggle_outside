> Round 8.9 summary first; earlier rounds follow. Round 8.5: the backend findings B01–B16 are reconciled; status per finding is at the end of [BACKEND-REVIEW.md](BACKEND-REVIEW.md). The verdict below is updated. "Accept" in the decisions table is the reviewer's recommendation, not Mats's approval.

# Baseline 8.20: final build specification

Decisions are closed in one register (PLAN §0); every active decision is accepted,
deferred, declined, blocked (with a named prerequisite) or superseded. This baseline is
the agreed instruction set, not proof that the unbuilt application is secure or correct.
Approving it and saying "kör" are separate actions by Mats. Build findings become tracked
changes (CONTRACTS §10), not new planning rounds.

## Decisions recorded (Mats, 10 October 2026)

| Topic | Recorded | Where |
|---|---|---|
| Decision sheet | accepted in full: step-free preference (D42 P); fees option (b) with the full label "Admission not verified" and `fee=no` as "Reported free admission" (D37); fonts Cabinet + Switzer with system fallback, licence and glyph checks still required (D41); Rune Icons declined (D47); local Ollama deferred (D38); preloading deferred (D34); working defaults kept: 20 s deadline, 4 h half day, distinct activities, one worker (D32, D35, D36, D21) | PLAN §0 |
| Catalogue | all dispositions, with **5 °C on all three** baby-eligible entries | CATALOGUE-REVIEW §0; drafts/*.toml |
| Integration lead | Claude Code integrates and runs the gates; Codex reviews integrated changes; Mats approves product decisions, protected changes and release, and alone commits, signs and pushes. **No build orchestrator (TC-003)** | PLAN D9; BUILD-PACKAGES §2, §2.1 |
| Hostname | `wiggle-outside.fly.dev`, if available; does not by itself settle 145/A+ | PLAN D20, D27; DEPLOYMENT |
| Night copy (new, Mats) | family path: fixed reviewed copy from the existing daylight check; no model call, polling or refresh; answers kept under "Change answers"; solo unchanged | BACKEND-CONTRACT §1; ERROR-HANDLING; CONTRACTS §3; DESIGN-SPEC §9, §12; WP1, WP6, WP8; mock `05-night.html` |

The established defaults that still said "proposed" are recorded as "accepted
(baseline 8.20)" as part of closing the register; Mats can reopen any of them only as a
tracked change.

## Mechanical corrections (reviewer, 8.19 review)

| Correction | Fixed in | Check |
|---|---|---|
| Decision statuses vs AGENT-BRIEF | PLAN §0 register and status words; status lines of CONTRACTS, BUILD-PACKAGES, BACKEND-CONTRACT, ARCHITECTURE, DEPLOYMENT, DESIGN-SPEC, PRODUCT-FIT; AGENT-BRIEF reading rule | no active decision says "proposed" or "needs Mats" |
| WP10 vs `deploy.md` | BUILD-PACKAGES WP10 row excludes WP5's two files and WP9's `deploy.md` | ownership table has no overlap |
| Hosted-model evidence | WP5 records model identifier, endpoint, settings and evaluation date; no weight digest; release record (§6) the same | `model-eval.md`, `model-smoke.md`, `release.md` fields |
| Rollback | ARCHITECTURE §2.1 and WP9: previously verified image **digest**, never a tag | deploy check in `deploy.md` |
| Cost language | DEPLOYMENT §1.3: 10,000 bytes enforced; 10,100 tokens labelled an unverified estimate, checked per run | table headings say "estimate" |
| Privacy wording | ARCHITECTURE §2 "never receives" = not deliberately included; free text is sent as typed; hint "Don't include personal details." in DESIGN-SPEC, PRODUCT-FIT and the mocks | copy test on the hint |
| D27 visibility | PLAN D27 **blocked** on P3; listed below | release gate |

## Prerequisites (cannot be closed by editing documents; PLAN §0.1)

| # | Prerequisite | Owner |
|---|---|---|
| P0 | Approval of this baseline and "kör" for M0 | Mats |
| P1 | Font files and licence, then glyph and layout-shift checks (D41) | Mats; WP8 |
| P2 | DeepInfra's two privacy answers, then spending approval | Mats |
| P3 | Hostname availability; Observatory 145/A+ on the deployed host (D20, D27) | Mats; WP9 |
| P4 | Runtime evidence (gates, hosted verification, deploy checks, accessibility, evaluation) | Claude Code with the WPs; Codex reviews |

# Round 8.19: reconciliation only

No new features, no application code. The independently hosted product is the primary
build path; local development is optional. Superseded text is kept only in change logs
and marked history sections.

## Findings → owner → work package → acceptance check

| # | Finding (8.18 review) | Owning document (fixed there) | Also reconciled | Work package | Acceptance check |
|---|---|---|---|---|---|
| 1 | Architecture showed local Ollama; D5/D24 recommended local/replay | ARCHITECTURE §2 (hosted diagram, recipient table, inactive O1/O4/replay) | PLAN D5/D24 superseded, §5, §6, tree, CSP table, §12; CONTRACTS `DeploymentMode`, `/examples` inactive; ERROR-HANDLING replay inactive; AGENT-BRIEF; WALKTHROUGH `hosted_live` | WP0, WP5, WP9 | `/examples` returns 404 (not built); the WALKTHROUGH fixture journey runs in `hosted_live`; `fly.toml` and `Dockerfile` match ARCHITECTURE §2.1 |
| 2 | Local GPU smoke before M0; WP5 owned only Ollama | PLAN §15 | BUILD-PACKAGES WP5 (`integrations/openrouter.py`, `tests/integrations/test_openrouter.py`), WP9 release text | WP5, WP9 | WP5 adapter tests on fixtures (pinned endpoint, strict schema, 10,000-byte cap, 402/429, no retry); hosted verification on the release image recorded in `docs/evidence/deploy.md` |
| 3 | D39 said "never sent to providers" | ARCHITECTURE §2 recipient table; PRODUCT-FIT §3.8 | PLAN D39 and §5; DESIGN-SPEC hints; BACKEND-CONTRACT town note; COMPETITION privacy; mocks | WP5, WP8 | Copy test: interests hint and town hint equal DESIGN-SPEC; log-allowlist test shows no interest text, coordinates or town |
| 4 | WP7 LRU eviction; WP6 storage failure as SERVICE_LIMIT_REACHED | DEPLOYMENT §2.3, §2.4 | BUILD-PACKAGES WP6, WP7; CONTRACTS §3 | WP6, WP7 | Store at 10,000 unexpired entries never evicts, new address goes to overflow; quota read/write failure → 503 SERVICE_UNAVAILABLE, exhausted → 503 SERVICE_LIMIT_REACHED |
| 5 | Step-free preference prescribed while D42 open | PLAN D42 (pending, both variants specified) | CONTRACTS form row, DESIGN-SPEC copy row, PLAN §2 form table, WP1, mock note | WP1, WP7, WP8 | After Mats's choice: one label, one rule, fixtures and tests for that variant only; until then no step-free code is built |
| 6 | B2 only partly integrated | DEPLOYMENT §2.2 (B2 contract and event table) | CONTRACTS §3 GET row, `/healthz` row; BUILD-PACKAGES WP7; ARCHITECTURE §2.1 | WP7 | 600th GET passes, 601st → 429 with `Retry-After`; HTML, htmx and static variants; `/healthz` not counted; overflow sharing; expiry; never called a spending cap |
| 7 | Fly operational contract missing | ARCHITECTURE §2.1 | DEPLOYMENT §1.2, §1.5, §2.2, §3; WP9 acceptance | WP9 | `fly machine list` shows one Machine; quota count unchanged across restart, deploy and rollback; spoofed `Fly-Client-IP` ignored or limits declared best effort; key absent from image and logs |
| 8 | $4.40 read as a ceiling; "overshoot < $0.01" | DEPLOYMENT §1.4, §1.5 | §1.2, §2.6; COMPETITION cost line | — (Mats's spending approval) | No sentence claims a cap on Fly traffic or on inference overshoot; §1.5 lists the remaining exposure |
| 9 | Catalogue: blanket approval, 30 km/h raising tree-twins, baby thresholds unsupported | CATALOGUE-REVIEW | — | WP2 | Test: no wind limit increases versus the reviewed TOML, `tree-twins` = 25; TOML edited only per Mats's per-item answers |
| 10 | Mocks stale (Shantell, "Proposed" D39/D40, local wording, tall layout) | mocks/ (`tools/build_mocks.py`, `mock.css`, README) | DESIGN-SPEC §1.5 energy note | WP8 (later, with real fonts) | `reports/check-report.json`: no overflow at 320/390/1440 px, targets ≥ 44 px, no axe violations at 390 px; placeholder font disclosed; no D39/D40 tags |

## Genuinely unresolved (Mats), in priority order

| # | Decision | Notes | Blocks |
|---|---|---|---|
| 1 | "Kör" for M0, and the integration owner | | everything |
| 2 | Spending approval (DEPLOYMENT §1.5), after DeepInfra answers its two privacy questions | needed for the hosted smoke and the deploy | hosted verification, release |
| 3 | D42: (P) preference or (R) requirement; if (R), whether generic ideas without a place stay | | WP1, WP7, WP8 step-free |
| 4 | Catalogue answers, one per line (CATALOGUE-REVIEW §6) | no blanket approval | WP2 content |
| 5 | Font files and licence for a public repository (D41) | then mocks are regenerated | WP8 fonts |
| 6 | D37 unknown fees | | places filter |
| 7 | D38 local development endpoint | optional; gates nothing | nothing |
| 8 | D47 icons | | nothing |

# Round 8.18: decisions recorded, catalogue review, remaining questions

Recorded: **D39 and D40 accepted** (Mats). Energy question set to "How much energy
today?", Gentle / Moderate / High, hint "We may suggest something gentler." Problem
statement first in PRODUCT-FIT and in `drafts/submission-draft.md`. Fly.io preferred
host (DEPLOYMENT §1.5), with a per-network page limit because Fly shows no spending cap.
New CATALOGUE-REVIEW.md. Build not authorised.

## Genuinely unresolved (in priority order)

| # | Decision | Recommendation | Blocks |
|---|---|---|---|
| 1 | Build start ("kör") for M0, and the integration owner | When you are ready; you as owner | everything; time is the constraint |
| 2 | Catalogue review answers (CATALOGUE-REVIEW §6: baby-plus-sibling coverage, 30 km/h tree wind cap, remove `shadow-play` and `cloud-stories`, baby 5 °C, daylight-only for kids, `statues` mobility line, two wording fixes) | ~~Accept all six~~ (withdrawn in 8.19: per-item answers, CATALOGUE-REVIEW §6) | WP2 |
| 3 | D42 step-free: preference (P) or requirement (R) | (P), for an honest label without empty results | form, ranking |
| 4 | D37 unknown fees: (b) with no "free" claim | Accept | places filter |
| 5 | Font files and licence into the package (D41) | Upload them for the checks | WP8 |
| 6 | D38 local development model endpoint | Dedicated Ollama instance | model smoke step |
| 7 | Spending proposal (DEPLOYMENT §1.5): Fly.io, DeepInfra after its two answers, $10.80 upfront, about $4.40 a month, $5 key cap | Email DeepInfra now; approve when answered | deployment only |
| 8 | D47 icons | Decline for v1 | nothing urgent |

# Round 8.17: visual direction, typography, and the priority list

- **Visual direction approved** (Mats): `mocks/reference/visual-direction-v2.png`,
  with a slightly more humanised finish (DESIGN-SPEC §1.5). The external design
  review's behavioural changes and wrong contrast figures are recorded as not adopted.
- **D41 revised:** Cabinet Grotesk ExtraBold + Switzer Variable, two self-hosted WOFF2
  files (≈ 64 KB). Pending: glyph coverage, licence for a public repository, layout
  shift.
- **Hosting:** Fly.io added beside Hetzner with verified prices; Fly's page shows no
  hard spending limit.
- **Post guardrails** for the write-up (PRODUCT-FIT §5.5).

## Unanswered questions, in priority order

| # | Question | Recommendation | Unblocks |
|---|---|---|---|
| 1 | Start the build ("kör") with the bootstrap milestone M0, and who is the integration owner? | Kör for M0 now; Mats as integration owner | everything (about 42 hours remain) |
| 2 | Product decisions the contracts encode: D39 interests field, D42 stroller/step-free split, D37 unknown fees, D40 name | Accept D39, D42, D37 (b), D40 | WP0 stubs, forms, schema |
| 3 | Activity list, story lines (hooks), weather limits and age bands | Approve the drafts after one read | WP2, real output |
| 4 | Energy labels: "Gentle / Some running / Full steam" (copy deck) or "Gentle / Moderate / High" (concept board) | Copy deck: more human, same meaning | WP8 copy |
| 5 | Font files and their licence: add `CabinetGrotesk-Extrabold.woff2`, `Switzer-Variable.woff2` and the licence text to the package | Upload them so coverage and licence can be checked | WP8, D41 |
| 6 | D38: local development model endpoint | A dedicated Ollama instance on the dev machine | model smoke step |
| 7 | Hosting: Fly.io or Hetzner CX23; model provider DeepInfra (after its two answers) or Google; the spending proposal (DEPLOYMENT §1.5) | Decide while the build runs; email DeepInfra now | deployment only |
| 8 | D47 Rune Icons | Decline for v1 | nothing urgent |

# Round 8.16: six deployment corrections and one spending proposal

1. **Hosted token budget:** the complete request (messages + schema) is capped at
   10,000 UTF-8 bytes before sending; reported `usage.prompt_tokens` checked each run;
   output including reasoning capped by `max_tokens` 256; reasoning disabled ("none",
   acceptance unknown until the smoke test).
2. **Privacy:** OpenRouter stores no prompts by default; DeepInfra states no disk
   storage, no prompt logging, no training (Gemma exception and processing location to
   confirm); Google states no training but may log prompts for abuse monitoring and
   caches 24 h, not switchable through OpenRouter. ZDR not set: no ZDR endpoint with
   structured output is confirmed for this model.
3. **Total cost:** VAT, IPv4 €0.50, credit fee 5.5 % (min $0.80), optional domain,
   traffic over 20 TB; credits are not an absolute limit (negative balance possible);
   auto top-up off.
4. **Network counters:** unexpired entries are never evicted; new addresses go to the
   overflow bucket at capacity.
5. **Quota:** one conditional SQLite transaction before provider work; concurrency and
   crash tests; storage failure → SERVICE_UNAVAILABLE, not "until midnight".
6. **Cancellation:** local keeps the slot until inference ends; hosted releases on
   connection close and claims nothing about remote generation.

**Spending proposal (DEPLOYMENT §1.5):** DeepInfra via OpenRouter (after two
confirmations) + Hetzner CX23 with IPv4; upfront $10.80 in credits; about €6–8 a month
expected; inference capped at $5 a month; 500 runs a day. Not approved, nothing bought.

# Round 8.15: O2 specified for Mats's spending decision

Mats's direction: **O2**, a public planner on managed Gemma, deployed independently of
the workbench (O3 removed; D38 limited to local development). Planning only: nothing is
bought or deployed. DEPLOYMENT §1 now gives:

- **Model:** Gemma 4 26B A4B on OpenRouter, with its own evaluation; the app design does
  not change.
- **Pinned endpoint:** Google, recommended ($0.15 / $0.60 per million tokens), or
  DeepInfra, cheaper ($0.07 / $0.34). Both support structured output. Their data-use
  terms still need reading.
- **Per run:** Google, $0.00036 typical and $0.00073 maximum; DeepInfra, $0.00018
  typical and $0.00036 maximum. These are estimates from stated token assumptions.
- **Fixed hosting:** Hetzner CX23 at €5.49 a month excluding VAT and IPv4 (verified), or
  DigitalOcean at $6 or $12 a month (verified).
- **Limits:** the daily allowance of 500 runs; a per-key cap of $10 a month with Google
  or $5 with DeepInfra (refusal leads to the labelled fallback; a small overshoot is
  possible); prepaid credits as the outer limit (purchase fee unknown); a fixed VPS
  price.
- **Correction:** the "$0.11/run" in the question was the daily maximum ($0.11 per day
  at the old cheapest-route price), not a per-run cost.

**For Mats to approve before any spending:** the endpoint, the key cap, the credit
amount, the VPS provider and plan, and the period it runs.

# Round 8.14: deployment corrections

Not called build-ready. DEPLOYMENT.md corrected per review: O4 (self-hosted E4B on a
rented GPU) added with its unknowns; no default deployment; restart-safe daily allowance;
counter-by-event table (an ambiguous place plus its choice is charged once); the separate
model allowance removed (model calls cannot exceed runs; the key cap is the backstop);
bounded network-counter storage; hosted inference contract (strict JSON schema, no
provider fallbacks, `max_tokens` 256, timeout, 402/429 handling, cancellation may not
stop billing); exact cost arithmetic, typical and maximum, with the price marked as
read once and to be rechecked; no latency claim; honeypot autofill as a test obligation
with a recovery path; `web/forms.py` owned by WP0; provider eligibility separate from
traffic limits. Product decisions unchanged.

**Decision 1 is now open-ended (replaces the 8.13 recommendation):** which deployment
will Mats operate and fund, and for how long — O1, O2 or O4 (DEPLOYMENT §1; O3 removed in 8.15). The rest
of the 8.13 list stands.

# Round 8.13: deployment, abuse and cost, decision list

Not called build-ready and not "fully secure". New DEPLOYMENT.md (D48 options, D49
hosted controls, connectivity). The seven 8.12 corrections are in place (status tables,
uniform location-choice 422, session-bound retention, HMAC fingerprint, conditional
cache budgets, no cancellation or progress leftovers, AGENT-BRIEF.md). Routine items
closed as engineering defaults: S2, S4, S6 kept as specified; `retain_until` = 60 min.

## Owner decisions (bounded list)

| # | Decision | Recommendation | Consequence | Blocks |
|---|---|---|---|---|
| 1 | D48: how the entry is delivered (superseded in 8.14: no default; see above) | — | O1: no hosting cost or public abuse surface; Gemma E4B stays local, as planned; D20, D27 and D49 drop out. O2: hosted Gemma 26B A4B or 31B (E4B isn't offered), capped spend, extra build and evaluation work, visitor data reaches the server and the model provider | deployment only |
| 2 | D39: the interests field | **Accept**: it makes language understanding Gemma's clearest, demonstrable job | one field, a 30-phrase evaluation, the schema `selection.v2` | implementation (form, schema, prompt) |
| 3 | D38: the local model endpoint | **A dedicated Ollama instance** for the app, pinned model, no public exposure | the workbench's shared service is untouched | implementation (model step) |
| 4 | Catalogue, hooks, weather thresholds and age bands | **Approve the drafts** after one read, changing only what looks wrong | the planner's real output | implementation (WP2) |
| 5 | D37: unknown admission fees | **(b)**: exclude `fee=yes`, label unknown fees "Admission not verified" | more usable places, honestly labelled | implementation (places filter) |
| 6 | D42: stroller vs step-free | **Accept the split** | two controls with different, honest effects | implementation (form, ranking) |
| 7 | D40, D41, D47: name, fonts, icons | **D40 and D41 accept** (weight-only Shantell file); **D47 decline for v1** (keep our own few icons, saves time) | copy and visual polish | implementation of WP8 only |
| 8 | Integration owner | **Mats**, or one agent session he reviews | someone owns contracts, lockfiles and assembly | implementation start (M0) |

Everything else is either decided or an engineering default.

## Competition fit (short)

| | Status |
|---|---|
| Official rules (theme, new repo inside the window, open-source AI at the core, template post with demo and repo links, open-innovation section, one English entry) | Plan fits; a video demo and hosted Gemma are both allowed; no local-only, model-size or baseline rule |
| Our engineering commitments (security gates, accessibility, request budgets, honest labels, lean architecture) | Specified; not contest rules |
| Execution evidence | **All missing**: repository and app, a real-model journey, one concrete example of Gemma's influence, one failure and recovery journey, H1 (and D39) evaluation, outdoor trial if feasible, the published post (PRODUCT-FIT §5.4) |

Time check: the contest closes Mon 12 Oct 08:59 CEST, about 44 hours after this round.
More planning rounds now cost build and evidence time.

# Round 8.12: correction round on 8.11

Not called build-ready. Corrections, each in its owning document:

| # | Finding | Correction |
|---|---|---|
| 1 | Removed behaviour still required (cancellation access, progress reconnect tests) | ERROR-HANDLING §4 and ARCHITECTURE §10 now test lost-response resubmission and internal cancellation instead |
| 2 | Simplicity review contradicted the decisions | Split into "Current state (binding)" and a historical review; S5 rows say "Keep (rejected)" |
| 3 | Location-choice 404 versus 422 | One uniform 422 LOCATION_CHOICE_EXPIRED for any candidate not in the session's live set; a POST never returns 404 — CONTRACTS §3, BACKEND-CONTRACT §3, §5 |
| 4 | Walkthrough outlived its idle session | Results live until the earlier of `retain_until` and session end; walkthrough now ends with idle expiry (404, then 403 for the stale token); separate active-session and idle-expiry tests — BACKEND-CONTRACT §2, WALKTHROUGH |
| 5 | "Change answers costs one model call" too broad | Only for an interests-only change with the same location and time budget and fresh covering weather; other cases listed with their calls — ARCHITECTURE §14, PRODUCT-FIT §3.5 |
| 6 | Idempotency comparison undefined | HMAC-SHA256 fingerprint over the canonical form, including the interest text; per-process key; kept only with the idempotency record — CONTRACTS §7 |
| 7 | Which response carries which status | POST table and GET table; full pages only; htmx swaps `<main>` for every status — CONTRACTS §3, ARCHITECTURE §13.2 |
| — | Prefilled interests lost meaning | Labelled "These are the interests we recognised. Edit them for your next search." — PRODUCT-FIT §3.5, DESIGN-SPEC §9 |
| — | Agent entry point | New AGENT-BRIEF.md (short; points to the canonical documents) |
| — | Cards too wordy | Title, one playful sentence, one practical line, labels, link; reasons and match on the detail page; hooks are fixed sentences without placeholders (removes hook substitution) |
| — | Rune Icons | Proposed D47: selected exported outline SVGs (Apache-2.0 icon assets), inspected, self-hosted, licence and provenance recorded; no package; decorative art stays original |

Mock checks re-run (`mocks/reports/check-report.json`): no overflow at 320/390/1440 px,
targets ≥ 44 px, no axe violations at 390 px. That does not establish keyboard
behaviour, screen-reader announcements, production-CSP compatibility or AAA
conformance.

**Still open for Mats:** D39, D40, D41, D42, D47, D37, D24/D27, D38, `retain_until`,
S2/S4/S6, the mock review and the integration owner.

# Round 8.11: simplification decisions applied

Mats decided four of the simplicity proposals: D43 (no progress stream or Stop), D44 (no
repair), D45 (D33 kept: single flight and negative cache stay), D46 (immutable results;
interests changed by resubmission). They are applied consistently to ARCHITECTURE (state
and sequence diagrams, transport, budgets), BACKEND-CONTRACT, CONTRACTS, ERROR-HANDLING,
PRODUCT-FIT, DESIGN-SPEC, BUILD-PACKAGES, PLAN, WALKTHROUGH and the mocks. Mock checks
re-run: no overflow at 320/390/1440 px, targets ≥ 44 px, no axe violations at 390 px.
Not called build-ready.

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

**Proof obligations added:** htmx 4 follows the 303 and swaps the result region under
the production CSP · lost-response resubmission joins the job (0 upstream calls) ·
"Change answers" with fresh caches makes only the model call · invalid-output rate
reported by reason in the smoke test and evaluation.

**Still open for Mats:** D39 (field itself), D40, D41, D42, D37, D24/D27, D38,
`retain_until` = 60 min, S2/S4/S6, the mock review and the integration owner.

# Round 8.10 addition

Purpose-and-simplicity review in SIMPLICITY-REVIEW.md. Proposals S1–S7 for Mats (SSE
progress and Stop, job states, repair attempt, cache table, single flight and negative
cache, two protocols, D39 re-sort). Only two diagram consistency fixes were applied;
every contract is unchanged until Mats decides.

# Wiggle Outside review result: round 8.9 (correction round)

Not called build-ready. The corrected interfaces now trace the fixture journey in
WALKTHROUGH.md on paper, without undocumented assumptions that we know of; nothing has
been executed. Whether the parallel packages may start is Mats's decision after review.

## Correction log (against 8.8)

| # | Finding | Correction | Owning text |
|---|---|---|---|
| 1 | `weather_code` treated as preceding-hour | Instant sampling, as Open-Meteo documents; worked example across an hourly boundary; fixture with hourly arrays | BACKEND-CONTRACT §1 |
| 2 | Retries could bypass the gate; cooldown capped at 15 min | Adapters make one attempt; the single retry is in the wrapper and every attempt passes admit/pace/record; full `Retry-After`, no cap; negative cache only after the final attempt | BACKEND-CONTRACT §6, CONTRACTS §4.1, ARCHITECTURE §14 |
| 3 | Stable links without stable content | Immutable idea snapshots (≤ 12, inside the 32 KiB bound); interest line computed from current tags; deterministic hook/reason rule for newly shown ideas | BACKEND-CONTRACT §2, CONTRACTS §2, §4.2, §5 |
| 4 | Duplicate location choice | One job per candidate (derived key); repeats return the same job until `retain_until`; candidate set keeps the answers; consumed choice page redirects | BACKEND-CONTRACT §3, CONTRACTS §4.2, §7 |
| 5 | Incomplete presentation contracts | Presenters take every input explicitly (job ID, session, catalogue, mode); progress view has stop URL and CSRF; `WeatherSummary`, `AnswersSummary`, `BingoView`, dated `PrintView`; each field's source named | CONTRACTS §2, §8 |
| 6 | Historical view versus expiry | `valid_until` (not current) and `retain_until` (removed); everything tied to a result removed together | BACKEND-CONTRACT §2, §4, ARCHITECTURE §4 |
| 7 | Double escaping | Plain text through domain and presenters; escape once at render; "Oak & Elm" test | BACKEND-CONTRACT §7, PLAN §3, ERROR-HANDLING §2 |
| — | Walkthrough | 21 transitions with input, retained state, output, status, request count and owner; 16 gaps found and fixed | WALKTHROUGH.md |
| — | UX | Shorter, compact form; accurate intro; one-column results with answers summary and "Change answers"; weather once; travel wording; stroller/step-free split (D42); privacy copy by mode; no language claim; dated print | DESIGN-SPEC §4, §6, §9, §10, §13; mocks |
| — | Bingo card | `card` field documented, validated (0 or 9), rendered as a 3 × 3 grid on detail and print | activities.toml, CONTRACTS §8, mocks |

## Status of claims

| Kind | Items |
|---|---|
| Documented behaviour (not executed) | All contracts, the walkthrough, request counts, statuses, retention, snapshots, escaping, provider gate |
| Verified on static mocks (reproducible: `mocks/tools/check_mocks.py`, report `mocks/reports/check-report.json`) | No overflow at 320/390/1440 px; smallest target ≥ 44 px; axe-core 4.10.2 found no violations at 390 px; no inline styles or scripts; print context visible |
| Unexecuted application proofs | The "Proof obligations" list below (updated in 8.9) |

## Owner decisions (short list)

1. D39 interests field: accept or drop. 2. D40 name. 3. D41 fonts (weight-only file
or with the bounce axis). 4. D42 stroller/step-free split. 5. D37 unknown fees.
6. D24 demo mode and D27 hostname. 7. D38 model endpoint. 8. `retain_until` = 60 min
after `valid_until` (proposed). 9. Review the mocks and name the integration owner.
D29–D32, D35, D36 stay as proposed unless Mats changes them.

---

# Round 8.8 review result

## Round 8.8 integration fixes (against 8.7)

| # | Point | Resolution | Where |
|---|---|---|---|
| 1 | Workbench scope still gated the app build | Hermes inventory, boundary proof and D28 are Mats's separately managed workbench readiness; removed from the delivery order, owner-decision table and proof list | PLAN §15, §17, D9, D28; this file |
| 2 | WP0 ↔ WP9 circular dependency | One bootstrap milestone M0 = WP0 + initial WP9 gates, one owner, accepted together; packages wait for M0 | BUILD-PACKAGES §3–4, PLAN §15 step 3 |
| 3 | Conflicting statuses for required-service failure | Canonical table: required service unavailable (weather, geocoder, places with no generic idea) → 503; evaluated with nothing suitable (NO_MATCHES, WEATHER_RESTRICTED) → 200 | CONTRACTS §3; ERROR-HANDLING §3 points there |
| 4 | Interest fallback contradiction | Four cases: both valid; valid interpretation + failed selection (keep chips, fallback ranking uses them, labelled); failed interpretation (no chips, "not applied"); both failed | PRODUCT-FIT §3.3–3.4, DESIGN-SPEC §9 |
| 5 | Position-based detail URLs | Stable opaque `idea_id` per pair; `/ideas/{idea_id}`; ideas shown once stay readable after a re-sort, with a "no longer in your current list" note | CONTRACTS §2, §5 |
| 6 | Missing parallel interfaces | Cache store, provider gate, single flight, counters and `cached_*` wrappers; complete view models, presenter signatures, detail weather times and print context; shared fixture views | CONTRACTS §4.1, §8 |
| 7 | WP5 writing into WP10's directory | WP5 owns `docs/evidence/model-eval.md` and `model-smoke.md`; WP10 links, never edits | BUILD-PACKAGES §3 |

Static mock screens are in `mocks/` (README there lists what was and was not checked).


Documentation and static mocks only. Nothing below is locked, accessible or performance-proven, and nothing
grants build permission.

## Owner decisions still open (Mats)

| ID | Question | Recommendation |
|---|---|---|
| D24 | Public demo: recorded replay or live | Replay with fixed examples; live local recording |
| D27 | Demo hostname (Observatory preload check) | Name it; then inspect |
| D29–D32 | Python 3.14, seasons, session/CSRF, stage budgets | Accept as proposed |
| D35, D36 | Half day = 4 h; unique activity per result | Accept |
| D37 | Unknown admission fees | (b) free-intended with "Admission not verified" |
| D38 | Model endpoint: dedicated Ollama or scoped proxy | Mats's choice |
| D39 | Interest understanding, refined in 8.7 | Accept if the extra field fits the schedule; evaluate either way |
| D40 | Name "Wiggle Outside" | Mats's choice |
| D41 | Shantell Sans headings + system body | Accept |
| D42 | Stroller filter and step-free preference as two controls (8.9) | Accept |
| — | Catalogue, hooks, weather thresholds, `interests` tags, 30-phrase set | Review |
| — | CONTRACTS.md and BUILD-PACKAGES.md (route paths, field names, ownership, integration owner) | Review; name the integration owner |
| — | Three mock screens (`mocks/`) | Review now; approve before any template work |
| — | ~~Workbench readiness (Hermes, D28)~~ | Closed by TC-003: no orchestrator; D28 declined; execution model in PLAN D9 |

## Hypothesis

**H1** (replaces "finding P1"): Gemma's choices, and with D39 its reading of interests,
help a parent more than the deterministic ranking. Unproven; not a contest requirement.
The blinded comparison is reported whatever it shows (PRODUCT-FIT §2).

## Proof obligations (runtime, none done)

Gemma on the GPU with cancellation evidence · selection
output fits `num_predict` 256 with v2 schema · canonical audit with coverage · localhost
`__Host-` cookie and CSRF in Firefox and Chromium · CSP with `hx-sse` and `hx-status`,
zero violations · request-budget counts including D39 re-sort = 0 · H1 blinded comparison ·
D39 tag accuracy vs keyword baseline (if accepted) · latency, memory and fallback rates ·
contrast script on `tokens.css`, keyboard, Orca, 400 % zoom, forced colours, reduced
motion, print · Shantell subset covers Swedish and French characters · contract tests and
package acceptance checks (BUILD-PACKAGES §3) · integration checks on the combined
project (§5) · final verification bound to the release commit and image digest (§6).
Added in 8.9: walkthrough acceptance test with request counts · weather boundary test on
the hourly fixture · every provider attempt through the gate, full `Retry-After` honoured ·
escape-once test ("Oak & Elm <b>") · snapshot stability across a re-sort · location
choice idempotency · removal at `retain_until` · bingo grid and dated print on paper.

## Next step

Review the static mock screens delivered in 8.8 (`mocks/README.md` lists the questions):

1. **Form:** all questions, D39 field shown as optional, one validation error state.
2. **Waiting:** progress text for the real stages, Stop button, no focus movement.
3. **Results and card:** three cards (sage, peach, butter) with inferred chips, one
   uncertainty label and the weather line; plus the detail/print view.

Mock screens are design artefacts, not application code. After approval: settle the open
owner decisions above, then kör when Mats decides.

---

> Historical (8.5). Since 8.8, Hermes inventory, boundary proof and D28 are workbench
> readiness, managed by Mats outside this package; R2, R10 and the first-build tasks 1–2
> below are no longer application gates.

# Round 8.5 review result

Reviewer: Claude, 9 Oct 2026 (late evening), against the verified 8.1 baseline
(SHA256SUMS checked) merged with the 8.2 review. Design review only; no control is
demonstrated and nothing here approves the build.

Note on 8.2: its input was the round 8 package, not 8.1. The 8.1 requirements were missing
from that input, not deliberately removed. Round 8.3 restores them and keeps D26.

## 1. Verdict

**Text-consistent, with pending choices and proofs.** All 16 backend findings are
text-resolved in the owning documents (BACKEND-CONTRACT, PLAN, ARCHITECTURE, ERROR-HANDLING,
HERMES-P0, catalogue). The earlier "only runtime proofs remain" verdict was premature and
is withdrawn. Open: Mats's choices (D24, D27 hostname, D28 inventory, D29–D32 parameters,
D35–D38, catalogue and thresholds) and every runtime proof.

## 2. Findings

| ID | Sev | Location | Issue | Resolution | Evidence | Status | Blocks |
|---|---|---|---|---|---|---|---|
| R1 | High | D20, D27 | The `hsts-preloaded` bonus depends on the host's preload coverage; a new preload submission takes weeks. | D20 stands. D27: inspect the chosen hostname first; Mats decides if it cannot qualify. | Hostname preload status; Observatory result | Open: hostname unknown | Release |
| R2 | High | HERMES-P0, D28 | Dispatcher, snapshot copier, `hermes-run` and Podman environments are not established by the documents. | Read-only Hermes inventory first; D28 fallback stays a proposal with its own boundary obligations. | build-process.md | Open: inventory unknown | Bootstrap |
| R3 | High | ARCH 13.3 | `pip-audit -r` resolves and installs by default; `uv export` emits the project line. | Canonical procedure: hashed export without project, `--require-hashes --disable-pip`; referenced from PLAN and HERMES-P0. | No downloads in audit-runner log | Fixed in text | Bootstrap |
| R4 | Med | ARCH 13.2, ERROR-HANDLING §5 | htmx 4: SSE is an extension; non-204/304 responses swap by default; indicator CSS via constructable stylesheets. | `hx-sse` pinned; `hx-status` mapping; documented stylesheet behaviour. | Playwright: zero CSP violations; errors land correctly | Fixed in text | Release |
| R5 | Med | Catalogue | Generic eligibility was implicit. | `generic_ok` on all 28 (5 true). | Property test | Fixed | Merge |
| R6 | Med | Catalogue, D30 | Seasons assumed northern hemisphere. | Hemisphere-aware seasons. | Unit tests both hemispheres | Fixed in text | Merge |
| R7 | Med | D31 | Session and CSRF transport unspecified. | Server-side session, `__Host-` cookie, form token. | Cookie on `http://localhost` in Firefox and Chromium | Proof pending | Bootstrap |
| R8 | Med | D32 | No stage budgets. | 3 / 4 / 11 / 2 s, proposed. | Smoke-test timings | Proof pending | Bootstrap |
| R9 | Med | PLAN §8 | Dependabot security-update support for uv and Bun is not confirmed by GitHub's page. | Daily canonical audits are the security net. | Observed behaviour | Fixed in text | Release |
| R10 | Med | HERMES-P0 §4 | Audit sources unnamed; image scan needs an archive. | Allowlist named; `trivy image --input`. | Section 8 proof | Fixed in text | Bootstrap |
| R11 | Low | PLAN §8 | Solo author cannot approve own PR. | 0 approvals, required checks, code scanning merge protection, review recorded in evidence. | Ruleset export | Fixed in text | Release |
| R12 | Med | ARCH §4 | Ollama stopping inference on disconnect is assumed. | Smoke test cancels mid-generation and checks GPU/`ollama ps`. | model-smoke.md | Proof pending | Model milestone |
| R13 | Low | D20 | SRI bonus needs `integrity` on our scripts. | Build-time SHA-384 attributes. | Observatory | Fixed in text | Release |
| R14 | Med | PLAN §15 | SSE progress had no cut position. | Cut after feedback storage; plain POST keeps the same budget and errors. | Plan text | Fixed | Release |
| R15 | Med | ERROR-HANDLING §7 | Error journey tested only for placement. | Added: no stale-result confusion, proxy/network failures, no duplicate inference on recovery. | Acceptance tests | Fixed in text | Merge |
| R16 | High | D33, ARCH 14–15 | Requests and caching had no enforceable budget. | Request budget table, cache contract (keys, scope, single flight, negative cache, bounds), CI call-count assertions. | respx counters, Playwright network log | Fixed in text | Merge |

## 3. Decisions

| ID | Answer |
|---|---|
| D20 | **Unchanged** until D27 is resolved. |
| D21–D25 | **Accept** (D22 with D32 budgets; D24 replay demo is Mats's choice). |
| D26 | **Accept**, mandatory. |
| D27, D28 | **Need Mats's facts**: hostname; Hermes inventory. |
| D29–D32 | **Proposed**, recommended. |
| D33 | **Accept**, mandatory per Mats. |
| D34 | **Proposed, optional**; not needed while the quiz is one page. |

## 4. Residual risks

GPU backend on the RX 6800 may fail and push inference to CPU; model ranking may not beat
the deterministic ranking; weather and infant limits are provisional; Nominatim pacing can
squeeze the geocode budget; Hermes controls are untested; Saturday holds infrastructure,
bootstrap and the deterministic flow.

## 5. First-build proof tasks (Saturday, in order)

1. Read-only Hermes inventory; decide P0 or a fully specified D28 fallback.
2. HERMES-P0 section 8 pre-bootstrap checks with the fixture repository.
3. Gemma 4 E4B on the GPU through the chosen connection: structured picks, latency, mid-generation cancellation.
4. Bootstrap with Python 3.14, the six runtime dependencies, Tailwind 4.3, htmx 4.0.0 and `hx-sse`; canonical audit with recorded coverage.
5. `__Host-` cookie and CSRF round trip on `http://localhost` in Firefox and Chromium.
6. `hx-sse` and `hx-status` under `default-src 'none'`, zero CSP violations; request-budget assertions green on the first journey.

## 6. Sources

htmx 4 docs (four.htmx.org/docs); GitHub Docs, Dependabot supported ecosystems; pip-audit
README; Mozilla HTTP Observatory scoring document and MDN tests-and-scoring page; DEV Week 1
rules and FAQ. All read on 9 Oct 2026.

## Delivery rule — required by Mats, 9 October 2026

Deliver each revision as one complete, versioned ZIP only. Include all current
planning documents, catalogues, review results and SHA256SUMS.txt inside it.
Do not attach individual documents, sidecar files or partial update bundles.
The ZIP is the authoritative handoff; provide one download link and a short
change summary. Verify its checksums before delivery. Keep reviews focused on
changed requirements, conflicts and outstanding proof; do not reopen settled
decisions without new evidence. This delivery change grants no build approval.
