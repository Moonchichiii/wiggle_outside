"""Render the fixture pages to files, for a visual review.

    bun run build:css
    uv run python tests/templates/render_pages.py out

Writes every DESIGN-SPEC section 12 screen into `out/` and copies the built stylesheet
next to them when `bun run build:css` has produced one. Not a gate and not application
code: it exists so the approved mocks and the real templates can be compared side by side.
"""

import shutil
import sys
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures import (
    CANDIDATES,
    CARRIED_ANSWERS,
    CATALOGUE,
    D39_ON,
    FORM_ERRORS,
    LATER,
    NOW,
    RESULT,
    RESULT_FALLBACK,
    RESULT_GENERIC,
    RESULT_NIGHT,
    RESULT_NO_MATCH,
    RESULT_NO_WEATHER,
    RESULT_NONE,
    RESULT_ONE,
    RESULT_TOO_SHORT,
    RESULT_TWO,
    SESSION,
)
from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import DeploymentMode
from wiggle_outside.web.presenters import (
    build_environment,
    present_detail,
    present_error,
    present_form,
    present_result,
    render_detail,
    render_error,
    render_form,
    render_result,
    with_assets,
)
from wiggle_outside.web.views import AssetRef, FormContext

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
BUILT_CSS: Final = REPO_ROOT / "src" / "wiggle_outside" / "web" / "static" / "app.css"
# The content-hashed manifest is WP9b's; until it exists the renderer names the one asset.
LOCAL_CSS: Final[dict[str, AssetRef]] = {"app.css": AssetRef(url="app.css", integrity="")}
MODE: Final = DeploymentMode.HOSTED_LIVE


ENV: Final = build_environment()


def _form(context: FormContext) -> str:
    return render_form(ENV, with_assets(present_form(context), LOCAL_CSS))


def pages() -> dict[str, str]:
    """Render every DESIGN-SPEC section 12 screen as HTML."""
    rendered = {
        "01-form.html": _form(FormContext(session=SESSION, mode=MODE, d39_enabled=D39_ON)),
        "01b-form-error.html": _form(
            FormContext(session=SESSION, mode=MODE, d39_enabled=D39_ON, errors=FORM_ERRORS)
        ),
        "01c-form-carried.html": _form(
            FormContext(session=SESSION, mode=MODE, d39_enabled=D39_ON, answers=CARRIED_ANSWERS)
        ),
        "01d-form-ambiguous.html": _form(
            FormContext(session=SESSION, mode=MODE, d39_enabled=D39_ON, candidates=CANDIDATES)
        ),
    }
    results = {
        "03-results.html": (RESULT, NOW),
        "03b-results-two.html": (RESULT_TWO, NOW),
        "03c-results-one.html": (RESULT_ONE, NOW),
        "03d-results-none.html": (RESULT_NONE, NOW),
        "03e-results-fallback.html": (RESULT_FALLBACK, NOW),
        "03f-results-generic.html": (RESULT_GENERIC, NOW),
        "03g-results-no-match.html": (RESULT_NO_MATCH, NOW),
        "03h-results-no-weather.html": (RESULT_NO_WEATHER, NOW),
        "03i-results-historical.html": (RESULT, LATER),
        "05-night.html": (RESULT_NIGHT, NOW),
        "05b-daylight-too-short.html": (RESULT_TOO_SHORT, NOW),
    }
    for name, (result, now) in results.items():
        page = present_result(result, CATALOGUE, now, SESSION, MODE, D39_ON)
        rendered[name] = render_result(ENV, with_assets(page, LOCAL_CSS))

    for name, idea_id, now in (
        ("04-detail-bingo.html", "i4", NOW),
        ("04b-detail-no-bingo.html", "i1", NOW),
        ("04c-detail-historical.html", "i4", LATER),
    ):
        detail = present_detail(RESULT, idea_id, CATALOGUE, now)
        rendered[name] = render_detail(ENV, with_assets(detail, LOCAL_CSS))

    for name, code in (
        ("06-error-weather.html", ErrorCode.WEATHER_UNAVAILABLE),
        ("06b-error-limit.html", ErrorCode.SERVICE_LIMIT_REACHED),
        ("06c-error-unexpected.html", ErrorCode.UNEXPECTED_FAILURE),
    ):
        error = present_error(code, "ref-9f3c21", None)
        rendered[name] = render_error(ENV, with_assets(error, LOCAL_CSS))

    invalid = present_error(
        ErrorCode.INPUT_INVALID,
        None,
        present_form(
            FormContext(session=SESSION, mode=MODE, d39_enabled=D39_ON, errors=FORM_ERRORS)
        ),
    )
    rendered["06d-error-invalid-with-form.html"] = render_error(
        ENV, with_assets(invalid, LOCAL_CSS)
    )
    return rendered


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else REPO_ROOT / "out"
    out.mkdir(parents=True, exist_ok=True)

    # A terminal entry point, so it reports to the terminal; ruff's print ban is for
    # library code.
    for name, html in pages().items():
        (out / name).write_text(html, encoding="utf-8")
        sys.stdout.write(f"wrote {out / name}\n")

    if BUILT_CSS.is_file():
        shutil.copyfile(BUILT_CSS, out / "app.css")
        sys.stdout.write(f"wrote {out / 'app.css'}\n")
    else:
        sys.stdout.write(f"no built stylesheet at {BUILT_CSS}; run: bun run build:css\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
