> **These documents are the build specification for Wiggle Outside.** **Claude Code is the integration owner and runs the build; Codex reviews every integrated change; Mats approves product decisions, protected changes and the release, and he alone commits, signs, pushes, publishes and submits** (BUILD-PACKAGES §2, TC-003). There is no build orchestrator: [HERMES-P0.md](HERMES-P0.md) is a superseded appendix that binds nothing, and its load-bearing rules are re-homed to BUILD-PACKAGES §2.1, PLAN §8, §17 and ARCHITECTURE §7, §13.3. Round 8.7 adds [CONTRACTS.md](CONTRACTS.md) (shared interfaces) and [BUILD-PACKAGES.md](BUILD-PACKAGES.md) (work packages, file ownership, order, integration and release checks), reframes P1 as hypothesis H1 and refines D39 in PRODUCT-FIT, and integrates the visual design in DESIGN-SPEC. Planning or design approval is not permission to start implementation; Mats gives "kör" separately.
>
> **Baseline 8.20: final build specification.** One decision register (§0) and named prerequisites (§0.1); Mats's decision sheet, catalogue answers, integration lead (Claude Code, Codex reviewing), hostname `wiggle-outside.fly.dev` and the family night copy recorded. Approving the baseline and "kör" remain separate.
>
> Round 8.19 (reconciliation only): the independently hosted product (Fly.io → OpenRouter → pinned model provider) is the primary build path; local Ollama is optional and gates nothing. Findings table in REVIEW-RESULT. No new features; build, spending and deployment not authorised.
>
> Round 8.18: D39 and D40 accepted; energy copy set; catalogue review; Fly.io preferred host; problem statement first. Build not authorised.
>
> Round 8.17: visual direction approved, typography revised (D41), priority list of open questions in REVIEW-RESULT.
>
> Round 8.16: deployment corrections and one spending proposal for approval (DEPLOYMENT §1.5). Nothing bought or deployed.
>
> Round 8.15: Mats prefers O2 (a public planner on managed Gemma, independent of the workbench); DEPLOYMENT §1 now gives exact model, provider, costs and limit behaviour for his spending decision.
>
> Round 8.14 tightens DEPLOYMENT.md (O4 added, no default, restart-safe quotas, hosted inference contract, figures marked verified/estimate/unknown).
>
> Round 8.13 adds deployment options and hosted abuse/cost controls ([DEPLOYMENT.md](DEPLOYMENT.md), D48–D49), a connectivity statement and a bounded decision list. Not called build-ready.
>
> Round 8.12 is a correction round on 8.11 (status and response rules, idempotency fingerprint, session-bound retention, location-choice outcome, tighter cards, agent entry point [AGENT-BRIEF.md](AGENT-BRIEF.md)). Not called build-ready.
>
> Round 8.11 applies Mats's simplification decisions D43–D46 (no progress stream or Stop, no repair, D33 kept, immutable results with "Change answers" resubmission) across every document and the mocks.
>
> Round 8.10 adds a purpose-and-simplicity review of the diagrams ([SIMPLICITY-REVIEW.md](SIMPLICITY-REVIEW.md)) with seven proposals for Mats; no contract changed.
>
> Round 8.9 is a correction round: seven backend and interface findings fixed in their owning documents, a fixture walkthrough ([WALKTHROUGH.md](WALKTHROUGH.md)), a simpler form and results layout, and reproducible mock checks. Not called build-ready.
>
> Round 8.8 resolves seven integration points from the 8.7 review (see REVIEW-RESULT) and adds static mock screens in `mocks/`.
>
> Round 8.6 adds [PRODUCT-FIT.md](PRODUCT-FIT.md) (purpose, AI value, competition table) and [DESIGN-SPEC.md](DESIGN-SPEC.md) (implementable UI specification). Round 8.5 reconciled the 10 October [BACKEND-REVIEW.md](BACKEND-REVIEW.md) (B01–B16). Backend rules live in [BACKEND-CONTRACT.md](BACKEND-CONTRACT.md); status per finding is at the end of BACKEND-REVIEW. No approval or build authorisation is implied.

# Wiggle Outside: engineering plan

Status: **final build specification, baseline round 8.20** (Sat 10 Oct 2026). Approving this baseline and saying "kör" are separate actions by Mats. Changes after the baseline are tracked changes (CONTRACTS §10), not new planning rounds.
Design discussion comes before any repository or application code; the build starts only after
"kör". Deadline: **Mon 12 Oct 2026, 08:59 Swedish time** (Sun 11 Oct 23:59 PDT).

Round 8 adds the architecture contract and four diagrams in [ARCHITECTURE.md](ARCHITECTURE.md),
plus a detailed independent-review brief in [CLAUDE-REVIEW.md](CLAUDE-REVIEW.md).
It preserves the round 7.1 competition, security, audit and release requirements.
Round 8.1 adds the shared backend/frontend contract in [ERROR-HANDLING.md](ERROR-HANDLING.md).
Round 8.3 merges the reviewed 8.2 corrections and the request-budget and caching contract;
the review closure is in [REVIEW-RESULT.md](REVIEW-RESULT.md).
Decisions are recorded in the register below (§0); nothing is silently approved. This document
authorises no application code, deployment, publication or submission by itself.

## 0. Decisions log (the one current register)

Status words: **accepted** is binding; **deferred** is not in v1; **declined** is not
built; **blocked** names its prerequisite in §0.1; **superseded** is history. (The status word
**outside this package** is retired with TC-003: there is no separate workbench policy.) "Accepted
(baseline 8.20)" marks the established defaults that Mats closed with the 8.20 decision
sheet; any later change is a tracked change. Accepting a decision proves nothing about
the unbuilt application: it is verified only by its acceptance checks.

| # | Decision | Status |
|---|---|---|
| D1 | Primary user: a tired parent of young children. "Just me" is a second path on the same system. | **accepted** (baseline 8.20) |
| D2 | v1 scope: activities without a known admission charge (D37: never described as free unless OpenStreetMap reports `fee=no`, and then as "reported free admission"), walking distance, leaving now. | **accepted** (baseline 8.20) |
| D3 | Results: **up to** three grounded ideas. Never pad with a weak one. | **accepted** (baseline 8.20) |
| D4 | AI role: Gemma ranks up to three code-supplied, pre-validated activity-place pairs and, for each pick, chooses one reviewed story hook and up to two reason codes. Templates render the introduction; Gemma writes no free text shown to users. Its value is measured against the deterministic ranking (section 13). One inference attempt per planning attempt, no repair (D44). | **accepted** (baseline 8.20) |
| D5 | ~~Local-first; public demo with fixed inputs; recording shows local use.~~ **Superseded by D48 (8.15–8.19):** the product is an independently hosted public planner. | superseded |
| D6 | SQLite (stdlib) for app state. pandas, Polars and DuckDB only in the analysis group. | **accepted** (baseline 8.20) |
| D7 | One validated model response per request. No progress events or per-card streaming in v1 (D43). | **accepted** (baseline 8.20) |
| D8 | Strict automated checks plus documented design judgment; exceptions are written down, not hidden. | **accepted** (baseline 8.20) |
| D9 | **No build orchestrator (TC-003).** Claude Code is the integration owner: it builds WP0 and WP9, merges package output, wires `main.py`, and runs the gates and the test suite. Codex reviews every integrated change. Mats approves product decisions, protected changes (BUILD-PACKAGES §2.1) and the release, and he alone commits, signs, pushes, publishes and submits. `HERMES-P0.md` is a superseded appendix; its load-bearing rules are re-homed (BUILD-PACKAGES §2.1, §5; PLAN §8, §17; ARCHITECTURE §7, §13.3). | **accepted** (Mats, TC-003) |
| D10 | Weekend events (SearXNG) and offline OSM are out of v1. | **accepted** (baseline 8.20) |
| D11 | Contest: Week 1, Touch Grass. New application and repository within the entry window; one English submission with repository, demo and open-innovation explanation. | fixed contest requirements; section 14 |
| D12 | Security for the application and for the build environment on Mats's machine (TC-003), criterion-level accessibility evidence, and playful handcrafted design remain project requirements. Claims must match completed verification. | **accepted** (baseline 8.20) |
| D13 | CI workflows and policy tests are written fresh for this repo; the pattern from earlier projects is credited in the post, no private code copied. | **accepted** (baseline 8.20) |
| D14 | The activity catalogue is drafted by Claude and reviewed line by line by Mats before it is used. | **accepted**; catalogue answers recorded 8.20 (CATALOGUE-REVIEW §0) |
| D15 | Competition contract lives in `COMPETITION.md`; this plan keeps a summary. | **accepted** (baseline 8.20) |
| D16 | When weather cannot be fetched or is stale, the app recommends nothing, says why, and offers a retry. Self-reported weather is out of v1. | **accepted** (baseline 8.20) |
| D17 | Domain values are frozen dataclasses whose nested values are immutable too (tuples, frozensets). Protocols use PEP 695 generics only where a boundary needs a type parameter (Python ≥ 3.12; the pin is whichever D29 version Mats accepts). No Memento or undo state in v1. | **accepted** (baseline 8.20) |
| D18 | Energy is a ceiling: `moderate` includes `gentle`, `energetic` includes both; the user-facing labels are Gentle / Moderate / High (TC-001). Ranking prefers the requested level, and the card says when picks are gentler than asked. Age compatibility stays mandatory for every selected band. | **accepted** (baseline 8.20) |
| D19 | Supply chain blocks on any known vulnerability, any severity, with or without a CVE ID. Scans on every PR, daily on main, and before release; a failed or unavailable scan means "not verified", never green. | **accepted** (baseline 8.20) |
| D20 | The deployed public planner (`wiggle-outside.fly.dev`, D27) must score 145/145 (A+) on MDN HTTP Observatory, measured on the deployed response headers. 145 is the maximum. | **accepted**; release requirement, verified only on the deployed host (D27) |
| D21 | One application worker, one SQLite worker and one open model request in v1 (ARCHITECTURE §2.1); scaling requires revisiting process-local guarantees. | **accepted** (working default, Mats 8.20) |
| D22 | Use the explicit job lifecycle, bounded retention/cache, cancellation and transport contracts in ARCHITECTURE sections 3–7. | **accepted** (baseline 8.20) |
| D23 | Six named runtime dependencies initially; standard library for persistence/concurrency; analysis/build/security tools stay outside the runtime image. | **accepted** (baseline 8.20) |
| D24 | ~~Public fixed-data replay demo as the default.~~ **Superseded by D48:** the live hosted planner is the demo; the replay demo is an inactive alternative. | superseded |
| D25 | Four diagrams, a requirement-to-evidence register, a controlled quantization comparison (conditional: if cut, the evidence states it was not done) and documented recovery are required planning/evidence work. | **accepted** (baseline 8.20) |
| D26 | Backend and frontend share a typed, accessible error/recovery contract: truthful messages, preserved recoverable input, bounded retries, safe diagnostics and tests for each failure path. It must preserve all contest and safety constraints. | **accepted** (baseline 8.20) |
| D27 | Observatory criterion check. **Intended hostname (Mats 8.20): `wiggle-outside.fly.dev`**, if available (no domain purchase). Before the release gate is final: confirm the name is free, then run Observatory against the deployed host and check how its HSTS preload criterion treats the host (the `.dev` top-level domain is preloaded as a whole; whether Observatory credits that is **unknown** until measured). If that host cannot carry the preload bonus by the deadline, Mats decides between a different host and a revised criterion; until then D20 stands unchanged. | **blocked** until hostname verification (prerequisite P3, owner Mats) |
| D28 | ~~Execution fallback: Claude Code in one rootless container, accepted only after a read-only Hermes inventory.~~ **Declined (TC-003):** it was the fallback to an orchestrator that is not used. The execution model is now stated plainly in D9 — Claude Code runs the gates on Mats's machine under his review, and Mats alone commits, signs and pushes. The controls that mattered are re-homed: protected inputs and stop conditions in BUILD-PACKAGES §2.1, hash recording in PLAN §8. | **declined** (TC-003) |
| D29 | Python 3.14 is the pin for v1; a bootstrap failure on a required wheel triggers a recorded decision, not a silent switch. | **accepted** (baseline 8.20) |
| D30 | Seasons come from the date and the hemisphere of the rounded location (meteorological seasons); equatorial regions get no season-restricted activities. English copy, metric units. | **accepted** (baseline 8.20) |
| D31 | Session and CSRF: opaque server-side session in a `__Host-` cookie (Secure, HttpOnly, SameSite=Strict, Path=/, no Domain); per-session CSRF token in every form; `hmac.compare_digest`; Origin check. Standard library only. | **accepted** (baseline 8.20) |
| D32 | Deadline budget inside 20 s: geocode 3 s, places and weather concurrently 4 s, queue + model 11 s (no repair, D44), 2 s reserved for fallback and render; each stage gets min(budget, remaining). Not measured. | **accepted** (working default, Mats 8.20); budgets are not measurements |
| D33 | Purposeful, bounded requests and caching: the request budget and cache contract in ARCHITECTURE sections 14–15 are mandatory and asserted in CI with mocked providers and browser network inspection. | **accepted** (baseline 8.20) |
| D34 | Optional intent preloading of small, allowlisted same-origin static UI assets only; never geolocation, provider calls or Gemma. Hover delay and byte limits are proposals to measure. Not needed while the quiz is a single page. | **deferred** (Mats 8.20); not in v1 |
| D35 | "Half day" means 4 hours (time from leaving to coming back). | **accepted** (working default, Mats 8.20) |
| D36 | No two cards in one result share an activity; the same destination may appear twice. | **accepted** (working default, Mats 8.20) |
| D37 | Unknown admission fees: (a) verified free only (`fee=no`), or (b) exclude places tagged `fee=yes` and label unknown fees "Admission not verified". **Chosen (8.20): (b)**: exclude places tagged `fee=yes`; label unknown fees "Admission not verified" (full label); `fee=no` is described as "reported free admission", never as verified; the post says so too. | **accepted: option (b)** (Mats 8.20) |
| D38 | Model endpoint for local development and testing only (production model access is D48): a dedicated Ollama instance or a scoped proxy that allows only generation for the pinned model, bound to host loopback (ARCHITECTURE §7, TC-003). No shared service is reconfigured silently. | **deferred** (Mats 8.20); gates nothing |
| D39 | Optional "What are they into?" field (≤ 120 characters). In the same single model call that ranks the eligible pairs, Gemma infers at most three tags from a fixed 14-tag vocabulary (or no match / unclear); code validates tags and picks and derives `matches_interest` itself. Evaluated in English, Swedish and French only. Tags are shown as inferred, display-only labels; changing them is an explicit resubmission through "Change answers" (D46). Interests affect ranking only, never eligibility. Free text is untrusted data, never logged or cached; it goes to the model only (through OpenRouter to the pinned model provider in the hosted product) and never to the place or weather providers (ARCHITECTURE §2 recipient table). Contract: PRODUCT-FIT §3. Tests hypothesis H1. | **accepted by Mats 8.18** |
| D40 | Product name "Wiggle Outside" (replaces the working title touchgrass in user-facing copy). **Bootstrap answer (TC-005):** repository `wiggle_outside`, Python package `src/wiggle_outside/`, session cookie `__Host-wo_session`. Decided before kör, so no package agent works against the old name. | **accepted by Mats 8.18**; names **accepted** (TC-005) |
| D41 | Typography (revised 8.17): Cabinet Grotesk for headings and activity titles at weight 800, Switzer for body (400), labels (500) and buttons (600); two self-hosted WOFF2 files supplied by Mats, `font-display: swap`, system fallbacks. **Closed by TC-007:** both files are the *variable* faces from fontshare.com (`wght` 100–900, 85 KB together, not the 64 KB estimated); glyph coverage passes for English, Swedish and French; the Fontshare FFL 2.0 licence permits self-hosting but **forbids redistribution in a public repository**, so the files are gitignored and supplied at deploy time; a metric-matched fallback cancels the layout shift. Shantell Sans superseded. | **accepted** (Mats 8.20); P1 **resolved** (TC-007) |
| D42 | The optional panel separates two needs. "We're bringing a stroller" keeps only activities with `activity_suits_stroller = true`. Step-free access is a **preference (P, chosen 8.20)**, labelled "Prefer places reported as step-free": places OpenStreetMap reports as step-free rank first; unknown access can still appear and is labelled "Step-free access not verified". Stroller suitability stays separate. (The requirement variant R is not built.) | **accepted: preference (P)** (Mats 8.20) |
| D43 | v1 has no live progress stream (SSE) and no user-facing Stop. POST `/plan` waits and answers 303 to the result; with JavaScript a busy state shows at once; no polling. Kept: the deadline, the bounded model queue, internal cancellation and cleanup at deadline and shutdown, duplicate-submission protection, recovery after a lost response (resubmit joins the same job) and model-slot ownership until inference finished or cancellation is verified. (Simplicity review S1.) | decided by Mats 8.11 |
| D44 | No model repair attempt. One inference attempt, validation, partial success kept, otherwise the labelled eligible fallback after the normal weather and eligibility checks. A frequent invalid-output rate in the smoke test or evaluation is investigated and fixed (prompt, schema, output budget, model configuration), not hidden. Amends D4 and D32. (S3.) | decided by Mats 8.11 |
| D45 | D33 is kept in full: single flight and the bounded negative cache (written only after the final attempt) stay with pacing and cooldowns, compactly, in the provider wrapper. Rate limits do not replace duplicate-fetch prevention. (S5 rejected.) | decided by Mats 8.11 |
| D46 | Results are immutable. Inferred interests are display-only labels; changing them, or any answer, is an explicit resubmission through "Change answers": other answers and the location coordinates are carried, the interests field is prefilled with the tag labels, a new idempotency key is used, fresh caches are reused, and the previous result stays readable unchanged until `retain_until`. Removes the re-sort route and idea snapshots. (S7.) | decided by Mats 8.11 |
| D47 | ~~Functional UI icons (location pin, clock, weather, info, check, alert, print) may come from Rune Icons: a small selection of exported outline SVGs, whose icon assets are Apache-2.0 (the website and editor code carry extra Attribution and Commons Clause terms and are not used). Each SVG is inspected (no scripts, external references or filters), normalised to `currentColor` in our self-hosted sprite, and its source repository, commit, file names and licence are recorded in `docs/evidence/attribution.md`, with the Apache-2.0 licence text shipped. No package or runtime dependency. Decorative tape and doodles stay original. The outline style is not hand-drawn, so this trades some personality for consistency.~~ **Declined for v1:** the small original SVG set in DESIGN-SPEC §3 is used. | **declined for v1** (Mats 8.20) |
| D48 | Deployment of the finished product, independent of the build machine (no tunnel, no shared inference endpoint, no dependency on Mats's computer). Mats's preferred direction (8.15): **O2**, a public planner using Gemma 4 26B A4B through OpenRouter with one pinned endpoint (8.16 proposal: DeepInfra, after two privacy confirmations; Google as alternative), on one Fly.io Machine (Mats's preference 8.18; Hetzner CX23 as alternative), with the D49 limits. Alternatives: O4 (self-hosted E4B on a rented GPU, unspecified) and O1 (recording only, as a fallback). O3 removed. Exact costs and limit behaviour in DEPLOYMENT §1. Planning only: no purchase or deployment until Mats approves spending. | **accepted** direction (Mats 8.15; Fly.io 8.18; hostname 8.20); spending and deployment **blocked** on prerequisite P2 |
| D49 | Hosted product: abuse and cost controls in DEPLOYMENT §2 — per-network counters with bounded storage, a restart-safe daily planning allowance charged once per run, the provider key cap, the honeypot as a supplement with a recovery path, and the hosted inference contract in §3 — reconciled with the existing limits. | **accepted** for the hosted product (baseline 8.20); values are starting limits, changed only by a tracked change |


### 0.1 Build and release prerequisites (cannot be closed by editing documents)

| # | Prerequisite | Owner | Blocks | Not blocked |
|---|---|---|---|---|
| P0 | Approval of this baseline and "kör" for M0 | Mats | all application work | — |
| P1 | ~~Cabinet Grotesk and Switzer WOFF2 files and their licence, then glyph-coverage and layout-shift checks (D41)~~ **RESOLVED (TC-007):** files supplied; licence is Fontshare FFL 2.0, which permits self-hosting but forbids redistribution in a public repository, so the files stay out of git and are supplied at deploy time; glyph coverage passes in full (`scripts/check_fonts.py`); the metric-matched fallback neutralises the swap shift | Mats supplied; integration owner checked | nothing | — |
| P2 | DeepInfra's two privacy answers (DEPLOYMENT §1.1), then Mats's spending approval (§1.5) | Mats | hosted model smoke, Fly deployment, hosted verification | all fixture-based work |
| P3 | Hostname: confirm `wiggle-outside.fly.dev` is available; after deployment, Observatory 145/A+ on that host (D20, D27) | Mats chooses; WP9 verifies | release gate | build |
| P4 | Runtime evidence: gates, hosted verification on the release image, deploy checks (ARCHITECTURE §2.1), accessibility checks, evaluation | integration lead (Claude Code) with the owning WPs; Codex reviews | release and submission | build |

## 1. Purpose and success

Help a tired parent choose a realistic outdoor activity quickly, then put the phone away.

- No account, no chat, no endless feed, no "regenerate" loop as the main interaction.
- The chosen idea works from one compact card without further AI.
- The app may honestly answer "nothing suitable right now".

Success = someone chose an idea and went outside. Speed, coverage and Lighthouse support
that outcome; they do not replace it.

## 2. Product contract

### 2.1 Quiz (defaults keep it to four taps)

| Input | Values | Default |
|---|---|---|
| Who | Just me / Me + kids, with age bands 0–2, 3–5, 6–9, 10–12 (several allowed) | none, required |
| Time from leaving to coming back | 30 min / 1 h / 2 h / half day (4 h, D35) | none, required |
| Energy (most effort wanted; see D18) | Gentle / Moderate / High (TC-001) | Moderate |
| Where | "Use my location" or a typed town/area | none, required |
| Anything to account for? (optional panel) | "We're bringing a stroller" (filters activities, D42) · "Prefer places reported as step-free" (ranks reported step-free places first; never a filter; never verified, D42 P) | both off |
| What are they into? (optional, D39 only) | Free text ≤ 120 characters; inferred tags shown as display-only labels (D46) | empty |

Fixed in v1: walking, no known admission charge (D37), leaving now, nothing required beyond everyday clothes. Items such
as crayons or a blanket are listed as optional, with an alternative. No names, no exact ages.
With several age bands selected, an activity qualifies only if it lists **every** selected band.

### 2.2 Result contract (each idea)

- Activity and why it fits these answers.
- Place name, kind (park, playground…) and approximate straight-line distance, labelled
  as such. If no place qualifies: a clearly labelled generic idea without a destination.
- Activity duration and, separately, an estimated travel time (straight-line distance at a
  conservative speed). The card says it is an estimate; the return time is not guaranteed.
- A playful introduction rendered from the story hook and reason codes Gemma chose, then the
  catalogue's steps, optional items, adaptation, safety note and question, all verbatim.
- Weather for the outing window, with the time it was checked, shown once above the ideas (they share one window) and in full on each detail and print view. There is no unchecked-weather result (D16).
- Known unknowns: "Access and facilities not verified". Where OSM has a tag, the card says
  "OpenStreetMap reports step-free access", never "step-free".
- "Choose this" opens a readable, printable card. Once loaded, the card needs no AI and remains readable without network; browser print/save-to-PDF is supported. Offline reload is outside v1 (contract in ARCHITECTURE section 8).

### 2.3 Copy tone (to review with the mock screens)

- Quiz: "Who's coming along?" → "Just me" / "Me and the kids"
- Waiting and fallback: superseded in 8.7 by the copy deck in DESIGN-SPEC §9 and the
  approved error copy in ERROR-HANDLING §2 (the busy state is static, D43).
- Nothing found: ~~"Nothing great nearby for the next hour. Try a longer outing or another
  spot?"~~ superseded; it offers an edit as a fix for limits the run may never have
  evaluated (ERROR-HANDLING §1, TC-002). Use the ERROR-HANDLING §2 copy.

## 3. What AI does and does not do

| Responsibility | Owner |
|---|---|
| Geocode a typed place; fetch candidate places; fetch weather | integrations |
| Turn time budget, energy and ages into constraints | core (pure) |
| Filter the reviewed activity catalogue by age, energy and weather rules | core (pure) |
| Rank candidate places by distance and fit; cap at 8 | core (pure) |
| Build the list of compatible (place, activity) pairs, max 12 | core (pure) |
| Rank up to 3 pairs; per pick choose a story hook ID and up to 2 reason codes | **Gemma** |
| Check every returned pair, hook and reason code is in the supplied sets; no duplicates | core (pure) |
| Supply, per pair, the hook IDs and reason IDs that are true for it | core (pure) |
| Render introductions from reviewed hook templates (`planner/hooks.toml`) | web templates |
| Render cards and all factual labels (distance, weather, uncertainty) | web templates |

The **activity catalogue** (`planner/activities.toml`) is written and reviewed by a human:
each entry has age bands, energy, weather limits, duration range and its own safety note.
Gemma's output is a list of IDs, so no model-written text is displayed. Display text comes
from the reviewed catalogue and hooks; place names come from OpenStreetMap and are rendered
as plain-text labels capped at 60 characters, escaped once at render. Code supplies each pair's own allowed hooks and
reasons, and validation checks every pick against that pair's sets:
- hooks marked `needs_destination` only for pairs with a destination (hooks are fixed sentences without placeholders since 8.12);
- `no-destination` only for generic pairs, which carry an explicit absent destination;
- hooks restricted by energy (such as `slow-reset`) only for activities at that level;
- `places = ["any"]` means any supported, eligible place kind, never anywhere at all.

Risk is controlled by construction, not by filtering prose. The model's contribution is
the choice and ordering, which the evaluation in section 13 compares with the
deterministic ranking.

**Weather rules** (core, pure; interval semantics and exact predicates in BACKEND-CONTRACT §1): severe conditions exclude every activity (thunderstorm,
freezing rain or heavy snow weather codes; wind over 50 km/h). A global heat rule excludes
everything when apparent temperature exceeds 30 °C with kids or 32 °C alone, unless an
entry sets a lower `max_temp_c`. Per-entry limits apply on top. All thresholds are
provisional product limits awaiting review, not established safety boundaries; passing
the filters does not make an outing safe, and the card never claims it does.

## 4. Failure policy

Detailed contract: [ERROR-HANDLING.md](ERROR-HANDLING.md). It defines stable error codes,
reviewed messages/actions, transport/status behaviour, accessibility, retry ownership and
acceptance evidence. The table below summarizes outcomes; it does not replace that contract.

| Situation | Behaviour |
|---|---|
| Model unavailable or over its budget (20 s end-to-end, including queueing) | Deterministic ranking of the same pairs; introductions from templates. Labelled "picks from our activity list". |
| Invalid model output | Invalid picks dropped; valid ones kept; none left → the fallback above, no repair (D44). Invalid outputs are counted by reason. |
| Returned pair not in the supplied list | Drop that idea; never repair by guessing. |
| Weather unavailable or older than 30 min (BACKEND-CONTRACT §1) | Recommend nothing, explain that conditions could not be checked, offer a retry (D16). |
| No candidate places | Generic pairs (absent destination) with the `no-destination` hook, or a prompt to widen time or area. |
| Fewer than three suitable ideas | Show fewer. |
| All ideas fail the rules | Explain that nothing suitable was found and what to change. |
| Places service fails | Cached result if under 7 days old, shown with its age; otherwise the generic path. |
| Geocoding fails or is ambiguous | Distinguish no match, ambiguity, denial and service failure; present relevant manual/location/retry actions and at most five matches only when matches exist. |
| Response lost (connection drops while the POST waits) | The job continues to its original deadline. Resubmitting the same form (same key and answers) joins it or returns its result; no new model call (D43). |
| Double submit | Same session/key/input joins or returns the existing job; changed input with the same key is rejected; expired jobs require explicit new submission. |
| Generation slot busy | Wait within the original deadline behind the busy state; at capacity reject admission with a recoverable busy state. No repeated POST/model starts. Eligible fallback on model-budget exhaustion. |

Fallbacks obey exactly the same rules as generated results.

## 5. Location, sources and privacy

**Location**
- "Use my location": the browser rounds coordinates to 2 decimals (~1 km) in `app.js`
  before sending; the server rounds again and rejects out-of-range values.
- Typed place: server-side Nominatim, one request per search (no autocomplete), with an
  identifying User-Agent, max 1 req/s, results cached 30 days, OSM attribution shown.
- Trade-off accepted: ~1 km precision. Distances are labelled "about X km as the crow
  flies". No walking time is promised; travel is estimated conservatively at 3 km/h
  with kids, 4.5 km/h alone, and stated as an estimate.

**Places**: Overpass, radius derived from the time budget (max 3 km), kinds: park,
playground, nature reserve, forest, picnic site (viewpoints and beaches are out of v1:
heights and water edges). Filtering by OSM kind and the catalogue's instructions reduce
exposure; they do not verify that a park has no pond, slope or road. Centre points are not
entrances. Missing access tags mean unknown. Private, closed and fee-charging places follow
BACKEND-CONTRACT §8 and D37. Cache: 7 days per rounded location + radius.

**Weather**: Open-Meteo hourly and daily (sunrise/sunset) variables for the outing window,
with the request, interval mapping, units and 30-minute freshness defined in
BACKEND-CONTRACT §1.
Thresholds per activity live in the catalogue, reviewed by a human.

**Privacy promises (each one testable)**
- Ages, answers and generated cards are not persisted by default. Bounded transient memory for jobs/results is disclosed and expires according to BACKEND-CONTRACT §2 and §4.
- One exception, disclosed on the form: a typed town or area is cached for up to 30 days as a hash of the query with its rounded coordinates and label, never the raw text (BACKEND-CONTRACT §9).
- Browser-derived coordinates are rounded before transmission. Typed town/area text
  goes to Nominatim; rounded search coordinates go to places/weather services. Those
  providers also receive ordinary network metadata. In the hosted product (primary path)
  the model prompt, including any interest text, goes through OpenRouter to the pinned
  model provider; the full recipient table is ARCHITECTURE §2. No claim of local
  processing is made.
- Logs contain request IDs, timings and outcomes. Never prompts, coordinates or answers.
- Optional feedback ("liked it / so-so") stores activity ID and timestamp only.
- "Open in map" is a plain link to openstreetmap.org, opened only on click, and labelled.
- No analytics, no error-reporting service, no third-party assets. Fonts are self-hosted.
- The OpenRouter key is a Fly secret; one pinned endpoint, no fallbacks (DEPLOYMENT §3).
  Dev-only: a local Ollama, if used, is bound to 127.0.0.1.

## 6. Architecture

| Part | Responsibility |
|---|---|
| `core` | Domain values, constraints, pure decisions (filter, rank, validate). |
| `planner` | Runs the outing workflow; declares the capabilities it needs in `planner/ports.py`. |
| `integrations` | Translate Nominatim, Overpass, Open-Meteo and the hosted model (OpenRouter) into application types; an Ollama adapter is optional for development. |
| `storage` | SQLite: cache and optional feedback, grouped by need, not by table. |
| `web` | Parse requests, render HTML, map outcomes to pages and statuses. |
| `main.py` | Build services and resources, own their lifecycle. Other modules still create domain objects freely. |

**Runtime detail:** [ARCHITECTURE.md](ARCHITECTURE.md) defines the lifecycle, transport, bounds, modes and diagrams (accepted, baseline 8.20).

**Lifecycle (FastAPI lifespan)**: one `httpx.AsyncClient` (pooled, timeouts, response
size cap), one SQLite connection, one model client, one generation semaphore (size 1).
All are created at startup and closed at shutdown. App health and model readiness are
separate endpoints; the app starts and serves fallbacks without a model.

**Concurrency**: places and weather run concurrently. Each provider returns a typed
`Ok | Unavailable` result instead of raising, so one failure never cancels the other.
No database lock is held during HTTP calls or generation. SQLite runs on a dedicated
single-thread executor (`ThreadPoolExecutor(max_workers=1)`) that creates, uses and closes
the connection, so ownership is guaranteed rather than assumed (`asyncio.to_thread` does
not promise the same thread twice).

**Transport** (D43): one owned job is awaited by the POST in both paths; the planner
returns a `PlanResult`; `web` answers 303 to the result page. The whole flow works as a
plain form POST; htmx only adds the busy state and swaps the result region. No event
stream.

**Import-linter contracts**
- Layers: `web → planner → core`; `integrations` and `storage` sit beside `planner`.
- Forbidden: `core` may not import `fastapi`, `httpx`, `sqlite3`, `jinja2`.
- Independence: the four integrations may not import each other.
- Only `main.py` imports from `integrations` and `storage`.

### 6.1 Tree

```
wiggle_outside/
├─ README.md · LICENSE (Apache-2.0) · SECURITY.md · .env.example
├─ docs/  PLAN.md · COMPETITION.md · ARCHITECTURE.md · decisions/  (HERMES-P0.md: appendix)
│         deliveries/ · post/ · evidence/ · drafts/
├─ src/wiggle_outside/
│  ├─ main.py               build and wire; lifespan
│  ├─ settings.py           one typed Settings; split only when a group earns its own file
│  ├─ core/
│  │   ├─ types.py          shared domain types (CONTRACTS §2)
│  │   ├─ errors.py         ErrorCode (CONTRACTS §3)
│  │   ├─ answers.py        quiz values and constraints derived from them
│  │   ├─ activities.py     catalogue entries and matching rules
│  │   ├─ places.py         candidate places, distance, ranking
│  │   ├─ weather.py        outing-window summary and limits
│  │   ├─ ideas.py          idea, card, validation of model picks and interests
│  │   ├─ ranking.py        deterministic ranking (fallback and H1 baseline)
│  │   └─ result.py         Ok | Unavailable
│  ├─ planner/
│  │   ├─ ports.py          what the planner needs (Protocols)
│  │   ├─ plan_outing.py    the workflow; yields events
│  │   ├─ jobs.py           job registry, idempotency, admission, lifecycle
│  │   ├─ catalogue.py      loads and validates the two TOML files
│  │   ├─ schema/           model output schemas selection.v1/v2 (CONTRACTS §6)
│  │   ├─ fallback.py       deterministic ideas with template wording
│  │   ├─ activities.toml   human-reviewed catalogue
│  │   ├─ hooks.toml        reviewed story hooks and reason codes
│  │   └─ prompts/          versioned prompt files
│  ├─ integrations/  nominatim.py · overpass.py · open_meteo.py · openrouter.py · (ollama.py, dev only)
│  ├─ storage/       sqlite.py · cache.py · feedback.py · migrations/
│  └─ web/           routes/ · forms.py · views.py · presenters.py · copy.py · security.py · templates/ · static/
├─ frontend/  css/ (tokens · base · components/ · utilities) · js/ (app.js · components/)
├─ tests/     mirrors src/ · contract/ · acceptance/ · policy/ · eval/ (real-model set, not in CI)
├─ analysis/  benchmark notebooks/scripts: pandas vs Polars vs DuckDB on the same data
├─ scripts/   check.ps1 · release.ps1 · check_contrast.py · benchmark.py
└─ pyproject.toml · uv.lock · package.json · bun.lock · bunfig.toml
   ruff.toml · mypy.ini · pytest.ini · .importlinter · .python-version
```

## 7. Code style

From the ArjanCodes Game of Life roast (`ArjanCodes/examples/2024/golroast`, before and
after, read in full) and his published principles:

- Functions for stateless transformations; classes for real state, invariants or a
  resource lifecycle. A class holding one static method is a function.
- Strategies as functions behind a PEP 695 `type` alias (the roast's rules; our matching
  rules).
- Split by reason to change. Every new module states its responsibility in one line.
- Dependencies are passed in; `main.py` assembles services.
- Protocols at real boundaries (what we replace or fake in tests), owned by the consumer.
  No interface around every helper.
- Talk to an object, not through it; hide iteration details behind iteration.
- Early returns; guards are allowed to exceed the return budget when they read better.
- Comments: short, one line, only where intent or a constraint needs explaining. No
  generated commentary, section banners, narration of the obvious, commented-out code,
  TODOs or speculative helpers. Longer explanations go in docs. Licence notices stay.
- FastAPI routes stay thin: parse, call the planner, render. Rules live in core and planner.
- Templates: semantic HTML, labelled controls, components only where repetition warrants.
- Tailwind and CSS: design tokens only, no unexplained magic values, no `!important`,
  no conflicting utilities on one element; component CSS only where utilities repeat.
- No inline scripts, event handlers or styles anywhere, including to escape the CSP.

## 8. Quality gates

**Hard, automated (fail the build).** The full set below is the target. **M0 ships five of
them — ruff, mypy, import-linter, pytest and the contract tests — and WP9b adds the rest
in parallel with WP1–WP8 (TC-006, BUILD-PACKAGES §3.1). Nothing is released, deployed or
called supply-chain verified until WP9b is green.**

- `ruff format --check`; `ruff check` with `select = ["ALL"]` and a justified ignore list
  (`D1`, `COM812`, `ISC001`, `CPY001`; tests also ignore `S101`, `PLR2004`).
- mypy strict, `warn_unreachable`, extra error codes; `disallow_any_explicit` in `core`
  and `planner`, plus `disallow_any_expr` in `core`.
- Function shape via ruff: complexity 6, 5 args, 8 branches, 30 statements.
- Import-linter contracts (6).
- pytest: strict markers/config, warnings as errors, random order, 5 s timeout, no real HTTP.
- Coverage by scope: three `coverage report --include=… --fail-under=…` runs
  (`core` 100, `planner` 95, total 90).
- djLint (templates), Biome (JS), Stylelint with a Tailwind v4-aware config (CSS), Tailwind
  production build, AAA contrast script on token pairs.
- Runtime CSP test: render every page in Playwright, assert zero CSP violations.
- Policy tests: SHA-pinned actions, workflow permissions, no inline script/style in
  templates, source budgets (maintained source only, with `docs/decisions/budget-exceptions.md`
  as the allowlist), direct runtime dependencies ≤ 8 unless a specific dependency-budget exception is approved and recorded; no custom security code to evade the budget.

**Review (checklist in every LEVERANS)**: cohesion of new modules, migration scope,
prompt and catalogue changes, copy tone, accessibility of new UI.

**Targets with documented exceptions**: module ~150 lines, function ~25 lines.

**Pinned tools**: uv, bun, Python, PowerShell 7, ruff, mypy, import-linter, djLint, Biome, Playwright.

**Commands** (PowerShell 7, TC-004): `scripts/check.ps1` runs every local check above without modifying maintained
source; builds, coverage and reports write only to git-ignored output directories.
`scripts/release.ps1` builds the zip from an explicit manifest (includes `.env.example`,
excludes `.env`, caches, `data/`), unzips it into a temp dir and runs `check.ps1` there.
**One gate script, local and CI (TC-004):** CI runs on GitHub's Linux runners and invokes
the same `./scripts/check.ps1` with `shell: pwsh`, which `ubuntu-latest` has
preinstalled, so there is never a second gate list to drift. `check.ps1` therefore uses
no drive letters or backslash path literals, builds paths with `Join-Path`, invokes tools
through `uv run` and `bun run`, and fails the job on any non-zero exit. A policy test
asserts every workflow's gate step calls `./scripts/check.ps1` and that no workflow
inlines a gate command of its own.

**CI: required checks** (branch ruleset on `main`; PRs only; protected configuration needs review)

| Workflow | Enforces |
|---|---|
| `python.yml` | ruff format/lint, mypy, import-linter, pytest, scoped coverage |
| `frontend.yml` | djLint, Biome, Stylelint, Tailwind production build |
| `browser.yml` | Playwright journeys under the production CSP, CSP negative tests, axe, Lighthouse |
| `supply-chain.yml` | Runs the canonical audit procedure in ARCHITECTURE section 13.3, which installs nothing and executes no project code. Package-identity coverage per scanner scope is recorded; empty, missing or unsupported coverage fails. Runs on PRs, daily on main and before release |
| `dependency-review.yml` | `fail-on-severity: low`, scopes runtime, development and unknown |
| `security.yml` | CodeQL (`security-events: write`), gitleaks, zizmor |

Rules for every workflow: least privilege per job, actions pinned by full SHA, container
images by digest, timeouts, no `continue-on-error`, no `|| true`, no skipped job counted as
passing. Dependabot opens PRs for uv, bun, GitHub Actions and container images; they pass
the full gate set like any change. No blanket advisory ignores and no automatic audit fix
in CI: affected dependencies are fixed, replaced or removed; a disputed finding needs
evidence and Mats's written decision.

**CI trust model** (B12)
- Every PR workflow runs on `pull_request` with a read-only token and no secrets, on
  GitHub-hosted runners only; Mats's machine never runs CI for untrusted code.
  `pull_request_target` and `workflow_run` are not used.
- Protected inputs (BUILD-PACKAGES §2.1, TC-003) are listed with SHA-256 in `gates.lock`
  on main; the integration owner generates the file and Mats signs the commit that
  updates it. A
  `gate-integrity` check compares the PR's protected inputs with main's `gates.lock`; any
  difference fails unless the PR is a protected-change PR that updates `gates.lock` in a
  commit signed by Mats. Rulesets require signed commits on main. This is the solo-author
  control: a PR that weakens its own gates cannot pass without Mats's signed approval.
- Required checks attach to the exact commit SHA. Release builds never restore caches or
  artifacts produced by PR workflows.
- The first bootstrap PR, which creates the gates, is reviewed and signed by Mats before
  `gates.lock` exists; this is recorded in evidence.

**Release gate** (separate from merge checks; `release.yml`; B13):
1. All required merge checks pass on the release commit (a signed tag from main).
2. Build the release image once; record its digest and the source commit and config hash.
3. Scan that exact image archive with the canonical procedure (ARCHITECTURE 13.3); the
   vulnerability database must be at most 24 hours old. A pass for one digest never
   carries over to another. If the demo is not container-based, name the platform evidence
   that replaces the image scan.
4. Deploy that digest to the candidate demo environment.
5. Verify the candidate: headers after the hosting proxy (including error pages), the
   Playwright journeys, and the MDN Observatory score of 145/A+ (D20, D27).
6. Mark the release ready only after step 5 passes; promote the same digest.

The live site is never checked as evidence for new code. `preload` in the HSTS header does
not mean the domain is on browsers' preload list; the evidence records the actual
Observatory result and preload status.

## 9. Security

| Threat | Control | Test |
|---|---|---|
| Model or place names inject markup | Jinja autoescape, no `|safe`, plain-text fields with length caps | acceptance test with hostile strings |
| SSRF through user input | Upstream hosts fixed in settings; users send values, never URLs | unit test on adapters |
| Bad input | Pydantic enums and ranges for every field; body size limit | property tests |
| CSRF on POSTs | SameSite=Strict cookie token + Origin check | acceptance test |
| Resource exhaustion | Generation semaphore, queue limit, timeouts, response size caps | load test (concurrency 5) |
| Script injection | Strict CSP, no inline JS/CSS, Alpine only if a reviewed interaction requires it, then CSP-compatible build; no `hx-on` | runtime CSP tests, positive and negative |
| Supply chain | Lockfiles, `--locked`/`--frozen-lockfile`, bun min release age, audits, review install scripts | CI |
| Data leakage | Log allowlist; no answers/coordinates in URLs or logs | test asserting log fields |

**CSP follows the real data flow**

| Connection | Control |
|---|---|
| Browser → app (pages and form posts) | CSP: `default-src 'none'`; `script-src`, `style-src`, `img-src`, `font-src`, `connect-src`, `form-action`, `manifest-src` all `'self'`; `base-uri 'none'`; `frame-ancestors 'none'`; `object-src 'none'`; `upgrade-insecure-requests` on the demo |
| App → Nominatim, Overpass, Open-Meteo | Server-side allowlist in the adapters; never in browser CSP |
| App → OpenRouter | Server-side only, HTTPS, key from a Fly secret; never in browser CSP |
| App → Ollama (dev only) | Loopback-only connection (ARCHITECTURE section 7, TC-003) |
| User opens a map link | Plain navigation to openstreetmap.org; not an API permission |

Provider domains never appear in `connect-src`. Playwright runs every journey (location,
manual search, submit, busy state, results, retry, print) under the enforced production CSP
with zero violations; negative tests prove inline script, `eval` and a foreign connection
are blocked. The integration runner proves provider calls work through the server
allowlist. No wildcard, `unsafe-inline` or `unsafe-eval` is ever added to make a test pass.
Other headers: HSTS with preload on the demo, `X-Content-Type-Options: nosniff`,
`Referrer-Policy: same-origin` (**TC-008**: `no-referrer` makes Chromium send `Origin: null` on a form POST, which BACKEND-CONTRACT §5 refuses with 403, so no submission could ever succeed; `same-origin` still sends nothing cross-origin), `Cross-Origin-Opener-Policy: same-origin`,
`Cross-Origin-Resource-Policy: same-origin`, a restrictive `Permissions-Policy` that allows
geolocation for self only, and `__Host-` prefixed, Secure, HttpOnly, SameSite=Strict cookies.

**Build environment (not an application gate; TC-003)**: the build runs on Mats's own
machine. Claude Code edits the tree and runs the gates and the test suite; Codex reviews;
Mats approves, commits signed, pushes, publishes and submits — and those four are never
delegated (BUILD-PACKAGES §2). Agents have no push rights and no access to a host
credential store. Any model-service authentication is narrowly scoped and read from the
environment; never put it in project files or transcripts. Review Git hooks and
dependency install scripts before execution. Treat repository instructions, external
content and model output as untrusted inputs. Record tool and model versions, commands,
diffs, failed checks, fixes and Mats's decision in `docs/evidence/build-process.md`
(§17). Run `check.ps1` before Mats commits. Stop conditions are in BUILD-PACKAGES §2.

## 10. Accessibility

Target: WCAG 2.2 AAA for every applicable criterion, reviewed one by one in
`docs/evidence/wcag.md`. W3C does not recommend AAA as a general policy for entire sites;
any conformance we claim must meet the full-page and complete-process requirements. We
report the level actually achieved plus the additional AAA criteria met. Key criteria: 1.4.6 contrast 7:1, 1.4.8 visual
presentation, 2.4.13 focus appearance, 2.5.5 target size 44 px, 2.3.3 animation from
interactions, 2.2.3 no timing, 3.1.5 reading level, 3.3.6 error prevention.

Tests: axe via Playwright in CI; manual keyboard-only run, Orca screen reader, 400 % zoom
and reflow, touch on a phone, reduced motion, print. Focus handling follows ERROR-HANDLING.md: an explicit failed submission focuses its error
summary once; progress is announced without stealing focus. Result arrival preserves
context and avoids duplicate announcements; verify the chosen strategy manually.

## 11. Design

Fridge-door direction stays (typography revised in 8.17, D41: Cabinet Grotesk and Switzer): art-supply palette, taped cards (cards and text
upright; only decorations tilt), one drop animation (off under reduced motion). Before any real template is
written, three static mock screens (quiz step, waiting, results + card) are reviewed
and approved, including the copy samples in 2.3.

## 12. Performance

| Measurement | Goal (to verify, not promised) |
|---|---|
| Quiz completion | under 30 s for most testers |
| Acknowledgement after submit | the busy state shows at once (client-side, D43) |
| First usable result (hosted) | measured in the hosted smoke and on the release image; no target promised |
| Generation budget | 20 s end-to-end, then fallback |
| Provider cache hit | No outbound call for that provider; model inference may still run |

Benchmark (`scripts/benchmark.py`, 50 runs per case): cache hit vs
miss, time to validated result, total time, invalid-output and fallback rates, peak app memory,
1 vs 5 concurrent requests. Records the hosted model ID, pinned endpoint, `max_tokens`
and reported `usage`; dev runs on a local model record its digest separately and are never
presented as product measurements. Analysis compares pandas, Polars and DuckDB on the same data.

## 13. Acceptance scenarios (written before the code they test)

Location denied → manual path · toddler + stroller · ages 0–2 and 6–9 together · "just me", gentle, 30 min ·
no nearby places · unknown access tags · weather unavailable or stale (retry offered) · thunderstorm forecast · ages 0–2 with default energy (gentle picks, explained) · malformed model
JSON · invented place ID · valid JSON with an activity outside the catalogue · valid IDs forming an unlisted pair · unexpected model free-text fields and invalid hook/reason IDs ·
double submit · disconnect mid-generation · keyboard-only quiz · choose and print a card ·
no JavaScript at all.

D39 (accepted), also: interest text with a match · no match ("dinosaurs") · unclear
("everything") · negation only · injection phrase · model returns `matches_interest`
(dropped) · unknown tag (dropped) · tags shown as plain labels · "Change answers" with an
edited interest text (new key, coordinates carried, caches reused: model call only; the
old result unchanged) · text in a fourth language (processed, no support claimed).
Also: a lost response followed by resubmission joins the job (D43) · an output with no
valid pick goes straight to the labelled fallback (D44).
Also (8.20): family run after sunset or before sunrise → DAYLIGHT_NIGHT copy · family run
starting in daylight but ending after sunset → DAYLIGHT_TOO_SHORT copy, which offers no
shorter-outing remedy (TC-002) · a "Change answers" resubmission from a daylight-blocked
run re-runs every check and may clear it, or newly hit a weather limit it never reached
(TC-002) · solo run after
dark unaffected · ages 0–2 with 3–5 at 3 °C apparent temperature (baby-eligible entries
excluded below 5 °C) · `tree-twins` at 28 km/h excluded, `nature-bingo` at 28 km/h allowed.

Real-model evaluation: 20 reviewed scenarios with expected properties, run outside CI.
Each scenario is ranked by Gemma and by the deterministic ranking; Mats judges which list
is better without knowing which is which. Hook and reason-code choices are checked for fit.
The result goes into the post, whichever way it falls.

## 14. Competition compliance

Full contract: [`COMPETITION.md`](COMPETITION.md) (sections 14.1–14.7).

- Contest: Hacktoberfest Open-Source AI Challenge Week 1, Touch Grass. Closes **Mon 12 Oct 08:59 CEST**; our target 08:30.
- New project and new repository, started and finished inside the window (opened Mon 5 Oct 18:00 CEST).
- One English DEV post using the Week 1 template (adds `#devchallenge`, `#hf26challenge`), with demo and repo links.
- Open-source AI must be central: Gemma 4 (E4B, or the hosted size chosen under D48) ranks the eligible pairs and picks reviewed hooks and reasons; fallback clearly labelled.
- Explain why open innovation matters; credit every reused component and data source.
- Commits after the deadline are listed in the README; the submitted commit is tagged.
- Category: Best Use of Gemma, claimed in the post's Prize Categories section.
- Checks C01–C12 stay PENDING until evidence exists; nothing passes by assumption.

## 15. Delivery order and cut lines

Elapsed clock slots are replaced by dependency order (B16). Each step needs the previous
one; nothing in steps 2–7 starts before Mats's explicit kör. The primary path is the
independently hosted planner (D48); a local model is optional for development and gates
nothing.

**Build environment (TC-003):** the build runs on Mats's machine with Claude Code
integrating, Codex reviewing and Mats approving (BUILD-PACKAGES §2). The tools actually
used are recorded in `docs/evidence/build-process.md` (§17). No orchestrator readiness
check gates anything.

| # | Step | Done when |
|---|---|---|
| 1 | Design review | This set is reconciled, Mats's pending choices are made, three mock screens approved; CONTRACTS and BUILD-PACKAGES accepted |
| 2 | Bootstrap milestone M0 (time-boxed, TC-006) | WP0 and WP9a together (BUILD-PACKAGES §3.1): repository, contracts, lockfiles, configs, `check.ps1` with five gates, one CI workflow, `gates.lock`; Mats signs the baseline. Then WP1–WP5, WP7, WP8 and WP9b run in parallel |
| 3 | Hosted model smoke (needs Mats's spending approval and a key) | The pinned OpenRouter endpoint returns valid picks on fixture pairs within `max_tokens` 256 and the 10,000-byte request cap; `usage` and latency recorded; reasoning tokens zero. Runs in parallel with steps 4–5; without approval, steps 4–5 continue on fixtures |
| 4 | Deterministic flow | Quiz → catalogue → fixture places and weather → cards → print, no model |
| 5 | Real sources | Nominatim, Overpass, Open-Meteo under BACKEND-CONTRACT budgets |
| 6 | Model integration and deployment | Hosted adapter wired; picks, validation, fallback (no repair), deadline, invalid-output rate, evaluation set on the hosted model; Fly.io deploy per ARCHITECTURE §2.1 |
| 7 | Trial and release | Hosted model verification on the release image (a release requirement), outdoor trial, accessibility checks, release gate, write-up, submission |

The contest closes Mon 12 Oct 08:59 CEST. If the order above cannot reach step 7 in time,
Mats decides between a smaller entry and continuing as a portfolio project; the plan never
cuts a "never cut" item to meet the date.

Cut in this order if behind: feedback storage → quantization comparison → benchmark breadth (keep 10 runs) →
Lighthouse polish → print styling details. Never cut: meaningful open-source AI use,
grounding and validation, failure policy, required security controls, keyboard access,
honest labels, mandatory competition evidence, demo/repository links and the final English
submission. Any change to other agreed accessibility/security gates requires an explicit
planning decision and truthful claims. Do not label an incomplete entry compliant or
move it to another contest window by assumption.

## 16. Round 8.1 decision and review gate

1. Mats: app name, age bands, 20-second end-to-end budget, catalogue/hooks and provisional weather-limit review.
2. Mats with Claude's recommendation: public demo replay versus live inference; local same-machine access versus deliberate phone HTTPS access.
3. Claude: close ARCHITECTURE's request ownership/transport, cancellation, TTL/capacity, provider budgets, cache eviction and geographic-scope decisions. Proposed numeric budgets are not measurements.
4. ~~Mats: four HERMES-P0 confirmations (runner, credential mechanism, agent execution configuration and Ollama connection).~~ **Removed (TC-003):** there is no orchestrator to confirm. The execution model is D9; the local-model rule is ARCHITECTURE §7.
5. Claude: run the deep document review in [CLAUDE-REVIEW.md](CLAUDE-REVIEW.md); reconcile every finding across documents and return evidence-based closure.

Approval means no known unresolved design blocker. It does not mean zero undiscovered
bugs, zero vulnerabilities or already-verified infrastructure. Separate design approval,
bootstrap proof and release readiness. Application implementation still requires Mats's
explicit kör after the prerequisite gates.

## 17. Round 8 evidence register

| Requirement | Evidence location | Blocking phase |
|---|---|---|
| Four coherent diagrams and resolved runtime choices | ARCHITECTURE.md and docs/decisions/ | Design lock |
| Complete dependency purposes and compatible pins | docs/evidence/dependencies.md | Bootstrap |
| Tools actually used to build. `docs/evidence/build-process.md` records, per task (TC-003, re-homed from HERMES-P0 §7): tool and model versions, a prompt summary, files changed, check results, failures and fixes, and Mats's decision. Extracts are redacted before publication: no secrets, no home coordinates, no other projects, no family details | docs/evidence/build-process.md | Recorded at release |
| Canonical audit with package-identity coverage | docs/evidence/dependencies.md | Bootstrap and release |
| Model loads, uses intended backend and returns validated IDs | docs/evidence/model-smoke.md | Early model milestone |
| Lifecycle, cancellation, deduplication, weather and eligibility properties | tests/ and docs/evidence/runtime.md | Merge/release as applicable |
| Two-quantization comparison and resource contention (conditional, D25) | docs/evidence/benchmark.md | Release evidence if not cut; otherwise recorded as not done |
| Local/demo mode, CSP, privacy and accessible offline card | docs/evidence/browser.md and wcag.md | Release |
| Same-digest promotion, actual-host verification and recovery | docs/evidence/release.md | Release |
| Typed errors, usable recovery, retained inputs, accessible status and redacted diagnostics | ERROR-HANDLING.md and docs/evidence/errors.md | Merge/release as applicable |
| Request budget, cache bounds, coalescing and duplicate suppression | tests/ (respx call counts, Playwright network log) and docs/evidence/requests.md | Merge |
| Contest contract and truthful write-up | COMPETITION.md and docs/post/ | Submission |

Use existing tools for these checks where practical. Add no framework, broker, database
service or telemetry vendor solely to complete the register. Each package must have a
named purpose; long explanations stay in docs, source comments remain short and useful.

## 18. Baseline 8.20 change log

- One register: every active decision accepted, deferred, declined, blocked or
  superseded; §0.1 prerequisites P0–P4 with owners; AGENT-BRIEF status words match.
- Mats's answers: D37 (b), D42 P, D41 accepted with P1, D47 declined, D34 and D38
  deferred, D21/D32/D35/D36 kept; D9 integration lead Claude Code, Codex reviews; D27
  hostname `wiggle-outside.fly.dev`, blocked on P3.
- Catalogue answers applied to `drafts/activities.toml` (26 entries) and `hooks.toml`.
- Family night copy (DAYLIGHT_NIGHT, DAYLIGHT_TOO_SHORT) from the existing daylight
  check; mock `05-night.html`.
- Reviewer's mechanical corrections: WP10 excludes `deploy.md`; hosted-model evidence
  fields without a weight digest; rollback by verified image digest; token ceiling
  labelled an estimate; "Don't include personal details" hint and the "never receives"
  meaning; D27 kept visible.

## 18.0000000000000 Round 8.19 change log (reconciliation only)

- Primary path: ARCHITECTURE §2 hosted diagram and recipient table, O1/O4/D24 replay
  marked inactive; new §2.1 Fly.io operating contract (one Machine, one worker, `/data`
  volume, `Fly-Client-IP`, health check, restart, deploy/rollback, release checks).
- PLAN §15: no local GPU step; hosted smoke (after spending approval) and hosted
  verification on the release image; §5, §6, the tree, the CSP table and §12 updated to
  the hosted path; D5/D24 superseded by D48.
- Privacy: model provider versus place/weather providers distinguished (D39 text,
  PRODUCT-FIT §3.8, DESIGN-SPEC hints, BACKEND-CONTRACT town note, COMPETITION).
- BUILD-PACKAGES: WP5 owns `integrations/openrouter.py` and its tests (Ollama optional);
  WP9 owns `Dockerfile`, `fly.toml`, `docs/evidence/deploy.md` with acceptance; WP6
  separates SERVICE_LIMIT_REACHED from SERVICE_UNAVAILABLE; WP7 no early eviction, B2.
- DEPLOYMENT: B2 contract (owner, counting, overflow, 429 variants, tests, not a
  spending cap); "< $0.01" overshoot removed; $4.40 is an estimate with stated exposure.
- D42 kept explicitly pending in PLAN, CONTRACTS, DESIGN-SPEC, WP1 and the mock.
- CATALOGUE-REVIEW rewritten: no blanket approval; W1 = min(current, 30), tree-twins
  stays 25; A1 names two activities and their caregiver sentences; W3/W4 rationale and
  uncertainty.
- Mocks: Shantell removed (system-font placeholder disclosed), D39/D40 tags removed,
  hosted wording, compact layout; checks rerun.
- WALKTHROUGH in `hosted_live` with the daily-allowance reservations; CONTRACTS marks
  `replay` and `/examples` inactive and adds the B2 GET row.

## 18.000000000000 Round 8.18 change log

- D39 and D40 accepted by Mats. D37 kept as a proposal with the no-"free"-claim
  qualification. D42 clarified into preference or requirement for Mats to choose.
- Energy question: "How much energy today?", Gentle / Moderate / High, hint "We may
  suggest something gentler." (energy ceiling unchanged).
- Product problem statement first in PRODUCT-FIT and in the new submission draft.
- New CATALOGUE-REVIEW.md: age coverage, weather limits, adaptations, hooks, text fixes.
- Fly.io as the preferred host in the spending proposal; per-network page-request limit
  added because Fly shows no provider spending cap.
- Build still not authorised.

## 18.00000000000 Round 8.17 change log

- Visual direction approved by Mats (concept board in `mocks/reference/`); DESIGN-SPEC
  §1.5 says what is kept, humanised and not adopted.
- D41 revised to Cabinet Grotesk ExtraBold + Switzer Variable; Shantell superseded.
- Print may span pages; ambiguous-place choices never trap focus.
- Fly.io hosting figures added; post-writing guardrails added.
- Priority list of unanswered questions in REVIEW-RESULT.

## 18.0000000000 Round 8.16 change log

- Hosted input bound made enforceable (10,000-byte request cap, usage checked);
  reasoning tokens counted and disabled; per-run maximums recomputed.
- Provider privacy checked for OpenRouter, DeepInfra and Google; recommendation DeepInfra
  pending two confirmations; ZDR not set (no structured-output ZDR endpoint confirmed).
- Total-cost wording: VAT, IPv4 (€0.50), credit fee (5.5 %, min $0.80), domain,
  traffic; credits are not an absolute limit; auto top-up off.
- Network counters keep unexpired entries; overflow bucket for new addresses.
- Quota reservation is one conditional SQLite transaction; storage failure is
  SERVICE_UNAVAILABLE, not "wait until midnight".
- Local and hosted cancellation contracts separated.
- One spending proposal for approval (DEPLOYMENT §1.5).

## 18.000000000 Round 8.15 change log

- Mats chose the direction O2 and set the boundary: the product is deployed
  independently of the workbench. O3 removed; D38 limited to local development.
- DEPLOYMENT §1 specifies O2: model, pinned provider options with verified per-endpoint
  prices, VPS options with verified prices, per-run cost (typical and maximum), and
  spending-limit behaviour. The "$0.11/run" in the question to Mats was a mistake for
  "$0.11/day maximum" and is corrected there.
- No purchase or deployment is authorised.

## 18.00000000 Round 8.14 change log

- DEPLOYMENT.md corrected: added O4 (self-hosted E4B on a rented GPU, unknowns marked);
  no default deployment; every figure marked verified, estimate or unknown; latency claim
  removed; exact token-cost calculation, typical and maximum.
- Daily allowance made restart-safe (atomic, write-through SQLite, UTC rollover, fails
  closed); the separate model allowance removed (model calls ≤ runs; the key cap is the
  backstop); a table of which request charges which counter.
- Network-counter storage bounded; "five families" claim removed.
- Hosted inference contract (structured output, no provider fallbacks, limits, timeout,
  cancellation uncertainty, 402 and 429).
- Honeypot autofill made a test obligation, with a recovery path.
- `web/forms.py` ownership fixed (WP0); provider eligibility separated from traffic.

## 18.0000000 Round 8.13 change log

- New DEPLOYMENT.md: three deployment options with verified provider facts (D48),
  proposed hosted abuse and cost controls (D49), and the connectivity statement.
- Honeypot field, per-network limits, daily allowances and SERVICE_LIMIT_REACHED added
  to the contracts as hosted-mode proposals.
- PRODUCT-FIT §5 now separates official rules, engineering commitments and missing
  evidence.
- Routine items closed as engineering defaults: S2, S4, S6 kept as specified;
  `retain_until` = 60 min.
- Bounded owner-decision list in REVIEW-RESULT.

## 18.000000 Round 8.12 change log

- Removed-behaviour leftovers fixed (cancellation access, progress reconnect tests).
- SIMPLICITY-REVIEW split into binding current state and historical review; withdrawn
  recommendations marked.
- CONTRACTS §3 now states which response carries each status (POST table, GET table),
  full pages only, and one uniform 422 for location candidates.
- Idempotency fingerprint defined (HMAC over the canonical form, including interests).
- Results live until the earlier of `retain_until` and session end; walkthrough follows
  the idle session to its end.
- "Change answers" cost stated precisely; prefilled interests labelled as recognised tags.
- Cards tightened; hooks are fixed sentences without placeholders.
- New AGENT-BRIEF.md entry point; proposed D47 (Rune Icons SVGs).

## 18.00000 Round 8.11 change log

- Mats's decisions on the simplicity review recorded as D43 (no SSE or Stop), D44 (no
  repair; amends D4, D7 and D32), D45 (D33 kept) and D46 (immutable results; interests
  changed through "Change answers").
- Applied across all documents, the walkthrough (new step 10: "Change answers" makes only
  the model call; 10a: lost-response resubmission joins) and the mocks.
- Removed endpoints, modules, types, bounds and screens are listed in REVIEW-RESULT.

## 18.0000 Round 8.10 change log

- New SIMPLICITY-REVIEW.md: keep / simplify / remove / decision verdict for every
  diagram component, trace findings, and proposals S1–S7 (not applied).
- ARCHITECTURE §2 and §5 diagrams brought in line with the contracts (build subgraph
  removed; domain names updated).

## 18.000 Round 8.9 change log (correction round)

- Seven build-blocking findings corrected in their owning documents: weather_code instant
  sampling, provider gate on every attempt with full Retry-After, idea snapshots,
  location-choice idempotency, complete presenter inputs, valid_until versus
  retain_until, escape once at render (correction log in REVIEW-RESULT).
- New WALKTHROUGH.md: one fixture journey, 21 transitions, gaps found and fixed.
- UX simplification in DESIGN-SPEC and the mocks; new proposed decision D42.
- Bingo card data documented and rendered; dated print context.
- Mock checks made reproducible (`mocks/tools/`, `mocks/reports/check-report.json`).
- Not called build-ready.

## 18.00 Round 8.8 change log

- Seven integration points from the 8.7 review resolved (summary table in REVIEW-RESULT):
  workbench readiness moved out of the app gates; bootstrap milestone M0; canonical
  503/200 split; interest fallback cases; stable `idea_id` detail URLs; cache, single
  flight and view-model interfaces completed; model evidence owned by WP5.
- Delivery order renumbered to seven steps (§15).
- Static mock screens added in `docs/mocks/` with screenshots at 390 and 1440 px.

## 18.0 Round 8.7 change log

- Purpose clarified: the package is the build specification for agents Mats coordinates
  with Hermes; Hermes policy is workbench operation, not a product deliverable.
- PRODUCT-FIT: P1 reframed as unproven product-value hypothesis H1; official contest
  requirements separated from our evaluation criteria; D39 refined (EN/SV/FR, inferred
  chips, one-call schema, code-derived `matches_interest`, chip removal re-sorts with zero
  upstream calls, negation/ambiguity/no-match, untrusted text, local versus demo privacy).
- Catalogue: `interests` on all 28 activities; new tag `puddles`; hooks.toml gains the
  code-derived reason `matches_interest`.
- DESIGN-SPEC: oatmeal palette with recalculated contrast, D41 typography, components,
  failure states, chip behaviour, checklist and conflict-resolution log.
- New CONTRACTS.md and BUILD-PACKAGES.md for parallel implementation.
- New decision D41 (typography). D39 stays proposed.

## 18.1 Round 8.6 change log

- Added PRODUCT-FIT.md: product goal, primary user and journey, an honest account of what
  Gemma adds (finding P1), the D39 proposal, open-approach benefits limited to what is
  demonstrated, and a requirement-to-evidence table for the contest.
- Added DESIGN-SPEC.md: tokens with computed contrast pairs, components with all states,
  dimensions, responsive rules, SVG inventory, interaction, errors, motion, copy deck,
  print and implementation, each with acceptance checks.
- New decisions D39 (interest understanding) and D40 (name), both needing Mats.

## 18a. Round 8.5 change log

- Added BACKEND-CONTRACT.md as the owning backend contract (B01–B07, B09, B10, B14, B15).
- One 30-minute weather freshness limit; no unchecked-weather card; exact interval semantics.
- Result validity, location-choice continuation, resource table, session security, shared
  fetch ownership, validation, place fees/access, geocoding privacy and lifecycle defined.
- CI trust model with `gates.lock`; release image scanned by digest before deployment.
- Model endpoint and cancellation evidence tightened (HERMES-P0 section 4, D38).
- Catalogue reconciled (B11); generic hook wording narrowed.
- Delivery order by dependency instead of clock slots; quantization marked conditional.
- New decisions D35–D38; D37 and D38 need Mats.

## 18b. Round 8.3 change log

- Baseline is the verified 8.1 set; D1–D26 keep their meaning. D26 remains the mandatory
  error/recovery contract.
- Merged reviewed 8.2 work under new IDs: D27 (Observatory host check, D20 unchanged),
  D28 (fallback proposal with its own boundary obligations), D29 Python, D30 seasons,
  D31 session/CSRF, D32 deadline budget.
- Added D33 request budget and caching contract (mandatory) and D34 optional preloading.
- One canonical audit procedure (ARCHITECTURE 13.3), referenced by this plan and HERMES-P0.
- Catalogue: explicit `generic_ok` (5 of 28); season rule tied to hemisphere.
- Cut list: SSE progress and quantization comparison placed explicitly.

## 18a. Round 8 change log

- Added ARCHITECTURE.md: four Mermaid diagrams; proposed mode/lifecycle/resource contracts;
  lean dependency inventory; concurrency, quantization, property checks and recovery.
- Added CLAUDE-REVIEW.md: concrete deep-review instructions, failure cases and closure format.
- Updated this plan's disconnect, transient privacy, offline card and dependency-budget
  wording to match the proposed architecture; corrected stale round references and the
  Saturday overlap. D21–D24 remain proposed rather than falsely approved.
- Preserved all-severity audit blocking, Observatory 145/A+, accessibility ambition,
  source-quality rules and competition scope. Audit coverage requires package identity
  reconciliation, not misleading cross-ecosystem count comparisons.
- Updated HERMES-P0 references to manifest evidence and included the audit runner in
  credential checks. No application code or infrastructure configuration was written.
- Activity and hook content is unchanged from the supplied matching masters. COMPETITION.md
  remains the previously supplied contract; round 8 does not independently recertify it.

### Round 8.1 additions

- Added ERROR-HANDLING.md: shared failure taxonomy, user copy/actions, backend exception and
  HTTP mapping, progressive enhancement, screen-reader/focus behaviour and retry ownership.
- Added fault-injection and recovery evidence to the release gate and Claude's review.
- Kept competition requirements authoritative in COMPETITION.md. Replay, fallback and live
  inference remain clearly distinguished; claims are limited to completed verification.
- No new runtime dependency, product feature or application implementation is authorized.

## Delivery rule — required by Mats, 9 October 2026

Deliver each revision as one complete, versioned ZIP only. Include all current
planning documents, catalogues, review results and SHA256SUMS.txt inside it.
Do not attach individual documents, sidecar files or partial update bundles.
The ZIP is the authoritative handoff; provide one download link and a short
change summary. Verify its checksums before delivery. Keep reviews focused on
changed requirements, conflicts and outstanding proof; do not reopen settled
decisions without new evidence. This delivery change grants no build approval.
