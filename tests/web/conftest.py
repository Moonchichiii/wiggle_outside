"""Fixtures for the WP7 route tests. The builders live in `support.py`."""

from collections.abc import Iterator

import pytest
from web_support import Harness, build_harness

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.preview_planner import PreviewPlanner


@pytest.fixture
def harness() -> Iterator[Harness]:
    """Build the default harness: a three-idea preview result."""
    yield from build_harness(PreviewPlanner())


@pytest.fixture
def blocked() -> Iterator[Harness]:
    """Build a harness whose result is evaluated but blocked (200 with a notice)."""
    yield from build_harness(PreviewPlanner(outcome=ErrorCode.DAYLIGHT_NIGHT))
