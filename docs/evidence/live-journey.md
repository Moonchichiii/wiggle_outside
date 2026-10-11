# Live search evidence (TC-009, TC-010), 11 October 2026

Run with `scripts/live_journey.py` against the real app (`create_app()`, the real
Nominatim, Overpass, Open-Meteo and OpenRouter adapters) served by uvicorn over https on
127.0.0.1 and driven by a real client that only speaks to that loopback origin;
screenshots by Playwright in the same session. Controlled input: a fixed family or a solo
adult, a fixed time budget, a typed place, interest text "birds and puddles". No visitor
exists; the app logs counts and the serving provider only. Pages are saved under `out/`
(gitignored). All times are stage times from the planner's own counters.

## Evening run, 17:21 and 17:23 UTC: fully live from Back Bay, Boston (the post's target)

`scripts/live_journey.py "Back Bay, Boston"`, family with a 3-5 year old, 1 h, 13:21 local,
real Overpass, real forecast, real model. The last two Overpass attempts of the evening's
allowance of two were spent here, one per run; neither obtained places, so the new
search with cached places was skipped by the script rather than spending a third.

| run (UTC) | Overpass instance | status | geocode | places+weather | model incl. queue | total | calls | result |
|---|---|---|---|---|---|---|---|---|
| 17:21 | overpass-api.de | POST 303, GET 200 | 1.00 s | 6.58 s | 1.99 s | 9.60 s | Nominatim 1, Open-Meteo 1, Overpass 1 (failed after ~6.5 s), OpenRouter 1 | `source=fallback`, `error=PLACES_UNAVAILABLE`, 3 generic ideas, 200 |
| 17:23 | overpass.kumi.systems | POST 303, GET 200 | 0.14 s | 0.20 s | 1.24 s | 1.61 s | Nominatim 1, Open-Meteo 1, Overpass 1 (error in 0.2 s), OpenRouter 1 | same |

- In both runs the model was asked to choose among the three generic pairs (shape-safari,
  colour-match, five-senses, each with the one hook `no-destination` and two or three
  allowed reasons) and answered in 20 completion tokens with the interests only
  (birds matched) and no valid pick, so the page is the labelled fallback: the three
  generic ideas with "AI selection isn't available right now" and "We couldn't load
  nearby places." Served by CoreWeave (1.95 s, 650 / 20 / 0) and DeepInfra (1.23 s,
  651 / 20 / 0), finish `stop`, no reasoning tokens. The raw answer is not logged by
  design; the token count and the matched interest are what the log shows.
- Identical resubmissions joined (0 calls, 0.01 s). Screenshots:
  `out/live-back-bay-boston-cold-390.png`, `-1440.png` (the 17:23 run overwrote the
  17:21 files; the pages are the same state).

## Evening run, 17:11 UTC: model to cards, with FIXTURE PLACES (route b)

`scripts/live_journey.py "Boston, Massachusetts" --fixture-places`: live geocode, live
forecast, live model, real routes and templates; the Overpass adapter alone replaced by
the four WALKTHROUGH fixture places translated to the geocoded origin. Family with a
3-5 year old, 1 h, 13:10 local. Budgets 3 / 9 / 6 / 2.

| step | status | geocode | places+weather | model incl. queue | render+transport | total | provider calls |
|---|---|---|---|---|---|---|---|
| cold search, fresh database | POST 303, GET 200 | 0.54 s | 0.19 s | 1.88 s | 0.03 s | 2.64 s | Nominatim 1, Open-Meteo 1, fixture places 1, OpenRouter 1 |
| identical resubmission | POST 303, GET 200 | 0 | 0 | 0 | 0.01 s | 0.01 s | none: joined the first job by its key |
| new search with cached geocode and weather (step-free preference) | POST 303, GET 200 | 0 | 0 | 1.44 s | 0.01 s | 1.46 s | Nominatim 0, Open-Meteo 0, fixture places 0 (the places cache, populated by the cold search with fixture places), OpenRouter 1 |

- Both searches ended `source=model`, `state=complete`, 2 ideas, no error, label
  "Boston, Suffolk County, Massachusetts, United States".
- Pairs sent to the model: 12 (the contracted maximum), listed in
  `out/live-boston-massachusetts-fixture-report.md`; the model was offered five hook IDs
  per pair and the reason IDs code had allowed for that pair.
- Validated picks, both runs: `p5` nature-bingo at Oak Lane Park, hook `expedition`,
  reason `close_by`; `p6` puddle-jumping at Elm & Oak Playground, hook `todays-idea`,
  reason `close_by`. Interests interpreted as matched: birds, puddles.
- Cards rendered: "Nature bingo", "Puddle jumping championship"; the two detail links
  carry exactly the two idea IDs of the result's picks (checked by the script).
- Served by DeepInfra, `google/gemma-4-26b-a4b-it`: cold 1608 / 82 / 0 tokens, finish
  `stop`, 1.84 s, request 7 548 bytes; warm 1608 / 82 / 0, 1.44 s. No reasoning tokens.
- Screenshots: `out/live-boston-massachusetts-fixture-cold-390.png`, `-1440.png`.
- Distances on the cards read "about 0.0 km" / "0 min there and back" for the two picked
  places: coordinates round to two decimals on construction (CONTRACTS section 2), so a
  fixture place offset by 0.003 degrees lands in the origin's cell. Not an effect of
  this change; the same rounding applies to Overpass places.

## Evening run, 17:09 to 17:10 UTC: live Overpass from English-speaking places (route a)

Two Overpass attempts were allowed in total; both were spent, one each, and each
answered within the places stage. Neither search reached the model: at that hour a
family outing ends after sunset in both places, and the family daylight rule decides the
run before any pair is built (BACKEND-CONTRACT section 1).

| place | input | status | geocode | places+weather | total | calls | result |
|---|---|---|---|---|---|---|---|
| Bloomsbury, London | family, 1 h, 18:09 local | POST 303, GET 200 | 0.50 s | 5.94 s | 6.52 s | Nominatim 1, Open-Meteo 1, Overpass 1 | `DAYLIGHT_TOO_SHORT`, 0 ideas, 200 with the fixed copy; label "Bloomsbury, London Borough of Camden, Greater London, England, WC1E 7HU, United Kingdom" |
| Dublin | family, 30 min, 18:10 local | POST 303, GET 200, POST 303, GET 200 (ambiguous; first candidate) | 0.76 s | 5.76 s | 6.56 s | Nominatim 1, Open-Meteo 1, Overpass 1 | `DAYLIGHT_TOO_SHORT`, 0 ideas; label "Dublin, County Dublin, Leinster, Ireland" |

In both, the identical resubmission joined the first job (0 calls, 0.01 s) and the new
search with cached geocode and weather made 0 provider calls (0.01 to 0.02 s): the
daylight rule ended it from the cached forecast. The warm search's places figure says
nothing about the places cache: the run never built pairs. Bloomsbury's identical
resubmission answered GET 200 directly; Dublin's answered GET 303 to the chosen
candidate's job and then GET 200 (the consumed-choice redirect, followed to the page).

## Afternoon run, 13:18 UTC, Växjö, with the TC-009 budgets (3 / 9 / 6 / 2)

| step | status | geocode | places+weather | model incl. queue | render+transport | total | provider calls |
|---|---|---|---|---|---|---|---|
| cold search, fresh database | POST 303, GET 503 | 0.18 s | 9.02 s | 0 | 0.02 s | 9.22 s | Nominatim 1, Open-Meteo 1, Overpass 1 attempt cancelled at the 9 s stage bound, OpenRouter 0 |
| identical resubmission | POST 303, GET 303 | 0 | 0 | 0 | 0.01 s | 0.01 s | none: joined the first job by its key, redirected to the chosen job's page |
| new search with cached geocode and weather (step-free preference) | POST 303, GET 503 | 0 | 7.53 s | 0 | 0.01 s | 7.54 s | Nominatim 0 (cached), Open-Meteo 0 (cached, covering), Overpass 1 answered after 7.5 s with an unusable answer, OpenRouter 0 |

- "Växjö" is ambiguous at Nominatim; the first candidate, "Växjö, Växjö kommun,
  Kronoberg County, 352 30, Sweden", was chosen through `/location-choice`.
- Both searches ended `source=fallback`, `state=unavailable`, `error=PLACES_UNAVAILABLE`,
  0 ideas, on the designed notice page ("We couldn't load nearby places.", HTTP 503 per
  CONTRACTS §3). Screenshots: `out/live-växjö-cold-390.png`, `-1440.png`.
- Why zero ideas rather than labelled generic ideas: at 15:13-16:13 local the forecast
  was showers, 79-88 % probability, 0.8 mm. The pure rules (`core.activities.eligible`)
  leave exactly one eligible entry, puddle-jumping, which needs a park or playground.
  At 08:00 local the same rules on the same day's forecast (25 %) leave ten entries,
  three of them generic: shape-safari, colour-match, five-senses, the three seen that
  morning. The generic path in `plan_outing` is unchanged.
- The places cache was never populated in this run: places were never obtained.

## Earlier runs the same day (6 s places stage)

| run (UTC) | step | status | geocode | places+weather | model | total | calls |
|---|---|---|---|---|---|---|---|
| 12:13 | cold search | POST 303, GET 503 | 0.25 s | 6.02 s | 0 | 6.29 s | Nominatim 1, Open-Meteo 1, Overpass cancelled at 6 s |
| 12:15 | cold search | POST 303, GET 503 | 0.15 s | 6.02 s | 0 | 6.19 s | same |
| both | identical resubmission | POST 303, GET 503 | 0 | 0 | 0 | 0.01 s | none |

## Overpass alone, the app's own query (Växjö, 1.5 km, five place kinds)

| time (UTC) | instance | cap | results |
|---|---|---|---|
| ~12:00 | overpass-api.de | 3 s | 3.18 s timeout, 2.96 s ok (6 places), 3.11 s timeout |
| ~12:02 | overpass-api.de | 6 s | six calls (1.5 km and 3 km), all timed out at 6.1 to 6.2 s |
| ~12:05 | overpass-api.de | 15 s | 1.5 km: 8.13 s server error, 3.00 s ok, 2.07 s ok; 3 km: 9.11 s error, 15.08 s timeout, 8.92 s error |
| 12:16 | overpass-api.de | 15 s | 5.13 s ok (6 places), 9.00 s error, 8.46 s error |
| 13:25 | overpass-api.de, full query | 15 s | 7.64 s error, 10.54 s error |
| 13:25 | overpass-api.de, without the two forest selectors | 15 s | 7.33 s error, 6.89 s error |
| 13:26 | overpass.kumi.systems, full | 15 s | 0.19 s error, 1.63 s ok (6 places) |
| 13:26 | overpass.kumi.systems, without forest | 15 s | 0.09 s error, 0.28 s error |
| 13:27 | overpass.private.coffee | 15 s | four errors in 0.2 to 0.3 s |
| 13:30 | raw status | 20 s | overpass-api.de: HTTP 504 after 7.33 s and 7.89 s (gateway timeout page); kumi: HTTP 500 in 0.18 s and 0.07 s |

Open-Meteo for the same point: 0.14 s, 0.03 s, 0.03 s.

## Model-call ledger (approved: 5, then 20 more)

| # | what | result |
|---|---|---|
| 1 | smoke, typical request | HTTP 200 with an in-body error: "The provided JSON schema contains features not supported by xgrammar", code 400 |
| 2 | smoke, largest request | same error |
| 3 | diagnostic, one pair, printing the error object only | same error; identified `uniqueItems` |
| 4 | smoke, typical request, `uniqueItems` no longer sent | served by DeepInfra, 1598 / 93 / 0 tokens, finish `stop`, 1.68 s; two valid picks (model-smoke.md) |
| 5 | Boston fixture-places journey, cold search | served by DeepInfra, 1608 / 82 / 0, finish `stop`, 1.84 s; two valid picks, two cards |
| 6 | Boston fixture-places journey, new search with cached geocode and weather | served by DeepInfra, 1608 / 82 / 0, finish `stop`, 1.44 s; the same two picks |
| 7 | Back Bay live journey, overpass-api.de run | served by CoreWeave, 650 / 20 / 0, finish `stop`, 1.95 s; interests only, no pick (generic pairs) |
| 8 | Back Bay live journey, kumi run | served by DeepInfra, 651 / 20 / 0, finish `stop`, 1.23 s; interests only, no pick (generic pairs) |
| 9 | generic-only smoke, first wording of the new select.v2 rule | served by DeepInfra, 699 / 27 / 0, 1.28 s; no pick (model-smoke-generic.md) |
| 10 | generic-only smoke, final wording | served by CoreWeave, 735 / 103 / 0, 1.42 s; three validated picks |
| 11 to 25 | unspent | |
