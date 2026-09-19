"""Provider-safe OpenMAIC settings gateway."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from ...models.multi_role import UserRow
from ...services.container import ServiceContainer, get_container
from ...services.openmaic.fusion_client import OpenMAICFusionClient
from ..deps import current_user

router = APIRouter(prefix="/openmaic/fusion", tags=["openmaic-provider"])


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> OpenMAICFusionClient:
    settings = container.settings
    return OpenMAICFusionClient(base_url=settings.openmaic_service_url, secret=settings.openmaic_internal_secret, timeout_seconds=settings.openmaic_service_timeout_seconds)


@router.get("/providers")
async def provider_status(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> Dict[str, Any]:
    if not container.settings.openmaic_fusion_enabled:
        return {"state": "disabled", "providers": {}}
    payload = await client.provider_status(user_id=str(user.id))
    # Do not pass through arbitrary fields from the service.
    allowed = ("llm", "web_search", "image", "video", "tts", "render", "external_3d")
    return {"state": "ready", "providers": {key: bool(payload.get(key)) for key in allowed}}


__all__ = ["router"]
