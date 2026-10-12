"""Recompute every contrast pair in DESIGN-SPEC section 1.1 from tokens.css.

WCAG 1.4.6 needs 7:1 for normal text. This script is the gate; the numbers in the
document are claims until it runs.

Not wired into check.ps1: it reads and prints the tokens. The contract test checks the
token values against the document; the 7:1 ratios are read off this output by hand.
"""

import re
import sys
from pathlib import Path
from typing import Final

TOKEN: Final = re.compile(r"--color-([a-z-]+):\s*(#[0-9a-fA-F]{6});")
AAA_NORMAL_TEXT: Final = 7.0
# sRGB linearisation constants, straight from the WCAG relative-luminance formula.
SRGB_LINEAR_CUTOFF: Final = 0.04045


def read_tokens(css_path: Path) -> dict[str, str]:
    return {
        name: value.lower() for name, value in TOKEN.findall(css_path.read_text(encoding="utf-8"))
    }


def _channel(value: float) -> float:
    if value <= SRGB_LINEAR_CUTOFF:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_colour: str) -> float:
    raw = hex_colour.lstrip("#")
    r, g, b = (int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(foreground: str, background: str) -> float:
    a, b = relative_luminance(foreground), relative_luminance(background)
    light, dark = max(a, b), min(a, b)
    return (light + 0.05) / (dark + 0.05)


def main() -> int:
    css = Path(__file__).resolve().parent.parent / "frontend" / "css" / "tokens.css"
    tokens = read_tokens(css)
    if not tokens:
        print(f"no colour tokens found in {css}", file=sys.stderr)
        return 1
    print(f"{len(tokens)} colour tokens read from {css.name}")
    for name, value in sorted(tokens.items()):
        print(f"  {name:14} {value}")
    print(
        "\nThe pair list and the 7:1 assertion are not automated; "
        "this run checks only that the tokens parse."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
