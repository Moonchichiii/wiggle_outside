"""The SVG assets against the DESIGN-SPEC section 5 drawing language.

Every icon: 2 px stroke, round caps and joins, currentColor, fewer than 20 path commands,
and no filters, scripts, rasters or external references. Every standalone file carries
width and height, because the page must stay usable if the stylesheet fails
(DESIGN-SPEC section 3).

The sprite is inlined in a template while the content-hashed static pipeline is WP9b's, so
each glyph exists twice. These tests keep the two copies identical.
"""

import re
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
SVG_DIR: Final = REPO_ROOT / "frontend" / "svg"
SPRITE: Final = (
    REPO_ROOT / "src" / "wiggle_outside" / "web" / "templates" / "partials" / "icon_sprite.html"
)
# DESIGN-SPEC section 5 names these six for the weather line. (Its tape strip went with
# the board's cards, TC-008.) They did not exist before WP8's results work.
WEATHER_GLYPHS: Final[tuple[str, ...]] = (
    "sun",
    "cloud",
    "rain",
    "wind",
    "sunset",
    "thermometer",
)
MAX_PATH_COMMANDS: Final = 20

PATH_D: Final = re.compile(r'\sd="([^"]+)"')
COMMAND: Final = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]")
SYMBOL: Final = re.compile(r'<symbol id="i-([a-z-]+)"[^>]*>(.*?)</symbol>', re.DOTALL)


def files() -> dict[str, str]:
    return {path.stem: path.read_text(encoding="utf-8") for path in sorted(SVG_DIR.glob("*.svg"))}


def symbols() -> dict[str, str]:
    return dict(SYMBOL.findall(SPRITE.read_text(encoding="utf-8")))


def inner(body: str) -> str:
    """Return what is inside the outermost svg element, with no whitespace at the ends."""
    start = body.index(">", body.index("<svg")) + 1
    return body[start : body.rindex("</svg>")].strip()


def test_the_weather_glyphs_exist_as_files() -> None:
    assert set(files()) == set(WEATHER_GLYPHS)


@pytest.mark.parametrize("name", WEATHER_GLYPHS)
def test_each_file_has_intrinsic_dimensions(name: str) -> None:
    svg = re.search(r"<svg[^>]*>", files()[name])
    assert svg, f"{name}: no svg element"
    assert "width=" in svg.group(0), f"{name}: no width attribute"
    assert "height=" in svg.group(0), f"{name}: no height attribute"
    assert 'aria-hidden="true"' in svg.group(0), f"{name}: decorative icons are aria-hidden"


@pytest.mark.parametrize("name", WEATHER_GLYPHS)
def test_each_file_follows_the_drawing_language(name: str) -> None:
    body = files()[name]
    assert 'stroke="currentColor"' in body, f"{name}: not currentColor"
    assert 'stroke-width="2"' in body, f"{name}: not a 2 px stroke"
    assert 'stroke-linejoin="round"' in body, f"{name}: joins are not round"
    # No filters, scripts, rasters or external references. The xmlns declaration is the
    # one URI an icon may carry: it names the SVG namespace, it fetches nothing.
    for banned in ("<filter", "<image", "<script", "<use", "xlink:href", "href=", "url("):
        assert banned not in body, f"{name}: {banned} is not allowed in an icon"
    assert body.count("http") == 1, f"{name}: a URI other than the xmlns declaration"
    # No raw colour: the only fills are "none", and colour comes from CSS tokens.
    assert not re.search(r'fill="#', body), f"{name}: a raw colour value"


@pytest.mark.parametrize("name", WEATHER_GLYPHS)
def test_each_icon_has_round_caps(name: str) -> None:
    assert 'stroke-linecap="round"' in files()[name], f"{name}: caps are not round"


@pytest.mark.parametrize("name", WEATHER_GLYPHS)
def test_each_icon_stays_under_twenty_path_commands(name: str) -> None:
    commands = sum(len(COMMAND.findall(d)) for d in PATH_D.findall(files()[name]))
    assert commands < MAX_PATH_COMMANDS, f"{name}: {commands} path commands"


@pytest.mark.parametrize("name", WEATHER_GLYPHS)
def test_the_sprite_symbol_matches_its_file(name: str) -> None:
    assert symbols()[name].strip() == inner(files()[name]), (
        f"{name}: the sprite symbol and frontend/svg/{name}.svg have drifted apart"
    )


def test_every_sprite_symbol_has_a_viewbox_of_twentyfour() -> None:
    sprite = SPRITE.read_text(encoding="utf-8")
    assert sprite.count('viewBox="0 0 24 24"') == sprite.count("<symbol ")
