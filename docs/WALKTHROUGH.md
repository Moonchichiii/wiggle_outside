# Fixture-driven walkthrough — baseline 8.20 (hosted mode)

Status: DRAFT, 10 October 2026. **Documented behaviour, not executed.** This traces one
journey through the contracts with concrete fixture data, to show that every transition
has a defined input, retained state, output, status, request count and owner. Where the
trace exposed a gap, the owning document was corrected in 8.9 or 8.11 (list at the end).
Round 8.11 applies D43 (no progress stream or Stop), D44 (no repair) and D46 (immutable
results; interests changed by resubmission). The same
data becomes `tests/fixtures/walkthrough.py` (WP0) and the acceptance test
`tests/acceptance/test_walkthrough.py` (integration owner), both still unwritten.

Journey: submit → ambiguous location → choice (double-click) → provider retry → model
result → change answers (new result) → lost response → open an older detail link →
print → expiry → removal.
Path shown: the plain form (no JavaScript). Enhanced-path differences are noted per step.

## Fixture data

- Deployment mode `hosted_live` (the primary build path, round 8.19); timezone of the place Europe/Stockholm (UTC+2) on Sat 10 Oct 2026.
- Session `S1` (cookie `__Host-tg_session`), CSRF token `T1`.
- Hosted counters at the start: daily allowance C = 0 for 2026-10-10 UTC; the network is
  well under its A, B and B2 limits (no 429 on this path).
- Answers: kids, ages 3–5 and 6–9, 1 hour, moderate energy, typed place "Bergby",
  stroller off, step-free off, D39 text "birds and puddles".
- Geocoder fixture: three hits — "Bergby, Gävleborg, Sweden", "Bergby, Uppsala län,
  Sweden", "Bergby, Åland, Finland" (candidates `c1`–`c3`).
- Weather fixture `open_meteo_boundary.json` for the chosen place, hourly arrays in UTC:

| UTC hour | 08:00 | 09:00 | 10:00 | 11:00 |
|---|---|---|---|---|
| `precipitation_probability` (preceding hour) | 20 | 30 | 40 | 50 |
| `precipitation` mm (preceding hour) | 0.0 | 0.0 | 0.1 | 0.4 |
| `weather_code` (instant) | 3 | 3 | 80 | 61 |
| `apparent_temperature` °C (instant) | 10.6 | 11.4 | 11.9 | 12.2 |
| `wind_speed_10m` km/h (instant) | 12 | 14 | 18 | 20 |

  Sunrise 05:21 UTC, sunset 16:20 UTC (07:21 and 18:20 local).
- Places fixture: Linden Park (park, 0.6 km, fee unknown, wheelchair unknown), Birchwood
  Nature Area (nature_reserve, 0.9 km, fee no, wheelchair unknown), Oak Lane Park (park,
  0.4 km, fee unknown, wheelchair yes), Elm & Oak Playground (playground, 0.5 km).
- Second model fixture output (step 10, text "birds"):
  `{"interests":["birds"],"interest_status":"matched","picks":[{"pair_id":"p4","hook_id":"explorer-club","reason_ids":["fits_time","matches_energy"]},{"pair_id":"p7","hook_id":"todays-idea","reason_ids":["in_season","close_by"]},{"pair_id":"p5","hook_id":"expedition","reason_ids":["close_by","fits_time"]}]}`
  (pair IDs are per request; `R3`'s ideas are written `j4`, `j7`, `j5`).
- Idea IDs are written `i1`, `i4`, … after their pair (`p1`, `p4`, …) for readability;
  real `idea_id`s are opaque random tokens.
- Model fixture output (schema `selection.v2`):
  `{"interests":["birds","puddles"],"interest_status":"matched","picks":[{"pair_id":"p1","hook_id":"pocket-adventure","reason_ids":["close_by","all_ages"]},{"pair_id":"p4","hook_id":"explorer-club","reason_ids":["fits_time","matches_energy"]},{"pair_id":"p7","hook_id":"todays-idea","reason_ids":["in_season","close_by"]}]}`

## Transitions

Request counts are upstream calls per step: G = geocode, P = places, W = weather,
M = model. "Owner" is the work package that implements the behaviour.

| # | Time (local) | Input | Retained state after | Output | Status | Requests | Owner |
|---|---|---|---|---|---|---|---|
| 1 | 10:30:00 | GET `/` | `S1` created (`T1`), counted against the session limit | form page; fresh `idempotency_key` `K1`; hosted place hint ("We look the town up with OpenStreetMap's search…") | 200 | 0 | WP7, WP8 |
| 2 | 10:30:40 | POST `/plan` with the answers, `K1`, `T1` | job `J1` (state `NeedsLocationChoice`); candidate set `C1` = `c1`–`c3` with labels, rounded coords **and the answers incl. D39 text**, expires 10:40:40 | 303 → `/results/J1` | 303 | G 1 | WP6, WP7 |
| 3 | 10:30:41 | GET `/results/J1` | unchanged | choice page: three radio tiles, LOCATION_AMBIGUOUS copy | 200 | 0 | WP7, WP8 |
| 4 | 10:31:00 | POST `/location-choice` `c2`, `T1` | `c2.job_id = J2`; job `J2` key `candidate:c2`, admitted 10:31:00 → `planned_start` 10:31:00, `planned_end` 11:31:00; deadline 10:31:20 | (waits; see 5–7) | — | — | WP6 |
| 4a | 10:31:00.3 | same POST again (double click) | `J2` joined (`JobRef.joined = true`) | waits on the same job | — | 0 | WP6 |
| 5 | 10:31:00–01 | stage `weather_places`: first the daily allowance C is reserved in SQLite (count 0 → 1 for the UTC day, DEPLOYMENT §2.3); then places and weather concurrently | Overpass `Ok` → places cache (7 days); Open-Meteo attempt 1 `TransportFailure` → `gate.record`, **no** negative-cache entry yet; attempt 2 passes `admit` and `pace`, `Ok` at 10:31:01.2 → `fetched_at`; weather cache (30 min) | — | — | P 1, W 2 | WP3, WP4 |
| 5b | (branch) | Open-Meteo attempt 1 returns 429 `Retry-After: 120` | provider cooldown until 10:33:01; no attempt 2 | WEATHER_UNAVAILABLE result; any submission before 10:33:01 fails fast at `admit` | 503 on GET of the result | W 1, then 0 | WP4, WP6, WP7 |
| 6 | 10:31:01 | eligibility (pure) | samples used: precipitation 09:00 and 10:00 UTC; instants 08:00, 09:00, 10:00 UTC; daylight holds; nothing severe (code 80 is slight showers); 12 eligible pairs `p1`–`p12`, each with an `idea_id` | `WeatherSummary`: showers_possible, 11–12 °C, max 40 %, max 18 km/h | — | 0 | WP1 |
| 7 | 10:31:02–06 | stage `choosing`: one model call (OpenRouter → the pinned endpoint) with the 12 pairs and the D39 text in `<family_text>` | output validated: interests `birds`, `puddles` (outcome MATCHED); picks `p1` → `i1`, `p4` → `i4`, `p7` → `i7`; immutable result `R2` state `Complete`, source MODEL, ideas (`i1`, `i4`, `i7`); created 10:31:06; `valid_until` = min(10:36:06, 11:01:01, 10:41:00) = **10:36:06**; `retain_until` **11:36:06**; D39 text dropped from memory | POST from step 4 (and 4a) answered: 303 → `/results/J2` | 303 | M 1 | WP5, WP6 |
| 8 | 10:31:06 | GET `/results/J2` | unchanged | answers summary ("Me and the kids (3–5, 6–9) · 1 hour · Moderate · near Bergby, Uppsala län, Sweden"); weather once; plain labels "We think they're into: birds, puddles."; three cards; match lines "puddles" (i1), "birds" (i4) | 200 | 0 | WP7, WP8 |
| 9 | 10:32:00 | GET `/results/J2/ideas/i7` (new tab) | unchanged | detail of Leaf colour hunt from `R2` | 200 | 0 | WP7, WP8 |
| 10 | 10:33:00 | POST `/plan` from "Change answers", **interests-only change**: same answers and time budget, `location_mode=coords` with the rounded coordinates and label carried from `R2`, `interests_text` edited from the prefilled "birds, puddles" to "birds", fresh key `K2` | job `J3`, `planned_start` 10:33:00; no geocode (coordinates carried); places and weather from cache (weather fetched 10:31:01, fresh, covers 10:33–11:33); C reserved (1 → 2) before the cached places and weather are used; every check re-run against the 10:33–11:33 window on the cached data (daylight, weather limits, eligibility, season, time) at 0 additional upstream calls (TC-002); one model call → immutable result `R3`: interests `birds`, ideas Nature bingo, Leaf colour hunt, Colour match walk at Elm & Oak Playground (`j4`, `j7`, `j5`); `valid_until` 10:38:05, `retain_until` 11:38:05; **`R2` unchanged** | 303 → `/results/J3` | 303 | M 1 | WP6, WP7 |
| 10a | 10:33:02 | the response to step 10 is lost; the parent presses "Try again" (same form, same `K2`, same answers) | `J3` joined | waits; answered with the same 303 | 303 | 0 | WP6, WP7 |
| 11 | 10:33:06 | GET `/results/J3` | unchanged | labels "birds"; three cards; "Elm & Oak Playground" in the HTML as `Elm &amp; Oak Playground` once | 200 | 0 | WP8 |
| 12 | 10:34:00 | GET `/results/J2/ideas/i1` (tab opened before step 10) | unchanged | Puddle jumping from `R2`, exactly as before: same intro, reasons, place, times, weather and match line "puddles" (R2's tags) | 200 | 0 | WP7, WP8 |
| 13 | 10:35:00 | GET `/results/J2/ideas/i4` and browser print | unchanged | Nature bingo with the 3 × 3 card; print context "Planned for Sat 10 Oct 2026, 10:31–11:31 (Europe/Stockholm), near Bergby, Uppsala län, Sweden. Weather checked at 10:31 on Sat 10 Oct 2026; times are estimates." | 200 | 0 | WP8 |
| 14 | 10:36:30 | GET `/results/J2` | unchanged (past `valid_until`) | historical view: "This information is no longer current. Planned for Sat 10 Oct, 10:31–11:31, weather checked at 10:31." and "Plan again" | 200 | 0 | WP7, WP8 |
| 15 | 10:36:50 | GET `/results/J2/ideas/i7` | unchanged | historical detail | 200 | 0 | WP7, WP8 |
| 16 | 10:37:00 | GET `/results/J1` | unchanged | `c2` consumed → redirect to `J2` (historical) | 303 | 0 | WP7 |
| 17 | 10:40:40 | `C1` TTL | `c1`, `c3` and the set's answers removed; consumed `c2` kept (points to `J2`) | — | — | 0 | WP6 |
| 18 | 11:07:00 | session `S1` idle for 30 min (last request at step 16, 10:37:00) | session ended: everything it owned is removed together — `R2` with `i1`, `i4`, `i7`; `R3` with `j4`, `j7`, `j5`; keys `candidate:c2` and `K2` with their fingerprints; `c2`; `J1` | — | — | 0 | WP6, WP7 |
| 19 | 11:10:00 | GET `/results/J2`, `/results/J3/ideas/j4`, `/results/J1` with the old cookie | the unknown session ID is not adopted; a fresh session `S2` is created | indistinguishable from unknown | 404 | 0 | WP7 |
| 20 | 11:10:10 | POST `/location-choice` `c2` with the old cookie and token | none | SESSION_INVALID (the token does not belong to `S2`); the page offers a fresh form | 403 | 0 | WP7 |

**Separate test, active session.** If the session stays active (a request at least every
30 minutes), removal follows `retain_until` instead: `R2` with its ideas, key and `c2`
goes at 11:36:06 while `R3` stays until 11:38:05; their URLs return 404 from then on.
A third test proves that idle expiry alone removes all owned results, keys and
candidates, with no request after the expiry.

**Totals:** G 1, P 1, W 2 (one retry), M 2 (the original search and the deliberate
"Change answers" search). Step 10 costs only the model call — a call count, not a check
count: every rule is re-evaluated against the new window on cached data (TC-002) — because only the interest
text changed, the carried coordinates and time budget give the same places key, and the
cached weather is fresh and covers the new window. Separate tests cover the other
"Change answers" cases (ARCHITECTURE §14): a newly typed place (geocode, places,
weather, model), a different time budget (places for the new radius, weather only if the
entry no longer covers the window, model) and expired weather (weather, model). Duplicate, lost-response, detail, print, expiry and removal
steps add 0, which the acceptance test asserts with respx counters (ARCHITECTURE §14).

**Enhanced path (htmx) differences (D43).** Steps 2, 4 and 10 are the same POSTs; htmx
shows the busy state ("Finding outings…" and the 20-second note) at once, follows the
303 and swaps the result region; focus moves to the results heading once it exists.
There is no progress stream and no Stop. Step 5b: the later GET returns 503 and
`hx-status` routes it to the page error region. Step 10a: htmx resubmits the same form on
"Try again".

**No-repair case (D44), not on the main path.** If step 7's output had no valid pick,
`R2` would be `Fallback` with the deterministic ranking, the MODEL_FALLBACK label and,
because the interests were valid, `INTERESTS_USED_BY_FALLBACK`; still M 1.

## Gaps this trace exposed, and where they were fixed

| Gap | Fix |
|---|---|
| A location choice had no answers to plan with | Candidate set keeps the answers (incl. D39 text) until consumed or expired — BACKEND-CONTRACT §3 |
| Double submission of a choice could start two jobs | One job per candidate, derived key — BACKEND-CONTRACT §3, CONTRACTS §4.2 |
| The negative cache would block the one permitted retry | Negative entry written only after the final attempt — BACKEND-CONTRACT §6 |
| A retry could skip pacing and a fresh cooldown | Retry moved into the wrapper; every attempt passes the gate — BACKEND-CONTRACT §6, CONTRACTS §4.1 |
| `weather_code` sampled as a preceding-hour value | Instant sampling, worked boundary example — BACKEND-CONTRACT §1 |
| `planned_start` undefined | Admission time — BACKEND-CONTRACT §2 |
| Detail content could change after interests changed | 8.9: snapshots; 8.11: immutable results, changes create a new result (D46) — BACKEND-CONTRACT §2 |
| Interest-match line could go stale | Computed from the result's own tags — CONTRACTS §2, PRODUCT-FIT §3.3 |
| "Change answers" would geocode the label again | 8.11: location carried as coordinates (`location_mode=coords`) — CONTRACTS §7 |
| "Change answers" needed the interest text, which is not retained | 8.11: prefilled with the tag labels — CONTRACTS §7, PRODUCT-FIT §3.5 |
| Historical view versus removal | `valid_until` and `retain_until` — BACKEND-CONTRACT §2 |
| Stop button without job or CSRF | 8.9: progress view model; 8.11: Stop removed (D43) |
| Result expected to outlive its idle session | 8.12: removal at the earlier of `retain_until` and session end — BACKEND-CONTRACT §2 |
| Location choice answered 404 or 422 depending on the reader | 8.12: one uniform 422 for any candidate not in the live set — CONTRACTS §3 |
| Idempotency comparison undefined once interest text is dropped | 8.12: HMAC fingerprint including the interest text — CONTRACTS §7 |
| Which response carries which status | 8.12: POST table and GET table, full pages only — CONTRACTS §3 |
| Presenters needing catalogue and weather data | Explicit `catalogue`, `WeatherSummary`, `AnswersSummary` — CONTRACTS §2, §8 |
| Bingo card unrenderable | `Activity.card`, `BingoView` — CONTRACTS §2, §8 |
| Print without date, timezone or place | `PrintView.context_line` — CONTRACTS §8, DESIGN-SPEC §10 |
| "Oak & Elm" double-escaping | Escape once at render — BACKEND-CONTRACT §7 |
| Back button to a consumed choice page | 303 to the started job — BACKEND-CONTRACT §3 |
