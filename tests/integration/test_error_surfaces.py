"""Paths and methods the router does not own still answer with the app's own headers.

Before this, an unknown path answered FastAPI's `{"detail":"Not Found"}` as JSON with no
CSP, and `HEAD /` answered 405 the same way. Now every such response is the uniform empty
answer with the page headers, and HEAD is allowed wherever GET is.
"""

from typing import TYPE_CHECKING, Final

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

HTTP_OK: Final = 200
HTTP_NOT_FOUND: Final = 404
HTTP_METHOD_NOT_ALLOWED: Final = 405
REQUIRED_HEADERS: Final = (
    "content-security-policy",
    "x-content-type-options",
    "referrer-policy",
    "cache-control",
)


def test_an_unknown_path_is_the_uniform_404_with_the_page_headers(
    asgi_client: TestClient,
) -> None:
    answered = asgi_client.get("/nope")

    assert answered.status_code == HTTP_NOT_FOUND
    assert answered.content == b""
    assert "application/json" not in answered.headers.get("content-type", "")
    for name in REQUIRED_HEADERS:
        assert name in answered.headers, name
    assert answered.headers["cache-control"] == "no-store, private"


def test_a_wrong_method_is_a_405_with_the_page_headers_and_allow(
    asgi_client: TestClient,
) -> None:
    answered = asgi_client.post("/healthz")

    assert answered.status_code == HTTP_METHOD_NOT_ALLOWED
    assert answered.content == b""
    assert "GET" in answered.headers["allow"]
    for name in REQUIRED_HEADERS:
        assert name in answered.headers, name


@pytest.mark.parametrize("path", ["/", "/healthz", "/readyz", "/favicon.ico"])
def test_head_is_allowed_wherever_get_is(asgi_client: TestClient, path: str) -> None:
    answered = asgi_client.head(path)

    assert answered.status_code in {HTTP_OK, HTTP_NOT_FOUND}  # the icon needs a build
    assert answered.status_code != HTTP_METHOD_NOT_ALLOWED
    assert "content-security-policy" in answered.headers


def test_head_on_an_unknown_result_is_the_uniform_404(asgi_client: TestClient) -> None:
    answered = asgi_client.head("/results/nope")

    assert answered.status_code == HTTP_NOT_FOUND
    assert "content-security-policy" in answered.headers
