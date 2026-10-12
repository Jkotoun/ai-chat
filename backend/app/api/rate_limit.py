import time
from collections.abc import Callable

# Above this many tracked clients, expired windows are dropped.
MAX_TRACKED_KEYS = 10_000


class RateLimiter:
    """Allows `limit` hits per key in each fixed window; state lives in process memory."""

    def __init__(
        self, limit: int, window_seconds: float = 60, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._windows: dict[str, tuple[float, int]] = {}  # key -> (window start, hits)

    def hit(self, key: str) -> bool:
        """Count a hit for `key`; False if it is over the limit."""
        now = self._clock()
        start, hits = self._windows.get(key, (now, 0))
        if now - start >= self.window_seconds:
            start, hits = now, 0
        if hits >= self.limit:
            return False
        if len(self._windows) >= MAX_TRACKED_KEYS:
            self._drop_expired(now)
        self._windows[key] = (start, hits + 1)
        return True

    def _drop_expired(self, now: float) -> None:
        self._windows = {
            key: window
            for key, window in self._windows.items()
            if now - window[0] < self.window_seconds
        }
