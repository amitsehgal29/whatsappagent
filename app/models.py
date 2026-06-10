"""
Per-phone rate limiter.

Protects against abuse (rapid-fire messages burning API credits) and enforces
fair-usage limits.  Uses a simple sliding-window counter keyed by phone number.

Production deployments should replace this with a Redis-backed implementation
that works across multiple workers.
"""

from __future__ import annotations

import time
from collections import defaultdict


class RateLimiter:
    """In-memory sliding-window rate limiter.

    Parameters
    ----------
    max_requests : int
        Maximum requests allowed in the window.
    window_seconds : float
        Sliding window duration in seconds.
    """

    def __init__(self, max_requests: int = 5, window_seconds: float = 10.0) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, phone: str) -> bool:
        """Return True if *phone* is within their rate limit."""
        now = time.monotonic()
        bucket = self._buckets[phone]

        # Expire old timestamps outside the window.
        cutoff = now - self._window
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)

        if len(bucket) >= self._max:
            return False

        bucket.append(now)

        # Clean up empty buckets periodically to prevent unbounded growth.
        # (Same memory-leak pattern as the old ConversationMemory — fixed here.)
        if not bucket:
            del self._buckets[phone]

        return True
