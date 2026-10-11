"""GET /favicon.ico and the touch icon (TC-011).

Browsers ask for /favicon.ico unprompted, so it is a route of its own with a one-day
cache; the touch icon is an ordinary static file. Both are exported once from the
approved sun artwork and committed as finished files under frontend/art/.
"""

import struct
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest
from web_support import Harness, build_harness

from wiggle_outside.preview_planner import PreviewPlanner
from wiggle_outside.web.security import FAVICON_CACHE_CONTROL

ART: Final = Path(__file__).resolve().parents[2] / "frontend" / "art"
ICO_HEADER: Final = b"\x00\x00\x01\x00"
PNG_HEADER: Final = b"\x89PNG\r\n\x1a\n"
TOUCH_ICON_PX: Final = 180
ICO_SIZES: Final = {16, 32, 48}


@pytest.fixture
def built(tmp_path: Path) -> Iterator[Harness]:
    (tmp_path / "favicon.ico").write_bytes(ICO_HEADER + b"\x01\x00")
    (tmp_path / "apple-touch-icon.png").write_bytes(PNG_HEADER)
    (tmp_path / "app.css").write_text(".wo-body{}", encoding="utf-8")
    yield from build_harness(PreviewPlanner(), static_root=tmp_path)


def test_the_favicon_is_served_with_a_day_of_cache(built: Harness) -> None:
    served = built.client.get("/favicon.ico")

    assert served.status_code == 200
    assert served.headers["content-type"] == "image/x-icon"
    assert served.headers["cache-control"] == FAVICON_CACHE_CONTROL
    assert served.content.startswith(ICO_HEADER)
    assert "content-security-policy" in served.headers


def test_the_page_names_both_icons_from_its_own_origin(built: Harness) -> None:
    page = built.client.get("/")

    assert '<link rel="icon" href="/favicon.ico" sizes="16x16 32x32 48x48">' in page.text
    assert '<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">' in page.text
    touch = built.client.get("/static/apple-touch-icon.png")
    assert touch.status_code == 200
    assert touch.headers["content-type"] == "image/png"


def test_an_absent_favicon_is_a_clean_404(tmp_path: Path) -> None:
    for harness in build_harness(PreviewPlanner(), static_root=tmp_path):
        missing = harness.client.get("/favicon.ico")

        assert missing.status_code == 404
        assert "content-security-policy" in missing.headers
        break


def test_the_exported_icons_are_the_three_sizes_and_the_touch_icon() -> None:
    ico = (ART / "favicon.ico").read_bytes()
    assert ico.startswith(ICO_HEADER)
    count = struct.unpack("<H", ico[4:6])[0]
    sizes = {ico[6 + 16 * i] for i in range(count)}
    assert sizes == ICO_SIZES

    png = (ART / "apple-touch-icon.png").read_bytes()
    assert png.startswith(PNG_HEADER)
    width, height = struct.unpack(">II", png[16:24])
    assert (width, height) == (TOUCH_ICON_PX, TOUCH_ICON_PX)
