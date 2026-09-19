"""CampusMate-owned status boundary for the managed OpenMAIC runtime."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...core.config import Settings, get_settings
from ...models.multi_role import UserRow
from ...schemas.openmaic_fusion import FusionStatus
from ...services.openmaic.fusion_client import OpenMAICFusionClient
from ..deps import current_user

router = APIRouter(prefix="/openmaic/fusion", tags=["openmaic-fusion"])


def disabled_fusion_status() -> FusionStatus:
    return FusionStatus(enabled=False, available=False, capabilities=[], reason="disabled")


def _client(settings: Settings = Depends(get_settings)) -> OpenMAICFusionClient:
    return OpenMAICFusionClient(
        base_url=settings.openmaic_service_url,
        secret=settings.openmaic_internal_secret,
        timeout_seconds=settings.openmaic_service_timeout_seconds,
    )


@router.get("/status", response_model=FusionStatus)
async def fusion_status(
    user: UserRow = Depends(current_user),
    settings: Settings = Depends(get_settings),
    client: OpenMAICFusionClient = Depends(_client),
) -> FusionStatus:
    if not settings.openmaic_fusion_enabled:
        return disabled_fusion_status()
    return await client.status(user_id=str(user.id))


__all__ = ["disabled_fusion_status", "fusion_status", "router"]
