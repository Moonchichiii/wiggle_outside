"""The app's own log lines reach stdout in production (TC-011).

uvicorn configures only its own loggers; `configure_logging` gives the root logger one
stdout handler at INFO, once, and leaves an existing handler alone. Exercised on a
logger of its own, because pytest keeps its capture handlers on the real root.
"""

import logging
import sys

import pytest

from wiggle_outside.main import LOG_FORMAT, QUIET_LOGGERS, configure_logging


@pytest.fixture
def bare_root() -> logging.Logger:
    """Build a root-like logger with no handler, as uvicorn leaves the real one."""
    # Not the registered root: pytest keeps its capture handlers on that one.
    return logging.Logger("wo-test-root")  # noqa: LOG001


def test_one_stdout_handler_at_info_is_added_once(bare_root: logging.Logger) -> None:
    assert configure_logging(root=bare_root) is True
    assert configure_logging(root=bare_root) is False

    [handler] = bare_root.handlers
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stdout
    assert bare_root.level == logging.INFO
    assert handler.formatter is not None
    assert handler.formatter._fmt == LOG_FORMAT  # noqa: SLF001  the one way to read it back


def test_an_existing_root_handler_is_left_alone(bare_root: logging.Logger) -> None:
    existing = logging.NullHandler()
    bare_root.addHandler(existing)

    assert configure_logging(root=bare_root) is False
    assert bare_root.handlers == [existing]


def test_an_info_line_reaches_stdout_in_the_operator_format(
    bare_root: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(root=bare_root)

    bare_root.info(
        "model served by %s (%s): prompt=%d", "deepinfra", "google/gemma-4-26b-a4b-it", 7
    )

    out = capsys.readouterr().out
    assert "INFO wo-test-root: model served by deepinfra (google/gemma-4-26b-a4b-it)" in out
    assert out.startswith("20")  # the timestamp comes first


def test_the_real_root_is_configured_by_create_app() -> None:
    # Under pytest the root already has capture handlers, so this must be a no-op there
    # and must never add a second handler.
    before = list(logging.getLogger().handlers)
    assert configure_logging() is False
    assert logging.getLogger().handlers == before


def test_request_url_loggers_are_quiet_whoever_owns_the_root(bare_root: logging.Logger) -> None:
    # httpx logs "HTTP Request: GET https://...?latitude=..&longitude=..&q=town" at INFO.
    # That line must never reach a log, so those loggers stay at WARNING even when the
    # root already has a handler and nothing else is configured.
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.NOTSET)
    bare_root.addHandler(logging.NullHandler())

    assert configure_logging(root=bare_root) is False
    for name in QUIET_LOGGERS:
        assert logging.getLogger(name).level == logging.WARNING
    assert "httpx" in QUIET_LOGGERS
