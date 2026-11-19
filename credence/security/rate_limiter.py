"""Sliding window in-memory rate limiter for heavy verification endpoints."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Dict, List

from fastapi import HTTPException, Request, status

DEFAULT_RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))  # 60 requests/minute per client IP


class SlidingWindowRateLimiter:
    """Thread-safe rate limiter tracking client request timestamps."""

    def __init__(self, requests_per_minute: int = DEFAULT_RATE_LIMIT):
        self.rpm = requests_per_minute
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def check_rate_limit(self, client_ip: str) -> None:
        """Enforce request rate limit for client IP."""
        if self.rpm <= 0:
            return  # Rate limiting disabled

        now = time.time()
        window_start = now - 60.0

        # Filter out requests older than 1 minute
        history = [t for t in self.requests[client_ip] if t > window_start]
        if len(history) >= self.rpm:
            retry_after = int(60.0 - (now - history[0]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.rpm} verification requests per minute. Try again in {max(1, retry_after)}s.",
                headers={"Retry-After": str(max(1, retry_after))},
            )

        history.append(now)
        self.requests[client_ip] = history


rate_limiter = SlidingWindowRateLimiter()


async def rate_limit_dependency(request: Request) -> None:
    """FastAPI dependency for endpoints requiring rate limiting."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    rate_limiter.check_rate_limit(client_ip)
