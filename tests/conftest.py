"""Shared test setup.

No test may make a real HTTP request (PLAN section 8). Sockets are blocked here, so a
missing respx mock fails loudly instead of reaching a provider.
"""

import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Final, NoReturn

import pytest
from fastapi.testclient import TestClient

from wiggle_outside.main import create_app
from wiggle_outside.settings import Settings

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
DOCS: Final = REPO_ROOT / "docs"

# Captured before anything is patched, so asgi_client can put them back.
_REAL_CONNECT: Final = socket.socket.connect
_REAL_CONNECT_EX: Final = socket.socket.connect_ex
_REAL_CREATE_CONNECTION: Final = socket.create_connection


class RealHTTPAttemptedError(RuntimeError):
    """A test tried to open a real socket."""


@pytest.fixture(autouse=True)
def _no_real_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def guard(*_args: object, **_kwargs: object) -> NoReturn:
        msg = (
            "a test tried to open a real socket; mock the provider with respx "
            "(PLAN section 8: no real HTTP in tests)"
        )
        raise RealHTTPAttemptedError(msg)

    # monkeypatch undoes all of this at teardown, so the fixture needs none of its own.
    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket.socket, "connect_ex", guard)
    monkeypatch.setattr(socket, "create_connection", guard)


@pytest.fixture
def asgi_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Build a TestClient that talks to the app in-process.

    The socket guard above exists to stop a test reaching a real provider. An ASGI
    client makes no network call at all, but the client library still touches
    socket.socket while setting up, so the guard is lifted for this fixture only.
    """
    monkeypatch.setattr(socket.socket, "connect", _REAL_CONNECT)
    monkeypatch.setattr(socket.socket, "connect_ex", _REAL_CONNECT_EX)
    monkeypatch.setattr(socket, "create_connection", _REAL_CREATE_CONNECTION)
    with TestClient(create_app(Settings.from_env())) as client:
        yield client


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def docs_dir() -> Path:
    return DOCS
