"""Measure the decorations against the rules of the visual-direction pass (TC-008).

    uv run python scripts/visual_check.py

For each page (form, errors, results, night) at 390, 1280, 1440, 1580 and 1920 px:
no decoration overlaps another (a piece standing in the grass excepted), none is cut
off by the viewport, none overlaps the panel or the masthead, and no label is clipped.
Exit 1 on any failure. An eyeball aid with teeth, not one of the gates.
"""

import sys
from itertools import combinations
from typing import Final

from playwright.sync_api import Page, sync_playwright

MAIN: Final = "https://127.0.0.1:8443/"
NIGHT: Final = "https://127.0.0.1:8444/"
WIDTHS: Final = (390, 1280, 1440, 1580, 1920)
PAGES: Final = ("form", "errors", "results", "night")
EDGE_TOLERANCE_PX: Final = 0.5

# Standing in the grass is layering, as on the board; it is not one piece covering another.
GRASS: Final = ("grass-left", "grass-right")
# The signpost's post, planks and base are one piece.
SIGNPOST_PARTS: Final = ("wo-d-post", "wo-d-plank", "wo-d-base")

BOXES_JS: Final = """() => [...document.querySelectorAll('.wo-decor > *')]
  .filter(e => getComputedStyle(e).display !== 'none')
  .map(e => { const r = e.getBoundingClientRect();
    return {c: e.className, x: r.x + window.scrollX, y: r.y + window.scrollY,
            w: r.width, h: r.height}; })"""
UI_JS: Final = """() => ['.wo-masthead', '.wo-panel'].map(s => {
  const e = document.querySelector(s); if (!e) return null;
  const r = e.getBoundingClientRect();
  return {c: s, x: r.x + window.scrollX, y: r.y + window.scrollY,
          w: r.width, h: r.height}; }).filter(Boolean)"""
CLIP_JS: Final = """() => [...document.querySelectorAll(
    '.wo-tile-label,.wo-card-title,.wo-legend,.wo-d-note,.wo-d-paper,.wo-d-plank')]
  .filter(e => e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 1)
  .map(e => e.textContent.trim().slice(0, 30))"""

Box = dict[str, float]


def intersects(a: Box, b: Box) -> bool:
    return (
        a["x"] < b["x"] + b["w"]
        and b["x"] < a["x"] + a["w"]
        and a["y"] < b["y"] + b["h"]
        and b["y"] < a["y"] + a["h"]
    )


def allowed(a: str, b: str) -> bool:
    joined = a + " " + b
    if any(part in joined for part in SIGNPOST_PARTS):
        return True
    return any(g in a for g in GRASS) or any(g in b for g in GRASS)


def drive(page: Page, kind: str) -> None:
    page.goto(NIGHT if kind == "night" else MAIN, wait_until="networkidle")
    if kind == "form":
        return
    page.check('input[name="who"][value="kids"]')
    if kind != "errors":
        page.check('input[name="age_band"][value="3-5"]')
        page.check('input[name="time"][value="60"]')
    page.fill('input[name="place"]', "Bergby")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


def overlaps(boxes: list[Box]) -> list[str]:
    return [
        f"overlap: {a['c']} / {b['c']}"
        for a, b in combinations(boxes, 2)
        if intersects(a, b) and not allowed(str(a["c"]), str(b["c"]))
    ]


def off_canvas(boxes: list[Box], width: int) -> list[str]:
    return [
        f"off-canvas: {box['c']}"
        for box in boxes
        if box["x"] < -EDGE_TOLERANCE_PX or box["x"] + box["w"] > width + EDGE_TOLERANCE_PX
    ]


def covering(boxes: list[Box], interface: list[Box]) -> list[str]:
    return [
        f"covers {ui['c']}: {box['c']}" for ui in interface for box in boxes if intersects(ui, box)
    ]


def check(page: Page, width: int) -> list[str]:
    boxes: list[Box] = page.evaluate(BOXES_JS)
    problems = overlaps(boxes) + off_canvas(boxes, width)
    problems += covering(boxes, page.evaluate(UI_JS))
    problems += [f"clipped: {text!r}" for text in page.evaluate(CLIP_JS)]
    if page.evaluate("document.documentElement.scrollWidth") > width:
        problems.append("horizontal scroll")
    return problems


def main() -> int:
    failures = 0
    with sync_playwright() as play:
        browser = play.chromium.launch()
        for kind in PAGES:
            for width in WIDTHS:
                page = browser.new_page(
                    viewport={"width": width, "height": 900}, ignore_https_errors=True
                )
                drive(page, kind)
                page.wait_for_timeout(250)
                problems = check(page, width)
                verdict = "ok " if not problems else "BAD"
                detail = "" if not problems else ": " + "; ".join(problems)
                print(f"{verdict} {kind:8} {width:5}px{detail}")
                failures += len(problems)
                page.close()
        browser.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
