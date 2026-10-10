"""Screenshot the running app, for comparing against the approved visual direction.

    uv run python scripts/shoot.py            # 390 and 1440
    uv run python scripts/shoot.py 390        # one width

Writes out/shot-<width>.png. Needs the app on 127.0.0.1:8000 and `bun run build:css`.
Playwright is a dev dependency; WP9b owns the CSP, axe and journey runs that use it for
real. This is an eyeball aid, not a check.
"""

import re
import sys
from pathlib import Path
from typing import Final

import httpx
from playwright.sync_api import sync_playwright

OUT: Final = Path(__file__).resolve().parent.parent / "out"
BASE: Final = "https://127.0.0.1:8443"
URL: Final = BASE + "/"
SESSION_COOKIE: Final = "__Host-wo_session"
HTTP_SEE_OTHER: Final = 303
WIDTHS: Final = (390, 1440)
TALL: Final = 1100


def result_url_and_cookie() -> tuple[str, str]:
    """Reach a results page, then hand the browser the session that owns it.

    The browser cannot do the POST itself here: the local certificate is self-signed, so
    Chrome treats the page as an untrusted origin, sends `Origin: null` and withholds the
    `__Host-` cookie — and the app correctly refuses that with 403 SESSION_INVALID. That
    is the capture rig, not the product: over a real certificate the browser journey
    works, and `tests/web` drives the same POST 192 ways. So the session is established
    with httpx and injected, and what gets screenshotted is the real rendered page.
    """
    with httpx.Client(verify=False, base_url=BASE, follow_redirects=False) as client:  # noqa: S501
        form = client.get("/").text
        token = re.search(r'name="csrf_token" value="([^"]+)"', form)
        key = re.search(r'name="idempotency_key" value="([^"]+)"', form)
        if token is None or key is None:
            msg = "the form page carried no csrf token or idempotency key"
            raise RuntimeError(msg)
        posted = client.post(
            "/plan",
            headers={"Origin": BASE},
            data={
                "csrf_token": token.group(1),
                "idempotency_key": key.group(1),
                "who": "kids",
                "age_band": "3-5",
                "time": "60",
                "energy": "moderate",
                "location_mode": "typed",
                "place": "Bergby",
                "hp_note": "",
            },
        )
        if posted.status_code != HTTP_SEE_OTHER:
            msg = f"POST /plan answered {posted.status_code}, not a redirect"
            raise RuntimeError(msg)
        return posted.headers["location"], client.cookies[SESSION_COOKIE]


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--results"]
    results = "--results" in sys.argv
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
            page.goto(URL, wait_until="networkidle")
            # The fonts must have swapped in before the shot, or the screenshot shows
            # the fallback and the comparison is meaningless.
            page.wait_for_timeout(400)
            if results:
                target_url, session = result_url_and_cookie()
                page.context.add_cookies(
                    [
                        {
                            "name": SESSION_COOKIE,
                            "value": session,
                            "domain": "127.0.0.1",
                            "path": "/",
                            "secure": True,
                            "sameSite": "Strict",
                        }
                    ]
                )
                page.goto(BASE + target_url, wait_until="networkidle")
                page.wait_for_timeout(300)
            target = OUT / f"shot-{'results' if results else 'form'}-{width}.png"
            page.screenshot(path=str(target), full_page=True)
            print(f"{target}  ({width} px)")
            page.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
