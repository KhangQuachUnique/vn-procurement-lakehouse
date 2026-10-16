from collections.abc import Callable, Generator
from contextlib import contextmanager
from math import isfinite
from threading import BoundedSemaphore, Lock
from time import monotonic, sleep


class RequestBudget:
    """Shared rate limiter and concurrency coordinator for HTTP source clients."""

    def __init__(
        self,
        max_inflight: int = 3,
        *,
        min_interval: float = 0.05,
        clock: Callable[[], float] = monotonic,
        wait: Callable[[float], None] = sleep,
    ) -> None:
        if max_inflight < 1:
            raise ValueError("max_inflight must be positive")
        if not isfinite(min_interval) or min_interval < 0:
            raise ValueError("min_interval must be finite and non-negative")

        self._slots = BoundedSemaphore(max_inflight)
        self._lock = Lock()
        self._interval = min_interval
        self._clock = clock
        self._wait = wait
        self._pace_lock = Lock()
        self._next_start = 0.0
        self._cooldown_until = 0.0

    def defer(self, seconds: float) -> None:
        """Pause all pending requests during a cooldown period (e.g. after HTTP 429)."""
        if seconds <= 0:
            return
        with self._lock:
            self._cooldown_until = max(self._cooldown_until, self._clock() + seconds)

    def _pace(self) -> None:
        """Wait until pacing interval and cooldown periods expire."""
        with self._pace_lock:
            while True:
                with self._lock:
                    delay = max(self._next_start, self._cooldown_until) - self._clock()
                if delay <= 0:
                    self._next_start = self._clock() + self._interval
                    return
                self._wait(min(delay, 0.25))

    @contextmanager
    def request(self) -> Generator[None, None, None]:
        """Context manager acquiring an in-flight slot and respecting rate pacing."""
        with self._slots:
            self._pace()
            yield
