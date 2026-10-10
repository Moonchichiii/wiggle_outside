# Touchgrass backend contract — baseline 8.20

Status: DRAFT, 10 October 2026. Owning document for weather, results, location choice,
resource bounds, sessions, shared fetches, validation, places, geocoding privacy and
lifecycle (BACKEND-REVIEW B01–B07, B09, B10, B14, B15). Other documents summarise and link
here; where they differ, this contract wins. Numbers marked *starting value* are accepted
working limits (baseline 8.20); measurements can expose problems, and any change is a
tracked change, never a silent one.

## 1. Weather (B01, B02)

**Freshness.** One limit: a forecast is usable for 30 minutes after `fetched_at` (our
clock at receipt). At 30:00 it is expired. No provider issue time is invented; if
Open-Meteo returns one, it is recorded, not substituted. Expired or missing weather means
no recommendation, no generic path and zero model calls (D16).

**Request.** One call per planning attempt: hourly `temperature_2m`,
`apparent_temperature`, `precipitation_probability`, `precipitation`, `wind_speed_10m`,
`weather_code`; daily `sunrise`, `sunset`; `timeformat=unixtime`, explicit units (°C, km/h,
mm). Returned `hourly_units` and `daily_units` must match or the forecast is rejected.
All times are aware UTC internally; local time only for display.

**Interval mapping** for an outing window `[start, end]`:

| Variable | Sample meaning | Samples used |
|---|---|---|
| `precipitation`, `precipitation_probability` | the preceding hour `(t − 1h, t]` | every `t` with `t − 1h < end` and `t > start` |
| `weather_code`, `temperature_2m`, `apparent_temperature`, `wind_speed_10m` | instant at `t` | `floor_hour(start)` through `ceil_hour(end)` inclusive |

Source: Open-Meteo forecast API documentation, hourly variable table ("Valid time"
column: `weather_code` Instant; `precipitation` Preceding hour sum;
`precipitation_probability` Preceding hour probability), checked 10 October 2026. Round
8.9 corrects `weather_code`, which earlier rounds treated as a preceding-hour value.

**Worked example (crosses an hourly boundary).** Outing 10:31–11:31 local time in
Europe/Stockholm (UTC+2) = `[08:31, 09:31]` UTC.

| Variable | Samples used (UTC) | Why |
|---|---|---|
| `precipitation`, `precipitation_probability` | 09:00 (covers 08:00–09:00), 10:00 (covers 09:00–10:00) | intervals overlapping the window; 11:00 (10:00–11:00) does not overlap |
| `weather_code`, temperatures, wind | 08:00, 09:00, 10:00 | instants from `floor_hour(08:31)` to `ceil_hour(09:31)` |
| Daylight | sunrise and sunset for 10 Oct (local date) | `sunrise ≤ 08:31` and `09:31 ≤ sunset` in UTC |

A window ending exactly on the hour (`[08:00, 09:00]`) uses precipitation sample 09:00
only and instants 08:00 and 09:00. Tests: `tests/core/test_weather.py` covers both cases
with the fixture `tests/fixtures/providers/open_meteo_boundary.json`, which carries the
hourly arrays, not a summary.
| Daylight | daily sunrise/sunset for each local date the window touches | `sunrise ≤ start` and `end ≤ sunset` |

`is_day` is not used. Any required value missing, null, non-finite, any array length
mismatch, an unknown weather code or a missing unit fails closed as WEATHER_UNAVAILABLE.

**Predicates** (pure functions in `core/weather.py`):
- Severe, excludes everything: weather codes {56, 57, 65, 66, 67, 75, 82, 86, 95, 96, 99},
  or any wind sample above 50 km/h. *Code set: starting value.*
- Heat, excludes everything: any apparent temperature above 30 °C with kids, 32 °C alone.
- `rain_ok = false`: every precipitation interval has probability ≤ `max_rain_pct` and 0 mm.
- `rain_ok = true`: every interval has probability ≤ `max_rain_pct`; severe rules still apply.
- Cold: every apparent-temperature sample ≥ `min_temp_c`.
- Optional `max_temp_c`: every apparent-temperature sample ≤ it.
- Wind: every sample ≤ `max_wind_kmh`.
- `daylight = true`: the daylight row above holds.
- Reason `dry_window`: every interval probability ≤ 20 % and 0 mm.

All thresholds are provisional product limits, not safety guarantees.

**Daylight outcome for the family path (Mats 8.20).** With `who = kids`, every kids'
activity is daylight-only (catalogue W4), so the daylight row decides the run before any
activity is checked. Pure function `daylight_outcome(window, sunrise, sunset)` in
`core/weather.py`, using the validated daily sunrise and sunset for the local date of
`planned_start`:

| Condition | Outcome | Copy (ERROR-HANDLING §2) |
|---|---|---|
| `planned_start < sunrise` or `planned_start ≥ sunset` | DAYLIGHT_NIGHT | "The adventures can wait till morning." |
| otherwise, `planned_end > sunset` | DAYLIGHT_TOO_SHORT | "Not enough daylight for this one." |
| otherwise | continue with the normal eligibility rules | — |

It runs after the weather is validated (sunrise and sunset come from it; missing or
invalid weather stays WEATHER_UNAVAILABLE) and before the severe, heat and
per-activity rules, so it takes precedence over WEATHER_RESTRICTED and NO_MATCHES. It is
fixed, reviewed copy chosen by code: no model call, no polling, no automatic refresh.
The result keeps the answers summary and "Change answers". The solo path is unchanged
(solo entries keep their own daylight flags). The copy never says the children are
asleep and never promises tomorrow's weather.

**The short-circuit lasts one run (TC-002).** It is a per-run ordering rule, never a
cached verdict, and the copy must not present an edit as a fix for a limit this run never
reached (ERROR-HANDLING §1). A resubmission through "Change answers" is a new job
(CONTRACTS §7) and re-runs every check — daylight, the severe, heat and per-activity
weather rules, eligibility, season and time — against its own `planned_start` and window.
Re-running costs no upstream calls when the caches still cover the new window
(ARCHITECTURE §14), so the same answers submitted a few minutes later may legitimately
get a different outcome in either direction.

**Durations.** 30 min, 1 h, 2 h, half day = 4 h (D35, accepted). **Seasons** (D30):
meteorological seasons by hemisphere; for |latitude| < 23.44° no season-restricted
activity qualifies.

## 2. Result validity (B03)

Each result stores `planned_start` (the job's admission time: "leave now"),
`planned_end = planned_start + time budget`, and two separate times:

- `valid_until = min(created + 5 min, weather.fetched_at + 30 min, planned_start + 10 min)`:
  the recommendations stop being current. After it the result is shown as historical
  ("This information is no longer current. Planned for Sat 10 Oct, 10:31–11:31,
  weather checked at 10:31") with a "Plan again" action that submits a new request; no
  background refetch.
- `retain_until = valid_until + 60 min` (engineering default, 8.13): the historical result is removed.
  At `retain_until` the planner deletes, together: the result (with its ideas and
  `idea_id`s), its idempotency record and any location-choice record that points to it.
  After that every URL for it returns 404, the same as an unknown ID. Everything a
  session owns is removed when the session ends (idle 30 min, absolute 2 h, or
  eviction), so in practice a result lives until the **earlier** of `retain_until` and
  session end; any request on the session (including viewing the result) resets the idle
  timer.

Redisplay never renews "leave now". A card already open or printed keeps its original,
dated time context.

**Immutable results (D46, round 8.11).** A result never changes after it is created. It
stores everything needed to render it and each of its detail pages until
`retain_until`: its 0–3 `Idea`s (pair with place, distances and times, hook ID, reason
IDs), its interest tags and outcome, the answers summary and the weather summary.
Catalogue and hooks are immutable for the process lifetime. Nothing is reconstructed from
newer state: changing answers creates a new result with a new key, and the old one stays
readable, unchanged, until it is removed.

## 3. Location choice (B04)

An ambiguous geocode ends the job with `NeedsLocationChoice` (not a failure). The session
stores one candidate set: up to 5 entries with opaque random IDs, rounded coordinates and
plain-text labels, TTL 10 minutes, **plus the submitted answers** (including D39 text, in
memory only), because the choice must plan with them. The answers are discarded when the
set expires or is replaced.

Choosing one is a CSRF-protected POST that starts a new planning attempt with a fresh
deadline, using the stored coordinates and answers without another geocode.
**Idempotency:** each candidate can start at most one job. Its submission key is derived
server-side (`candidate:<candidate_id>`); the candidate records the resulting `job_id`.
A repeated POST for the same owned candidate (double click, lost response, resubmission)
returns that same job (303 to its result, or joins it while running) with zero upstream
calls, until the job's `retain_until`. Choosing a different candidate from the same set
starts its own job under the normal busy and rate limits. Once a candidate is consumed,
a GET of the original `NeedsLocationChoice` result redirects (303) to the most recently
started job from that set, so the back button never offers a stale choice as new. Any `candidate_id` that is not in this
session's live set (unknown, forged, from another session, expired or removed) gets the
same 422 LOCATION_CHOICE_EXPIRED with the manual-entry form; a POST never returns 404
(CONTRACTS §3 is canonical). The plain form shows the
choices as radio buttons. ERROR-HANDLING's LOCATION_AMBIGUOUS row links here.

## 4. Resource and admission bounds (B05)

| Resource | Limit (*starting value*) | Expiry / owner | On overflow |
|---|---|---|---|
| Sessions | 500 global | idle 30 min, absolute 2 h; session store | evict least-recently-used idle session; never one with an active job |
| Location candidate sets | 1 per session, ≤ 5 entries plus answers | 10 min unconsumed; a consumed entry lives until its job's `retain_until`; session | replaced by the newest |
| Active jobs | 1 per session, 5 global | job deadline; planner | 429 REQUEST_BUSY with Retry-After |
| Terminal results (immutable, ≤ 3 ideas) | 100 global, 32 KiB each | `retain_until` (section 2); session | evict results past `valid_until` first, oldest first; never active work |
| Provider in-flight keys | 20 per provider | fetch deadline; fetch registry | fail fast as provider unavailable |
| Waiters per shared fetch | 10 | fetch end; fetch registry | fail fast as provider unavailable |
| SQLite queue | 32 operations, `busy_timeout` 2 s | DB thread | bypass cache; never block planning |
| New submissions | 6 per minute per session, 30 per minute global (token buckets) | web | 429 before any work |
| Model request | `num_ctx` 4096, `num_predict` 256, 1 at a time | planner slot | fallback |

**Hosted product (D49, accepted).** DEPLOYMENT §2 is the owning text for the
per-network counters (bounded to 10,000 entries with an overflow bucket), the
restart-safe daily planning allowance (atomic, written through to SQLite before provider
calls, UTC rollover, fails closed on storage failure), which events charge which counter,
and the provider spending cap. They apply to the hosted product, the primary build path.

Deduplication is not rate limiting: the token buckets apply to every new key. The global
bucket holds even when clients create new sessions.

## 5. Sessions and request security (B06)

- **Hosts and origins.** Exact allowed hosts and origins (scheme, host, port) from
  settings: `http://localhost:8000` and `http://127.0.0.1:8000` locally, the demo host
  when chosen. Host header checked on every request (Starlette's trusted-host check).
  No proxy is trusted locally; the demo lists its proxy explicitly and forwarded headers
  are read only from it.
- **Unsafe methods.** POST only. `Origin` must equal an allowed origin; if absent, `Referer`
  must be same-origin; if both are absent or `Origin` is `null`, reject with 403
  SESSION_INVALID. Never a silent bypass.
- **Session.** `secrets.token_urlsafe(32)`; unknown client session IDs are never adopted:
  the request gets a fresh session and must resubmit. Cookie per D31. Created on the first
  GET of the form page and counted against the session limit.
- **CSRF.** Per-session token (`secrets.token_urlsafe(32)`) in every form, compared with
  `hmac.compare_digest`.
- **Ownership.** Result and detail URLs check that the job belongs to the session; a
  mismatch returns the same 404 as an unknown ID. Location candidates are form values
  checked against the session's own live set; anything else gets the uniform 422 in
  section 3. GET never starts work.
- **Caching headers.** `Cache-Control: no-store, private` on every HTML page (pages
  only; no fragments) and error. Static assets use content-hashed names with
  `public, max-age=31536000, immutable`.
- **Tabs and expiry.** Tabs share the session; a second submission while a job is active
  returns REQUEST_BUSY with a link to the active result. If the session expires mid-job,
  the job runs to its deadline and its result is discarded.

## 6. Shared provider fetches (B07)

- Each cache key has at most one in-flight fetch with its **own** deadline (the provider's
  stage budget, set at creation). Waiters await it with their own remaining deadline;
  joining never extends it. A waiter that times out or cancels detaches; when the last
  waiter leaves, the fetch is cancelled. The registry entry is removed in `finally`.
- Cancelled callers never write the cache.
- Outcome classes: `Ok`, `Empty` (valid, cached normally), `Malformed` (not cached,
  counted), `TransportFailure` (negative-cached 60 s per key, written only when the fetch's final
  attempt fails, so the one permitted retry is not blocked by its own first failure), `QuotaOrUnavailable` (429 or
  503: provider-wide cooldown of `max(60 s, Retry-After)`; `Retry-After` as seconds or an
  HTTP date; missing or unparseable means 60 s). **No cap below the provider's requested
  delay:** the full cooldown is respected. Requests during cooldown fail fast and are never
  held, so the user gets the unavailable outcome promptly. The cooldown is one timestamp
  per provider, so a long delay costs no memory.
- **Every HTTP attempt passes the provider gate**, including a retry. Adapters perform
  exactly one HTTP attempt per call and never retry. The retry policy lives in the provider
  wrapper (CONTRACTS §4.1): at most one retry, only after `TransportFailure`, only if the
  stage budget allows, and only after `admit` and `pace` succeed again; every attempt's
  outcome is `record`ed before the next decision, so a 429 received on the first attempt
  stops the retry. `Malformed` and `QuotaOrUnavailable` are never retried.
- Coalescing, pacing (Nominatim 1 request/s app-wide) and cooldowns live in memory,
  independent of SQLite. If persistent caching fails, they still apply, so a disk failure
  cannot cause a stampede.

## 7. Input and output validation (B09)

- **Requests.** `application/x-www-form-urlencoded` only; multipart and file uploads are
  rejected (415). Body ≤ 8 KiB before parsing. Fields are enumerated: unknown fields and
  repeated scalar fields return 422. Coordinates finite, in range, rounded server-side.
  Age bands from the enum, unique, required with "kids". Typed place: 2–80 characters,
  NFC-normalised, printable.
- **Providers.** Queries are built from typed values (Overpass from a fixed template with
  numeric parameters only). `follow_redirects=False`, TLS verification on, decompressed
  responses capped at 2 MiB while streaming, JSON parsed only within the cap. SQL is
  parameterised.
- **Model output.** Schema with `additionalProperties: false`: `picks` of
  `{pair_id, hook_id, reason_ids[≤2]}`. Invalid picks (unknown pair, hook or reason;
  duplicate reasons) are dropped and the valid ones are shown (partial success, never
  padded). If none remain, or the output is empty or off-schema, the job goes straight to
  the labelled deterministic fallback, after the same weather and eligibility checks; there
  is no repair attempt (D44). Every invalid output is counted by reason; the model smoke
  test and evaluation report the rate, and a frequent rate is fixed in the prompt, schema,
  output budget or model configuration, never hidden behind the fallback. Duplicate activity IDs across picks: the
  lower-ranked one is dropped (D36, accepted).
- **Escaping (corrected in 8.9).** Text stays plain text through the domain and the presenters
  (hooks have no placeholders since 8.12; the only substitution left is copy parameters
  such as the matched interests): a place called "Oak & Elm" is the string `Oak & Elm`
  everywhere until rendering. Escaping happens exactly once, by Jinja autoescape at the
  HTML boundary; no `|safe`, no `Markup`, no manual escaping, including on
  validation-failure pages.
  Test: the place `Oak & Elm <b>` appears in the HTML as `Oak &amp; Elm &lt;b&gt;` once,
  never `&amp;amp;`. Earlier rounds said to escape before hook assembly; that would
  double-escape and is withdrawn.

## 8. Places: fee, access and time (B10)

- Excluded outright: `access` in {`private`, `no`}; lifecycle prefixes (`disused:`,
  `abandoned:`, `demolished:`); no usable centre coordinate.
- Fees, D37 (**accepted (b)**, 8.20): exclude places tagged `fee=yes`; an unknown fee is
  labelled "Admission not verified" (the full label); `fee=no` is shown as "Reported
  free admission", never as verified or as "free".
- Access tags are reported as "OpenStreetMap reports …", never as verified. Stroller fit
  is an activity property, separate from site access.
- Time: `travel = 2 × distance / speed` (3 km/h with kids, 4.5 km/h alone);
  `selected_duration = clamp(budget − travel, min, max)`; the pair qualifies only if
  `travel + min ≤ budget`. The card shows `selected_duration` and the travel estimate,
  both labelled as estimates.

## 9. Geocoding privacy and provider policy (B14)

- The form asks for "a town or area", with the hosted-product note: "Please don't type a
  street address. We look the town up with OpenStreetMap's search and keep the lookup on
  our server for up to 30 days to avoid repeat requests." (Local development may show
  the same note; it is not a product mode.)
- The geocode cache stores the SHA-256 of the normalised query, the rounded coordinates and
  the display label, never the raw query text. Retention is 30 days; `scripts/clear_cache`
  deletes all cached provider data.
- Nominatim: base URL from trusted settings only, identifying User-Agent, 1 request/s
  app-wide, attribution shown, no autocomplete, caching as above, no personal data sent
  beyond the typed area. Integration tests make at most 5 real calls per run.
- Provider, model and asset licences and policies are recorded in
  `docs/evidence/attribution.md`.

## 10. Lifecycle (B15)

**States** (ARCHITECTURE section 4): admission rejection happens before a job exists.
Jobs end in `Complete`, `Fallback`, `Unavailable`, `NeedsLocationChoice` or
`Failed` (an unexpected exception, safe message plus reference), then `Expired`.

**Startup.** Catalogue, hooks, settings and the static asset manifest are validated; any
failure sets readiness false and planning endpoints return a minimal 503 page. Cache open
failure: degraded mode without persistence. Model unreachable at the startup probe:
`model_ready = false`, fallback allowed. Health and readiness never call providers or the
model; readiness reports the last known model state.

**Shutdown.** Stop admission (503); waiting POSTs receive a minimal 503 page; cancel owned
tasks and wait at most 5 s; close the HTTP client; queue
the SQLite close on its owner thread, wait at most 2 s, then shut the executor down. A
guard flag rejects any database use after close. Thread work that outlives its awaiting
coroutine is bounded by `busy_timeout` and its result is discarded. A generation running
at shutdown is cancelled and the slot is marked unknown. The process never stops other
workloads on the host.
