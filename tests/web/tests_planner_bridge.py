"""Rigs for the real-planner route test, built from the planner test fakes.

`tests/planner` is on the import path only while its tests are collected, so this module
adds it explicitly rather than relying on collection order. The web layer keeps real
time (session expiry, candidate TTL), so these rigs run their fake clock on real time
too, with a weather day built around it.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

PLANNER_TESTS = Path(__file__).resolve().parent.parent / "planner"
if str(PLANNER_TESTS) not in sys.path:
    sys.path.insert(0, str(PLANNER_TESTS))

from planner_support import (  # noqa: E402
    BUDGETS,
    HITS,
    FakeGeocoder,
    FakeWeather,
    Rig,
    day_window_around,
    rig,
)

from wiggle_outside.core.result import Ok  # noqa: E402
from wiggle_outside.core.types import GeocodeHits  # noqa: E402

if TYPE_CHECKING:
    from wiggle_outside.planner.plan_outing import Budgets


def budgets() -> Budgets:
    return BUDGETS


def _on_real_time(built: Rig) -> Rig:
    now = datetime.now(UTC)
    built.clock.wall = now
    built.weather = FakeWeather(outcome=Ok(day_window_around(now)))
    return built


def plain_rig() -> Rig:
    return _on_real_time(rig())


def ambiguous_rig() -> Rig:
    return _on_real_time(rig(geocoder=FakeGeocoder(outcome=Ok(GeocodeHits(hits=HITS)))))
