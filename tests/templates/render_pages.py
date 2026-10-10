"""Render the fixture form pages to files, for a visual review.

    uv run python tests/templates/render_pages.py out

Writes out/01-form.html, out/01b-form-error.html, out/01c-form-carried.html and
out/01d-form-ambiguous.html, and copies the built stylesheet next to them when
`bun run build:css` has produced one. Not a gate and not application code: it exists so
the approved mocks and the real templates can be compared side by side.
"""

import shutil
import sys
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures import CANDIDATES, CARRIED_ANSWERS, D39_ON, FORM_ERRORS, SESSION
from wiggle_outside.core.types import DeploymentMode
from wiggle_outside.web.presenters import (
    build_environment,
    present_form,
    render_form,
    with_assets,
)
from wiggle_outside.web.views import AssetRef, FormPage

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
BUILT_CSS: Final = REPO_ROOT / "src" / "wiggle_outside" / "web" / "static" / "app.css"
# The content-hashed manifest is WP9b's; until it exists the renderer names the one asset.
LOCAL_CSS: Final[dict[str, AssetRef]] = {"app.css": AssetRef(url="app.css", integrity="")}
MODE: Final = DeploymentMode.HOSTED_LIVE


def pages() -> dict[str, FormPage]:
    """Build the DESIGN-SPEC section 12 form states as view models."""
    return {
        "01-form.html": present_form(None, {}, SESSION, None, MODE, D39_ON),
        "01b-form-error.html": present_form(None, FORM_ERRORS, SESSION, None, MODE, D39_ON),
        "01c-form-carried.html": present_form(CARRIED_ANSWERS, {}, SESSION, None, MODE, D39_ON),
        "01d-form-ambiguous.html": present_form(None, {}, SESSION, CANDIDATES, MODE, D39_ON),
    }


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else REPO_ROOT / "out"
    out.mkdir(parents=True, exist_ok=True)
    env = build_environment()

    # A terminal entry point, so it reports to the terminal; ruff's print ban is for
    # library code.
    for name, page in pages().items():
        (out / name).write_text(render_form(env, with_assets(page, LOCAL_CSS)), encoding="utf-8")
        sys.stdout.write(f"wrote {out / name}\n")

    if BUILT_CSS.is_file():
        shutil.copyfile(BUILT_CSS, out / "app.css")
        sys.stdout.write(f"wrote {out / 'app.css'}\n")
    else:
        sys.stdout.write(f"no built stylesheet at {BUILT_CSS}; run: bun run build:css\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
