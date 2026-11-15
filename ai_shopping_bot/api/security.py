"""API key check and a fixed-window per-client rate limit."""

from __future__ import annotations

import secrets
import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from ai_shopping_bot.settings import Settings


class RateLimiter:
    def __init__(self, per_minute: int):
        self._limit = per_minute
        self._hits: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
        self._lock = threading.Lock()

    def allow(self, client: str) -> bool:
        window = int(time.time() // 60)
        with self._lock:
            w, n = self._hits[client]
            if w != window:
                w, n = window, 0
            n += 1
            self._hits[client] = (w, n)
            return n <= self._limit


def make_guard(settings: Settings, limiter: RateLimiter):
    expected = settings.api_key.get_secret_value() if settings.api_key else None

    def guard(request: Request) -> None:
        if expected is not None:
            given = request.headers.get("x-api-key", "")
            if not secrets.compare_digest(given, expected):
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing API key")
        client = request.headers.get("x-api-key") or (
            request.client.host if request.client else "?"
        )
        if not limiter.allow(client):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limit exceeded")

    return guard
