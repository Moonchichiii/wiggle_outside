"""GET / must link a stylesheet, and that stylesheet must actually serve CSS.

Written because it did not. `base.html` emits the `<link>` only for an asset whose *key*
ends in `.css`, and the preview passed the key `"css"`, so the page shipped with no
stylesheet at all and rendered in Times with 300x150 icons. Every check was green: the
route tests only compared paths, and the template tests rendered through a fixture that
supplied its own assets. Nothing asserted the two ends met.
"""

import re
from typing import TYPE_CHECKING, Final

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

LINK: Final = re.compile(r'<link[^>]+rel="stylesheet"[^>]*>', re.IGNORECASE)
HREF: Final = re.compile(r'href="([^"]+)"')
HTTP_OK: Final = 200
MIN_CSS_BYTES: Final = 1000


@pytest.fixture
def page(asgi_client: TestClient) -> str:
    response = asgi_client.get("/")
    assert response.status_code == HTTP_OK
    return response.text


def test_the_page_links_exactly_one_stylesheet(page: str) -> None:
    links = LINK.findall(page)
    assert len(links) == 1, f"expected one stylesheet link, found {len(links)}"


def test_the_stylesheet_url_serves_non_empty_css(page: str, asgi_client: TestClient) -> None:
    href_match = HREF.search(LINK.findall(page)[0])
    assert href_match, "the stylesheet link has no href"

    response = asgi_client.get(href_match.group(1))
    assert response.status_code == HTTP_OK
    assert "text/css" in response.headers["content-type"]
    assert len(response.content) > MIN_CSS_BYTES, "the stylesheet is suspiciously small"
    # A built Tailwind bundle defines the design tokens; an empty or unbuilt file does not.
    assert "--color-oatmeal" in response.text
    assert "--color-ink" in response.text


def test_the_page_carries_no_inline_style_or_script(page: str) -> None:
    # The CSP forbids both (PLAN section 9). Asserted on what is actually served, not
    # only on a template rendered in a test.
    assert "<script" not in page.lower()
    assert "style=" not in page.lower()
    assert "javascript:" not in page.lower()


def test_every_inline_svg_has_intrinsic_dimensions(page: str) -> None:
    # An svg with a viewBox but no width/height falls back to 300x150, so the page has to
    # stay usable when the stylesheet fails (DESIGN-SPEC section 3 sizes).
    svgs = re.findall(r"<svg[^>]*>", page)
    assert svgs, "no inline svg found on the page"
    missing = [tag for tag in svgs if "width=" not in tag or "height=" not in tag]
    assert not missing, f"svg without width/height: {missing}"


def test_health_and_readiness_answer(asgi_client: TestClient) -> None:
    assert asgi_client.get("/healthz").text == "ok"
    body = asgi_client.get("/readyz").text
    assert "app: ready" in body
    # No model adapter is wired until WP5, and the endpoint must not claim otherwise.
    assert "model: unavailable" in body
