"""Course-bound per-scene narration gateway.

The teacher's voice for one slide. Two properties matter and are enforced here:

1. **No text crosses this boundary.** The client sends a scene id, never the
   words to speak. The managed service derives the script from the scene body,
   so "the audio for this page" is a function of "this page" and cannot drift
   from it. An endpoint that accepted text would let the browser synthesize a
   paragraph unrelated to any scene — which is exactly the defect this replaces.
2. **Audio is addressed by scene, not by artifact.** The browser asks about a
   scene and gets that scene's job, so switching pages or reloading cannot
   attach one page's audio to another.
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

router = APIRouter(prefix="/courses", tags=["课堂讲解"])


class NarrationIn(BaseModel):
    """Only identifiers: the script is derived server-side from the scene body."""

    scene_id: str = Field(..., min_length=1, max_length=192)
    stage_id: str = Field(..., min_length=1, max_length=192)


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
        raise FusionInvalidRequest("讲解生成请求必须携带有效的 Idempotency-Key")
    return text


@router.get(
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/narration",
    summary="读取场景讲解",
    responses={
        200: {
            "description": "该场景是否已有讲解音频，以及所属任务",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取场景讲解状态",
                            "value": {
                                "scene_id": "scene-a",
                                "stage_id": "stage_1",
                                "available": True,
                                "has_script": True,
                                "script_chars": 128,
                                "truncated": False,
                                "stale": False,
                                "job": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def get_scene_narration(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    scene_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """读取该场景是否已有讲解音频，以及所属任务。

    - 场景按 id 寻址，音频始终绑定到这一页，切换或刷新不会挂错页。
    - 讲稿变化会让已有音频失效（stale=true）。
    - 需要已登录且对该课程有访问权限；受管服务未启用时返回 503。
    """
    _require(container)
    assert_course_access(container, user, course_id)
    return await client.get_scene_narration(
        user_id=str(user.id), course_id=course_id, workspace_id=workspace_id,
        stage_id=stage_id, scene_id=scene_id,
    )


@router.post(
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/narration",
    status_code=202,
    summary="合成场景讲解",
    responses={
        202: {
            "description": "已受理，返回可轮询的讲解合成任务",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "为这一页排入讲解合成",
                            "value": {
                                "scene_id": "scene-a",
                                "has_script": True,
                                "reuse": False,
                                "job": {
                                    "id": "job_narr_1",
                                    "course_id": "course_db_2025",
                                    "kind": "tts",
                                    "mode": "mimo-v2.5-tts",
                                    "status": "queued",
                                    "progress": 0,
                                    "attempts": 0,
                                    "error_code": None,
                                    "artifact_id": None,
                                    "scene_id": "scene-a",
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
async def synthesize_scene_narration(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    scene_id: str,
    body: Annotated[
        NarrationIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "为 scene-a 合成讲解",
                    "value": {"scene_id": "scene-a", "stage_id": "stage_1"},
                }
            }
        ),
    ],
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """为一个场景排入讲解合成任务；音频稍后以产物形式取回。

    合成是排队的，因此返回 202 与任务引用；同一场景重复调用复用已有任务，
    不会重复计费。请求体只带场景标识，讲稿由服务端派生；路径与请求体不一致
    返回 400（MAGICCLASS_INVALID_REQUEST）。
    """
    _require(container)
    assert_course_access(container, user, course_id)
    # A body scene_id that disagrees with the path is a client bug worth
    # surfacing, not something to silently reconcile.
    if body.scene_id != scene_id or body.stage_id != stage_id:
        raise FusionInvalidRequest("请求体中的场景标识与路径不一致")
    return await client.synthesize_scene_narration(
        user_id=str(user.id), course_id=course_id, workspace_id=workspace_id,
        stage_id=stage_id, scene_id=scene_id,
        idempotency_key=_key(idempotency_key),
    )


__all__ = ["router", "NarrationIn"]
