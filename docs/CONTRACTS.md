# Shared build contracts — baseline 8.20

Status: **baseline 8.20, accepted specification**, 10 October 2026; the build starts only
after Mats's "kör". These are the interfaces
that parallel work packages ([BUILD-PACKAGES.md](BUILD-PACKAGES.md)) build against. Behaviour
stays in the owning documents; this file names the shapes that cross package boundaries.

| Topic | Owning document | This file adds |
|---|---|---|
| Product rules, D39 | PRODUCT-FIT.md, PLAN.md | type names |
| Backend behaviour | BACKEND-CONTRACT.md | ports, routes |
| Errors and copy for errors | ERROR-HANDLING.md | the error enum and status map |
| Visual tokens, components, copy deck | DESIGN-SPEC.md | template context |
| Request budget, cache | ARCHITECTURE.md §14–15 | none |

Where this file and an owning document differ, the owning document wins and this file is
corrected through §10. Route paths, field names and type names below are accepted as
the baseline; changes go through §10.

**Owner:** the integration owner (WP0, BUILD-PACKAGES §2). Contract files in the
repository (`core/types.py`, `core/errors.py`, `planner/ports.py`,
`planner/schema/selection.v*.json`, `web/forms.py`, `web/views.py`, `frontend/css/tokens.css`,
`tests/fixtures/views.py`, `tests/fixtures/walkthrough.py`)
are written in WP0 and changed only through §10.

## 1. Conventions

- Python 3.14; frozen `dataclass(slots=True)` values; `StrEnum` for closed sets; no
  `Any` across a package boundary; mypy strict.
- Time: timezone-aware `datetime` in UTC inside the app; local time only when rendering.
  Durations as `int` minutes. Distances as `int` metres.
- Opaque IDs (session, job, idempotency key, location candidate): `secrets.token_urlsafe`,
  16 bytes for job/key/candidate, 32 for session and CSRF. Never derived from input.
- Outcomes are values, not exceptions: `Ok[T] | Empty | Malformed | TransportFailure |
  QuotaOrUnavailable` (BACKEND-CONTRACT §6). Cancellation propagates as
  `asyncio.CancelledError` and is never converted to an outcome.

## 2. Domain types (`core/types.py`)

```python
class Who(StrEnum): SOLO = "solo"; KIDS = "kids"
class AgeBand(StrEnum): B0_2 = "0-2"; B3_5 = "3-5"; B6_9 = "6-9"; B10_12 = "10-12"
class TimeBudget(IntEnum): M30 = 30; H1 = 60; H2 = 120; HALF_DAY = 240   # D35
class Energy(StrEnum): GENTLE = "gentle"; MODERATE = "moderate"; ENERGETIC = "energetic"
                       # display labels: Gentle / Moderate / High (DESIGN-SPEC §9, TC-001).
                       # ENERGETIC is never shown to a user; "High" is never a stored value.
class InterestTag(StrEnum): ...   # 14 tags, PRODUCT-FIT §3.2 (D39 only)
class InterestStatus(StrEnum): MATCHED, NO_MATCH, UNCLEAR, NOT_PROVIDED   # model-facing
class InterestOutcome(StrEnum): MATCHED, NO_MATCH, UNCLEAR, NOT_PROVIDED, NOT_APPLIED
                                # code-side; NOT_APPLIED = interpretation failed (PRODUCT-FIT §3.4)
class Season(StrEnum): SPRING, SUMMER, AUTUMN, WINTER   # D30; Activity.seasons (CC-002)
class Source(StrEnum): MODEL = "model"; FALLBACK = "fallback"; REPLAY = "replay"
class JobState(StrEnum): RUNNING, NEEDS_LOCATION_CHOICE, WAITING, GENERATING, CANCELLING,
                         COMPLETE, FALLBACK, UNAVAILABLE, FAILED, EXPIRED
                         # CANCELLING = internal cleanup at deadline or shutdown only (D43)
                         # = ARCHITECTURE §4 diagram, one value per state
```

| Type | Fields (all required unless marked) |
|---|---|
| `Coordinates` | `lat: float`, `lon: float` (finite, in range, rounded to 2 dp on construction) |
| `TypedPlace` | `text: str` (2–80 chars, NFC, printable) |
| `Answers` | `who`, `age_bands: frozenset[AgeBand]` (empty iff solo), `time_budget`, `energy`, `location: Coordinates \| TypedPlace`, `stroller: bool`, `step_free: bool` (D42), `interest_text: str \| None` (D39; memory only, excluded from `repr`, hashing and logs) |
| `AnswersSummary` | everything in `Answers` except `interest_text`, plus `location_label: str` (geocode display label, or "Your location" for device coordinates) — kept with the result for the answers summary and the prefilled "Change answers" form |
| `Activity` | one field per key in activities.toml (**CC-002**): `activity_id` (TOML `id`), `title`, `who`, `ages`, `energy`, `place_kinds` (TOML `places`), `generic_ok`, `interests: tuple[InterestTag, ...]` (1–3), `minutes_min`/`minutes_max` (TOML `minutes = [min, max]`, on site, travel excluded), `rain_ok`, `max_rain_pct`, `min_temp_c`, `max_wind_kmh`, `max_temp_c: int \| None` (optional), `daylight_only` (TOML `daylight`), `activity_suits_stroller`, `seasons: frozenset[Season]` (empty = all year, D30), `optional`, `steps`, `adapt`, `ask: str \| None`, `safety`, `card: tuple[str, ...]` (empty, or exactly 9 items for a bingo-style card). A contract test parses the TOML and compares the key set, so prose can no longer stand in for the shape |
| `Hook` | one field per key in hooks.toml (**CC-003**): `hook_id` (TOML `id`), `text` (a fixed sentence, no placeholders), `for_who` (TOML `for`), and the three flags that decide which pairs may offer it — `needs_destination`, `generic_only`, `max_energy: Energy \| None`. Code derives each pair's `allowed_hook_ids` from these; the model never sees the rule |
| `Reason`, `DerivedReason` | as in drafts/hooks.toml: `reason_id` (TOML `id`), `when`, `text`. `when` is reviewer-facing prose, not a machine-evaluated expression; the condition is implemented in `core/ideas.py` (open item in CC-003) |
| `Place` | `place_id: str` (opaque, internal), `name: str` (≤ 60, plain text; escaped once at render), `kind: str`, `coords`, `fee: Literal["no","yes","unknown"]`, `osm_access: Literal["yes","limited","no","unknown"]` (OSM `wheelchair` tag, reported, never verified) |
| `WeatherWindow` | `start`, `end`, `fetched_at`, `tz: str` (IANA name from the provider), and the hourly arrays as received (BACKEND-CONTRACT §1): `times`, `temp_c`, `apparent_temp_c`, `precip_probability`, **`precipitation_mm`** (preceding-hour sum; **CC-001** — `rain_ok = false` and the `dry_window` reason both require 0 mm), `wind_kmh`, `weather_code`, plus the daily `sunrise` and `sunset`. Input to the predicates in `core/weather.py` |
| `WeatherSummary` | `fetched_at`, `tz`, `window_start`, `window_end`, `condition: WeatherCondition` (`clear`, `cloudy`, `showers_possible`, `rain_likely`, `fog`, `snow`), `temp_min_c: int`, `temp_max_c: int`, `max_precip_probability: int`, `max_wind_kmh: int` — derived by `core/weather.py` from the samples used; this, not the arrays, is kept with the result |
| `Pair` | `pair_id: str` (`p1`…`p12`, model-facing, per request), `idea_id: str` (opaque `token_urlsafe(16)`, assigned when the pairs are built, stable for the life of the result, never sent to the model), `activity_id`, `place: Place \| None` (None = generic), `distance_m: int \| None`, `travel_min: int`, `duration_min: int`, `allowed_hook_ids: frozenset[str]`, `allowed_reason_ids: frozenset[str]` |
| `Pick` | `pair_id`, `hook_id`, `reason_ids: tuple[str, ...]` (≤ 2) |
| `Interests` | `tags: tuple[InterestTag, ...]` (≤ 3; empty unless `MATCHED`), `outcome: InterestOutcome` |
| `Idea` | `pair: Pair`, `hook_id`, `reason_ids` (model or deterministic). Interest matches are **not** stored: `core/ideas.py::matched_interests(activity, tags)` computes them for display from the result's tags |
| `PlanResult` | `job_id`, `state: JobState`, `source: Source`, `ideas: tuple[Idea, ...]` (0–3, display order; immutable, D46), `notices: tuple[NoticeId \| ErrorCode, ...]`, `interests: Interests \| None`, `answers: AnswersSummary`, `weather: WeatherSummary \| None`, `planned_start`, `planned_end`, `valid_until`, `retain_until`, `error: ErrorCode \| None`. Whole object ≤ 32 KiB |
| `LocationCandidates` | up to 5 × (`candidate_id`, `label` ≤ 80, `coords`, `job_id: str \| None` once consumed), `answers: Answers` (incl. D39 text, memory only), `expires_at` |

`NoticeId` is a `StrEnum` of notices that are not in the ERROR-HANDLING table:
`GENTLER_THAN_ASKED`, `INTEREST_NO_MATCH`, `INTEREST_UNCLEAR`,
`INTEREST_NOT_APPLIED`, `INTERESTS_USED_BY_FALLBACK`, `REPLAY`. `DeploymentMode` (`hosted_live` = the product and primary build path; `local` =
optional development; `replay` = **inactive**, D24 superseded by D48, kept only so the
enum is stable) comes from settings and is passed explicitly to presenters; it selects mode-specific copy such as the privacy note. The
successful-result rows of that table (`FEWER_MATCHES`, `MODEL_FALLBACK`, `PLACES_CACHED`)
stay `ErrorCode` members and render as notices on a result.

## 3. Error codes (`core/errors.py`)

`ErrorCode` is a `StrEnum` whose members are exactly the codes in the ERROR-HANDLING §2
table (INPUT_INVALID … REPLAY_FIXTURE_MISSING). A test asserts the enum and the table
match. HTTP mapping (ERROR-HANDLING §3); **this section is canonical** and states which
response carries each status (round 8.12).

**Responses are full pages only.** Every HTML response is a complete page. With htmx,
the same request carries `HX-Request`; the server returns the same page and htmx swaps
`<main>` from it (`hx-select`), for every status including 4xx and 5xx (`hx-status`
allows the error swaps). There are no fragment endpoints. Plain and enhanced paths get
identical statuses and bodies; both are tested for every row below.

**POST `/plan` and POST `/location-choice`**

| Situation | Status | Body |
|---|---|---|
| Job admitted, or joined (same key and same fingerprint, §7), and it reached a terminal state | **303** to `/results/{job_id}` | — (the outcome's status is on the GET) |
| Repeat of an already consumed, owned location candidate | **303** to that candidate's job | — |
| Unparseable body | 400 | error page |
| Unknown session, CSRF mismatch, bad Origin | 403 SESSION_INVALID | error page |
| Same key, different fingerprint | 409 REQUEST_CONFLICT | error page with "Start a new search" |
| Body over 8 KiB / not urlencoded | 413 / 415 | error page |
| Invalid or incomplete answers | 422 INPUT_INVALID | form page, answers kept, error summary |
| `/location-choice` with a `candidate_id` that is not in this session's live candidate set: unknown, forged, from another session, expired or already removed | 422 LOCATION_CHOICE_EXPIRED | manual-entry form; same body in every one of these cases, so nothing about other sessions is revealed |
| An active job in this session, or a session, global or per-network rate limit (D49) | 429 REQUEST_BUSY (`Retry-After` when known) | error page linking to the active result, answers kept |
| Daily planning allowance exhausted (hosted live mode, D49; DEPLOYMENT §2.3) | 503 SERVICE_LIMIT_REACHED (`Retry-After` until 00:00 UTC) | error page, answers kept |
| Quota storage cannot be read or written (hosted live mode; fails closed) | 503 SERVICE_UNAVAILABLE (`Retry-After: 60`) | error page, answers kept; never mentions midnight |
| Honeypot `hp_note` not empty (D49) | 422 INPUT_INVALID | form re-rendered with answers kept, the honeypot cleared and "Something in the form couldn't be accepted. Please check your answers and send them again."; no provider or model call |
| Readiness false, or shutdown | 503 | minimal error page |

A POST never returns 404: location candidates are form values scoped to the session, so
the uniform 422 above is their single outcome. 404 is only for URLs that name a job,
result or idea (below).

**GET `/results/{job_id}`** (owned job; otherwise 404 with the same body as an unknown ID)

| Job outcome | Status | Page |
|---|---|---|
| Still running (e.g. a second tab) | waits, bounded by the job's deadline, then as below | — |
| Complete or Fallback (1–3 ideas, with notices such as MODEL_FALLBACK, FEWER_MATCHES, PLACES_CACHED, PLACES_UNAVAILABLE with generic ideas) | 200 | results; historical view after `valid_until` |
| NO_MATCHES, WEATHER_RESTRICTED (evaluated; nothing qualified) | 200 | notice with the edits that could help |
| DAYLIGHT_NIGHT, DAYLIGHT_TOO_SHORT (family path; evaluated before the weather limits, BACKEND-CONTRACT §1) | 200 | fixed copy, answers summary and "Change answers"; no model call. The verdict is not cached: a resubmission re-runs every check (TC-002) |
| NeedsLocationChoice, not yet consumed | 200 | choice page (LOCATION_AMBIGUOUS) |
| NeedsLocationChoice, consumed | 303 to the most recent job from that set | — |
| LOCATION_NOT_FOUND | 422 | form page, answers kept, location error |
| SERVICE_LIMIT_REACHED (hosted: the run's allowance was exhausted at reservation) | 503 | notice, answers kept |
| SERVICE_UNAVAILABLE (hosted: the reservation could not be stored) | 503 | notice, answers kept |
| WEATHER_UNAVAILABLE, GEOCODER_UNAVAILABLE, PLACES_UNAVAILABLE without generic ideas (a required service was unavailable; nothing evaluated) | 503 | notice with retry; `Retry-After` only from a real provider cooldown |
| Failed | 500 UNEXPECTED_FAILURE | safe message with reference |
| Removed (past `retain_until` or session ended) | 404 | same as unknown |

**GET `/results/{job_id}/ideas/{idea_id}`**: 200 (historical view after `valid_until`);
404 for an unknown or unowned job, an `idea_id` not in the result, or a removed result.

**Any GET in the hosted product (B2, DEPLOYMENT §2.2):** beyond 600 GETs per network in
the sliding hour, 429 REQUEST_BUSY with `Retry-After`, checked before routing: a minimal
static page for a full-page request, the same text as a fragment for an htmx request,
an empty body for `/static/*`. `/healthz` is never counted. This is an abuse limit, not a
spending cap.

Not reached in v1: 410 RESULT_EXPIRED (no route changes a result) and the codes marked
"not in v1" in ERROR-HANDLING §2. The contract test compares `ErrorCode` with the
ERROR-HANDLING table rows that are in v1.

## 4. Ports (`planner/ports.py`)

```python
class Geocoder(Protocol):
    async def resolve(self, place: TypedPlace, deadline: float) -> Outcome[GeocodeHits]: ...
class PlacesProvider(Protocol):
    async def nearby(self, at: Coordinates, radius_m: int, kinds: frozenset[str],
                     deadline: float) -> Outcome[tuple[Place, ...]]: ...
class WeatherProvider(Protocol):
    async def window(self, at: Coordinates, start: datetime, end: datetime,
                     deadline: float) -> Outcome[WeatherWindow]: ...
class Ranker(Protocol):
    async def select(self, request: ModelRequest, deadline: float) -> Outcome[RawSelection]: ...
class Catalogue(Protocol):
    def activities(self) -> tuple[Activity, ...]: ...
    def hooks(self) -> tuple[Hook, ...]: ...
    def reasons(self) -> tuple[Reason, ...]: ...
class Clock(Protocol):
    def now(self) -> datetime: ...
    def monotonic(self) -> float: ...
```

### 4.1 Cache, single flight and provider gate (`storage/`, WP4)

WP3 adapters make exactly one HTTP attempt per call and nothing else (no retry). WP4 provides
the wrappers that give the planner cached providers with the **same port types** as
above, so the planner never sees caching. Interfaces (in `planner/ports.py`, written by
WP0):

```python
class CacheNamespace(StrEnum): GEOCODE = "geocode"; PLACES = "places"; WEATHER = "weather"
class ProviderName(StrEnum): NOMINATIM = "nominatim"; OVERPASS = "overpass"; OPEN_METEO = "open_meteo"

@dataclass(frozen=True, slots=True)
class CacheKey:                       # all inputs that affect the result (ARCHITECTURE §15)
    namespace: CacheNamespace
    provider: ProviderName
    params: tuple[tuple[str, str], ...]   # normalised, sorted; coordinates already rounded
    schema_version: int
    def digest(self) -> str: ...          # SHA-256 hex of a canonical encoding

class CacheStore(Protocol):           # SQLite on the DB thread; never raises to callers
    async def get(self, key: CacheKey, now: datetime) -> bytes | None: ...   # fresh entries only
    async def put(self, key: CacheKey, payload: bytes, fresh_until: datetime) -> None: ...

class ProviderGate(Protocol):         # in memory, independent of SQLite (BACKEND-CONTRACT §6)
    def admit(self, provider: ProviderName, key: CacheKey, now: float) -> GateDecision: ...
    def record(self, provider: ProviderName, key: CacheKey, outcome: OutcomeClass, retry_after_s: float | None, now: float) -> None: ...
    async def pace(self, provider: ProviderName, deadline: float) -> bool: ...  # False = deadline would pass

GateDecision = Allow | CoolingDown(until: float) | NegativeCached(until: float) | Saturated

class SingleFlight(Protocol):
    async def run(self, key: CacheKey, fetch_deadline: float, caller_deadline: float,
                  fetch: Callable[[float], Awaitable[Outcome[bytes]]]) -> Outcome[bytes]: ...
    # fetch_deadline is fixed by the first caller; joiners never extend it; the last
    # waiter leaving cancels the fetch; cancelled fetches never reach the cache

class Counters(Protocol):             # stage counters, no answers or coordinates
    def incr(self, name: str, stage: str) -> None: ...

def cached_places(inner: PlacesProvider, store: CacheStore, gate: ProviderGate,
                  flight: SingleFlight, counters: Counters, clock: Clock) -> PlacesProvider: ...
# likewise cached_geocoder(...) -> Geocoder and cached_weather(...) -> WeatherProvider
```

Payloads are bytes: each domain type that is cached (`GeocodeHits`, `tuple[Place, ...]`,
`WeatherWindow`) has `to_cache() -> bytes` and `from_cache(bytes)` defined with the type
in `core/types.py` (WP0), so WP3 and WP4 never depend on each other. A payload that fails
to decode is treated as a miss and counted.

Order inside a wrapper (corrected in 8.9 so that every HTTP attempt passes the gate):

```
cache get ─ hit → return
          └ miss → single flight (one fetch per key):
                attempt 1: gate.admit → gate.pace → inner call → gate.record
                if TransportFailure and stage budget left and gate.admit/pace allow:
                attempt 2: (same sequence)               # the only retry, in the wrapper
                cache put (Ok and Empty only); negative-cache entry only if the
                final attempt ended in TransportFailure
```

`gate.admit` returns `CoolingDown` immediately during a provider cooldown, which is
`max(60 s, Retry-After)` with no lower cap (BACKEND-CONTRACT §6); the caller gets the
unavailable outcome at once and is never held.

### 4.2 Planner service

The web layer depends on the planner only through this protocol, so routes can be built
against a fake planner while the real one is written:

```python
class PlannerService(Protocol):
    async def start_or_join(self, session_id: str, key: str, answers: Answers) -> JobRef: ...
    async def choose_location(self, session_id: str, candidate_id: str) -> JobRef: ...
        # idempotent per candidate: the same owned candidate returns the same JobRef
        # (joined=True) until that job's retain_until (BACKEND-CONTRACT §3)
    async def wait(self, session_id: str, job_id: str) -> PlanResult: ...
    def get(self, session_id: str, job_id: str) -> PlanResult | None: ...
```

Removed in 8.11: `observe` and `PlannerEvent` (no progress stream, D43), `cancel` (no
Stop, D43) and `resort` (no re-sort, D46). Fallback ideas use the deterministic hook and
reasons: the first allowed hook and the first two true reasons in hooks.toml order.
`JobRef` carries `job_id` and whether the job was joined. Ownership failures raise one `NotFound`; admission failures raise `Busy`
with an optional retry delay; key conflicts raise `Conflict`.

`deadline` is an absolute `monotonic()` value; adapters use `min(stage budget, remaining)`.
Caching, gating and single flight are the §4.1 wrappers (WP4 wraps WP3), invisible to
the planner. `RawSelection` is untrusted parsed JSON; only
`core/ideas.py` turns it into `Pick` and `Interests`.

## 5. Routes (`web/routes/`)

All HTML responses: `Cache-Control: no-store, private`; full security headers; CSP per
PLAN §9. Every POST: urlencoded only, ≤ 8 KiB, CSRF token, Origin check (BACKEND-CONTRACT
§5, §7). Every `{job_id}` route checks session ownership. A GET never starts work.

| Method and path | Purpose | Plain form | Enhanced (htmx) | Upstream calls |
|---|---|---|---|---|
| GET `/` | form page; creates the session | page | same page | 0 |
| POST `/plan` | start or join a job | waits for the terminal state, then 303 to `/results/{job_id}` (other statuses: §3) | same request and responses; busy state shown at once; htmx follows the 303 and swaps `<main>` from the full page | per D33 |
| GET `/results/{job_id}` | result, notice or historical result | page | page | 0 |
| GET `/results/{job_id}/ideas/{idea_id}` | detail and print view of one idea, addressed by its stable `idea_id` | page | page | 0 |
| POST `/location-choice` | choose an ambiguous-place candidate; starts at most one job per candidate | as `/plan`; uniform 422 for any candidate not in the session's live set (§3) | as `/plan` | no geocode |
| GET `/healthz` | liveness, `ok` only; Fly health check; not counted in B2 | text | — | 0 |
| GET `/readyz` | app readiness; model readiness reported separately in the body as `model: ready \| unavailable` | text | — | 0 |
| GET `/static/{hashed}` | assets, immutable cache | — | — | 0 |
| ~~GET `/examples`, `/examples/{id}`~~ | **inactive**: replay demo (D24 superseded by D48); not built, returns 404 | — | — | 0 |

**Detail stability.** Results are immutable (D46), so a detail URL shows the same
content for as long as the result is retained: activity, introduction, reasons, place,
times, weather and interest match. Past `valid_until` it renders the historical view; an
`idea_id` not in the result, or a result past `retain_until`, returns 404.

Removed in 8.11: `GET /results/{job_id}/events` (D43), `POST /results/{job_id}/cancel`
(D43), `POST /results/{job_id}/interests` (D46).

## 6. Model input and output (`planner/schema/`)

**Input** (built only by `planner`, sent by the WP5 adapter): system prompt file
`planner/prompts/select.v{n}.md` (versioned); user message with three delimited blocks:
`<pairs>` (JSON list: `pair_id`, `activity_id`, activity title, place kind or `none`,
distance band, energy levels, `interests`, allowed hook IDs, allowed reason IDs),
`<vocabulary>` (D39 tags) and `<family_text>` (D39 text or empty). Place names,
coordinates and free-text OSM fields are **never** sent to the model.

**Output, `selection.v1`** (D39 declined) and **`selection.v2`** (D39 accepted). v2:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["interests", "interest_status", "picks"],
  "properties": {
    "interests": {"type": "array", "maxItems": 3, "uniqueItems": true,
                  "items": {"enum": ["animals","birds","bugs","trees","colours","shapes",
                                     "stories","running","building","sounds","drawing",
                                     "sky","quiet","puddles"]}},
    "interest_status": {"enum": ["matched","no_match","unclear","not_provided"]},
    "picks": {"type": "array", "maxItems": 3, "items": {
      "type": "object", "additionalProperties": false,
      "required": ["pair_id","hook_id","reason_ids"],
      "properties": {
        "pair_id": {"type": "string"},
        "hook_id": {"type": "string"},
        "reason_ids": {"type": "array", "maxItems": 2, "uniqueItems": true,
                       "items": {"type": "string"}}}}}
  }
}
```

v1 is the same object with `picks` only. The schema is passed as OpenRouter's
`response_format` (`json_schema`, strict) in the product, or as Ollama's `format` in
optional local development;
whichever keywords the runtime enforces, `core/ideas.py` re-validates everything:
per-pair hook and reason sets, duplicates, D36, `matches_interest` dropped from model
output and derived by code (PRODUCT-FIT §3.3). Output must fit `num_predict` 256 (proof
obligation).

## 7. Form fields (`web/forms.py`)

Unknown field names and repeated scalar fields → 422. Values not listed → 422.

| Form | Field | Values | Rule |
|---|---|---|---|
| plan | `csrf_token` | token | required |
| plan | `idempotency_key` | opaque, rendered into the form on GET | required; same key + different input → 409 |
| plan | `who` | `solo`, `kids` | required |
| plan | `age_band` (repeatable) | `0-2`, `3-5`, `6-9`, `10-12` | ≥ 1 and unique when `kids`; ignored when `solo` |
| plan | `time` | `30`, `60`, `120`, `240` | required |
| plan | `energy` | `gentle`, `moderate`, `energetic` | default `moderate`; rendered as Gentle / Moderate / High, never as the raw value (TC-001) |
| plan | `location_mode` | `typed`, `coords` | default `typed`; `coords` is set by "Use my location" or carried by the prefilled "Change answers" form (D46), so a resubmission needs no new geocode |
| plan | `place` | text 2–80 | required when `typed` |
| plan | `lat`, `lon` | decimal | required when `coords`; rounded server-side |
| plan | `location_label` | text ≤ 80, printable | optional with `coords` (display only; default "Your location"); plain text, escaped at render |
| plan | `stroller` | `1` | optional; D42: only activities with `activity_suits_stroller = true` |
| plan | `step_free` | `1` | optional; **D42 (P), accepted 8.20**: label "Prefer places reported as step-free"; ranks OSM `wheelchair=yes` first and never filters; unknown access labelled "Step-free access not verified". Access is always labelled as reported |
| plan | `hp_note` | must be empty | honeypot (DEPLOYMENT §4); present in every plan form, hidden from keyboard and screen readers; excluded from the fingerprint |
| plan | `interests_text` | text ≤ 120, printable | optional; D39 only, otherwise unknown field. In "Change answers" it is prefilled with the inferred tag labels ("birds, puddles"), never the original text, with the hint "These are the interests we recognised. Edit them for your next search." |
| location-choice | `csrf_token`, `candidate_id` | token, opaque | required; no client key: the submission key is derived from the candidate (BACKEND-CONTRACT §3) |

**Submission fingerprint (idempotency comparison, round 8.12).** The job registry compares
submissions by `fingerprint = HMAC-SHA256(process_key, canonical_form)`, never by
dataclass hashing. `process_key` is 32 random bytes created at startup and never stored.
`canonical_form` is the UTF-8 encoding of every plan field except `csrf_token`,
`idempotency_key` and `hp_note`, in a fixed field order, after normalisation: NFC, surrounding
whitespace trimmed, age bands sorted and de-duplicated, coordinates rounded to 2 dp,
absent optional fields as empty strings, and **including `interests_text`**. So two
submissions that differ only in their interest text are different submissions. The
fingerprint is kept with the idempotency record only, for the job's retention (until the
earlier of `retain_until` and session end), is never logged, rendered or sent anywhere,
and is lost with the jobs on restart. Same key + same fingerprint joins; same key +
different fingerprint is 409. For `/location-choice` the key is `candidate:<id>` and the
fingerprint is the candidate ID itself. Owner: `web/forms.py`, including `canonical_form`
and the HMAC, is a WP0 contract file (BUILD-PACKAGES §3); WP7 calls it; `planner/jobs.py`
stores and compares (WP6).

"Change answers" renders a fresh `idempotency_key`, so changed answers are a new job;
the old result stays as it was until `retain_until` (D46). Forms removed in 8.11: cancel
and interests.

## 8. Template context (`web/views.py`, built by `web/presenters.py`)

Templates receive only these view models (frozen dataclasses), never domain objects,
raw provider data or exceptions. Strings are plain text: copy from `web/copy.py`,
catalogue and hook text verbatim, OSM labels as data. Escaping happens once, by Jinja
autoescape (BACKEND-CONTRACT §7). Times are `HH:MM` and dates `Sat 10 Oct 2026` in the
timezone of the planned location (`WeatherSummary.tz`), never the server's.

**Presenter functions** (WP8 owns `web/presenters.py` and `web/copy.py`). Every input is
an explicit parameter: no globals, no hidden catalogue or settings lookups. WP7 routes
gather the arguments and pass the view to `render`.

```python
# One carrier, so the signature stays small and every value stays explicit
# (CC-A, CC-B, CC-C, CC-D, CC-G). FormContext lives in web/views.py.
def present_form(context: FormContext) -> FormPage
def present_result(result: PlanResult, catalogue: Catalogue, now: datetime,
                   session: SessionView, mode: DeploymentMode, d39_enabled: bool) -> ResultPage
def present_detail(result: PlanResult, idea_id: str, catalogue: Catalogue,
                   now: datetime) -> DetailPage
def present_error(code: ErrorCode, reference: str | None, form: FormPage | None) -> ErrorPage
```

`FormContext` carries: `session`, `mode`, `d39_enabled`, `assets` (the build manifest,
which the caller knows and a presenter must never reach for), `answers` (a previous
result's complete, geocoded answers, D46), `submitted` (what was actually typed, possibly
partial or ungeocodable, which wins field by field so a 422 keeps it), `errors`,
`candidates`, `candidates_tz` (candidate expiry renders in the planned location's
timezone, never the server's) and `interests` (a previous result's validated tags, so
"Change answers" prefills the interests field with their labels rather than the original
free text).

The busy state is static markup in the form (button text "Finding outings…" and the
note "This can take up to 20 seconds."), shown by htmx's request indicator; it needs no
view model (D43). `SessionView` carries `csrf_token` and, on pages with a plan form, a fresh
`idempotency_key`. `Catalogue` is the port from §4 (activities, hooks, reasons), passed
in by the route from the app state built in `main.py`.

**View models.** Every field required; `| None` means "not shown". The comment names the
source of each value, as traced in WALKTHROUGH.md.

```python
class AssetRef:      url: str; integrity: str                        # build manifest
class PageMeta:      title: str; assets: Mapping[str, AssetRef]; demo_mode: bool   # copy; manifest; mode
class SessionView:   csrf_token: str; idempotency_key: str | None    # session store
class FieldError:    field: str; anchor: str; message: str           # errors + copy
class Option:        value: str; label: str; icon: str | None; checked: bool  # enums + copy + values
class FormPage:      meta: PageMeta; session: SessionView
                     intro: str                                       # copy
                     who: tuple[Option, ...]; ages: tuple[Option, ...]
                     time: tuple[Option, ...]; energy: tuple[Option, ...]
                     location_mode: str; place: str                   # values
                     coords: tuple[str, str] | None                   # rounded; device or carried from the result (D46)
                     location_label: str | None                       # AnswersSummary.location_label when carried
                     place_hint: str                                  # copy by DeploymentMode
                     stroller: bool; step_free: bool                  # values
                     interests_text: str | None                       # None = D39 off; prefilled only with tag labels
                     field_errors: Mapping[str, FieldError]; summary: tuple[FieldError, ...]
                     candidates: tuple[Option, ...]                   # LocationCandidates labels
                     candidates_expire_at: str | None
class ActionView:    label: str; url: str; method: Literal["get", "post"]; csrf_token: str | None
class NoticeView:    kind: Literal["info", "success", "alert"]; heading: str | None
                     body: str; actions: tuple[ActionView, ...]       # copy by code + params
class InterestsView: heading: str; labels: tuple[str, ...]           # Interests.tags + copy; plain labels, not controls
                     note: str                                        # "To change these, edit … under Change answers."
class WeatherView:   icon: str; line: str                             # WeatherSummary + copy:
                     checked_at: str; window: str                     # "Checked at 10:31 for 10:31–11:31: …"
class AnswersView:   lines: tuple[str, ...]                           # AnswersSummary + copy
                     change_label: str                                # "Change answers"
class PlaceView:     name: str | None; kind_label: str                # Pair.place; copy (None = generic)
                     distance: str | None                             # Pair.distance_m: "About 0.6 km away (straight line)"
                     uncertainty: tuple[str, ...]                     # Place.fee, Place.osm_access + copy
class IdeaView:      idea_id: str; variant: Literal["sage", "peach", "butter"]   # Idea; position
                     title: str                                       # Activity.title
                     intro: str                                       # Hook.text verbatim (no placeholders)
                     reasons: tuple[str, ...]                         # Reason.text by Idea.reason_ids
                     interest_match: str | None                       # matched_interests(activity, result tags)
                     place: PlaceView
                     times: str                                       # "24 min there and back · 36 min activity" (estimates)
                     detail_url: str                                  # f"/results/{job_id}/ideas/{idea_id}"
                     # The card renders title, intro, place, times, uncertainty and the link only;
                     # reasons and interest_match appear on the detail page ("Why this idea"), 8.12.
class ResultPage:    meta: PageMeta; session: SessionView; heading: str
                     answers: AnswersView; edit_form: FormPage        # prefilled, inside "Change answers"
                     weather: WeatherView | None                      # shown once above the ideas
                     ideas: tuple[IdeaView, ...]                      # PlanResult.ideas; 0–3, no padding
                     notices: tuple[NoticeView, ...]; interests: InterestsView | None
                     source_label: str | None                         # Source + copy
                     is_historical: bool; historical_text: str | None # now vs valid_until
                     plan_again: ActionView
class BingoView:     heading: str; items: tuple[str, ...]             # Activity.card (9 items, 3 × 3 grid)
class ActivityView:  steps: tuple[str, ...]; optional: tuple[str, ...]; adapt: str
                     ask: str | None; safety: str                     # Activity, verbatim
                     card: BingoView | None                           # None when Activity.card is empty
class PrintView:     context_line: str  # "Planned for Sat 10 Oct 2026, 10:31–11:31 (Europe/Stockholm), near Uppsala"
                     weather_line: str  # "Weather checked at 10:31 on Sat 10 Oct 2026; times are estimates."
                     source_line: str   # "Place data © OpenStreetMap contributors; weather from Open-Meteo"
                     note: str          # "Check the weather again before you go if plans change."
class DetailPage:    meta: PageMeta; idea: IdeaView; activity: ActivityView
                     weather: WeatherView; print: PrintView           # the result's weather summary
                     notices: tuple[NoticeView, ...]                  # historical
                     is_historical: bool; back_url: str; print_label: str
class ErrorPage:     meta: PageMeta; notice: NoticeView; reference: str | None
                     form: FormPage | None                            # 422 re-render keeps answers
```

| Template | Receives |
|---|---|
| `base.html` | `PageMeta` (via the page) |
| `pages/form.html` | `FormPage` |
| `pages/results.html` | `ResultPage` |
| `pages/detail.html` | `DetailPage` |
| `pages/error.html` | `ErrorPage` |
| `partials/idea_card.html` | `IdeaView` |
| `partials/notice.html` | `NoticeView` |
| `partials/interests.html` | `InterestsView` |
| `partials/bingo.html` | `BingoView` |

Fixture instances of every view model for every DESIGN-SPEC §12 state, and the domain
fixtures they are presented from (WALKTHROUGH.md), live in `tests/fixtures/` (WP0 creates
them with the types; WP8 renders them; WP7 uses them in route tests).

## 9. Design tokens

Canonical values: DESIGN-SPEC §1. Implemented once in `frontend/css/tokens.css` (`@theme`
colours, type scale, space, corners as `@utility`, shadow, focus). Templates use token
utilities only; no raw hex, pixel radius or shadow values in templates or component CSS.
`scripts/check_contrast.py` reads `tokens.css` and checks every pair listed in
DESIGN-SPEC §1.1.

## 10. Contract-change process

### 10.0 Tracked changes (TC) — changes Mats makes to the accepted baseline

A change to the accepted baseline is a tracked change, not a new planning round
(PLAN §0). Each one is recorded as `docs/decisions/tracked-changes/TC-NNN.md` with: the
change, the reason, **the commit SHA that edits the documents**, the documents edited, any
rules re-homed, the acceptance checks affected, and the approver. Conventions:

- **Marker.** Every edited sentence, table row or cell ends with `(TC-00x)`, in the style
  the documents already use for `(Mats 8.20)`, so baseline text and tracked text are
  distinguishable without a diff.
- **Two commits.** The document edits land first; the record commit follows and names the
  edit commit's SHA. A lightweight tag `tc-00x` points at the edit commit.
- **Baseline is immutable.** Commit `8b734cc` (baseline 8.20) is never amended, rebased or
  force-pushed. `git diff 8b734cc -- docs/` is the complete tracked-change set.
- A TC needs Mats for the same reasons §10.4 lists; in practice Mats initiates them.

| TC | Change | Edit commit | Status |
|---|---|---|---|
| TC-001 | User-facing energy label "High"; internal value stays `energetic` | `7f443e6` | accepted (Mats) |
| TC-002 | Daylight copy promises no cross-limit remedy; a resubmission reruns all checks | `6917ca4` | accepted (Mats) |
| TC-003 | No Hermes in this build: Claude Code integrates, Codex reviews, Mats approves | `5251a9e` | accepted (Mats) |
| TC-004 | `scripts/check.ps1` and `release.ps1` are the gate scripts | `bb4ff07` | accepted (Mats) |
| TC-005 | Package `wiggle_outside`; session cookie `__Host-wo_session` | `1187030` | accepted (Mats) |
| TC-006 | M0 time-boxed to five gates; WP9b carries the rest, in parallel | `3d91f31` | accepted (Mats) |
| TC-007 | P1 resolved: fonts supplied, self-hosted, never committed (FFL 2.0) | `c9856b0` | accepted (Mats) |
| TC-008 | The approved visual direction implemented, artwork included | `051570b`, `d03c08b`, `5f8c048`, `3c1eb1d` | accepted (Mats) |
| TC-009 | Deadline budget 3 / 9 / 6 / 2, measured; both Overpass attempts share the places stage | pending (checkpoint commit by Mats) | accepted (Mats, 11 Oct) |
| TC-010 | Live Gemma through OpenRouter with the approved-provider allowlist (NextBit, DeepInfra, CoreWeave) | pending (checkpoint commit by Mats) | accepted (Mats, with the reviewer's binding changes) |

### 10.1 Contract changes raised by a package (CC)

1. A package that needs a contract change stops work on the affected part and writes a
   proposal: `docs/decisions/contract-changes/CC-NNN.md` with the change, the reason, the
   packages affected and the tests that change.
2. It does **not** edit a contract file, another package's files, a manifest or a
   lockfile.
3. The integration owner accepts or rejects it. Accepted changes are made by the
   integration owner in one commit that updates the contract file, this document and the
   contract tests together; affected packages are notified and rebase.
4. Changes that touch a decision in PLAN §0, safety, privacy, the request budget or the
   error contract also need Mats.
5. Contract tests (WP0) run on every package branch: enum/table equality, schema
   fixtures, port signatures (mypy), route table, form field list, token presence.
