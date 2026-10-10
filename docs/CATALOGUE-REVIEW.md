# Catalogue review — answered, baseline 8.20

Status: **answered by Mats on 10 October 2026 (8.20) and applied** to
`drafts/activities.toml` (now 26 entries: 19 for kids, 7 solo) and `drafts/hooks.toml`.
The answers are in §0; §1–§6 keep the review as it was put to Mats (round 8.19) for
history. Every threshold is a **product assumption**, not an established safety
threshold; no medical or meteorological source was used to set any number, and "the
adult decides" does not validate any number either. Owner: WP2 (catalogue and hooks,
`tests/planner/test_catalogue.py`); the TOML files are protected inputs
(BUILD-PACKAGES §2.1, TC-003).

## 0. Answers recorded (Mats, 8.20) and applied

| Item | Answer | Applied as |
|---|---|---|
| A1 baby participation | add | `colour-match` and `nature-bingo` gain `0-2` and the caregiver sentence in `safety` (§1) |
| A1 × W3 baby temperature | **5 °C on all three** | `narrated-stroll`, `colour-match`, `nature-bingo`: `min_temp_c` 5. This also removes the two shared activities for older children below 5 °C apparent temperature |
| A2 `animal-walk` ages | leave unchanged | 3–5 only |
| W1 tree wind | min(current, 30), kids and solo | lowered to 30: `leaf-colour-hunt`, `nature-bingo`, `track-detective`, `stick-houses`, `minibeast-safari`, `i-spy-far`, `brisk-loop`, `leaf-study-solo`; `tree-twins` stays **25** |
| W2 sky activities | remove | `shadow-play` and `cloud-stories` removed from v1 |
| W3 / W4 | 5 °C (above); daylight only for kids | `five-senses` `daylight = true`, after-dark sentence removed from its safety line; family runs outside daylight get the fixed night copy (BACKEND-CONTRACT §1, Mats 8.20) |
| X1 `statues` | add mobility alternative | `adapt`: "Use a raised hand as the freeze signal as well as the word. Freeze by stopping your arms, head or wheels; any way of stopping counts." (one field, both adaptations) |
| H1 solo hook | new wording | "A small escape for right now." |
| T1 `quick-sketch` | reworded (reviewer's wording) | "Make three sketches of three different things." |

Eligible kids' activities after the answers, before weather, season and place filters
(gentle / moderate): 0–2 only 6 / 6; 3–5 only 11 / 13; 6–9 only 12 / 14; 10–12 only
8 / 9; 3–5 + 6–9 10 / 11; 0–2 + 3–5 5 / 5; 0–2 + 6–9 4 / 4; 0–2 + 10–12 2 / 2. Below
5 °C apparent temperature, families with a baby still have few or no ideas; the post
says so.

**WP2 acceptance additions:** 26 entries; every kids' entry has `daylight = true`; no
wind limit is higher than in the 8.19 review copy and `tree-twins` is 25; the three
baby-eligible shared entries have `min_temp_c` ≥ 5; `shadow-play` and `cloud-stories`
are absent.

# Review as put to Mats (round 8.19, history)

**Corrected in 8.19:** the 8.18 version recommended "30 km/h for any forest or tree
activity" and "accept all six". Applied literally, that would have **raised**
`tree-twins` from 25 to 30 km/h. Both are withdrawn; W1 is now a cap that can only lower
a limit.

## 1. Age suitability

Counts of eligible kids' activities before weather, season and place filters (an
activity qualifies only if it lists **every** selected band; the energy ceiling
includes gentler entries):

| Ages selected | Gentle | Moderate | With A1 below |
|---|---|---|---|
| 0–2 only | 4 | 4 | 6 / 6 |
| 3–5 only | 12 | 15 | unchanged |
| 6–9 only | 13 | 16 | unchanged |
| 10–12 only | 9 | 10 | unchanged |
| 3–5 + 6–9 | 11 | 13 | unchanged |
| 0–2 + 3–5 | 3 | 3 | 5 / 5 |
| 0–2 + 6–9 | 2 | 2 | 4 / 4 |
| 0–2 + 10–12 | 1 | 1 | 2 / 2 |

### A1 (decide): baby participation for mixed-age families

Families with a baby and an older child get one to three candidates before weather
filtering, and two of them (`sound-map`: no rain, at least 5 °C; `picnic-adventure`:
at least 12 °C) drop out on a typical cool autumn day.

**Proposal, exactly two activities, no new field.** The adaptation follows the existing
pattern in `sound-map` ("With babies, the adult listens and names the sounds aloud."):
one caregiver sentence appended to the activity's `safety` line, rendered verbatim.

| Activity | Change to `ages` | Sentence appended to `safety` | Why this one |
|---|---|---|---|
| `colour-match` | add `0-2` (→ 0–2, 3–5, 6–9) | "With a baby, the adult names each colour match out loud and shows it; baby watches from the stroller, carrier or your arms." | any place, stroller-suitable, nothing is touched or picked; the baby's part is watching and hearing |
| `nature-bingo` | add `0-2` (→ 0–2, 3–5, 6–9, 10–12) | "With a baby, the adult shows baby each find and names it; baby watches from the stroller, carrier or your arms." | stroller-suitable, "look and point" already; also the only extra option for 0–2 + 10–12 |

Not proposed: activities that involve jumping, running, building, rubbing bark or
handling material (`puddle-jumping`, `statues`, `stick-houses`, `bark-rubbing`,
`minibeast-safari`), where a baby's part would be nominal or the safety line would need
more than one sentence.

**Interaction with W3:** each activity has one `min_temp_c`, with no per-age value. If
W3 sets a 5 °C baby minimum, it covers only the activity it is written on. Mats picks
one: (a) accept that `colour-match` and `nature-bingo` stay at 0 °C for everyone, with
the adult deciding for the baby; or (b) raise both to 5 °C, which also removes them for
older children between 0 and 5 °C. A per-age temperature rule would be a new feature and
is not proposed.

Alternative to A1: change nothing and say plainly in the post that families with a baby
and an older child will often see few or no ideas.

- **A2 (optional):** `animal-walk` lists 3–5 only; adding `6-9` is a content judgement,
  not a safety one.
- **A3:** `picnic-adventure` lists 0–2 and needs food from home; its safety line covers
  it. No change.
- No entry asks children to climb, approach water, go near traffic or touch animals;
  safety lines are present on all 28.

## 2. Weather limits

### W1 (decide): wind among trees — a cap that only lowers

Rule: for every activity whose `places` include `forest` or `nature_reserve`, or that is
about trees, `max_wind_kmh` becomes **the lower of its current value and 30**. Effect:

| Lowered to 30 | Unchanged |
|---|---|
| `leaf-colour-hunt` 40, `nature-bingo` 40, `track-detective` 40, `stick-houses` 35, `minibeast-safari` 35, `i-spy-far` 35; solo `brisk-loop` 45, `leaf-study-solo` 40 | `tree-twins` **25** (stays stricter), `sound-map` 30, `bark-rubbing` 30, solo `sit-spot` 30, `quick-sketch` 30 |

- **Rationale:** branches and debris fall more often in wind, and the current limits
  are inconsistent (25 for one tree activity, 40 for others).
- **Uncertainty:** 30 km/h is a product assumption, not a published threshold. The
  limit is compared with the forecast sustained wind the eligibility rules already use
  (`wind_speed_10m`, BACKEND-CONTRACT §1), not gusts; gusts and local exposure can be much higher, and the forecast
  is for the place, not under the trees. The card's safety line and the adult's judgement
  remain the real control. Including the two solo entries is part of the choice; Mats may
  restrict W1 to kids' activities.
- **Acceptance (WP2):** a test asserts that no activity's wind limit increases between
  the reviewed and the edited TOML, and that `tree-twins` is 25.

### W2 (decide): sky conditions we never check

`shadow-play` needs sunshine and `cloud-stories` needs some clouds; neither rain
probability nor temperature says that. Options: remove both from v1 (recommended, given
the time left), or add a sky-condition field (weather codes 0–1 and 1–3), which is new
scope.

### W3 (decide): a baby minimum temperature

`narrated-stroll` (0–2 only) allows 0 °C apparent temperature for up to 45 minutes,
relying on "Dress baby for the wind." Proposal: raise its `min_temp_c` to 5.

- **Rationale:** babies sitting still in a stroller lose heat faster than walking adults
  and can't say they're cold; a higher minimum keeps the app from suggesting long
  still outings on the coldest days.
- **Uncertainty:** 5 °C is a product assumption, not a medical threshold; no source was
  used. Families in Sweden routinely take babies out well below 5 °C with suitable
  clothing, so the limit may be stricter than needed and will hide ideas on cold days.
  The forecast apparent temperature is approximate. The alternative is to keep 0 °C and
  rely on the clothing line. See the A1 interaction above.

### W4 (decide): daylight for kids

`five-senses` is the only kids' activity allowed after dark (`daylight = false`, "stay on
lit paths"). Proposal: daylight only for all kids' entries in v1.

- **Rationale:** consistency, and the app cannot know whether paths are lit.
- **Uncertainty:** a product assumption; it removes the one evening option for families
  in October, when daylight ends around 18:20 locally.

- Solo entries allow −2 °C and after-dark use with lit-path safety lines: no change
  proposed.
- Severe weather (thunder, freezing rain, heavy snow, wind over 50 km/h) and the heat
  rule (30 °C with kids, 32 °C alone) apply to everything; unchanged.

## 3. Accessibility adaptations

- Every entry has one `adapt` line. Most cover sight or hearing by switching to touch or
  sound.
- **X1 (decide):** `statues` only adapts the signal (a raised hand for people who can't
  hear it). Proposed additional mobility line: "Freeze by stopping your arms, head or
  wheels; any way of stopping counts."
- **X2:** `puddle-jumping`, `animal-walk`, `movement-trail` and `brisk-loop` already
  include mobility alternatives. No change.
- **X3:** `activity_suits_stroller` describes only the activity, never the route or
  site access; the card labels access as reported or not verified. This holds whichever
  D42 variant Mats chooses.
- One adaptation line per entry is a v1 limit, not full inclusive design; the post
  should not claim more.

## 4. Hooks and reasons

- The 8 hooks are fixed sentences without placeholders (8.12). None mentions weather,
  safety or price.
- **H1 (decide):** "A small escape, close enough to start now." implies closeness for
  every solo pair; travel time can be up to half the budget. Proposed: "A small escape
  for right now."
- **H2:** activity-specific taglines from the concept board would need a reviewed field
  per activity; not proposed for v1.
- Reasons are factual and derived from data. No change.

## 5. Text fixes

- **T1 (decide):** `quick-sketch` step 3, "Do three of three different things.", should
  read "Do three, of three different things."

## 6. Answers needed (one per line; no item implies another)

| # | Item | Options | Claude's suggestion |
|---|---|---|---|
| 1 | A1 | add `0-2` to `colour-match` and `nature-bingo` with the two caregiver sentences / change nothing and say so in the post | add both |
| 2 | A1 × W3 | (a) both stay at 0 °C / (b) both rise to 5 °C | (a), the adult decides |
| 3 | A2 | add `6-9` to `animal-walk` / no | optional |
| 4 | W1 | cap at min(current, 30) for kids and solo / kids only / no change | kids and solo |
| 5 | W2 | remove `shadow-play` and `cloud-stories` / add a sky field | remove |
| 6 | W3 | `narrated-stroll` minimum 5 °C / keep 0 °C | 5 °C, uncertainty recorded |
| 7 | W4 | daylight only for kids / keep `five-senses` after dark | daylight only |
| 8 | X1 | add the `statues` mobility line / no | add |
| 9 | H1 | new solo hook wording / keep | new wording |
| 10 | T1 | fix / keep | fix |

Once each line is answered, the integration owner edits the TOML accordingly, WP2's
catalogue tests are updated (including the W1 never-raise test), and the remaining
uncertainties above are kept in the post's limitations.
