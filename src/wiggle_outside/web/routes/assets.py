"""The static mount: content-hashed assets, and the two self-hosted font faces.

Content-hashed names are immutable, so they carry a one-year cache. The fonts are not in
the repository under their licence (TC-007), so a missing face is a clean 404 and the
metric-matched fallback in tokens.css renders instead.
"""

import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from wiggle_outside.web.views import AssetRef

if TYPE_CHECKING:
    from collections.abc import Mapping

# src/wiggle_outside/web/routes/assets.py -> src/wiggle_outside/web/static
STATIC_DIR: Final = Path(__file__).resolve().parents[1] / "static"
# The Bun build writes here; the repository root holds the source fonts in development.
REPO_FONTS_DIR: Final = Path(__file__).resolve().parents[4] / "frontend" / "fonts"
MANIFEST_NAME: Final = "manifest.json"

# DESIGN-SPEC section 1.2 (D41). An exact list, so nothing else can be served as a font.
FONT_FILES: Final[frozenset[str]] = frozenset(
    {
        "CabinetGrotesk-Variable.woff2",
        "Switzer-Variable.woff2",
    }
)
WOFF2: Final = "font/woff2"


@dataclass(frozen=True, slots=True)
class StaticFile:
    path: Path
    media_type: str


def build_manifest(static_dir: Path = STATIC_DIR) -> Mapping[str, AssetRef]:
    """Map a logical asset name to the hashed file actually on disk.

    WP9b's build writes `manifest.json`; until it does, every stylesheet in the static
    directory is its own entry, so the page is styled either way.
    """
    manifest = static_dir / MANIFEST_NAME
    if manifest.is_file():
        return _from_manifest(manifest)
    return {
        found.name: AssetRef(url=f"/static/{found.name}", integrity="")
        for found in sorted(static_dir.glob("*.css"))
    }


def _from_manifest(manifest: Path) -> Mapping[str, AssetRef]:
    try:
        raw: object = json.loads(manifest.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    if not isinstance(raw, dict):
        return {}
    entries: dict[str, AssetRef] = {}
    for name, value in raw.items():
        if not isinstance(name, str):
            continue
        entries[name] = _asset_ref(value)
    return entries


def _asset_ref(value: object) -> AssetRef:
    if isinstance(value, str):
        return AssetRef(url=f"/static/{value}", integrity="")
    if isinstance(value, dict):
        url = value.get("url") or value.get("file") or ""
        integrity = value.get("integrity") or ""
        if isinstance(url, str) and isinstance(integrity, str):
            return AssetRef(
                url=url if url.startswith("/") else f"/static/{url}", integrity=integrity
            )
    return AssetRef(url="", integrity="")


def resolve_static(relative: str, static_dir: Path, fonts_dir: Path) -> StaticFile | None:
    """Find the file a `/static/...` path names, or None.

    Traversal is refused by resolving the candidate and checking it is still inside the
    root. Fonts come from the build output first and the development directory second,
    and only the two named faces are servable.
    """
    if relative.startswith("fonts/"):
        return _resolve_font(relative.removeprefix("fonts/"), static_dir, fonts_dir)
    found = _inside(static_dir, relative)
    if found is None:
        return None
    guessed, _ = mimetypes.guess_type(found.name)
    return StaticFile(path=found, media_type=guessed or "application/octet-stream")


def _resolve_font(name: str, static_dir: Path, fonts_dir: Path) -> StaticFile | None:
    if name not in FONT_FILES:
        return None
    for root in (static_dir / "fonts", fonts_dir):
        found = _inside(root, name)
        if found is not None:
            return StaticFile(path=found, media_type=WOFF2)
    return None


def _inside(root: Path, relative: str) -> Path | None:
    if not relative or relative.startswith("/") or "\\" in relative:
        return None
    try:
        candidate = (root / relative).resolve()
        base = root.resolve()
    except OSError:
        return None
    if not candidate.is_relative_to(base) or not candidate.is_file():
        return None
    return candidate
