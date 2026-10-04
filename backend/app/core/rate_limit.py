"""Bounded, thread-safe request throttling for a single backend process."""
from __future__ import annotations

import math
import time
from collections import OrderedDict, deque
from threading import RLock

from fastapi import Request

from .exceptions import AppException


class RateLimited(AppException):
    code = "RATE_LIMITED"
    http_status = 429
    message = "请求过于频繁，请稍后重试。"

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(details={"retry_after_seconds": retry_after})


class RequestRateLimiter:
    def __init__(self, *, max_keys: int = 4096) -> None:
        self._max_keys = max_keys
        self._requests: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self._lock = RLock()

    def check(self, scope: str, identity: str, *, limit: int, window: float = 60) -> None:
        now = time.monotonic()
        key = (scope, identity)
        with self._lock:
            requests = self._requests.get(key)
            if requests is None:
                if len(self._requests) >= self._max_keys:
                    self._requests.popitem(last=False)
                requests = self._requests[key] = deque()
            self._requests.move_to_end(key)
            while requests and now - requests[0] >= window:
                requests.popleft()
            if len(requests) >= limit:
                raise RateLimited(max(1, math.ceil(window - (now - requests[0]))))
            requests.append(now)


def check_request_rate(request: Request, scope: str, *, limit: int) -> None:
    # Forwarded headers are user input unless validated by the trusted proxy
    # configuration; use the ASGI peer address supplied by the server.
    identity = request.client.host if request.client else "unknown"
    request.app.state.request_rate_limiter.check(scope, identity, limit=limit)


def request_rate_limit(scope: str, *, limit: int):
    def dependency(request: Request) -> None:
        check_request_rate(request, scope, limit=limit)

    return dependency
