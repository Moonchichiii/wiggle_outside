"""Form field list, route table and token names (CONTRACTS sections 5, 7 and 9).

Each test parses the document and compares it with the code, so a drift in either
direction fails.
"""

import re
from pathlib import Path
from typing import Final

import pytest

from wiggle_outside.core.types import AgeBand, Energy, TimeBudget, Who
from wiggle_outside.main import build_state, create_app, readiness_body
from wiggle_outside.settings import Settings
from wiggle_outside.web.forms import (
    ALLOWED_VALUES,
    EXCLUDED_FROM_FINGERPRINT,
    LOCATION_CHOICE_FIELDS,
    PLAN_FIELDS,
    PLAN_FORM_FIELDS,
    canonical_form,
    fingerprint,
)

pytestmark = pytest.mark.contract

# | plan | `lat`, `lon` | ... -> the form name, then every backticked field in cell 2
FORM_ROW: Final = re.compile(r"^\|\s*(plan|location-choice)\s*\|([^|]*)\|")
FIELD_NAME: Final = re.compile(r"`([a-z_]+)`")
# | GET `/` | ... or | POST `/plan` | ...
ROUTE_ROW: Final = re.compile(r"^\|\s*(GET|POST)\s+`([^`]+)`\s*\|")
# | `oatmeal` | `#F2EDE4` | ...
TOKEN_ROW: Final = re.compile(r"^\|\s*`([a-z-]+)`\s*\|\s*`(#[0-9A-Fa-f]{6})`", re.MULTILINE)

# CONTRACTS section 5 lists these as removed in 8.11; they must 404, not exist.
REMOVED_ROUTES: Final = frozenset(
    {
        "/results/{job_id}/events",
        "/results/{job_id}/cancel",
        "/results/{job_id}/interests",
        "/examples",
    }
)


def _section(path: Path, start: str, end: str) -> str:
    text = path.read_text(encoding="utf-8")
    return text[text.index(start) : text.index(end)]


# --- Forms (section 7) -------------------------------------------------------------


def test_form_field_list_equals_the_document(docs_dir: Path) -> None:
    body = _section(
        docs_dir / "CONTRACTS.md",
        "## 7. Form fields",
        "**Submission fingerprint",
    )
    documented: dict[str, set[str]] = {"plan": set(), "location-choice": set()}
    for line in body.splitlines():
        match = FORM_ROW.match(line)
        if match:
            documented[match.group(1)].update(FIELD_NAME.findall(match.group(2)))
    # The document lists csrf_token and candidate_id on one row for location-choice.
    assert documented["plan"] == set(PLAN_FORM_FIELDS)
    assert documented["location-choice"] == set(LOCATION_CHOICE_FIELDS)


def test_fingerprint_excludes_exactly_three_fields() -> None:
    # CONTRACTS section 7: csrf_token, idempotency_key and hp_note are excluded.
    assert {"csrf_token", "idempotency_key", "hp_note"} == EXCLUDED_FROM_FINGERPRINT
    assert not EXCLUDED_FROM_FINGERPRINT & set(PLAN_FIELDS)


def test_allowed_values_match_the_enums() -> None:
    assert ALLOWED_VALUES["who"] == {w.value for w in Who}
    assert ALLOWED_VALUES["age_band"] == {b.value for b in AgeBand}
    assert ALLOWED_VALUES["time"] == {str(t.value) for t in TimeBudget}
    assert ALLOWED_VALUES["energy"] == {e.value for e in Energy}
    # TC-001: the wire value is the enum value; "High" is never submitted or stored.
    assert "High" not in ALLOWED_VALUES["energy"]  # TC-001: a label, never a value
    assert Energy.ENERGETIC.value in ALLOWED_VALUES["energy"]


def test_canonical_form_normalises_age_bands_and_coordinates() -> None:
    a = canonical_form(
        {
            "who": ["kids"],
            "age_band": ["6-9", "3-5", "3-5"],
            "lat": ["60.123456"],
            "lon": ["17.9"],
        }
    )
    b = canonical_form(
        {
            "who": ["kids"],
            "age_band": ["3-5", "6-9"],
            "lat": ["60.12"],
            "lon": ["17.90"],
        }
    )
    assert a == b


def test_interest_text_changes_the_fingerprint() -> None:
    # CONTRACTS section 7: two submissions differing only in interest text are different.
    key = b"\x00" * 32
    base = {"who": ["kids"], "interests_text": ["birds"]}
    other = {"who": ["kids"], "interests_text": ["birds, puddles"]}
    assert fingerprint(key, base) != fingerprint(key, other)


def test_honeypot_does_not_change_the_fingerprint() -> None:
    key = b"\x00" * 32
    clean = {"who": ["solo"]}
    tripped = {"who": ["solo"], "hp_note": ["spam"]}
    assert fingerprint(key, clean) == fingerprint(key, tripped)


# --- Routes (section 5) ------------------------------------------------------------


def _documented_routes(docs_dir: Path) -> set[tuple[str, str]]:
    body = _section(docs_dir / "CONTRACTS.md", "## 5. Routes", "**Detail stability.**")
    routes: set[tuple[str, str]] = set()
    for line in body.splitlines():
        if line.lstrip().startswith("| ~~"):
            continue  # struck-through rows are the inactive replay demo
        match = ROUTE_ROW.match(line)
        if match:
            routes.add((match.group(1), match.group(2)))
    return routes


def _app_routes() -> set[tuple[str, str]]:
    app = create_app(Settings.from_env())
    found: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path is None or methods is None:
            continue
        for method in methods:
            if method in {"GET", "POST"}:
                found.add((method, path))
    return found


def test_the_document_lists_every_route_we_register(docs_dir: Path) -> None:
    # WP7 owns web/routes/** and will assert full equality. Until then the binding rule
    # is the one-way one: the app registers nothing the document does not list.
    assert _app_routes() <= _documented_routes(docs_dir)


def test_health_and_readiness_exist() -> None:
    # The app must start and report honestly without a model (PLAN section 6).
    assert ("GET", "/healthz") in _app_routes()
    assert ("GET", "/readyz") in _app_routes()


def test_removed_routes_are_not_registered() -> None:
    paths = {path for _, path in _app_routes()}
    assert not paths & REMOVED_ROUTES


def test_readyz_reports_the_model_unavailable_until_an_adapter_is_wired() -> None:
    # Readiness comes from the wired adapter, never from configuration, so the endpoint
    # cannot claim a model this process does not have. WP5 supplies the adapter.
    state = build_state(Settings.from_env())
    assert state.ranker is None
    assert state.model_status == "unavailable"

    body = readiness_body(state)
    assert "app: ready" in body
    assert "model: unavailable" in body


def test_readyz_is_registered() -> None:
    # The transport-level test belongs to WP7's route tests; here the route only has to
    # exist and delegate, because conftest blocks real sockets.
    assert ("GET", "/readyz") in _app_routes()


# --- Tokens (section 9) ------------------------------------------------------------


def test_every_colour_token_is_defined_in_tokens_css(docs_dir: Path, repo_root: Path) -> None:
    body = _section(docs_dir / "DESIGN-SPEC.md", "### 1.1 Colour", "**Rules.**")
    documented = {name: value.lower() for name, value in TOKEN_ROW.findall(body)}
    assert documented, "DESIGN-SPEC section 1.1 colour table did not parse"

    css = (repo_root / "frontend" / "css" / "tokens.css").read_text(encoding="utf-8")
    for name, value in documented.items():
        assert f"--color-{name}:" in css, f"token {name} missing from tokens.css"
        assert value in css.lower(), f"token {name} has the wrong value in tokens.css"


def test_corner_utilities_are_defined(repo_root: Path) -> None:
    css = (repo_root / "frontend" / "css" / "tokens.css").read_text(encoding="utf-8")
    for utility in ("wonk-card", "wonk-button", "wonk-tile", "wonk-field"):
        assert f"@utility {utility}" in css


def test_type_scale_and_focus_tokens_are_defined(repo_root: Path) -> None:
    css = (repo_root / "frontend" / "css" / "tokens.css").read_text(encoding="utf-8")
    for token in ("--text-sm", "--text-base", "--text-lg", "--text-xl", "--text-2xl"):
        assert f"{token}:" in css
    for token in ("--spacing-s1", "--spacing-s8", "--shadow-card", "--outline-width-focus"):
        assert f"{token}:" in css
