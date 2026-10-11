# Wiggle Outside

Find a realistic outdoor activity near you, for the next hour or two, then put the phone
away.

Answer five short questions — who is coming, how long you have, how much energy, where you
are, anything to account for — and Wiggle Outside offers up to three grounded ideas, each
one a nearby place from OpenStreetMap paired with a reviewed activity that suits the
forecast, the daylight and the ages you named. If nothing suitable exists right now, it
says so rather than padding the list.

Built for the Hacktoberfest Open-Source AI Challenge, Week 1 ("Touch Grass").

- Live app: **[URL — not yet deployed]**
- DEV post: **[URL — drafted separately]**
- Specification and decisions: [`docs/`](docs/), starting with [`docs/PLAN.md`](docs/PLAN.md)

## What the hosted model actually does

The model is Gemma 4 26B A4B (`google/gemma-4-26b-a4b-it`), reached through OpenRouter.
Its job is deliberately small and fully checked:

1. The application does everything factual first: geocodes the place, fetches nearby
   places from OpenStreetMap and the forecast from Open-Meteo, applies the daylight,
   weather, age, energy, season and time rules in code, and builds at most twelve
   (activity, place) pairs that already pass every rule. Each pair carries the story
   hooks and the reason codes that code has allowed for it.
2. The model gets those pairs, the vocabulary, and the visitor's free-text interests
   ("birds and puddles"). It answers under a strict JSON schema with up to three picks:
   a pair ID, one hook ID from that pair's allowed list, up to two reason IDs from that
   pair's allowed list, and the interests it recognised as tags.
3. The application validates every pick against what was offered. An unknown pair, a
   hook or reason the pair does not allow, a repeated reason or a repeated activity
   drops that pick; the valid ones are kept, never repaired, never padded.

So the model **ranks and interprets**. It never writes a sentence you read (every title,
hook and reason is reviewed text from the catalogue), it never invents or moves a place,
and it never overrides a rule. One call per search, 256 output tokens at most, reasoning
off, request capped at 10 000 bytes.

Routing: `provider.only` = NextBit, DeepInfra, CoreWeave, `require_parameters: true`,
fallbacks only within that list, `data_collection: "deny"`. The list rests on OpenRouter's
published data policy per provider (no training, no prompt retention), not on an
independent review of each provider's terms (TC-010). Which provider served each request
is logged with token counts and latency; prompts and answers are not logged.

## Online dependencies

| Service | Used for | Cached | If it fails |
|---|---|---|---|
| [Nominatim](https://nominatim.org/) | typed place → coordinates and an English label | yes | "We couldn't find that place" form, answers kept |
| [Overpass](https://overpass-api.de/) (OpenStreetMap) | parks, playgrounds, nature areas and woods within walking range | yes | ideas that need no particular place, labelled; or an honest notice if none qualify |
| [Open-Meteo](https://open-meteo.com/) | hourly forecast, sunrise and sunset in the place's own timezone | yes | notice page: no recommendation without a forecast |
| [OpenRouter](https://openrouter.ai/) → Gemma on an approved provider | ranking and interest interpretation (above) | no | the application's own deterministic ranking, labelled |

Every search runs under one 20 s deadline split per stage (3 s geocode, 9 s places and
forecast together, 6 s model, 2 s reserve); a stage that overruns is cancelled and the
search continues to its labelled fallback. Nothing is retried past the budget, and an
identical resubmission joins the running search instead of starting another.

## Labelled fallbacks

The page always says what it is:

- **"AI selection isn't available right now."** The model was unreachable, over budget,
  rate-limited, or answered without a valid pick; the cards come from the application's
  own ranking over the same validated pairs.
- **"We couldn't load nearby places."** Overpass failed; the cards, if any, are the
  activities that need no particular place.
- **Daylight and weather notices.** A family outing that would end after sunset, a night
  search, severe weather or nothing eligible gives a fixed notice with "Change answers",
  not a thinner list.
- **Historical view.** A result older than its validity window says so when reopened.

Nothing is described as "safe" or "verified": a place's admission fee and step-free
access are shown as OpenStreetMap reports them, and the forecast is a forecast.

## Evidence

All measurements are from 11 October 2026 and recorded in
[`docs/evidence/`](docs/evidence/). Two kinds, kept apart:

**Live model, fixture places** (`live-journey.md`, Boston run; `model-smoke.md`). The real
app, the real geocoder, the real forecast and the real hosted model, with the four
fixture places from the walkthrough standing in for Overpass. Gemma was offered twelve
pairs and answered with two validated picks (nature bingo at a park, puddle jumping at a
playground), served by DeepInfra in 1.84 s cold and 1.44 s on a second search; the two
cards link exactly the two picked ideas. **This shows the model-to-card path, not live
performance:** the places stage took 0.19 s only because nothing was fetched.

**Fully live** (`live-journey.md`, Växjö, Bloomsbury, Dublin and Back Bay runs). Real
Overpass, forecast and model. What was shown: the designed pages for an Overpass failure
(three labelled generic ideas, or the notice when nothing is eligible), the family
daylight rule stopping an evening search in London and Dublin on the place's own sunset,
the cached-geocode and cached-forecast path (0 calls), and identical resubmissions
joining (0 calls, 0.01 s). What was not shown: a search whose cards came from Overpass
places picked by the model. The public Overpass instance answered the app's query with
gateway timeouts after 6 to 8 s for most of the day, and the one alternative instance
tried answered one query in five.

- **[Placeholder: fully live search, Overpass places, model picks, screenshots at 1440
  and 390 — not yet captured.]**
- **[Placeholder: measured cold and warm timings of that search.]**

In the fully live runs where places failed, Gemma was asked to choose among the three
place-free pairs and, under the prompt as it then stood, answered with the interests
only and no pick, so those pages carry the fallback label. The prompt rule was then
tightened (every offered pair has already passed the rules; a pair with no particular
place is as valid as any other) and verified the same evening with the same three
place-free pairs: three picks, all validated, served in 1.42 s
([`model-smoke-generic.md`](docs/evidence/model-smoke-generic.md)). A fully live search
showing that through the page is still to be captured.

## Limitations

- **Overpass is the weak link.** The public instance is shared and often slow; a search
  that cannot get places within its stage gets place-free ideas or an honest notice. The
  instance is configurable (`WO_OVERPASS_URL`).
- **Distances are coarse by design.** Coordinates are rounded to two decimals (about a
  kilometre) before anything is stored or shown; a place in the same cell reads "close
  by", others "about 0.6 km away" in a straight line.
- **Place-free picks are verified in a controlled call, not yet in a fully live
  search.** If the model ever answers without a valid pick, the application ranks the
  pairs itself and says so.
- **English only**, and the catalogue is small and reviewed by hand.
- **One active search per session**, bounded hosted capacity, a daily run allowance in
  hosted mode, and a 20 s ceiling per search.
- **No JavaScript.** Plain forms; a search is a POST, a wait and a redirect.
- **Not yet deployed**, and no accessibility or performance claim in the documents has
  been verified on a hosted instance.

## Privacy

The five answers and the interest text are processed to make one search and are not
stored beyond the search's own short lifetime in process memory. The interest text and
the validated pairs go through OpenRouter to one of the approved model providers it
selects, chosen because OpenRouter's published data policy says they neither train on
nor retain prompts. The application logs counts, the serving provider and timings only,
never a visitor's text or coordinates. There are no accounts and no analytics.

## Run it locally

Requires [uv](https://docs.astral.sh/uv/), [bun](https://bun.sh/) and PowerShell 7.

```powershell
uv sync --all-groups
$env:WO_CONTACT_EMAIL = "you@example.org"      # Nominatim's usage policy wants a contact
$env:OPENROUTER_API_KEY = "..."                 # optional: without it, every result is the labelled fallback
uv run uvicorn wiggle_outside.main:create_app --factory --host 127.0.0.1 --port 8000
```

`GET /readyz` reports the app and the model separately (`model: unavailable` without a
key). Other settings, all optional, are `WO_` environment variables (`WO_MODE`,
`WO_DB_PATH`, `WO_OVERPASS_URL`, `WO_DEADLINE_SECONDS`, `WO_DAILY_RUN_LIMIT`; see
[`settings.py`](src/wiggle_outside/settings.py)). The key is read from the environment
only and never written to a file or a log.

The two headline fonts (Cabinet Grotesk and Switzer, both from
[fontshare.com](https://www.fontshare.com/)) are **not in this repository**: the
Fontshare Font Licence 2.0 allows self-hosting them but not redistributing the files
publicly. See [`frontend/fonts/README.md`](frontend/fonts/README.md). The app renders
correctly without them, on the metric-matched system-font fallback.

## Development

```powershell
./scripts/check.ps1
```

`check.ps1` is the one gate script (ruff, mypy, import-linter, pytest with the contract
tests); CI runs the same file on Linux with `shell: pwsh`. Per TC-006 the remaining
release gates arrive with WP9b, and until then nothing is described as supply-chain
verified. The architecture is layered and enforced by import-linter: `web` above
`planner` above `core`, with the provider and model adapters beside the planner and
wired only in `main.py`. Changes after the frozen baseline are tracked in
[`docs/decisions/tracked-changes/`](docs/decisions/tracked-changes/).

Evidence scripts: `scripts/model_smoke.py` (two controlled model calls) and
`scripts/live_journey.py` (a real search through the real app on a loopback server,
with `--fixture-places` for the labelled fixture mode).

## Licence and credits

Apache-2.0 — see [LICENSE](LICENSE). Place data © OpenStreetMap contributors (ODbL);
weather from [Open-Meteo](https://open-meteo.com/); geocoding by
[Nominatim](https://nominatim.org/) and places by [Overpass](https://overpass-api.de/).
Model: Gemma 4 26B A4B by Google, served through [OpenRouter](https://openrouter.ai/).
Security policy: [SECURITY.md](SECURITY.md).
