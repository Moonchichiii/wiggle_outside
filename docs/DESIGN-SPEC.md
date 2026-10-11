# Design specification — baseline 8.20

Status: DRAFT, 10 October 2026, for Mats's review. Owning document for visual tokens,
components, layout, assets, interaction, motion, copy and print. Behaviour defers to
BACKEND-CONTRACT.md and ERROR-HANDLING.md; requests follow ARCHITECTURE §14. Nothing here
is locked, accessible or performance-proven until the checks in §12 run on real screens.
Direction: a warm paper "adventure board": oatmeal background, dark ink, pastel cards,
hand-drawn SVG details, asymmetric corners, restrained shadows. Decoration may wobble;
text, controls and focus indicators stay straight and stable.

## 1. Tokens

### 1.1 Colour

| Token | Hex | Role |
|---|---|---|
| `oatmeal` | `#F2EDE4` | Page background |
| `card` | `#FFFCF6` | Form panel, detail view, fields |
| `ink` | `#191C20` | All body text, borders, icons |
| `ink-soft` | `#42464D` | Secondary text: hints, meta lines |
| `sage` | `#D3E0D0` | Idea card background (variant 1) |
| `peach` | `#F7D6C8` | Idea card background (variant 2) |
| `butter` | `#FAE8C3` | Idea card background (variant 3); selected tile fill |
| `alert` | `#EAD5D1` | Error notice background |
| `success` | `#D7E4D7` | Success notice background |
| `action` | `#2C5234` | Primary button background |
| `action-hover` | `#22412A` | Primary button hover and pressed |
| `link` | `#1E4A85` | Links, focus ring, selected-tile border |
| `error` | `#8A2A17` | Error text and error borders |

**Rules.** Text on `sage`, `peach`, `alert` and `success` is `ink` only. The coloured inks
(`action`, `link`, `error`) and `ink-soft` appear as text only on `oatmeal`, `card` or
`butter`. Meaning never relies on colour alone: icons, borders and words carry it too.

**Calculated text pairs (WCAG 1.4.6 needs 7:1):**
ink on oatmeal 14.66 · sage 12.49 · peach 12.54 · butter 14.16 · alert 12.16 · success 13.00 ·
card 16.70. ink-soft on oatmeal 8.13 · card 9.26 · butter 7.85 · success 7.21.
link on oatmeal 7.59 · card 8.64 · butter 7.33. error on oatmeal 7.43 · card 8.46.
action on oatmeal 7.62 · card 8.68. card text on action 8.68 · on action-hover 11.04.
**Fail, never used for text:** ink-soft on sage 6.93, peach 6.96, alert 6.74; link, error and
action on any pastel (6.16–6.76); the earlier moss `#5C745C` (4.38 on oatmeal) and clay
`#BD6351` (3.55). Passing contrast is one criterion, not complete accessibility.
`scripts/check_contrast.py` recomputes every pair in CI.

**Forced colours:** borders, focus outlines and selected states use real borders and
outlines (not backgrounds or shadows), so they survive `forced-colors: active`; SVG icons
use `currentColor`.

### 1.2 Typography (D41, accepted 8.20; files and licence are prerequisite P1)

| Role | Font | File | Weights used |
|---|---|---|---|
| Headings, page title, activity titles | Cabinet Grotesk ExtraBold | `CabinetGrotesk-Extrabold.woff2` (≈ 21 KB, one static weight) | 800 |
| Body, hooks, labels, controls, errors | Switzer Variable | `Switzer-Variable.woff2` (≈ 43 KB; smaller than three static weights at ≈ 57 KB) | 400 body and hooks, 500 labels, 600 buttons and emphasis |

Both files are supplied by Mats and self-hosted; about 64 KB in total (sizes from Mats's
screenshots, not yet measured here). `font-display: swap`; fallbacks
`system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", sans-serif`. No full
families, no italics, no external font service. Preload only a file that measurably
helps the first render (to be measured; likely Switzer only). Shantell Sans is
**superseded**.

**Checks, done (TC-007).** The files are the two *variable* faces from fontshare.com
— `CabinetGrotesk-Variable.woff2` (41.9 KB) and `Switzer-Variable.woff2` (43.2 KB),
both `wght` 100–900, 85 KB together rather than the 64 KB estimated above, and not the
single static ExtraBold this section first assumed.
1. **Glyph coverage: passes.** `scripts/check_fonts.py` reads each character map and
   compares it with the set above plus the copy deck's · and …. Both faces cover all of
   it (Cabinet 465 glyphs / 405 codepoints, Switzer 386 / 385).
2. **Licence: Fontshare Font Licence 2.0.** Self-hosting on our own site is permitted;
   putting the font files in a public repository is **not**. So they are gitignored,
   `frontend/fonts/README.md` records their origin and the rule, and `Dockerfile` copies
   `frontend/fonts/` when the build context supplies it from private storage.
3. **Layout shift: neutralised at the source.** Measured against the real Segoe UI,
   Switzer's x-height is 6.2 % larger and its line box 7.5 % shorter than the fallback's,
   and Cabinet's line box is 13.5 % shorter. `tokens.css` therefore declares
   metric-matched fallback faces whose `size-adjust` and ascent/descent/line-gap
   overrides come from these files' own metrics, so the swap does not move the layout. A
   browser-measured CLS figure is still outstanding and belongs with WP9b's Playwright
   work.

| Token | Size / line height | Use |
|---|---|---|
| `text-sm` | 1 rem / 1.6 | Meta lines, hints |
| `text-base` | 1.125 rem / 1.6 | Body, labels, buttons |
| `text-lg` | 1.4 rem / 1.35 | Card titles, question legends |
| `text-xl` | 1.75 rem / 1.25 | Section headings |
| `text-2xl` | 2.2 rem / 1.15 | Page title |

Weights: body 400, labels 500, buttons and emphasis 600 (Switzer); headings 800 (Cabinet Grotesk). Reading width at most 65
characters (`max-width: 40rem`). Paragraph spacing at least 1.5× the font size. Long place
names and translated text wrap with `overflow-wrap: anywhere`; nothing is truncated with
an ellipsis.

### 1.3 Space, shape, shadow

- Spacing: `s1` 4 · `s2` 8 · `s3` 12 · `s4` 16 · `s5` 24 · `s6` 32 · `s7` 48 · `s8` 64 px.
- Page gutter: 16 px below 30 rem, 24 px up to 64 rem, 32 px above. Grid gap 16 / 24 px.
- Borders: 2 px `ink`; selected and focus states add `link`.
- Corners, one per component type: `wonk-card` `16px 6px 14px 8px / 8px 14px 6px 16px`,
  `wonk-button` `10px 14px 8px 12px`, `wonk-tile` `12px 8px 14px 6px`, `wonk-field`
  `6px 10px 8px 12px`. The layout grid stays straight; only corners are irregular.
- Shadow: `3px 3px 0 rgb(25 28 32 / 0.16)` on cards and the form panel only.
- Tilt: decorative SVGs only (tape, doodles). Cards and text are not rotated.

### 1.4 Focus

3 px solid `link` outline, 2 px offset, on every interactive element (`:focus-visible`).
Contrast against oatmeal 7.59, card 8.64, butter 7.33; perimeter at least 2 px (2.4.13).
Never removed. In forced-colours mode the system highlight colour is used.

### 1.5 Approved visual direction (Mats, round 8.17)

Reference: `mocks/reference/visual-direction-v2.png` (an AI-generated concept board;
Mats: "love it", with a request for a slightly more humanised feel). **Approved as the
visual direction, not as a specification**: the contracts and copy deck still decide
behaviour and wording.

- **Keep:** warm paper on oatmeal, the existing palette, confident headings, pastel
  activity cards, small hand-drawn outdoor doodles (leaf, sun, cloud, magnifier, trees),
  clear form groups, a compact results summary with "Change answers", weather once.
- **Humanise:** slightly irregular paper edges and asymmetric corners, softer hand-drawn
  line work, flat colours with no shading or gradients. Text, controls and focus stay
  upright and crisp.
- **Mobile:** the large side illustrations (family, signpost, notes) belong to the
  presentation board only; the app shows at most one small doodle per card. Stroller and
  step-free sit on separate rows; practical details wrap freely.
- **Not adopted from the concept:** its example activities and hooks (only reviewed
  catalogue and hooks text is used; "Sky watch" is a solo activity in the catalogue and
  cannot appear for kids), its energy heading "Energy to spend" (the copy deck's "How much
  energy today?" with Gentle / Moderate / High is settled, 8.18), its example weather
  wording, and anything implying where
  inference runs.

## 2. Components

All components work without JavaScript unless noted. Keyboard behaviour is native.

| Component | Size and spacing | States | Accessible name | Long content | JS |
|---|---|---|---|---|---|
| Primary button | min 48 px tall, padding 12 × 24, `wonk-button` | default action/card text · hover action-hover · focus ring · pressed 1 px down, shadow off · loading "Finding outings…" + `aria-busy` | visible label | wraps to two lines; never truncates | no (loading text needs htmx) |
| Secondary button | 48 px, 2 px ink border on card | hover butter · focus · pressed | visible label | wraps | no |
| Radio tile (time, energy, who) | min 56 × 44 px, padding 12 × 16, `wonk-tile`, native radio inside a `<label>` | default · hover butter at 50 % · focus ring on the tile · checked: butter fill, 3 px link border, check icon | `<legend>` + label | label wraps; tile grows | no |
| Checkbox tile (age bands) | as radio tile, native checkbox | as radio tile; several may be checked | `<legend>` + label | wraps | no |
| Text field (town) | 48 px tall, padding 12, `wonk-field`, card background | hover border link · focus ring · invalid: 2 px error border, error text below with icon, `aria-invalid`, `aria-describedby` | visible `<label>` + hint | wraps in message, not in field | no |
| Fieldset | legend `text-lg`, gap 12 between tiles | — | `<legend>` | legend wraps | no |
| Idea card | padding 24, `wonk-card`, sage/peach/butter by position, shadow | focus ring on "Read the full activity" link · hover lift 2 px (motion-safe, hover-capable only) | `<h3>` title | place names wrap | no |
| Notice | padding 16, 4 px left border, icon, ink text on alert/success or card | — | heading or first sentence | wraps | no |
| Error summary | notice on alert, list of links to fields | receives focus once after a failed submission | `<h2>` "Check these answers" | wraps | no |
| Busy state (D43) | button text "Finding outings…" with `aria-busy`, plus the static note "This can take up to 20 seconds." in a polite live region and a small static SVG | shown at once on submit (htmx request indicator); hidden on every terminal outcome | live region | wraps | the indicator needs htmx; without JS the browser's own loading state is used |
| Answers summary | card background, 2 px ink border, `wonk-tile`, padding 16; "Change answers" is a native `<details>` summary, min 44 px | collapsed · open (prefilled form inside) · focus ring on summary | summary text | lines wrap | no |
| Bingo grid | 3 × 3 grid of bordered cells, min 44 px tall, ink on card | — (print: plain borders) | `<h3>` "Your bingo card"; table with 9 cells | cell text wraps | no |
| Link | link colour, 2 px underline | hover thicker underline · focus ring | link text | wraps | no |
| Interest labels (D39, D46) | plain text list after "We think they're into:", card background, 2 px ink border, `wonk-tile` box; no buttons, no × icons, nothing that looks removable | — | part of the text | wraps | no |

Radio buttons and checkboxes have no `readonly` state; while a request runs, the answers
stay visible and editable, and the submit button ignores repeat clicks instead.

## 3. Dimensions

Targets at least 44 × 44 CSS px everywhere. Buttons and fields 48 px tall; tiles at least
56 px tall. Icons 24 px in tiles and notices, 32 px in card meta, 48 px for the weather
glyph. Form panel and detail view max 40 rem wide; results area max 72 rem.

## 4. Responsive behaviour

Review widths: 320, 390, 768, 1024, 1440 CSS px (review sizes, not breakpoints).

- **Base (320–479 px):** one column. Form panel full width; tiles one per row, except
  energy and time, which fit two per row from 360 px if labels allow. Results stack.
- **≥ 30 rem (480 px):** tiles two per row where labels fit; they wrap otherwise.
- **≥ 64 rem (1024 px):** still one main column (max 48 rem, centred) for both the form
  page and the results page (8.9: no side-by-side form and results); decorative doodles
  in the margins. Cards stay in one column of up to three, so zero-, one-, two- and
  three-result states never leave visual gaps.
- **Landscape phones:** same as base; the form panel never fixes to the viewport.
- **Zoom and reflow:** at 400 % (320 px equivalent) one column, no horizontal scroll
  (1.4.10); text spacing overrides do not clip (1.4.12).
- **No hover:** hover styles only under `@media (hover: hover)`.

## 5. SVG assets

One self-hosted sprite `static/icons.svg` (viewBox `0 0 24 24` per symbol), plus three
decorative files. Drawing language: 2 px stroke, round caps and joins, `currentColor`,
fewer than 20 path commands per icon, no filters, scripts, rasters or external references.

| Asset | Location | Sizes | Class | Treatment |
|---|---|---|---|---|
| adult, adult-with-child | who tiles | 24 | decorative (label beside) | `aria-hidden` |
| clock-30, clock-1h, clock-2h, clock-half-day | time tiles | 24 | decorative | `aria-hidden` |
| snail, walker, whirlwind | energy tiles | 24 | decorative | `aria-hidden` |
| location-pin | "Use my location" | 24 | decorative | `aria-hidden` |
| sun, cloud, rain, wind, sunset, thermometer | card weather line | 32, 48 | decorative (text states the weather) | `aria-hidden` |
| info, check, alert | notices | 24 | decorative (text carries meaning) | `aria-hidden` |
| tape-strip | card tops | 64 × 16 | decorative | `aria-hidden`, separate file |
| leaf-doodle, cloud-doodle | page margins, ≥ 64 rem only | 48–96 | decorative | `aria-hidden`, separate file |

Rune Icons (D47) are **declined for v1**: all icons are this small original set. At 24 px every icon keeps at least 2 px gaps between strokes. No illustration shows water
edges, climbing, heights, fire or roads.

## 6. Interaction

- **Form:** one page, fieldsets for who, ages (shown when "Me and the kids" is chosen;
  without JS they are always visible with a hint), time, energy, where, and the D39 field
  (accepted). Defaults only where decided: energy "Moderate" (D18);
  everything else starts unselected.
- **"Use my location":** asks the browser once on click. It fills hidden rounded
  coordinates and shows "Using your location". There is no reverse geocoding. The button
  is rendered hidden and shown only once `location.js` runs in a secure context with the
  geolocation API, so without JavaScript only the town field is offered (TC-011).
- **Submit and busy state (D43):** validation first (BACKEND-CONTRACT §7). With htmx the
  button shows "Finding outings…" at once and the note "This can take up to 20 seconds."
  appears in a polite live region; repeat clicks are ignored and the server deduplicates.
  There is no Stop button, no stage messages, no polling and no progress stream. Without
  JavaScript the browser's own loading state shows while the POST waits. No percentages,
  splash screens or artificial delays.
- **Focus:** stays on the submit button while work runs. It moves to the results heading
  or error summary only once those exist.
- **Results page (simplified in 8.9):** one column at every width, in this order:
  heading and planned window → a short answers summary ("Me and the kids (3–5, 6–9) ·
  1 hour · Moderate · near Bergby") with a "Change answers" disclosure that
  holds the prefilled form (native `<details>`, works without JS, collapsed by default) →
  the shared weather line, once → notices and the fallback label → interest labels →
  zero to three cards. The editable form is not shown beside the results, so there is
  one task on screen. Cards replace earlier results; earlier ones are removed before a
  new request starts.
- **Cards (tightened in 8.12):** the title, one playful sentence (the hook, which no
  longer repeats the activity or place), one practical line ("Linden Park · park · about
  0.6 km away · 24 min there and back · 36 min activity"), the uncertainty labels that
  apply, and "Read the full activity". Reasons, the interest match and every instruction
  live on the detail page under "Why this idea" and "What to do". No per-card weather:
  the cards share one window, shown once above them.
- **Form (compacted in 8.9):** short legends, 12 px between tiles, 24 px between
  fieldsets; two tiles per row from 360 px for who, ages and time, energy one per row
  below 40 rem; ages four per row and energy three per row from 40 rem; decorative tile
  icons hidden below 30 rem; panel padding 16 px below 30 rem; tiles keep 56 px height
  and native controls; the
  check mark is drawn only on the selected tile and takes no space otherwise, so "10–12"
  never wraps.
- **Detail view:** "Read the full activity" opens a page (works without JS) with steps,
  the bingo card as a 3 × 3 grid when the activity has one, optional items with
  alternatives, adaptation, safety note, the full weather line with date and time,
  the source line ("Place data © OpenStreetMap contributors; weather from Open-Meteo"),
  "Print this card" and "Back to results".
- **D39 interest labels (accepted; D46):** "We think they're into: birds, running." as
  plain text, followed by "To change these, edit "What are they into?" under Change
  answers." The tags are inferred, not confirmed, and are not controls. "Change answers"
  is prefilled with the other answers, the carried location and the tag labels in the
  interests field; submitting it starts a new search and the old result stays readable,
  unchanged. Behaviour in PRODUCT-FIT §3.4–3.5.

## 7. Failure states (behaviour per ERROR-HANDLING.md)

| State | Recommendations allowed? | Screen |
|---|---|---|
| Invalid or incomplete input | No | error summary + inline messages; answers kept |
| Ambiguous town | No (until a choice) | list of up to 5 places as radio tiles (BACKEND-CONTRACT §3); focus is never trapped: the town field stays editable and the person can navigate away |
| Location permission denied | No | message at the location button; town field gets focus |
| Weather unavailable or expired | **No** | notice with retry; no card of any kind |
| No eligible activities | **No** | notice with the edits that could help; no generic filler |
| Service busy / rate limit | No | notice with the server's retry time if given; no automatic background retry |
| Provider cooldown | No | notice; retry offered only after the cooldown the server reports |
| Response lost (network) | No | CONNECTION_FAILED copy; the form keeps its answers and key, so "Try again" resubmits the same form and joins the existing job (D43) |
| Model unavailable | **Yes, labelled** | catalogue picks after every normal check, with the fallback label |
| Expired result | No new ones | historical card: "This information is no longer current." |
| Unexpected server error | No | safe message with reference; answers kept |

## 8. Motion

Cards fade and rise 8 px over 240 ms with an 80 ms stagger; hover lift 2 px, 120 ms. Under
`prefers-reduced-motion: reduce`, none. No looping animation.

## 9. Copy

| Place | Copy |
|---|---|
| Page title | Wiggle Outside (D40) |
| Intro | A few details. Up to three outdoor ideas near you. |
| Who | Who's coming? — Just me / Me and the kids |
| Ages | Kids' ages — hint: Pick all that apply. — 0–2 / 3–5 / 6–9 / 10–12 |
| Time | Time, there and back — 30 min / 1 hour / 2 hours / Half day; hint "Half day means about 4 hours." |
| Energy (8.18, Mats) | How much energy today? — hint: We may suggest something gentler. — Gentle / Moderate / High (the energy ceiling, D18, is unchanged) |
| Where | Where are you? — Use my location / Town or area |
| Where hint | Type a town or area, or use your location. Please don't enter a street address. (The OpenStreetMap lookup and its 30-day cache are explained under "How your information is used", a native disclosure below the form.) |
| Interests (D39) | What are they into? (optional) — for "Just me": What are you into? (optional) |
| Interests hint | For example: birds, puddles, running. Optional. Don't include personal details. We send this to our AI model provider to choose ideas; we don't store it. (No language claim until the PRODUCT-FIT §3.9 evaluation has run.) |
| Interest labels | We think they're into: {tags}. — note: To change these, edit "What are they into?" under Change answers. |
| No match | We couldn't match that to our activity list, so these ideas aren't sorted by interests. |
| Unclear | We weren't sure what that meant, so these ideas aren't sorted by interests. |
| Interests used by fallback | These picks are sorted by our activity list using the interests above. |
| Interests not applied | We couldn't read the interests this time, so these ideas aren't sorted by them. |
| Submit | Find outings |
| Service unavailable (hosted, D49) | Wiggle Outside can't take new searches right now. Your answers are kept; please try again in a few minutes. |
| Service limit (hosted, D49) | Wiggle Outside has reached today's limit. Please try again after {reset_time}. |
| Honeypot recovery (D49) | Something in the form couldn't be accepted. Please check your answers and send them again. |
| Honeypot label (D49) | Leave this field empty (off-screen, `aria-hidden` container, `tabindex="-1"`, `autocomplete="off"`; DEPLOYMENT §4) |
| Busy (D43) | Finding outings… · note: This can take up to 20 seconds. |
| Prefilled interests (Change answers) | hint: These are the interests we recognised. Edit them for your next search. |
| Carried location (Change answers) | {label} (kept from this search; no new place lookup) — or type a different town or area |
| Results heading | Here's what we found |
| Fewer results | We found {count} matching ideas. |
| Night, family path (DAYLIGHT_NIGHT) | heading: The adventures can wait till morning. — text: Time to put the phone down and get some rest. The outdoors will still be there tomorrow. |
| Too little daylight, family path (DAYLIGHT_TOO_SHORT, copy TC-002) | heading: Not enough daylight for this one. — text: The outing would end after sunset. Change your answers and we’ll check the daylight and the weather again, or leave the adventure for tomorrow. |
| Gentler notice | These suggestions are gentler than the energy level you selected. |
| Fallback label | AI selection isn't available right now. These picks come from our activity list and passed every normal check. |
| Card practical line | {place} · {kind} · about {distance} km away · {travel} min there and back · {duration} min activity (times are estimates; distance is straight-line, stated on the detail page; a distance that would round to 0.0 km reads "close by", with no straight-line suffix) |
| Detail: why | Why this idea — reasons, then "Matches the interests: {tags}" when true |
| Answers summary | {who} ({ages}) · {time} · {energy} · near {location} — "Change answers" |
| Stroller (D42) | We're bringing a stroller |
| Step-free (D42 P, accepted 8.20) | Prefer places reported as step-free — hint: Places OpenStreetMap reports as step-free come first. We can't check this ourselves. |
| Uncertainty | Admission not verified · Reported free admission (only for OSM `fee=no`, D37) · Step-free access not verified · OpenStreetMap reports step-free access (only the ones that apply) |
| Weather line (results, once) | Forecast for {start}–{end}, checked at {time}: {summary} (TC-010: the forecast is called a forecast) |
| Bingo heading | Your bingo card |
| Card link | Read the full activity |
| Historical | This information is no longer current. Planned for {date}, {start}–{end}, forecast checked at {time}. Plan again for fresh ideas. (TC-010) |
| Print context | Planned for {date}, {start}–{end} ({timezone}), near {location}. Weather checked at {time} on {date}; times are estimates. Check the weather again before you go if plans change. |

Errors use ERROR-HANDLING §2 copy: what happened, whether answers are kept, what to do next.
Playful wording appears only in headings, hooks and successful states.

## 10. Print

Only the detail view prints. It may run to **several pages**: steps, safety notes,
adaptations and the bingo grid are never shrunk, clipped or dropped to fit one page
(`break-inside: avoid` on each section, not on the whole card). No shadows, tape or
doodles, ink on white, with place,
activity, steps, optional items, adaptation, safety note, the weather line with its time
the bingo grid when present, and the dated print context from §9 ("Planned for Sat 10 Oct
2026, 10:31–11:31 (Europe/Stockholm), near Uppsala…"). A printed card can outlive its
day, so the date, timezone and place are always printed.

## 11. Implementation

Jinja: `base.html`; `pages/` form, results, detail, error; `partials/` fieldsets, idea
card, notice, error summary, interests; `macros/` tile, button, field, icon. Tailwind v4
with these tokens in `@theme` and the corners as `@utility`; component CSS only where
utilities repeat. Built with Bun (packages from the npm registry are fine; no npm or npx
tooling). Content-hashed self-hosted assets, SRI on scripts, the canonical CSP from PLAN §9.
No inline scripts, styles or event handlers. Usable before any JavaScript runs.

## 12. Screen, component and state checklist

| Item | Check |
|---|---|
| Form, empty and filled, mobile and desktop | mock approved; keyboard order: who → ages → time → energy → where → location → interests → submit |
| Form with errors | summary focused once; each field linked; answers kept |
| Ambiguous town list | radio tiles; expired choice handled |
| Waiting | busy state only; no focus movement until a result or error exists |
| Results 0 / 1 / 2 / 3 | no empty slots; fallback label when applicable |
| Night and too-little-daylight (family path) | fixed copy as §9 in the results heading position; answers summary with "Change answers"; no cards, no weather promise; mock `05-night.html` |
| Gentler notice, uncertainty labels | only when true |
| Detail view and print | print preview shows time context |
| Each failure state in §7 | allowed/blocked recommendations as listed |
| Historical result | "no longer current" wording; no refetch |
| D39: labels, no match, unclear | plain labels, no controls; copy as §9 |
| D39 fallback cases (PRODUCT-FIT §3.4 table) | labels only when the interpretation was valid; notices as §9 |
| "Change answers" resubmission (D46) | other answers, location and tag labels prefilled; new search; old result unchanged |
| Results page layout | one column; answers summary with "Change answers"; weather once; no per-card weather |
| Form at 320 and 390 px | "10–12" on one line; who/ages/energy two per row where they fit; no horizontal scroll |
| Bingo detail and print | 3 × 3 grid for nature-bingo; none for other activities |
| Print context | date, timezone and place printed |
| Busy state (D43) | "Finding outings…" and the 20-second note appear at once; no Stop; no stage text; cleared on every outcome |
| Contrast script | all §1.1 pairs pass |
| 320/390/768/1024/1440 px, 400 % zoom, landscape | no horizontal scroll, no clipping |
| Keyboard only, Orca, forced colours, reduced motion, no hover, no JS | full journey works |

## 13. Conflict-resolution log (design input reconciled in round 8.7)

The original design response was not part of Claude's input; these resolutions follow the
conflicts listed in Mats's round 8.7 handoff.

| Input proposed | Resolution |
|---|---|
| Invented age bands, defaults, time ranges and energy options | Our decisions kept (2.1, D18, D35); unresolved choices stay with Mats |
| Every choice as a radio group | Ages are checkboxes (several children) |
| Automatic reverse geocoding | Removed; not in the request budget |
| Universal fallback when nothing qualifies | Removed; honest no-results |
| Silent model fallback | Labelled fallback, after every normal check |
| Blanket background retry, retry during cooldown, fixed 5 s reset | Removed; retries per BACKEND-CONTRACT §6 |
| Expiry phrased as "the weather changed" | "This information is no longer current." |
| Sequential loading messages | 8.11: no stage messages at all; a static busy state (D43) |
| Focus moved on submission | Focus moves only when results or errors exist |
| `readonly` radios and checkboxes | Not supported; answers stay editable, submit ignores repeats |
| Driving estimates, unreviewed instructions | Removed; walking estimates only, catalogue text only |
| "Unverified Status" labels | Specific labels: "Admission not verified" and similar |
| System font for everything vs Shantell Sans everywhere | 8.7: Shantell for headings, system body; **superseded in 8.17** by Cabinet Grotesk + Switzer (D41) |
| Sample HTML with inline styles, `!important`, broken noise SVG, hidden brand text | Not imported |
| Its own CSP | Not adopted; PLAN §9 canonical CSP stands |
| Moss and clay text colours | Fail AAA; replaced by the inks in §1.1 |
| (8.9 review) Tall form, "four quick questions" claim | Compacted spacing and two-per-row tiles; intro "A few details." |
| (8.9 review) Weather repeated on every card | One shared weather line above the results; full line on detail and print |
| (8.9 review) Editable form beside results | Answers summary plus "Change answers" disclosure; one column |
| (8.9 review) "walking … outside" wording | "travel there and back · activity" |
| (8.9 review) Stroller and step-free combined | Two controls with different effects (D42) |
| (8.9 review) "kept on this computer" in every mode | Copy by deployment mode |
| (8.9 review) Language claim before evaluation | Removed from product copy; annotation only in mocks |
| (8.9 review) Undated print | Date, timezone and place printed |
| (8.17) Concept board and an external design review | Visual direction adopted (§1.5). Not adopted: claims of verified contrast with wrong figures (ours stand, §1.1), Shantell Sans, cleared form defaults, automatic reconnection, an invented 15-second countdown, "local planning engine" wording, weather promises about trail conditions or child safety, "Clear filters and restart" (we use "Change answers", inputs kept), a hidden AI fallback, a resetting "catalogue limit", one-page print, blanket `!important`, new SVG conventions, a multi-step form, and npx tooling |
