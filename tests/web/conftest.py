"""Fixtures for the WP7 route tests. The builders live in `support.py`."""

from collections.abc import Iterator

import pytest
from support import Harness, build_harness

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.preview_planner import PreviewPlanner


@pytest.fixture
def harness() -> Iterator[Harness]:
    """The default harness: a three-idea preview result."""
    yield from build_harness(PreviewPlanner())


@pytest.fixture
def blocked() -> Iterator[Harness]:
    """A planner that returns an evaluated-but-blocked result (200 with a notice)."""
    yield from build_harness(PreviewPlanner(outcome=ErrorCode.DAYLIGHT_NIGHT))
