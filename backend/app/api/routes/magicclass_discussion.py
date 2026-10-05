"""Course-bound multi-agent round-table discussion gateway.

Like speech synthesis, the provider call runs as a queued job on the managed
service: this route answers 202 with a job reference, and the transcript is
fetched afterwards through the artifact download route.
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, Header
from pydantic import BaseModel, Field

from ...models.multi_role import UserRow
from ...services.container import ServiceContainer, get_container
from ...services.magicclass.course_context import assert_course_access
from ...services.magicclass.fusion_client import MagicClassFusionClient
from ...services.magicclass.fusion_errors import FusionInvalidRequest, FusionUnavailable
from ..deps import current_user
from ..magicclass_gateway import build_fusion_client

router = APIRouter(prefix="/courses", tags=["课堂讨论"])


class DiscussionIn(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> MagicClassFusionClient:
    return build_fusion_client(container, client_type=MagicClassFusionClient)


def _require(container: ServiceContainer) -> None:
    if not container.settings.magicclass_fusion_enabled:
        raise FusionUnavailable("受管 magic class 服务未启用")


def _key(value: Optional[str]) -> str:
    text = (value or "").strip()
    if not text or len(text) > 200:
        raise FusionInvalidRequest("圆桌讨论请求必须携带有效的 Idempotency-Key")
    return text


@router.post(
    "/{course_id}/discussion",
    status_code=202,
    summary="运行圆桌讨论",
    responses={
        202: {
            "description": "已受理，返回可轮询的多智能体讨论任务",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "排队一场圆桌讨论",
                            "value": {
                                "job_id": "job_9",
                                "job": {
                                    "id": "job_9",
                                    "course_id": "course_db_2025",
                                    "kind": "discussion",
                                    "mode": "stub-model",
                                    "status": "queued",
                                    "progress": 0,
                                    "attempts": 0,
                                    "error_code": None,
                                    "artifact_id": None,
                                    "scene_id": None,
                                    "created_at": "2026-10-06T08:00:00+00:00",
                                    "updated_at": "2026-10-06T08:00:00+00:00",
                                },
                            },
                        }
                    }
                }
            },
        }
    },
)
async def run_discussion(
    course_id: str,
    body: Annotated[
        DiscussionIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "就函数极限发起圆桌讨论",
                    "value": {"prompt": "请讨论函数极限的直观含义"},
                }
            }
        ),
    ],
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """运行一场绑定课程的多智能体圆桌讨论。

    讨论在受管服务上作为排队任务执行，因此返回 202 与任务引用，讨论记录稍后
    经产物下载路由取回。必须携带有效 Idempotency-Key；需要已登录且对该课程有
    访问权限；受管服务未启用时返回 503。
    """
    _require(container)
    assert_course_access(container, user, course_id)
    return await client.run_discussion(
        user_id=str(user.id),
        course_id=course_id,
        prompt=body.prompt,
        idempotency_key=_key(idempotency_key),
    )


__all__ = ["router", "DiscussionIn"]
