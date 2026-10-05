"""Provider-safe magic class settings gateway."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from ...models.multi_role import UserRow
from ...services.container import ServiceContainer, get_container
from ...services.magicclass.fusion_client import MagicClassFusionClient
from ..deps import current_user
from ..magicclass_gateway import build_fusion_client

router = APIRouter(prefix="/magicclass/fusion", tags=["融合服务提供方"])


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> MagicClassFusionClient:
    return build_fusion_client(container, client_type=MagicClassFusionClient)


@router.get(
    "/providers",
    summary="读取提供方状态",
    responses={
        200: {
            "description": "受管服务各提供方的可用性布尔量；未启用时返回 disabled",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取提供方状态",
                            "value": {
                                "state": "ready",
                                "providers": {
                                    "llm": True,
                                    "web_search": False,
                                    "image": False,
                                    "video": False,
                                    "tts": True,
                                    "render": False,
                                    "external_3d": False,
                                },
                            },
                        }
                    }
                }
            },
        }
    },
)
async def provider_status(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """读取各生成提供方（llm/tts/render 等）是否可用。

    只转发白名单能力布尔量，上游多余字段（含凭据与地址）一律丢弃；未启用时
    返回 {"state": "disabled", "providers": {}} 且不联系上游。需要已登录。
    """
    if not container.settings.magicclass_fusion_enabled:
        return {"state": "disabled", "providers": {}}
    payload = await client.provider_status(user_id=str(user.id))
    # Do not pass through arbitrary fields from the service.
    allowed = ("llm", "web_search", "image", "video", "tts", "render", "external_3d")
    return {"state": "ready", "providers": {key: bool(payload.get(key)) for key in allowed}}


__all__ = ["router"]
