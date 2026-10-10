"""GET /static/{hashed}: immutable assets, the two fonts, and nothing else.

Content-hashed names never change meaning, so they carry a one-year cache. The fonts are
not in the repository under their licence (TC-007), so an absent face is a clean 404.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from web_support import Harness, build_harness

from wiggle_outside.preview_planner import PreviewPlanner
from wiggle_outside.web.routes.assets import FONT_FILES, build_manifest
from wiggle_outside.web.security import STATIC_CACHE_CONTROL

FONT = "CabinetGrotesk-Variable.woff2"


@pytest.fixture
def built(tmp_path: Path) -> Iterator[Harness]:
    """Build a static root that looks like a finished build."""
    (tmp_path / "app.abc123.css").write_text(".wo-body{color:#000}", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(
        '{"app.css": {"url": "/static/app.abc123.css", "integrity": "sha384-x"}}',
        encoding="utf-8",
    )
    yield from build_harness(PreviewPlanner(), static_root=tmp_path)


def test_a_hashed_asset_is_immutable(built: Harness) -> None:
    served = built.client.get("/static/app.abc123.css")

    assert served.status_code == 200
    assert served.headers["cache-control"] == STATIC_CACHE_CONTROL
    assert served.headers["content-type"].startswith("text/css")


def test_an_asset_that_is_not_there_is_a_404(built: Harness) -> None:
    missing = built.client.get("/static/nothing.css")

    assert missing.status_code == 404
    assert "content-security-policy" in missing.headers


@pytest.mark.parametrize(
    "path",
    [
        "../support.py",
        "..%2Fsupport.py",
        "%2e%2e%2fsupport.py",
        "/etc/passwd",
        "fonts/../../support.py",
    ],
)
def test_nothing_outside_the_static_root_is_servable(built: Harness, path: str) -> None:
    answered = built.client.get(f"/static/{path}")

    assert answered.status_code == 404


def test_a_font_is_served_when_it_is_present(tmp_path: Path) -> None:
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    (fonts / FONT).write_bytes(b"wOF2-not-really")
    for harness in build_harness(PreviewPlanner(), static_root=tmp_path):
        served = harness.client.get(f"/static/fonts/{FONT}")

        assert served.status_code == 200
        assert served.headers["content-type"] == "font/woff2"
        assert served.headers["cache-control"] == STATIC_CACHE_CONTROL
        break


def test_an_absent_font_is_a_clean_404(built: Harness) -> None:
    # TC-007: the files are gitignored under the Fontshare licence.
    missing = built.client.get(f"/static/fonts/{FONT}")

    assert missing.status_code == 404
    assert missing.text == ""


def test_only_the_two_named_faces_are_servable(tmp_path: Path) -> None:
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    (fonts / "Smuggled.woff2").write_bytes(b"nope")
    for harness in build_harness(PreviewPlanner(), static_root=tmp_path):
        assert harness.client.get("/static/fonts/Smuggled.woff2").status_code == 404
        break


def test_the_two_faces_are_the_ones_the_design_spec_names() -> None:
    assert {"CabinetGrotesk-Variable.woff2", "Switzer-Variable.woff2"} == FONT_FILES


def test_the_manifest_names_the_logical_asset_and_its_hashed_file(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text(
        '{"app.css": {"url": "/static/app.abc123.css", "integrity": "sha384-x"}}',
        encoding="utf-8",
    )

    manifest = build_manifest(tmp_path)

    assert manifest["app.css"].url == "/static/app.abc123.css"
    assert manifest["app.css"].integrity == "sha384-x"


def test_without_a_manifest_every_stylesheet_is_its_own_entry(tmp_path: Path) -> None:
    (tmp_path / "app.css").write_text(".wo-body{}", encoding="utf-8")

    manifest = build_manifest(tmp_path)

    assert manifest["app.css"].url == "/static/app.css"


def test_a_broken_manifest_is_no_assets_rather_than_a_crash(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text("{not json", encoding="utf-8")

    assert build_manifest(tmp_path) == {}


def test_the_stylesheet_link_is_emitted_from_the_manifest(built: Harness) -> None:
    # The page was unstyled once because the link was never emitted; keep it tested.
    page = built.client.get("/")

    assert '<link rel="stylesheet" href="/static/app.abc123.css"' in page.text
    assert 'integrity="sha384-x"' in page.text
