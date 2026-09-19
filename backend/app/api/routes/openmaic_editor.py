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
from ...schemas.openmaic_fusion import (
    SceneOutlineOut,
    StageCommandResultOut,
    StageCommandsIn,
    StageOutlineOut,
    StageOut,
)
from ...services.container import ServiceContainer, get_container
from ...services.openmaic.course_context import assert_course_access
from ...services.openmaic.fusion_client import OpenMAICFusionClient
from ...services.openmaic.fusion_errors import FusionInvalidRequest, FusionUnavailable
from ..deps import current_user

router = APIRouter(prefix="/courses", tags=["openmaic-editor"])

MAX_COMMANDS_PER_REQUEST = 50
MAX_IDEMPOTENCY_KEY_LENGTH = 200


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> OpenMAICFusionClient:
    settings = container.settings
    return OpenMAICFusionClient(
        base_url=settings.openmaic_service_url,
        secret=settings.openmaic_internal_secret,
        timeout_seconds=settings.openmaic_service_timeout_seconds,
    )


def _require_fusion_enabled(settings: Settings) -> None:
    if not settings.openmaic_fusion_enabled:
        # An empty outline would read as "this stage has no scenes" — a different
        # and wrong answer when the runtime is simply switched off.
        raise FusionUnavailable("受管 OpenMAIC 服务未启用")


def _require_idempotency_key(value: Optional[str]) -> str:
    key = (value or "").strip()
    if not key:
        raise FusionInvalidRequest("编辑请求必须携带 Idempotency-Key")
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise FusionInvalidRequest("Idempotency-Key 过长")
    return key


def _require_revision(value: Optional[str]) -> int:
    raw = (value or "").strip().replace("W/", "").replace('"', "")
    if not raw:
        raise FusionInvalidRequest("编辑请求必须携带 If-Match（当前 revision）")
    if raw == "*":
        raise FusionInvalidRequest("If-Match 不接受 *，请传回你读到的 revision")
    try:
        revision = int(raw)
    except ValueError as exc:
        raise FusionInvalidRequest("If-Match 必须是正整数 revision") from exc
    if revision < 1:
        raise FusionInvalidRequest("If-Match 必须是正整数 revision")
    return revision


@router.post(
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/commands",
    response_model=StageCommandResultOut,
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
    client: OpenMAICFusionClient = Depends(_client),
) -> StageCommandResultOut:
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
)
async def get_stage_outline(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> StageOutlineOut:
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
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}",
)
async def get_stage_scene(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    scene_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> Dict[str, Any]:
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
