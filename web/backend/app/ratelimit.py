"""Simple in-memory fixed-window rate limiter — no external deps."""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

_CLEANUP_INTERVAL = 300  # seconds between expired-entry sweeps


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: int) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._calls: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()

    def _key(self, request: Request) -> str:
        # Trust request.client.host — set to the real client IP by
        # ProxyHeadersMiddleware (which only trusts 127.0.0.1/::1).
        return request.client.host if request.client else "unknown"

    def _cleanup(self, now: float) -> None:
        """Evict expired buckets to prevent unbounded memory growth."""
        expired = [k for k, calls in self._calls.items() if not any(now - t < self.window for t in calls)]
        for k in expired:
            del self._calls[k]
        self._last_cleanup = now

    def check(self, request: Request) -> None:
        if os.environ.get("DISABLE_RATE_LIMIT") == "1":
            return
        key = self._key(request)
        now = time.monotonic()
        with self._lock:
            if now - self._last_cleanup > _CLEANUP_INTERVAL:
                self._cleanup(now)
            calls = [t for t in self._calls[key] if now - t < self.window]
            if len(calls) >= self.max_calls:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Zu viele Anfragen. Bitte warte einen Moment.",
                    headers={"Retry-After": str(self.window)},
                )
            calls.append(now)
            self._calls[key] = calls


login_limiter = RateLimiter(max_calls=10, window_seconds=60)
register_limiter = RateLimiter(max_calls=5, window_seconds=300)
nwz_creds_limiter = RateLimiter(max_calls=5, window_seconds=300)
link_limiter = RateLimiter(max_calls=5, window_seconds=300)
forgot_password_limiter = RateLimiter(max_calls=5, window_seconds=900)
verify_email_limiter = RateLimiter(max_calls=5, window_seconds=900)
