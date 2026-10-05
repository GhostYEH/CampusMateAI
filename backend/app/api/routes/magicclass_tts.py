"""Course-bound speech synthesis gateway.

The upstream call never happens in the request path: the managed service runs
providers through a queued job worker because its route handlers are synchronous
by design (identity consumption and writes share one SQLite transaction). So
this route answers 202 with a job reference, the service synthesizes offline,
and the audio is fetched afterwards through the artifact download route.
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

router = APIRouter(prefix="/courses", tags=["课堂语音"])


class TtsIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    instruction: Optional[str] = Field(None, min_length=1, max_length=2000)
    voice: Optional[str] = Field(None, min_length=1, max_length=80)


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
        raise FusionInvalidRequest("语音合成请求必须携带有效的 Idempotency-Key")
    return text


@router.post(
    "/{course_id}/tts",
    status_code=202,
    summary="合成课堂语音",
    responses={
        202: {
            "description": "已受理，返回可轮询的语音合成任务",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "排队合成一段课堂语音",
                            "value": {
                                "job_id": "job_1",
                                "job": {
                                    "id": "job_1",
                                    "course_id": "course_db_2025",
                                    "kind": "tts",
                                    "mode": "mimo-v2.5-tts",
                                    "status": "queued",
                                    "progress": 0,
                                    "attempts": 0,
                                    "error_code": None,
                                    "artifact_id": None,
                                    "scene_id": None,
                                    "created_at": "2026-10-06T08:00:00+00:00",
                                    "updated_at": "2026-10-06T08:00:00+00:00",
                                },
                                "voice": "苏打",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def synthesize_speech(
    course_id: str,
    body: Annotated[
        TtsIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "合成一段课堂讲解语音",
                    "value": {
                        "text": "同学们好，今天我们讲函数极限。",
                        "instruction": "用沉稳清晰的教学语气朗读",
                        "voice": "苏打",
                    },
                }
            }
        ),
    ],
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """把一段文本合成为课堂语音，返回 202 与可轮询任务。

    上游调用不在请求路径里执行：受管服务用排队任务跑提供方，音频随后经产物
    下载路由取回。必须携带有效 Idempotency-Key；需要已登录且对该课程有访问
    权限；受管服务未启用时返回 503。
    """
    _require(container)
    assert_course_access(container, user, course_id)
    return await client.synthesize_speech(
        user_id=str(user.id),
        course_id=course_id,
        text=body.text,
        instruction=body.instruction,
        voice=body.voice,
        idempotency_key=_key(idempotency_key),
    )


__all__ = ["router", "TtsIn"]
