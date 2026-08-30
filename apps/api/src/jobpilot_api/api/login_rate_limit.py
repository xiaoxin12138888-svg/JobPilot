from __future__ import annotations

import math
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from threading import Lock

WEB_LOGIN_RATE_LIMIT = 10
WEB_LOGIN_RATE_WINDOW_SECONDS = 60
WEB_LOGIN_RATE_MAX_CLIENTS = 10_000


class WebLoginRateLimiter:
    """A bounded process-local rolling-window baseline for login starts."""

    def __init__(
        self,
        *,
        limit: int = WEB_LOGIN_RATE_LIMIT,
        window_seconds: int = WEB_LOGIN_RATE_WINDOW_SECONDS,
        max_clients: int = WEB_LOGIN_RATE_MAX_CLIENTS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if limit <= 0 or window_seconds <= 0 or max_clients <= 0:
            raise ValueError("rate limit settings must be positive")
        self._limit = limit
        self._window_seconds = window_seconds
        self._max_clients = max_clients
        self._clock = clock
        self._attempts: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def check(self, client_key: str) -> int | None:
        now = self._clock()
        cutoff = now - self._window_seconds
        with self._lock:
            attempts = self._attempts.pop(client_key, deque())
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()

            if len(attempts) >= self._limit:
                self._attempts[client_key] = attempts
                return max(1, math.ceil(attempts[0] + self._window_seconds - now))

            attempts.append(now)
            self._attempts[client_key] = attempts
            while len(self._attempts) > self._max_clients:
                self._attempts.popitem(last=False)
        return None
