"""Shared test setup.

No test may make a real HTTP request (PLAN section 8). Sockets are blocked here, so a
missing respx mock fails loudly instead of reaching a provider.
"""

import socket
from collections.abc import Callable, Iterator
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


def _is_local(address: object) -> bool:
    """Report whether this address is inside the machine.

    asyncio's event loop opens a loopback socket pair for its own self-pipe, and on
    Windows that happens during test setup, so blocking every socket blocks every async
    test. An in-process ASGI client is local too. What the gate is actually for is a test
    reaching a *provider*, which is never loopback.
    """
    if not isinstance(address, tuple) or not address:
        return True  # AF_UNIX and anything else we do not recognise: not a provider.
    host = address[0]
    return not isinstance(host, str) or host in {
        "127.0.0.1",
        "::1",
        "localhost",
        "",
        "0.0.0.0",  # noqa: S104  a bind target, not a destination
    }


@pytest.fixture(autouse=True)
def _no_real_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly when a test reaches off the machine (PLAN section 8: no real HTTP)."""

    def refuse(address: object) -> NoReturn:
        msg = (
            f"a test tried to connect to {address!r}; mock the provider with respx "
            "(PLAN section 8: no real HTTP in tests)"
        )
        raise RealHTTPAttemptedError(msg)

    def gated(real: Callable[..., object], *, address_first: bool) -> Callable[..., object]:
        """Wrap a connect call so a non-local address is refused."""

        def guard(*args: object, **kwargs: object) -> object:
            address = args[0] if address_first else args[1]
            if _is_local(address):
                return real(*args, **kwargs)
            return refuse(address)

        return guard

    # monkeypatch undoes all of this at teardown, so the fixture needs none of its own.
    monkeypatch.setattr(socket.socket, "connect", gated(_REAL_CONNECT, address_first=False))
    monkeypatch.setattr(socket.socket, "connect_ex", gated(_REAL_CONNECT_EX, address_first=False))
    monkeypatch.setattr(
        socket, "create_connection", gated(_REAL_CREATE_CONNECTION, address_first=True)
    )


@pytest.fixture
def asgi_client() -> Iterator[TestClient]:
    """Talk to the app in-process. Loopback is allowed, so the guard stays on."""
    # WP7 checks the Host header on every request (BACKEND-CONTRACT section 5), and
    # TestClient's default "testserver" host is correctly refused with 400.
    with TestClient(create_app(Settings.from_env()), base_url="http://127.0.0.1:8000") as client:
        yield client


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def docs_dir() -> Path:
    return DOCS
