import time
from collections import defaultdict
from typing import Dict, List


class RateLimiter:
    """Sliding window rate limiter per user or guild."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[int, List[float]] = defaultdict(list)

    def is_rate_limited(self, entity_id: int) -> bool:
        """
        Check if entity (user_id or guild_id) has exceeded rate limit.
        If not limited, registers the current request timestamp.
        """
        now = time.time()
        cutoff = now - self.window_seconds

        # Clean entries outside current window
        self.requests[entity_id] = [ts for ts in self.requests[entity_id] if ts > cutoff]

        if len(self.requests[entity_id]) >= self.max_requests:
            return True

        self.requests[entity_id].append(now)
        return False

    def get_reset_time(self, entity_id: int) -> int:
        """Get seconds until oldest request expires allowing a new request."""
        if not self.requests[entity_id]:
            return 0

        now = time.time()
        cutoff = now - self.window_seconds
        valid_requests = [ts for ts in self.requests[entity_id] if ts > cutoff]

        if len(valid_requests) < self.max_requests:
            return 0

        oldest_request = min(valid_requests)
        reset_time = int(oldest_request + self.window_seconds - now)
        return max(1, reset_time)

    def clear(self, entity_id: int) -> None:
        """Clear rate limit history for a specific entity."""
        if entity_id in self.requests:
            del self.requests[entity_id]
