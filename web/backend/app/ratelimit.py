"""Simple in-memory fixed-window rate limiter — no external deps."""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: int) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._calls: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _key(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def check(self, request: Request) -> None:
        # Allow tests to bypass rate limiting
        if os.environ.get("DISABLE_RATE_LIMIT") == "1":
            return
        key = self._key(request)
        now = time.monotonic()
        with self._lock:
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
