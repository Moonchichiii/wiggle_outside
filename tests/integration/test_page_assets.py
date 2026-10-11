"""GET / must link a stylesheet, and that stylesheet must actually serve CSS.

Written because it did not. `base.html` emits the `<link>` only for an asset whose *key*
ends in `.css`, and the preview passed the key `"css"`, so the served_html shipped with no
stylesheet at all and rendered in Times with 300x150 icons. Every check was green: the
route tests only compared paths, and the template tests rendered through a fixture that
supplied its own assets. Nothing asserted the two ends met.
"""

import base64
import hashlib
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

LINK: Final = re.compile(r'<link[^>]+rel="stylesheet"[^>]*>', re.IGNORECASE)
HREF: Final = re.compile(r'href="([^"]+)"')
HREF_ANY: Final = re.compile(r'src="([^"]+)"')
INTEGRITY: Final = re.compile(r'integrity="([^"]+)"')
SCRIPT: Final = re.compile(r"(<script[^>]*>)(.*?)</script>", re.IGNORECASE | re.DOTALL)
HTTP_OK: Final = 200
MIN_CSS_BYTES: Final = 1000


@pytest.fixture
def served_html(asgi_client: TestClient) -> str:
    response = asgi_client.get("/")
    assert response.status_code == HTTP_OK
    return response.text


def test_the_page_links_exactly_one_stylesheet(served_html: str) -> None:
    links = LINK.findall(served_html)
    assert len(links) == 1, f"expected one stylesheet link, found {len(links)}"


def test_the_stylesheet_url_serves_non_empty_css(served_html: str, asgi_client: TestClient) -> None:
    # The bundle is a gitignored build artifact. scripts/check.ps1 builds it before
    # pytest; a bare `pytest` in a fresh checkout has to be told why, not just fail.
    built = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "wiggle_outside"
        / "web"
        / "static"
        / "app.css"
    )
    if not built.is_file():
        pytest.skip("run `bun run build:css` first, or ./scripts/check.ps1 which does")

    href_match = HREF.search(LINK.findall(served_html)[0])
    assert href_match, "the stylesheet link has no href"

    response = asgi_client.get(href_match.group(1))
    assert response.status_code == HTTP_OK
    assert "text/css" in response.headers["content-type"]
    assert len(response.content) > MIN_CSS_BYTES, "the stylesheet is suspiciously small"
    # A built Tailwind bundle defines the design tokens; an empty or unbuilt file does not.
    assert "--color-oatmeal" in response.text
    assert "--color-ink" in response.text


def test_the_page_carries_no_inline_style_or_script(served_html: str) -> None:
    # The CSP forbids both (PLAN section 9). Asserted on what is actually served, not
    # only on a template rendered in a test. A script is allowed only as an external,
    # same-origin, integrity-pinned file with no body (TC-011).
    for tag, body in SCRIPT.findall(served_html):
        assert body.strip() == "", tag
        assert 'src="/static/' in tag, tag
        assert 'integrity="sha384-' in tag, tag
        assert " defer" in tag, tag
    assert "<script>" not in served_html.lower()
    assert "style=" not in served_html.lower()
    assert "javascript:" not in served_html.lower()


def test_every_script_is_served_as_javascript_with_a_matching_integrity(
    served_html: str, asgi_client: TestClient
) -> None:
    # TC-011: the build hashes location.js into static/ and names it in manifest.json.
    tags = [tag for tag, _ in SCRIPT.findall(served_html)]
    if not tags:
        pytest.skip("run `bun run build` first, or ./scripts/check.ps1 which does")
    for tag in tags:
        src = HREF_ANY.search(tag)
        integrity = INTEGRITY.search(tag)
        assert src, tag
        assert integrity, tag
        response = asgi_client.get(src.group(1))
        assert response.status_code == HTTP_OK
        assert "javascript" in response.headers["content-type"]
        digest = base64.b64encode(hashlib.sha384(response.content).digest()).decode()
        assert integrity.group(1) == f"sha384-{digest}"
        assert "geolocation" in response.text


def test_every_inline_svg_has_intrinsic_dimensions(served_html: str) -> None:
    # An svg with a viewBox but no width/height falls back to 300x150, so the served_html has to
    # stay usable when the stylesheet fails (DESIGN-SPEC section 3 sizes).
    svgs = re.findall(r"<svg[^>]*>", served_html)
    assert svgs, "no inline svg found on the page"
    missing = [tag for tag in svgs if "width=" not in tag or "height=" not in tag]
    assert not missing, f"svg without width/height: {missing}"


def test_health_and_readiness_answer(asgi_client: TestClient) -> None:
    assert asgi_client.get("/healthz").text == "ok"
    body = asgi_client.get("/readyz").text
    assert "app: ready" in body
    # No model adapter is wired until WP5, and the endpoint must not claim otherwise.
    assert "model: unavailable" in body
