"""Glyph coverage and metrics for the self-hosted fonts (DESIGN-SPEC section 1.2, D41).

Check 1 of the three the specification requires before D41 is approved: the character map
must cover English, Swedish and French, plus the typographic marks the copy deck uses.

This reports. It does not decide: whether the files may be redistributed is a licence
question (check 2), and layout shift needs a real browser (check 3).

    uv run python scripts/check_fonts.py
    uv run python scripts/check_fonts.py --json
"""

import argparse
import json
import sys
import unicodedata
from pathlib import Path
from typing import Final

from fontTools.ttLib import TTFont

FONT_DIR: Final = Path(__file__).resolve().parent.parent / "frontend" / "fonts"

# DESIGN-SPEC section 1.2 check 1, verbatim.
SPEC_REQUIRED: Final = "å ä ö Å Ä Ö é è ê ë à â ç î ï ô û ù ü ÿ œ Œ æ « » ’ – —"

# The copy deck and the fixture data use these too (DESIGN-SPEC section 9, WALKTHROUGH).
COPY_MARKS: Final = "·…‚’“”"

LANGUAGE_SETS: Final[dict[str, str]] = {
    "ASCII letters": "".join(chr(c) for c in range(0x41, 0x5B))
    + "".join(chr(c) for c in range(0x61, 0x7B)),
    "ASCII digits and punctuation": "0123456789.,:;!?()[]{}'\"-/&%+=@#*",
    "Swedish": "åäöÅÄÖ",
    "French": "éèêëàâäçîïôöûùüÿœŒæÆÀÂÇÉÈÊËÎÏÔÛÙÜŸ«»",
    "Typographic (spec)": "’–—",
    "Typographic (copy deck)": COPY_MARKS,
}


def _codepoints(font: TTFont) -> set[int]:
    covered: set[int] = set()
    for table in font["cmap"].tables:
        covered |= set(table.cmap)
    return covered


def _describe(char: str) -> str:
    try:
        name = unicodedata.name(char)
    except ValueError:
        name = "unnamed"
    return f"U+{ord(char):04X} {char} ({name})"


def _axes(font: TTFont) -> list[dict[str, float | str]]:
    if "fvar" not in font:
        return []
    return [
        {
            "tag": axis.axisTag,
            "min": axis.minValue,
            "default": axis.defaultValue,
            "max": axis.maxValue,
        }
        for axis in font["fvar"].axes
    ]


def _metrics(font: TTFont) -> dict[str, float]:
    head = font["head"]
    hhea = font["hhea"]
    upm = head.unitsPerEm
    os2 = font.get("OS/2", None)
    metrics: dict[str, float] = {
        "unitsPerEm": upm,
        "ascent": hhea.ascent,
        "descent": hhea.descent,
        "lineGap": hhea.lineGap,
        # Ratios are what drive layout shift against a fallback face.
        "ascent_ratio": round(hhea.ascent / upm, 4),
        "descent_ratio": round(abs(hhea.descent) / upm, 4),
        "line_height_ratio": round((hhea.ascent - hhea.descent + hhea.lineGap) / upm, 4),
    }
    if os2 is not None:
        for name, attr in (("x_height", "sxHeight"), ("cap_height", "sCapHeight")):
            value = getattr(os2, attr, 0)
            if value:
                metrics[name] = value
                metrics[f"{name}_ratio"] = round(value / upm, 4)
    return metrics


def inspect(path: Path) -> dict[str, object]:
    font = TTFont(path, fontNumber=0, lazy=True)
    covered = _codepoints(font)

    missing_by_set: dict[str, list[str]] = {}
    for label, chars in LANGUAGE_SETS.items():
        gaps = [_describe(c) for c in dict.fromkeys(chars) if ord(c) not in covered]
        if gaps:
            missing_by_set[label] = gaps

    spec_chars = [c for c in SPEC_REQUIRED if not c.isspace()]
    spec_missing = [_describe(c) for c in spec_chars if ord(c) not in covered]

    names = font["name"]
    family = names.getDebugName(16) or names.getDebugName(1) or "?"
    subfamily = names.getDebugName(17) or names.getDebugName(2) or "?"

    result: dict[str, object] = {
        "file": path.name,
        "bytes": path.stat().st_size,
        "family": family,
        "subfamily": subfamily,
        "glyphs": len(font.getGlyphOrder()),
        "codepoints": len(covered),
        "is_variable": "fvar" in font,
        "axes": _axes(font),
        "metrics": _metrics(font),
        "spec_required_missing": spec_missing,
        "missing_by_set": missing_by_set,
    }
    font.close()
    return result


def _print_report(report: dict[str, object]) -> bool:
    """Print one font's findings. Returns False if anything is missing."""
    print()
    print(f"=== {report['file']} ({report['bytes']:,} bytes) ===")
    print(f"  family      {report['family']} / {report['subfamily']}")
    print(f"  glyphs      {report['glyphs']}, {report['codepoints']} codepoints")
    if report["is_variable"]:
        axes = ", ".join(
            f"{a['tag']} {a['min']}-{a['max']} (default {a['default']})"
            for a in report["axes"]  # type: ignore[union-attr]
        )
        print(f"  VARIABLE    {axes}")
    else:
        print("  static")
    print(f"  metrics     {report['metrics']}")

    ok = True
    missing = report["spec_required_missing"]
    if missing:
        ok = False
        print(f"  MISSING from the DESIGN-SPEC 1.2 set ({len(missing)}):")  # type: ignore[arg-type]
        for item in missing:  # type: ignore[union-attr]
            print(f"    - {item}")
    else:
        print("  covers every character in the DESIGN-SPEC 1.2 set")

    for label, gaps in report["missing_by_set"].items():  # type: ignore[union-attr]
        ok = False
        print(f"  MISSING from {label} ({len(gaps)}):")
        for item in gaps:
            print(f"    - {item}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    files = sorted(FONT_DIR.glob("*.woff2"))
    if not files:
        print(f"no .woff2 files in {FONT_DIR}", file=sys.stderr)
        return 1

    reports = [inspect(path) for path in files]
    complete = all(not r["spec_required_missing"] for r in reports)

    if args.json:
        print(json.dumps(reports, indent=2, ensure_ascii=False))
        return 0 if complete else 1

    ok = all([_print_report(report) for report in reports])  # noqa: C419  print them all
    print()
    print("Coverage is one of three D41 checks. The licence question (redistribution")
    print("in a public repository) and the layout-shift measurement are separate.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
