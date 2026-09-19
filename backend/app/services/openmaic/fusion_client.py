"""Minimal FastAPI client for the repository-managed OpenMAIC service."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from ...schemas.openmaic_fusion import FusionStatus
from .service_assertion import issue_service_assertion


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
            return FusionStatus(
                enabled=True,
                available=False,
                capabilities=[],
                reason="service_unavailable",
            )
        try:
            assertion = issue_service_assertion(
                user_id=user_id,
                course_id="__fusion_status__",
                scopes=["service:status"],
                secret=self.secret,
            )
            headers = {"X-CampusMate-Service-Assertion": assertion}
            response = await self._get("/internal/health/ready", headers=headers)
            if response.status_code != 200:
                return FusionStatus(
                    enabled=True,
                    available=False,
                    capabilities=[],
                    reason="service_unavailable" if response.status_code >= 500 else "degraded",
                )
            payload = response.json()
            capabilities = payload.get("capabilities", []) if isinstance(payload, dict) else []
            return FusionStatus(
                enabled=True,
                available=True,
                capabilities=[item for item in capabilities if isinstance(item, str)],
                reason="ready",
            )
        except Exception:
            # The internal address and assertion are deliberately absent from the public status.
            return FusionStatus(
                enabled=True,
                available=False,
                capabilities=[],
                reason="service_unavailable",
            )

    async def _get(self, path: str, *, headers: dict[str, str]):
        if self.transport is not None:
            return await self.transport.get(f"{self.base_url}{path}", headers=headers, timeout=self.timeout_seconds)
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=False) as client:
            return await client.get(f"{self.base_url}{path}", headers=headers)


__all__ = ["OpenMAICFusionClient"]
