# Live search evidence (TC-009, TC-010), 11 October 2026

Run with `scripts/live_journey.py "Växjö"` against the real app (`create_app()`, the real
Nominatim, Overpass, Open-Meteo and OpenRouter adapters) served by uvicorn over https on
127.0.0.1 and driven by a real client; screenshots by Playwright in the same session.
Controlled input: family with a 3-5 year old, 1 h, moderate energy, typed place "Växjö",
interest text "birds and puddles". No visitor exists; the app logs counts and the
serving provider only. Pages are saved under `out/` (gitignored).

## Run at 13:18 UTC with the TC-009 budgets (3 / 9 / 6 / 2)

| step | status | geocode | places+weather | model incl. queue | render+transport | total | provider calls |
|---|---|---|---|---|---|---|---|
| cold search, fresh database | POST 303, GET 503 | 0.18 s | 9.02 s | 0 | 0.02 s | 9.22 s | Nominatim 1, Open-Meteo 1, Overpass 1 attempt cancelled at the 9 s stage bound, OpenRouter 0 |
| identical resubmission | POST 303, GET 303 | 0 | 0 | 0 | 0.01 s | 0.01 s | none: joined the first job by its key, redirected to the chosen job's page |
| new search on cached places (step-free preference) | POST 303, GET 503 | 0 | 7.53 s | 0 | 0.01 s | 7.54 s | Nominatim 0 (cached), Open-Meteo 0 (cached, covering), Overpass 1 answered after 7.5 s with an unusable answer, OpenRouter 0 |

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
  morning. The generic path in `plan_outing` is unchanged (see the working-tree diff).
- The warm search cached nothing new: the geocode and the forecast were cache hits
  (zero calls), places were never obtained to cache.

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
| 5 to 25 | unspent | no live search reached the model: Overpass never answered usably inside its stage |
