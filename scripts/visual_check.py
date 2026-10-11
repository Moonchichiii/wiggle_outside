"""Measure the board decorations against the kit's placement (docs/design-kit, TC-008).

    uv run python scripts/visual_check.py

For each page (form, errors, results, detail, night) at 390, 1280, 1440, 1580 and 1920 px:
every decoration sits where kit.css puts it (board pixels times the stage scale, measured
from the panel's edges), none is cut off by the viewport, none overlaps the panel, no
label is clipped, and the page does not scroll sideways. On a phone only the sun and one
sprig show, above the panel. Exit 1 on any failure. An eyeball aid with teeth, not one of
the WP9b gates.
"""

import sys
from typing import Final

from playwright.sync_api import Page, sync_playwright

MAIN: Final = "https://127.0.0.1:8443/"
NIGHT: Final = "https://127.0.0.1:8444/"
WIDTHS: Final = (390, 1280, 1440, 1580, 1920)
PAGES: Final = ("form", "errors", "results", "detail", "night")
PHONE_MAX: Final = 599
DECOR_MIN: Final = 1100
TOLERANCE_PX: Final = 1.5

# kit.css: (side, width, top, gap) in board pixels. Left pieces measure from the panel's
# left edge, right pieces from its right edge, all tops from the panel's top.
PLACEMENT: Final[dict[str, tuple[str, float, float, float]]] = {
    "wo-d-sun": ("left", 154, 18, 30),
    "wo-d-sprig-lt": ("left", 62, 186, 15),
    "wo-d-small-people": ("left", 156, 231, 39),
    "wo-d-sprig-lm": ("left", 55, 463, 155),
    "wo-d-grass-lb": ("left", 113, 919, 51),
    "wo-d-nature-ideas": ("right", 185, 18, 30),
    "wo-d-sprig-rt": ("right", 55, 250, 42),
    "wo-d-curiosity": ("right", 117, 378, 72),
    "wo-d-sprig-rm": ("right", 56, 458, 23),
    "wo-d-signpost": ("right", 202, 543, 23),
}
# The phone subset: (width, top, left or right offset from the stage).
PHONE: Final[dict[str, tuple[float, float, str, float]]] = {
    "wo-d-sun": (74, -66, "left", 6),
    "wo-d-sprig-rt": (34, -58, "right", 10),
}

BOXES_JS: Final = """() => [...document.querySelectorAll('.wo-stage > .wo-decor')]
  .filter(e => getComputedStyle(e).display !== 'none')
  .map(e => { const r = e.getBoundingClientRect();
    return {c: e.className, x: r.x + window.scrollX, y: r.y + window.scrollY,
            w: r.width, h: r.height}; })"""
RECT_JS: Final = """(sel) => { const e = document.querySelector(sel);
  const r = e.getBoundingClientRect();
  return {x: r.x + window.scrollX, y: r.y + window.scrollY, w: r.width, h: r.height,
          k: parseFloat(getComputedStyle(e).getPropertyValue('--wo-k')) || 1}; }"""
CLIP_JS: Final = """() => [...document.querySelectorAll(
    '.wo-tile-label,.wo-card-title,.wo-legend,.wo-btn,.wo-brand')]
  .filter(e => e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 1)
  .map(e => e.textContent.trim().slice(0, 30))"""

Box = dict[str, float]


def piece(box: Box) -> str:
    return next(c for c in str(box["c"]).split() if c in PLACEMENT)


def intersects(a: Box, b: Box) -> bool:
    return (
        a["x"] < b["x"] + b["w"]
        and b["x"] < a["x"] + a["w"]
        and a["y"] < b["y"] + b["h"]
        and b["y"] < a["y"] + a["h"]
    )


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
    if kind == "detail":
        page.click(".wo-card-link a")
        page.wait_for_load_state("networkidle")


def expected_desktop(name: str, panel: Box) -> tuple[float, float, float]:
    side, width, top, gap = PLACEMENT[name]
    k = panel["k"]
    x = panel["x"] - (gap + width) * k if side == "left" else panel["x"] + panel["w"] + gap * k
    return x, panel["y"] + top * k, width * k


def expected_phone(name: str, stage: Box) -> tuple[float, float, float]:
    width, top, side, offset = PHONE[name]
    x = stage["x"] + offset if side == "left" else stage["x"] + stage["w"] - offset - width
    return x, stage["y"] + top, width


def placement(boxes: list[Box], panel: Box, stage: Box, width: int) -> list[str]:
    phone = width <= PHONE_MAX
    wanted = set(PHONE) if phone else (set(PLACEMENT) if width >= DECOR_MIN else set())
    shown = {piece(box): box for box in boxes}
    problems = [f"missing: {name}" for name in sorted(wanted - set(shown))]
    problems += [f"shown but should not be: {name}" for name in sorted(set(shown) - wanted)]
    for name in sorted(wanted & set(shown)):
        box = shown[name]
        x, y, w = expected_phone(name, stage) if phone else expected_desktop(name, panel)
        off = max(abs(box["x"] - x), abs(box["y"] - y), abs(box["w"] - w))
        if off > TOLERANCE_PX:
            problems.append(f"misplaced: {name} by {off:.1f}px")
    return problems


def check(page: Page, width: int) -> list[str]:
    boxes: list[Box] = page.evaluate(BOXES_JS)
    panel: Box = page.evaluate(RECT_JS, "main.wo-panel")
    stage: Box = page.evaluate(RECT_JS, ".wo-stage")
    problems = placement(boxes, panel, stage, width)
    problems += [
        f"off-canvas: {piece(box)}"
        for box in boxes
        if box["x"] < -TOLERANCE_PX or box["x"] + box["w"] > width + TOLERANCE_PX
    ]
    # The kit sets the phone sun's box so its ray tips touch the panel's top edge; the
    # placement check above already pins it, so only the desktop pieces are tested here.
    if width > PHONE_MAX:
        problems += [f"covers the panel: {piece(box)}" for box in boxes if intersects(panel, box)]
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
