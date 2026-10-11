"""'Use my location' in a real browser (TC-011), with a faked position.

The app runs on loopback with the preview planner (no provider, no model), under the
production CSP. Chromium treats http://127.0.0.1 as a secure context, so the
geolocation API is available exactly as it is on the hosted https origin. Skipped
when the frontend has not been built: the script only exists after `bun run build`.
"""

import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import replace
from typing import Final

import pytest
import uvicorn
from playwright.sync_api import Browser, expect, sync_playwright
from playwright.sync_api import Error as PlaywrightError

from wiggle_outside.core.types import DeploymentMode
from wiggle_outside.main import create_app
from wiggle_outside.preview_planner import PreviewPlanner
from wiggle_outside.settings import Settings
from wiggle_outside.web import copy
from wiggle_outside.web.routes.assets import build_manifest

# Somewhere in Stockholm, with more precision than the form may send.
POSITION: Final = {"latitude": 59.33456, "longitude": 18.06321}
ROUNDED: Final = ("59.33", "18.06")
START_TIMEOUT_S: Final = 15
BROWSER_TIMEOUT_S: Final = 120


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    if "location.js" not in build_manifest():
        pytest.skip("run `bun run build` first, or ./scripts/check.ps1 which does")
    port = _free_port()
    settings = replace(Settings.from_env(), mode=DeploymentMode.LOCAL, host="127.0.0.1", port=port)
    app = create_app(settings, planner=PreviewPlanner())
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    instance = uvicorn.Server(config)
    thread = threading.Thread(target=instance.run, daemon=True, name="wo-browser-test")
    thread.start()
    deadline = time.monotonic() + START_TIMEOUT_S
    while not instance.started:
        if time.monotonic() > deadline or not thread.is_alive():
            pytest.fail("the test server did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    instance.should_exit = True
    thread.join(timeout=START_TIMEOUT_S)


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as play:
        try:
            launched = play.chromium.launch()
        except PlaywrightError as missing:  # no browser installed: say so, do not fail
            pytest.skip(f"run `uv run playwright install chromium` first: {missing}")
        yield launched
        launched.close()


@pytest.mark.timeout(BROWSER_TIMEOUT_S)
def test_without_javascript_the_button_is_not_offered(server: str, browser: Browser) -> None:
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    page.goto(f"{server}/")

    button = page.locator("[data-wo-locate]")
    assert button.count() == 1
    expect(button).to_be_hidden()
    expect(page.locator("#locate-status")).to_be_hidden()
    context.close()


@pytest.mark.timeout(BROWSER_TIMEOUT_S)
def test_use_my_location_fills_rounded_coordinates_and_the_search_runs(
    server: str, browser: Browser
) -> None:
    context = browser.new_context(geolocation=POSITION, permissions=["geolocation"])
    page = context.new_page()
    console_errors: list[str] = []
    page.on("console", lambda message: _collect(message, console_errors))
    page.on("pageerror", lambda error: console_errors.append(str(error)))
    response = page.goto(f"{server}/")

    assert response is not None
    assert "script-src 'self'" in response.headers["content-security-policy"]
    button = page.locator("[data-wo-locate]")
    expect(button).to_be_visible()  # the external script ran under the CSP

    button.click()
    status = page.locator("#locate-status")
    expect(status).to_have_text(copy.LOCATION_USING)
    assert page.input_value('input[name="lat"]') == ROUNDED[0]
    assert page.input_value('input[name="lon"]') == ROUNDED[1]
    assert page.input_value('input[name="location_mode"]') == "coords"
    assert page.input_value('input[name="place"]') == ""

    page.check('input[name="who"][value="kids"]')
    page.check('input[name="age_band"][value="3-5"]')
    page.check('input[name="time"][value="60"]')
    page.click('.wo-plan-form button[type="submit"]')
    page.wait_for_url("**/results/*")
    expect(page.locator("#results-heading")).to_be_visible()
    assert console_errors == []
    context.close()


@pytest.mark.timeout(BROWSER_TIMEOUT_S)
def test_typing_a_town_after_locating_means_the_town(server: str, browser: Browser) -> None:
    context = browser.new_context(geolocation=POSITION, permissions=["geolocation"])
    page = context.new_page()
    page.goto(f"{server}/")
    page.click("[data-wo-locate]")
    expect(page.locator("#locate-status")).to_have_text(copy.LOCATION_USING)

    page.fill('input[name="place"]', "Bergby")

    assert page.input_value('input[name="location_mode"]') == "typed"
    expect(page.locator("#locate-status")).to_be_hidden()
    context.close()


@pytest.mark.timeout(BROWSER_TIMEOUT_S)
def test_a_refused_prompt_says_so_and_keeps_the_typed_route(server: str, browser: Browser) -> None:
    context = browser.new_context()  # no permission granted: the prompt is refused
    page = context.new_page()
    page.goto(f"{server}/")
    page.click("[data-wo-locate]")

    expect(page.locator("#locate-status")).to_have_text(copy.LOCATION_DENIED)
    assert page.input_value('input[name="location_mode"]') == "typed"
    assert page.locator('input[name="lat"]').count() == 0
    context.close()


def _collect(message: object, into: list[str]) -> None:
    kind = getattr(message, "type", "")
    if kind == "error":
        into.append(str(getattr(message, "text", message)))
