"""The stage counter names storage reports (ARCHITECTURE section 14).

Counts only: no answers, no coordinates, no place queries. The stage is the cache
namespace, so one name per line of the request budget.
"""

from typing import Final

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
