"""CampusMate-facing stage-editing routes.

The browser's only door to the editor. The gateway owns:

- **identity and course access** — the acting user is the CampusMate JWT subject
  and the course is re-checked against the unified visibility policy before the
  internal call;
- **retry safety** — applying a command list twice creates two scenes, so
  `Idempotency-Key` is required; a conditional edit requires `If-Match` and the
  service's 412 becomes a 409 for the browser;
- **input shape** — the command list is length-bounded here as well as in the
  service, so an oversized request is a 400 rather than an expensive internal
  call that fails late;
- **error translation** — a rejected command keeps its machine-readable `code`
  and `path` so the editor can highlight the offending row, while the raw
  document, the internal URL and the assertion never reach the client.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header

from ...core.config import Settings

from ...models.multi_role import UserRow
from ...schemas.magicclass_fusion import (
    SceneOutlineOut,
    StagePlaybackOut,
    StageCommandResultOut,
    StageCommandsIn,
    StageOutlineOut,
    StageOut,
)
from ...services.container import ServiceContainer, get_container
from ...services.magicclass.course_context import assert_course_access
from ...services.magicclass.fusion_client import MagicClassFusionClient
from ...services.magicclass.fusion_errors import FusionInvalidRequest, FusionUnavailable
from ..deps import current_user
from ..magicclass_gateway import build_fusion_client, require_idempotency_key, require_revision

router = APIRouter(prefix="/courses", tags=["课堂编辑器"])

MAX_COMMANDS_PER_REQUEST = 50
MAX_IDEMPOTENCY_KEY_LENGTH = 200


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> MagicClassFusionClient:
    return build_fusion_client(container, client_type=MagicClassFusionClient)


def _require_fusion_enabled(settings: Settings) -> None:
    if not settings.magicclass_fusion_enabled:
        # An empty outline would read as "this stage has no scenes" — a different
        # and wrong answer when the runtime is simply switched off.
        raise FusionUnavailable("受管 magic class 服务未启用")


def _require_idempotency_key(value: Optional[str]) -> str:
    return require_idempotency_key(
        value,
        missing_message="编辑请求必须携带 Idempotency-Key",
        max_length=MAX_IDEMPOTENCY_KEY_LENGTH,
    )


def _require_revision(value: Optional[str]) -> int:
    return require_revision(value, missing_message="编辑请求必须携带 If-Match（当前 revision）")


@router.post(
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/commands",
    response_model=StageCommandResultOut,
    summary="应用舞台编辑命令",
    responses={
        200: {
            "description": "命令应用成功，返回应用后的舞台与已应用命令数",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "应用舞台编辑命令",
                            "value": {
                                "id": "stg_001",
                                "workspace_id": "ws_001",
                                "course_id": "course_001",
                                "title": "第一讲·极限与连续（修订）",
                                "revision": 4,
                                "dsl_version": "1.0",
                                "created_at": "2026-09-20T08:00:00+00:00",
                                "updated_at": "2026-10-06T10:15:00+00:00",
                                "document": {"stage": {"id": "stg_001", "name": "第一讲·极限与连续（修订）"}, "scenes": []},
                                "applied_commands": 1,
                                "migrated": False,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def apply_stage_commands(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    body: StageCommandsIn,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> StageCommandResultOut:
    """把编辑器提交的命令列表作用在舞台当前文档上。

    - 必须同时携带 If-Match（当前 revision）与 Idempotency-Key；缺失或非法返回 400（MAGICCLASS_INVALID_REQUEST）。
    - 一次 1–50 条命令，超出返回 400；服务端 revision 不一致返回 409（MAGICCLASS_REVISION_CONFLICT）。
    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    if not body.commands:
        raise FusionInvalidRequest("至少需要一条命令")
    if len(body.commands) > MAX_COMMANDS_PER_REQUEST:
        raise FusionInvalidRequest(f"一次最多提交 {MAX_COMMANDS_PER_REQUEST} 条命令")

    payload = await client.apply_stage_commands(
        user_id=str(user.id),
        course_id=course_id,
        workspace_id=workspace_id,
        stage_id=stage_id,
        commands=body.commands,
        revision=_require_revision(if_match),
        idempotency_key=_require_idempotency_key(idempotency_key),
    )
    return StageCommandResultOut(**payload)


@router.get(
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/outline",
    response_model=StageOutlineOut,
    summary="读取舞台目录",
    responses={
        200: {
            "description": "舞台目录：场景顺序与摘要，不含场景正文",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取舞台目录",
                            "value": {
                                "stage_id": "stg_001",
                                "workspace_id": "ws_001",
                                "title": "第一讲·极限与连续",
                                "revision": 2,
                                "dsl_version": "1.0",
                                "scenes": [
                                    {
                                        "id": "scn_001",
                                        "type": "slide",
                                        "title": "开场导入",
                                        "order": 0,
                                        "actions": 3,
                                        "updated_at": 1759654200,
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        }
    },
)
async def get_stage_outline(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> StageOutlineOut:
    """读取舞台目录：场景的顺序与摘要（不含场景正文）。

    - 目录是导航面，只有先读目录再按需读取单个场景。
    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    payload = await client.get_stage_outline(
        user_id=str(user.id), course_id=course_id, workspace_id=workspace_id, stage_id=stage_id
    )
    return StageOutlineOut(
        stage_id=payload["stage_id"],
        workspace_id=payload["workspace_id"],
        title=payload["title"],
        revision=int(payload["revision"]),
        dsl_version=payload.get("dsl_version", ""),
        scenes=[SceneOutlineOut(**scene) for scene in payload.get("scenes", [])],
    )


@router.get(
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/playback",
    response_model=StagePlaybackOut,
    summary="读取舞台播放计划",
    responses={
        200: {
            "description": "按服务端决定的播放计划：场景渲染方式、动作顺序与降级说明",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取舞台播放计划",
                            "value": {
                                "stage_id": "stg_001",
                                "workspace_id": "ws_001",
                                "title": "第一讲·极限与连续",
                                "revision": 2,
                                "dsl_version": "1.0",
                                "start_index": 0,
                                "scenes": [
                                    {
                                        "id": "scn_001",
                                        "type": "slide",
                                        "title": "开场导入",
                                        "order": 0,
                                        "render": {"kind": "native"},
                                        "steps": [],
                                        "dropped_actions": [],
                                        "whiteboards": 0,
                                        "multi_agent": False,
                                    }
                                ],
                                "degraded": [],
                            },
                        }
                    }
                }
            },
        }
    },
)
async def get_stage_playback(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    scene_id: Optional[str] = None,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> StagePlaybackOut:
    """舞台播放计划；`scene_id` 携带来自 URL 的续播位置。

    - `render.kind` 是唯一渲染判据：native 自渲染，sandbox-* 才允许放进受限 iframe，unsupported 必须带 reason。
    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    payload = await client.get_stage_playback(
        user_id=str(user.id),
        course_id=course_id,
        workspace_id=workspace_id,
        stage_id=stage_id,
        scene_id=scene_id,
    )
    return StagePlaybackOut(**payload)


@router.get(
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}",
    summary="读取舞台场景",
)
async def get_stage_scene(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    scene_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """读取单个舞台场景的完整内容（含场景正文）。

    - 场景正文结构由受管 DSL 决定，为开放对象，故不提供固定响应示例。
    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    return await client.get_stage_scene(
        user_id=str(user.id),
        course_id=course_id,
        workspace_id=workspace_id,
        stage_id=stage_id,
        scene_id=scene_id,
    )


__all__ = ["router", "MAX_COMMANDS_PER_REQUEST", "StageOut"]
