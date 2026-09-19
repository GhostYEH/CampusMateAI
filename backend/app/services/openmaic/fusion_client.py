"""Minimal FastAPI client for the repository-managed OpenMAIC service."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from ...schemas.openmaic_fusion import FusionState, FusionStatus
from .capabilities import filter_capabilities
from .service_assertion import issue_service_assertion

# Health/status is not course-scoped, so the assertion carries a sentinel that is
# obviously not a CampusMate course id rather than borrowing a real one.
SERVICE_SCOPE_SENTINEL = "__service__"


def _status(
    state: FusionState,
    *,
    reason: str,
    capabilities: Optional[list[str]] = None,
) -> FusionStatus:
    """构造对外状态。

    只有 ``ready`` 才带 capability —— 依赖没就绪时声称能力可用，会让浏览器
    打开一个必然失败的功能入口。
    """
    return FusionStatus(
        enabled=state is not FusionState.DISABLED,
        available=state is FusionState.READY,
        state=state,
        capabilities=capabilities if state is FusionState.READY else [],
        reason=reason,
    )


class OpenMAICFusionClient:
    def __init__(
        self,
        *,
        base_url: str,
        secret: str,
        timeout_seconds: float = 5.0,
        transport: Optional[Any] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.secret = secret
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def status(self, *, user_id: str) -> FusionStatus:
        if not self.base_url or not self.secret:
            # 开关开着但没配地址/密钥：网关自己就是没就绪的那一环。
            return _status(FusionState.UNAVAILABLE, reason="service_unconfigured")
        try:
            assertion = issue_service_assertion(
                user_id=user_id,
                course_id=SERVICE_SCOPE_SENTINEL,
                scopes=["service:status"],
                secret=self.secret,
            )
        except Exception:
            return _status(FusionState.UNAVAILABLE, reason="assertion_unsupported")

        try:
            headers = {"X-CampusMate-Service-Assertion": assertion}
            response = await self._get("/internal/health/ready", headers=headers)
        except Exception:
            # The internal address and assertion are deliberately absent from the public status.
            return _status(FusionState.UNAVAILABLE, reason="service_unreachable")

        if response.status_code in (401, 403):
            # 受管服务在线但拒绝我们：部署问题，重试无用。
            return _status(FusionState.UNAVAILABLE, reason="assertion_rejected")
        if response.status_code == 503:
            # 服务在线、依赖未就绪 —— 这是 degraded，不是 unavailable。
            return _status(FusionState.DEGRADED, reason="dependency_unavailable")
        if response.status_code != 200:
            return _status(FusionState.UNAVAILABLE, reason="service_unreachable")

        payload = response.json() if hasattr(response, "json") else None
        if not isinstance(payload, dict):
            return _status(FusionState.UNAVAILABLE, reason="service_unreachable")
        if payload.get("status") != "ready":
            # 200 但自称未就绪：以服务自己的判断为准。
            return _status(FusionState.DEGRADED, reason="dependency_unavailable")
        raw = payload.get("capabilities")
        # Only tags this build actually understands may reach the browser.
        capabilities = filter_capabilities(raw if isinstance(raw, list) else [])
        return _status(FusionState.READY, reason="ready", capabilities=capabilities)

    async def _get(self, path: str, *, headers: dict[str, str]):
        if self.transport is not None:
            return await self.transport.get(f"{self.base_url}{path}", headers=headers, timeout=self.timeout_seconds)
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=False) as client:
            return await client.get(f"{self.base_url}{path}", headers=headers)


__all__ = ["OpenMAICFusionClient", "SERVICE_SCOPE_SENTINEL"]
