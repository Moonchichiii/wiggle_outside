# Wiggle Outside: board design kit

A reference implementation of the approved board
(`docs/mocks/reference/visual-direction-v2.png`), built and screenshotted in a browser.
Open `form.html` and `results.html` directly in a browser to see it.

## What is here

| Path | What |
|---|---|
| `board/*.png` | Every decoration and card illustration, cut from the approved board with the paper background removed (transparent PNG). The walking family is deliberately not included (no people or children). |
| `placement.json` | Where each piece sits on the board, in board pixels, measured from the panel edges. |
| `kit.css` | The page shell, panel, form and results styles, and the decoration placement. Offsets are board pixels times `--k`, so the composition scales with the panel. |
| `form.html`, `results.html` | Static reference pages using the kit. |
| `shots/` | Screenshots at 390, 1180, 1440 and 1920 px (fonts here: Poppins and system fallbacks; on Mats's machine Cabinet Grotesk and Switzer load). |

## How to port it into the app

1. Copy `board/*.png` to `frontend/img/board/` and serve them as static assets.
2. Port `kit.css` into the app's stylesheet. Keep the app's existing tokens where they
   match; where they disagree with the kit, the kit wins (it is measured from the board).
3. Wrap every page (form, 422 re-render, results, detail, night) in the stage + panel
   structure from `form.html`: `.stage` > decoration `<div>`s + `<main class="panel">`.
4. Decorations are `aria-hidden`, `pointer-events: none`, `alt=""`, hidden in print, and
   only shown when the window is at least 1100 px wide; on phones only the sun and one
   sprig show above the panel.
5. Card illustrations: `card-trees`, `card-magnifier`, `card-sun-cloud` for the top-right
   of a card, `card-grass-a`, `card-plant-b`, `card-grass-c` for the bottom-right corner.
   Map them to activities as the app sees fit; the app's own drawn illustrations can stay
   for activities these do not suit.
6. Copy rules from the accepted contract still apply: "Prefer places reported as
   step-free", fixture data labelled "Example forecast · Illustrative places and weather",
   catalogue activities only.

## Provenance

The artwork comes from the AI-generated concept board Mats approved for this project.
Mention this in the write-up ("illustrations from our AI-generated concept board").
