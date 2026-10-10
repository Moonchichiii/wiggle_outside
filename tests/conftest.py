"""Shared test setup.

No test may make a real HTTP request (PLAN section 8). Sockets are blocked here, so a
missing respx mock fails loudly instead of reaching a provider.
"""

import socket
from pathlib import Path
from typing import Final, NoReturn

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
DOCS: Final = REPO_ROOT / "docs"


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


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def docs_dir() -> Path:
    return DOCS
