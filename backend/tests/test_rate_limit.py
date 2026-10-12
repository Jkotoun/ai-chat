import pytest

from app.api import rate_limit
from app.api.rate_limit import RateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_allows_limit_hits_per_window() -> None:
    clock = Clock()
    limiter = RateLimiter(limit=2, window_seconds=60, clock=clock)

    assert [limiter.hit("a") for _ in range(3)] == [True, True, False]
    clock.now = 59
    assert not limiter.hit("a")
    clock.now = 60
    assert limiter.hit("a")


def test_counts_keys_separately() -> None:
    limiter = RateLimiter(limit=1)

    assert limiter.hit("a")
    assert limiter.hit("b")
    assert not limiter.hit("a")


def test_drops_expired_windows_when_tracking_too_many(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit, "MAX_TRACKED_KEYS", 2)
    clock = Clock()
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    limiter.hit("a")
    limiter.hit("b")

    clock.now = 60
    limiter.hit("c")

    assert limiter._windows.keys() == {"c"}
