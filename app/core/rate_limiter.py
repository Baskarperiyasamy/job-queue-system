"""
Rate Limiter
============
A small, dependency-free sliding-window rate limiter. Protects the
job submission endpoint from being flooded — e.g. a script accidentally
looping and submitting thousands of jobs a second.

This is intentionally simple (in-memory, per-process) rather than
pulling in Redis: fine for a single-process deployment like this one,
and the RATE_LIMIT_* settings make the behaviour easy to tune.
"""

import time
from collections import defaultdict, deque
from fastapi import Request, HTTPException

from app.core.config import settings


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def check(self, client_key: str):
        now = time.monotonic()
        hits = self._hits[client_key]

        # Drop timestamps that have fallen outside the sliding window.
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()

        if len(hits) >= self.max_requests:
            retry_after = round(self.window_seconds - (now - hits[0]), 1)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: max {self.max_requests} job "
                       f"submissions per {self.window_seconds}s. "
                       f"Try again in {retry_after}s.",
            )

        hits.append(now)


_limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_MAX_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
)


def enforce_rate_limit(request: Request):
    """FastAPI dependency: raises 429 if the caller is over the limit."""
    client_key = request.client.host if request.client else "unknown"
    _limiter.check(client_key)
