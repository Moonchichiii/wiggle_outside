"""The stage counter names storage reports (ARCHITECTURE section 14), and a logger for them.

Counts only: no answers, no coordinates, no place queries. The stage is the cache
namespace, so one name per line of the request budget.
"""

import logging
from collections import Counter
from typing import Final

log = logging.getLogger("wiggle_outside.counters")

CACHE_HIT: Final = "cache_hit"
CACHE_MISS: Final = "cache_miss"
CACHE_STORED: Final = "cache_stored"
# The cache was unavailable, full or handed an oversized entry: the request bypassed it.
CACHE_BYPASSED: Final = "cache_bypassed"
CACHE_UNREADABLE: Final = "cache_unreadable"
CACHE_UNWRITABLE: Final = "cache_unwritable"
# A weather entry that no longer covers the whole outing window (ARCHITECTURE section 15).
CACHE_NOT_COVERING: Final = "cache_not_covering"
UPSTREAM_CALL: Final = "upstream_call"
UPSTREAM_RETRY: Final = "upstream_retry"
DUPLICATE_PREVENTED: Final = "duplicate_prevented"
GATE_BLOCKED: Final = "gate_blocked"
PACE_EXCEEDED: Final = "pace_exceeded"


class LogCounters:
    """Counters (CONTRACTS section 4.1): kept in memory and written to the operator log."""

    def __init__(self) -> None:
        self._counts: Counter[tuple[str, str]] = Counter()

    def incr(self, name: str, stage: str) -> None:
        self._counts[(name, stage)] += 1
        log.info("%s %s=%d", stage, name, self._counts[(name, stage)])

    def count(self, name: str, stage: str | None = None) -> int:
        return sum(
            value
            for (seen, where), value in self._counts.items()
            if seen == name and (stage is None or where == stage)
        )
