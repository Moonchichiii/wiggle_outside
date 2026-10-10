# Deployment options, abuse and cost controls, connectivity — baseline 8.20

Status: DRAFT, 10 October 2026. **Build path (8.19):** the independently hosted public
planner (O2 on Fly.io) is the primary build path; its operating contract is
ARCHITECTURE §2.1. **Not approved:** spending, purchase and deployment (Mats's separate
approval of §1.5, prerequisite P2 in PLAN §0.1), and the build itself ("kör"). The hosted
controls (D49) are accepted starting values for that primary path. Intended hostname:
`wiggle-outside.fly.dev` (D27), availability to be confirmed. Every figure is marked **verified** (read on a primary source on 10 October
2026; recheck before deploying), **estimate** (our arithmetic on stated assumptions) or
**unknown**. Nothing here claims full security, measured performance or a guaranteed
spending cap.

## 1. Deployment choices (D48)

**Boundary (Mats, round 8.15):** the finished product is deployed independently of the
workbench. Production has its own hosting, model access, credentials and operating
limits: no tunnel, no shared inference endpoint, no dependency on Mats's computer being
on. The workbench only builds and tests the project (HERMES-P0). Local development with a
local model (D38) is optional and gates nothing.

**Mats's preferred direction: O2.** Planning only; no purchase or deployment is
authorised. Spending needs his separate approval.

| | O2 managed Gemma API (preferred) | O4 self-hosted E4B on a rented GPU | O1 recording only |
|---|---|---|---|
| Visitors get | a live public planner | a live public planner | a recording and the repository; no live planner |
| Model | Gemma 4 26B A4B through OpenRouter (§1.1). Gets its own evaluation (H1, D39), with no change to the app design | Gemma 4 E4B, run by us | Gemma 4 E4B during the recording |
| Fixed cost | VPS (§1.2) | GPU instance (**unknown**) | none |
| Per-run cost | §1.3 | none per call | none |
| Status | **primary build path** (specified below) | **inactive**; not specified | **inactive**; fallback only if Mats does not approve O2 spending |

O3 (public app reaching the workbench) is **removed**: it contradicts the boundary above.

### 1.1 Model and provider (O2)

- **Model:** `google/gemma-4-26b-a4b-it` on OpenRouter (Gemma 4 26B A4B, instruction-
  tuned). E4B is not offered by the managed APIs checked.
- **One pinned endpoint:** `provider.only` = the chosen endpoint,
  `allow_fallbacks: false`, `require_parameters: true` (structured output required).
- **Both candidates support** `response_format`, `structured_outputs`, `max_tokens`,
  `reasoning` and `include_reasoning` (OpenRouter endpoints API, **verified**).

**Privacy checks (the reviewer's point 2):**

| Check | OpenRouter itself | DeepInfra (`deepinfra/fp8`) | Google (`google-vertex/global`) |
|---|---|---|---|
| Stores prompts or completions | no, unless prompt logging is opted in; stores metadata such as token counts (**verified**) | inputs not stored on disk, deleted after inference; outputs deleted once returned; only debugging metadata logged (**verified**, DeepInfra docs) | in-memory cache of inputs and outputs with a 24 h TTL for Google's published models unless disabled per project; may log prompts for abuse monitoring under the Google Cloud terms (**verified**, Google docs). Through OpenRouter we cannot switch these off, because the Google Cloud project is OpenRouter's (**inference**) |
| Trains on data | no | no, "except with Google or Anthropic models, where the provider's policy applies". Gemma here is an open model run by DeepInfra itself (fp8), so the exception likely does not apply, but that is **unknown until DeepInfra confirms** | Google "won't use your data to train or fine-tune any AI/ML models without your prior permission" (**verified**) |
| Zero data retention (`provider.zdr: true`) | supported as a request filter (**verified**) | not confirmed: the OpenRouter ZDR list we could read showed only Io Net for this model, and Io Net lacks structured-output support; the list was truncated (**unknown**) | not confirmed (**unknown**); abuse logging makes ZDR unlikely through OpenRouter |
| Processing location | EU in-region routing is enterprise-only (**verified**) | **unknown** (not stated; ask DeepInfra) | endpoint is "global"; region **unknown** |

**Recommendation: DeepInfra**, because it states no disk storage, no prompt logging and
no training, and it is cheaper, **subject to two confirmations before any spending**:
that the "Google models" exception does not cover Gemma hosted by DeepInfra, and where
the processing happens. If either answer is unacceptable, fall back to Google (no
training; abuse logging and a 24 h cache apply) or to O1. `zdr: true` is **not** set,
because no endpoint that supports structured output is confirmed as ZDR for this model;
setting it would leave no endpoint. The privacy notice and the post say plainly that the
answers and the model prompt are processed by OpenRouter and the chosen provider.

### 1.2 Fixed hosting cost (O2)

| Item | Price | Status |
|---|---|---|
| Hetzner Cloud CX23 (2 vCPU, 4 GB RAM, 40 GB NVMe, 20 TB EU traffic), Germany or Finland | €5.49 a month excl. VAT | **verified** |
| Primary IPv4 address (needed: many phone networks are IPv4-only) | €0.50 a month excl. VAT | **verified** |
| VAT | depends on Mats's billing country and whether a VAT ID is registered (19 % in the German price list) | **unknown for this account** |
| Traffic above 20 TB | billed; price not checked | not expected at demo scale |
| Domain name | optional; a subdomain of an existing domain costs nothing extra | **unknown** if a new domain is bought |

**Mats's preference (8.18): Fly.io**, operated as in ARCHITECTURE §2.1. Hetzner and
DigitalOcean are **inactive** alternatives.

- **Fly.io**: one shared-cpu-1x Machine in Stockholm or Amsterdam: about $3.84
  a month with 512 MB or $6.95 with 1 GB, always on (computed from Fly's published
  formula, **verified** inputs); a 1 GB volume for the SQLite quota and cache at
  $0.15 a month; shared IPv4 free (dedicated $2 a month); outbound data in Europe
  $0.02/GB with no free allowance stated; no free tier (a short trial only). The pricing
  page does **not** describe a hard spending limit. Machine prices vary by region, and
  outbound data is metered, so the hosting figure is an estimate (§1.5), not a ceiling.
- **DigitalOcean** Basic Droplet at $6 (1 GiB) or $12 (2 GiB) a month, stated capped at
  the plan price (**verified**).

Whichever host is chosen, the quota table needs persistent disk (a Fly volume, or the
VPS disk).

### 1.3 Per-run cost (O2)

**Correction kept from 8.15:** "$0.11/run" in an earlier question was the daily maximum
at the old cheapest-route price, not a per-run cost.

A run is one planning attempt with at most one model call (D44).

- **Typical** (estimate): about 1,800 input tokens and 150 output tokens.
- **Enforced:** the complete hosted request (messages plus the JSON schema) is capped at
  **10,000 UTF-8 bytes** before it is sent (§3), and output, including any reasoning
  tokens, is capped by `max_tokens` 256.
- **Not established (estimate):** how many billable input tokens 10,000 bytes can become.
  We assume about 10,100 (our text at most one token per byte, plus a template overhead
  of tens of tokens we cannot see); neither the tokenizer behaviour at the provider nor
  the overhead is verified. The adapter compares the reported `usage.prompt_tokens`
  with 10,100 on every run and logs a breach for review, so the assumption is checked,
  not relied on.

| Endpoint (input / output per million) | Typical per run (estimate) | "Maximum" per run (estimate, assumes 10,100 input tokens) | 500 runs/day at that estimate |
|---|---|---|---|
| DeepInfra ($0.07 / $0.34) | 126 + 51 = 177 µ$ → **$0.00018** | 10,100 × 0.07 + 256 × 0.34 = 707 + 87 → **$0.00079** | $0.40 |
| Google ($0.15 / $0.60) | 270 + 90 = 360 µ$ → **$0.00036** | 1,515 + 154 → **$0.00167** | $0.83 |

(µ$ = millionths of a dollar: tokens × price per million.) The provider's reported
`usage` is logged per run, so the real figures replace these estimates after the smoke
test.

### 1.4 Spending-limit behaviour (O2)

1. **Daily allowance** (§2.3): at most 500 runs per UTC day, enforced by the app,
   restart-safe, failing closed.
2. **Per-key cap** at OpenRouter: when reached, calls are refused (402) and each run
   ends in the labelled deterministic fallback after all normal checks.
3. **Prepaid credits, auto top-up off:** the purchased balance is the practical outer
   limit, **not an absolute one**: OpenRouter charges a request when it finishes and its
   docs note a balance can become negative. Our app has at most one model request open,
   but timed-out requests may still finish and be billed (§3). **No upper bound is
   claimed** for the overshoot past the cap or balance; it is limited in practice by the
   daily allowance (each started run is counted) and by how the provider applies the key
   cap, neither of which we can verify in advance. Auto top-up must stay **off**; this
   is recorded as a deployment setting.
4. **Purchase fee** (**verified**): 5.5 %, at least $0.80, for card payments; platform
   fees are non-refundable; unused credits may expire after a year.
5. **Hosting (Fly.io):** Machine and volume billed by time, outbound data metered; no
   provider spending cap. Only the Machine count is fixed by us (one, ARCHITECTURE §2.1).

### 1.5 Spending proposal for approval (O2)

| | Proposal |
|---|---|
| Model and provider | Gemma 4 26B A4B through OpenRouter, pinned to **DeepInfra** (`deepinfra/fp8`), no fallbacks, structured output required, reasoning off; **only after** DeepInfra confirms the two privacy questions in §1.1 |
| Hosting (Mats's preference, 8.18) | **Fly.io**: exactly one shared-cpu-1x Machine with 512 MB in Stockholm (`arn`) or Amsterdam, always on, deployed with `--ha=false`, a 1 GB volume at `/data` for SQLite, shared IPv4 (free); full contract in ARCHITECTURE §2.1. Upgrade to 1 GB only if the smoke test measures the need. Inactive alternative: Hetzner CX23 + IPv4 at €5.99 a month + VAT |
| Upfront payment | OpenRouter credits **$10.00 + $0.80 fee = $10.80** (auto top-up off). Fly.io bills monthly in arrears (card required after the short trial) |
| Expected monthly cost | Fly Machine about **$3.84** + volume **$0.15** + outbound data at $0.02/GB (a few GB at demo scale: **≈ $0.10**) + inference at a realistic 50 runs a day, about 50 × $0.00018 × 30 = **$0.27**. Total roughly **$4.40 a month** — an **estimate, not a ceiling**: Machine prices vary by region, outbound data is metered, and VAT may apply (**unknown**) |
| Maximum monthly inference | bounded by the per-key cap: **$5.00 a month** (at the maximum per-run cost, 500 runs a day would reach it in about 13 days; after that, labelled fallback) |
| Configured limits | 500 runs per UTC day; per-network 30 POSTs, 20 new sessions and 600 GET requests an hour (abuse limits, **not spending caps**); key cap $5 a month; auto top-up off; `max_tokens` 256; request cap 10,000 bytes; exactly one Machine; Fly billing alert set (alerts only) |
| Remaining exposure (not bounded) | **Outbound data:** Fly.io shows no hard spending cap. Per-network limits slow one network but do not bound total traffic across many networks, and browser caching does not make a hostile client reuse assets (for scale: 1 TB would cost about $20). **Inference overshoot:** timed-out requests may still finish and be billed; no upper bound is claimed (§1.4). Also: VAT if applicable; an optional new domain; credits expiring after a year if unused. Mitigation is operational: Fly billing alert, and stopping the Machine if traffic is abnormal |
| Period | until judging ends, then Mats decides; stopping means deleting the server and revoking the key |

Nothing is bought or deployed until Mats approves this table.

## 2. Hosted abuse and cost controls (D49, accepted starting values)

### 2.1 What already exists (unchanged)

Validation before any provider or model call; body 8 KiB, place 80, interests 120;
hosted request cap 10,000 bytes and `max_tokens` 256 (§3); 20 s deadline; one provider
retry; no model repair; duplicate protection by key and fingerprint; 5 active jobs, 1
per session; one open model request at a time; 6 submissions per minute per session and
30 per minute globally; the model API key server-side only (Fly secret), CSP
`connect-src 'self'`. (Dev-only: a local Ollama is never public, D38.)

### 2.2 New counters and how each request affects them

| Counter | Limit (*starting value*) | Storage |
|---|---|---|
| A. Per-network POSTs (IPv4 address or IPv6 /64, from `Fly-Client-IP` only, ARCHITECTURE §2.1) | 30 per hour, sliding | memory |
| B. Per-network new sessions | 20 per hour, sliding | memory |
| B2. Per-network GET requests (pages, fragments and static files that reach the app; `/healthz` from Fly's health checks excluded) | 600 per hour, sliding. An abuse limit, **not a spending cap** (§1.5) | memory (same bounded store as A and B) |
| C. Global daily planning runs | 500 per UTC day | memory **and** SQLite, write-through |
| D. Provider spending cap | per-key cap on the hosted-model API key ($5 a month in the §1.5 proposal) | at the provider |

| Event | A | B | B2 | C | Session and global per-minute buckets |
|---|---|---|---|---|---|
| Any GET (page, result, job status, static file), counted first, whatever happens next | — | — | +1 | — | — |
| GET `/` that creates a session | — | +1 | +1 | — | — |
| GET beyond the B2 limit | — | — | (already +1) | — | — |
| Any POST to `/plan` or `/location-choice`, counted first, whatever happens next (including rejected, honeypot, duplicate) | +1 | — | — | — | — |
| POST rejected before admission (400, 403, 409, 413, 415, 422, 429, 503) | (already +1) | — | — | 0 | 0 |
| Duplicate submission joining an existing job, or a repeat of a consumed candidate | (already +1) | — | — | 0 | 0 |
| New job admitted (`/plan` or `/location-choice`) | (already +1) | — | — | 0 at admission | +1 (as today) |
| A job reaches the places-and-weather stage (the expensive part) | — | — | — | **+1, reserved atomically before the provider calls** | — |
| A job that ends before that stage (ambiguous place, place not found) | — | — | — | 0 | — |

**B2 contract (owner WP7):** counted in the same middleware as A, before routing, for
every GET that reaches the app (pages, htmx fragments, `/static/*`); `/healthz` is
excluded so Fly's health checks never trip it. Beyond 600 in the sliding hour: **429**
with `Retry-After` (seconds until the oldest counted request leaves the window). An HTML
request gets the minimal static "Too many requests from your network. Please try again
in a few minutes." page (no template rendering, no session work); an htmx request gets
the same text as a fragment; a static file gets an empty body. Untracked networks in
overflow share the overflow bucket's B2 count (§2.4). Tests (WP7): the 600th GET passes
and the 601st gets 429 with `Retry-After`; HTML, htmx and static variants; `/healthz`
not counted; overflow-bucket sharing; expiry after one hour.

So an ambiguous place followed by a choice is charged once (C), when the chosen
location's job starts its places and weather work. "Change answers" is a new run and
charged once. The model call needs no separate counter: at most one model call per run
(D44), so model calls ≤ C, and the provider cap D is the backstop for spend.

### 2.3 Restart-safe daily allowance (C)

- **One conditional transaction:** the reservation runs on the SQLite thread as a single
  statement in one transaction:
  `INSERT INTO quota(utc_day, runs) VALUES(:day, 1) ON CONFLICT(utc_day) DO UPDATE SET
  runs = runs + 1 WHERE runs < :limit`, followed by checking that exactly one row
  changed. It commits **before** any provider work starts; the job awaits the result.
  The DB thread serialises concurrent reservations, so two jobs cannot both take the
  last slot.
- **Separate table:** `quota(utc_day TEXT PRIMARY KEY, runs INTEGER NOT NULL)` lives
  outside the disposable cache and is never cleared by a cache reset or
  `scripts/clear_cache`.
- **Restart:** the count is read from SQLite; a restart never resets it. A crash after the
  commit but before the provider call leaves the run counted (conservative).
- **UTC rollover:** the key is the UTC date at reservation time; the first run after
  midnight UTC gets a new row.
- **Exhausted:** POST `/plan` and `/location-choice` answer 503 SERVICE_LIMIT_REACHED
  before any work, with `Retry-After` until the next 00:00 UTC; a job whose reservation
  fails ends with the same code.
- **Storage failure fails closed, with different wording:** if the reservation cannot be
  written or read, the run is refused with 503 **SERVICE_UNAVAILABLE** ("Wiggle Outside
  can't take new searches right now. Your answers are kept; please try again in a few
  minutes.", `Retry-After: 60`), and the operator log records it. It never tells people
  to wait until midnight, and the allowance never silently resets or grows.
- **Tests (WP4, WP6):** many concurrent reservations at `limit − 1` give exactly one
  success; a crash between commit and provider call keeps the count; restart keeps the
  count; rollover at 00:00 UTC; read or write failure gives SERVICE_UNAVAILABLE.
- **Provider cap hit (402):** the model is unavailable for that run; labelled fallback
  after every normal check; operator log.

### 2.4 Bounded network-limit storage (A, B, B2)

At most 10,000 tracked networks. An entry is **kept until it expires** (one hour after
its last event) and is never evicted early, so no address loses its limit history. When
all 10,000 slots hold unexpired entries, any address that is not already tracked is
counted in **one shared overflow bucket** with the same limits until slots free up.
Expired entries are purged on access and by a periodic sweep. Addresses stay in memory
only, are never logged or stored, and come only from `Fly-Client-IP` (ARCHITECTURE
§2.1). The store is in-process memory, so a restart or deploy clears A, B and B2 (the
daily allowance C is in SQLite and survives).
Shared school and mobile-carrier addresses vary widely; no claim is made about how many
families fit behind one address. A legitimate user who hits a limit gets REQUEST_BUSY
with `Retry-After` and keeps their answers.

### 2.5 Inference cost (O2)

See §1.3 (per run) and §1.4 (limits). Earlier per-run figures based on the cheapest route
are superseded.

### 2.6 Billing alerts versus enforced limits (verified)

- Google Cloud budgets: "an alerts-only budget doesn't automatically cap … usage or
  spending."
- Gemini API: tier spend limits are enforced per 10 minutes ($10 at Tier 1) and per tier
  ($250 total at Tier 1): real ceilings, far above this demo's needs.
- OpenRouter: an optional per-key spending cap is enforced; requests are charged when
  they finish, and the docs note a balance can become negative, so a small overshoot is
  possible.
- Fly.io: billing alerts only; no hard spending cap is described. Fixed-price servers
  (inactive alternatives) bound the server price, not traffic beyond the allowance.

### 2.7 Honeypot (supplement only)

- Field `hp_note`: a text input in an off-screen container (`aria-hidden="true"`), with
  `tabindex="-1"`, `autocomplete="off"` and the label "Leave this field empty".
- **Autofill is a test obligation, not a claim:** before release, test Chrome, Firefox
  and Safari autofill and at least one password manager on the plan form; if anything
  fills the field, rename or restructure it.
- **False-positive recovery:** a non-empty value gets 422 with the form re-rendered,
  answers kept, the honeypot cleared, and the message "Something in the form couldn't be
  accepted. Please check your answers and send them again." A real person's resubmission
  then passes. No provider or model call; the event is counted.
- Never treated as bot protection on its own.

### 2.8 Provider eligibility versus traffic limits

Two separate checks for each provider, both required:

| Provider | Eligibility (who may use it, and how) | Traffic limits |
|---|---|---|
| Open-Meteo free API | non-commercial use only; data under CC BY 4.0, so attribution is shown ("weather from Open-Meteo") | < 10,000 calls a day, 5,000 an hour, 600 a minute |
| Nominatim (OSMF) | end-user-triggered searches by a moderate user base; identifying User-Agent; results cached; no client-side autocomplete; switch service when asked | ≤ 1 request a second, application-wide |
| Overpass public instances | guideline-based public service | about 10,000 requests and 1 GB a day |
| Hosted model provider (O2) | its terms and data-use policy for the chosen route | its rate limits and our key cap |

Being under a traffic limit does not establish eligibility. A commercial or high-traffic
deployment would need different providers or plans.

## 3. Hosted inference contract (O2)

- **Structured output:** `response_format` of type `json_schema`, `strict: true`, schema
  `selection.v1` or `v2`; `provider.require_parameters: true`. Our validation still runs
  on every output (D4).
- **Routing:** `provider.only` = the approved endpoint, `allow_fallbacks: false`: one
  application request is one provider attempt.
- **Input bound (enforced):** the adapter serialises the complete request body it will
  send (messages and schema) and refuses to send it if it exceeds 10,000 UTF-8 bytes;
  that run uses the labelled fallback and the event is logged. The prompt builder keeps
  typical requests far below this (fixed system prompt, at most 12 pairs with bounded
  fields, interest text ≤ 120 characters). The smoke test records the real `usage`
  token counts for the typical and the largest fixture.
- **Output bound:** `max_tokens` 256. Reasoning tokens are billed as output and count
  toward `max_tokens` (OpenRouter docs, **verified**), so this caps billed output either
  way. Reasoning is disabled with `reasoning.effort: "none"`; whether this model accepts
  that is **unknown** until the smoke test, which checks that reported reasoning tokens
  are zero and that answers are not cut off (`finish_reason` "length" with empty content
  counts as invalid → fallback).
- **Timeout:** the model stage budget (D32: 11 s inside the 20 s deadline). On timeout
  the adapter closes the connection and the run uses the labelled fallback.
- **Hosted cancellation (different from local, see ARCHITECTURE §4):** closing the
  connection may not stop the remote generation or its billing. The app therefore makes
  no claim that only one remote generation is active. Its hosted "slot" limits only the
  number of **open requests from the app** (one); it is released when the connection is
  closed. Abandoned remote generations are bounded by the daily allowance (each started
  run is already counted), the 11 s timeout and the key cap, and are assumed billable.
- **Errors:** 402 → model unavailable for the run, fallback, operator log. 429 →
  provider cooldown through the provider gate respecting `Retry-After`, fallback for the
  run. 5xx or network failure → fallback for the run. None is retried.
- **Secrets:** the API key is a Fly secret read from the environment, never the
  repository, HTML, JavaScript or logs.

## 4. Caching and connectivity

- Shared provider caching, single flight, bounded failure caching and cooldowns stay
  (D33, D45).
- Cached weather is usable only while it meets the existing contract (fetched within 30
  minutes, covering the whole window, validated; BACKEND-CONTRACT §1). A provider outage
  never extends that. Unusable weather still means no recommendation.
- Three different things, never mixed up: still-valid cached data during a provider
  outage; a printed or saved card that works offline; the app itself needing internet.
  No service worker, on-device model or offline subsystem.

## Sources (checked 10 October 2026)

- ai.google.dev/gemma/docs/core · ai.google.dev/gemma/docs/core/gemma_on_gemini_api ·
  ai.google.dev/gemini-api/docs/pricing · ai.google.dev/gemini-api/docs/rate-limits
- docs.cloud.google.com/billing/docs/how-to/budgets
- openrouter.ai/google/gemma-4-26b-a4b-it · openrouter.ai/docs/api-reference/limits ·
  openrouter.ai/docs/features/provider-routing · openrouter.ai/docs/features/structured-outputs
- hetzner.com/cloud/cost-optimized · docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
- openrouter.ai/api/v1/models/google/gemma-4-26b-a4b-it/endpoints (per-provider prices and supported parameters)
- digitalocean.com/pricing/droplets · docs.hetzner.com/general/infrastructure-and-availability/ipv4-pricing
- openrouter.ai/docs/features/privacy-and-logging · openrouter.ai/docs/features/zdr ·
  openrouter.ai/api/v1/endpoints/zdr · openrouter.ai/docs/use-cases/reasoning-tokens ·
  openrouter.ai/docs/faq
- docs.deepinfra.com/account/data-privacy
- docs.cloud.google.com/gemini-enterprise-agent-platform/resources/zero-data-retention
- fly.io/docs/about/pricing · fly.io/docs/volumes/overview · fly.io/docs/apps/app-availability ·
  fly.io/docs/networking/request-headers
- open-meteo.com/en/terms · operations.osmfoundation.org/policies/nominatim/ ·
  dev.overpass-api.de/overpass-doc/en/preface/commons.html
