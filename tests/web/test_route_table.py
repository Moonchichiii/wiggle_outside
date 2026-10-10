"""The registered routes equal the CONTRACTS section 5 table, exactly.

Both directions: nothing the document lists is missing, and nothing is registered that
the document does not list. The routes removed in 8.11 must answer 404, not exist.
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

if TYPE_CHECKING:
    from web_support import Harness

pytestmark = pytest.mark.contract

ROUTE_ROW: Final = re.compile(r"^\|\s*(GET|POST)\s+`([^`]+)`\s*\|")

# CONTRACTS section 5, "Removed in 8.11" plus the inactive replay demo.
REMOVED: Final = (
    ("GET", "/results/job-1/events"),
    ("POST", "/results/job-1/cancel"),
    ("POST", "/results/job-1/interests"),
    ("GET", "/examples"),
    ("GET", "/examples/1"),
)


def _documented(docs_dir: Path) -> set[tuple[str, str]]:
    text = (docs_dir / "CONTRACTS.md").read_text(encoding="utf-8")
    body = text[text.index("## 5. Routes") : text.index("**Detail stability.**")]
    routes: set[tuple[str, str]] = set()
    for line in body.splitlines():
        if line.lstrip().startswith("| ~~"):
            continue  # struck through: the inactive replay demo (D24 superseded by D48)
        match = ROUTE_ROW.match(line)
        if match:
            routes.add((match.group(1), match.group(2)))
    return routes


def _registered(harness: Harness) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for route in harness.router.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not isinstance(path, str) or not isinstance(methods, set):
            continue
        # The document writes `/static/{hashed}`; Starlette needs the path converter.
        for method in methods:
            if method in {"GET", "POST"}:
                found.add((method, path.replace(":path}", "}")))
    return found


def test_the_router_registers_exactly_the_documented_routes(
    harness: Harness, docs_dir: Path
) -> None:
    documented = _documented(docs_dir)

    assert documented, "CONTRACTS section 5 route table did not parse"
    assert _registered(harness) == documented


@pytest.mark.parametrize(("method", "path"), REMOVED)
def test_the_removed_routes_are_not_registered(harness: Harness, method: str, path: str) -> None:
    answered = harness.client.request(method, path, follow_redirects=False)

    assert answered.status_code == 404


def test_no_route_reads_a_query_parameter(harness: Harness) -> None:
    """None of our answers depends on the query string.

    FastAPI resolves a handler's annotations when the route is registered. A `Request`
    it cannot resolve becomes a required query parameter, and every page then answers
    422 instead of its own status, so this guards the whole route table at once.
    """
    for route in harness.router.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        assert dependant.query_params == [], f"{route.path} reads the query string"


def test_healthz_is_ok_and_readyz_reports_the_model_separately(harness: Harness) -> None:
    assert harness.client.get("/healthz").text == "ok"

    body = harness.client.get("/readyz").text

    assert "app: ready" in body
    assert "model: unavailable" in body
