import time
from typing import Dict, List, Optional
from fastapi import HTTPException, Request, status
from app.config import get_settings


# In-memory storage for sliding-window rate limiting: {key: [timestamp1, timestamp2, ...]}
_rate_limit_records: Dict[str, List[float]] = {}


def get_client_ip(request: Request) -> str:
    """Safely extract client IP from X-Forwarded-For or direct socket connection."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the leftmost untrusted client IP
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def check_rate_limit(
    request: Request,
    limit: int = 15,
    window_seconds: int = 60,
    key_prefix: str = "login",
) -> None:
    """
    Sliding-window rate limiter for abuse-sensitive endpoints.
    Throws HTTP 429 Too Many Requests if the limit is exceeded within the window.
    """
    settings = get_settings()
    if not settings.RATE_LIMITING_ENABLED:
        return

    # In automated test runs, bypass rate limiting unless explicitly testing it via header
    if settings.ENVIRONMENT == "testing" and request.headers.get("X-Enforce-Rate-Limit") != "true":
        return

    ip = get_client_ip(request)
    key = f"{key_prefix}:{ip}"
    now = time.time()
    window_start = now - window_seconds

    # Retrieve and filter records within the current window
    timestamps = _rate_limit_records.get(key, [])
    active_timestamps = [ts for ts in timestamps if ts > window_start]

    if len(active_timestamps) >= limit:
        # Calculate retry-after in seconds based on the oldest record in the window
        oldest = active_timestamps[0]
        retry_after = max(1, int(oldest + window_seconds - now) + 1)
        _rate_limit_records[key] = active_timestamps
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Please wait {retry_after} seconds before trying again.",
            headers={"Retry-After": str(retry_after)},
        )

    active_timestamps.append(now)
    _rate_limit_records[key] = active_timestamps


def reset_rate_limiter() -> None:
    """Utility to clear rate limit records for test isolation."""
    global _rate_limit_records
    _rate_limit_records.clear()
