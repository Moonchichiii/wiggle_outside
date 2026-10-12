"""Screenshot the running app, for comparing against the approved visual direction.

    uv run python scripts/shoot.py                       # the form at 390, 1440, 1920
    uv run python scripts/shoot.py --results 390         # one page, one width
    (--errors, --results, --detail, --night)

Writes out/shot-<page>-<width>.png. Needs the app on 127.0.0.1:8443 (night: 8444) and
`bun run build`. Compare with docs/design-kit/shots/.
Playwright is a dev dependency; the browser tests under tests/web use it for real.
This is an eyeball aid, not a check.
"""

import sys
from pathlib import Path
from typing import Final

from playwright.sync_api import sync_playwright

OUT: Final = Path(__file__).resolve().parent.parent / "out"
BASE: Final = "https://127.0.0.1:8443"
URL: Final = BASE + "/"
# The night page needs a daylight-blocked planner; see scripts/night_server.py.
NIGHT_BASE: Final = "https://127.0.0.1:8444"
NIGHT_URL: Final = NIGHT_BASE + "/"
WIDTHS: Final = (390, 1440, 1920)
TALL: Final = 1100


def submit_form(page: object, *, invalid: bool = False) -> None:
    """Drive the real browser journey: fill the form and submit it.

    No injected session and no out-of-band POST: with `Referrer-Policy: same-origin`
    (TC-008) the browser's own submission is accepted, so what is screenshotted is what
    a person would actually get. `invalid` leaves the age bands empty, which is the
    422 the form must re-render in place.
    """
    page.check('input[name="who"][value="kids"]')  # type: ignore[attr-defined]
    if not invalid:
        page.check('input[name="age_band"][value="3-5"]')  # type: ignore[attr-defined]
        page.check('input[name="time"][value="60"]')  # type: ignore[attr-defined]
    page.fill('input[name="place"]', "Bergby")  # type: ignore[attr-defined]
    page.click('button[type="submit"]')  # type: ignore[attr-defined]
    page.wait_for_load_state("networkidle")  # type: ignore[attr-defined]


def main() -> int:
    flags = {
        "--results": "results",
        "--errors": "errors",
        "--night": "night",
        "--detail": "detail",
    }
    args = [a for a in sys.argv[1:] if a not in flags]
    mode = next((name for flag, name in flags.items() if flag in sys.argv), "form")
    widths = [int(a) for a in args] or list(WIDTHS)
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as play:
        browser = play.chromium.launch()
        # The dev certificate is self-signed. The app must be served over HTTPS
        # locally because a browser refuses a __Host- cookie on plain HTTP (D31).
        for width in widths:
            page = browser.new_page(
                viewport={"width": width, "height": TALL},
                ignore_https_errors=True,
            )
            page.goto(NIGHT_URL if mode == "night" else URL, wait_until="networkidle")
            # The fonts must have swapped in before the shot, or the screenshot shows
            # the fallback and the comparison is meaningless.
            page.wait_for_timeout(400)
            if mode != "form":
                submit_form(page, invalid=mode == "errors")
                page.wait_for_timeout(300)
            if mode == "detail":
                page.click(".wo-card-link a")
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(300)
            target = OUT / f"shot-{mode}-{width}.png"
            page.screenshot(path=str(target), full_page=True)
            print(f"{target}  ({width} px)")
            page.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
