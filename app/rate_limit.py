"""Simple in-memory rate limiter for abuse protection (private alpha)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window limiter keyed by client IP + path class."""

    def __init__(self, app, *, per_minute: int = 120, auth_per_minute: int = 30, chat_per_minute: int = 40):
        super().__init__(app)
        self.per_minute = max(10, per_minute)
        self.auth_per_minute = max(5, auth_per_minute)
        self.chat_per_minute = max(5, chat_per_minute)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _limit_for(self, path: str) -> int:
        if path.startswith("/api/auth/login") or path.startswith("/api/auth/register") or path.startswith("/api/auth/mfa"):
            return self.auth_per_minute
        if path.startswith("/api/chat") or path.startswith("/api/tools/run"):
            return self.chat_per_minute
        return self.per_minute

    def _allow(self, key: str, limit: int) -> bool:
        now = time.time()
        window = 60.0
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        if path in {"/api/health", "/api/realtime"}:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        limit = self._limit_for(path)
        bucket = "auth" if "auth" in path else ("chat" if "chat" in path or "tools" in path else "api")
        key = f"{client}:{bucket}"
        if not self._allow(key, limit):
            return JSONResponse(
                {"detail": f"Rate limit exceeded ({limit}/min). Retry shortly."},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        return await call_next(request)
