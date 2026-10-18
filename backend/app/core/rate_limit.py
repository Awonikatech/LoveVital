"""In-process sliding-window rate limiter.

Suitable for a single API process. For multi-instance deployments, swap the
`_store` for Redis (see docs/DEPLOYMENT.md) — the dependency interface stays the same.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import settings
from app.core.errors import TooManyRequests

_store: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(name: str, limit: int, window_seconds: int):
    def dependency(request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return
        key = f"{name}:{client_ip(request)}"
        now = time.monotonic()
        with _lock:
            dq = _store[key]
            while dq and dq[0] <= now - window_seconds:
                dq.popleft()
            if len(dq) >= limit:
                retry = int(window_seconds - (now - dq[0])) + 1
                raise TooManyRequests(
                    f"Too many attempts. Please try again in {retry} seconds.", details={"retry_after": retry}
                )
            dq.append(now)

    return dependency


def reset_rate_limits() -> None:
    with _lock:
        _store.clear()
