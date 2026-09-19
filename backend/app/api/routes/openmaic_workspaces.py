"""CampusMate-facing workspace/stage routes.

These are the browser's only door to the managed OpenMAIC runtime's persistence
layer, so the gateway owns four things the client must not:

- **identity** — the acting user is the CampusMate JWT subject and the course is
  the one in the path, re-checked against the unified course-visibility policy
  before anything is sent upstream. The browser never names a user;
- **retry safety** — a create must carry an `Idempotency-Key`, and a conditional
  write must carry `If-Match`. Missing either is refused rather than guessed,
  because "create it again" and "overwrite whatever is there" are exactly the two
  mistakes those headers exist to prevent;
- **status translation** — the service's 412 becomes a 409 for the browser, and
  its validation payload is reduced to what the client can act on;
- **the fusion switch** — when the runtime is off, these routes answer 503 rather
  than an empty list, which would read as "you have no work".
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, Header, Query

from ...core.config import Settings

from ...models.multi_role import UserRow
from ...schemas.openmaic_fusion import (
    StageCreateIn,
    StageListOut,
    StageOut,
    StageReplaceIn,
    StageSummaryOut,
    WorkspaceCreateIn,
    WorkspaceListOut,
    WorkspaceOut,
    WorkspaceUpdateIn,
)
from ...services.container import ServiceContainer, get_container
from ...services.openmaic.course_context import assert_course_access
from ...services.openmaic.fusion_client import UNSET, OpenMAICFusionClient
from ...services.openmaic.fusion_errors import FusionInvalidRequest, FusionUnavailable
from ..deps import current_user

router = APIRouter(prefix="/courses", tags=["openmaic-workspaces"])

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 50
MAX_IDEMPOTENCY_KEY_LENGTH = 200


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> OpenMAICFusionClient:
    """构造内部客户端。

    配置取自容器而不是应用级单例：路由的其它依赖都走容器，混用两套配置源会让
    测试里的覆盖静默失效（真实症状是"开关明明是开的却报未启用"）。
    """
    settings = container.settings
    return OpenMAICFusionClient(
        base_url=settings.openmaic_service_url,
        secret=settings.openmaic_internal_secret,
        timeout_seconds=settings.openmaic_service_timeout_seconds,
    )


def _require_fusion_enabled(settings: Settings) -> None:
    if not settings.openmaic_fusion_enabled:
        # An empty list would read as "you have no workspaces" — a different and
        # wrong answer when the runtime is simply switched off.
        raise FusionUnavailable("受管 OpenMAIC 服务未启用")


def _require_idempotency_key(value: Optional[str]) -> str:
    key = (value or "").strip()
    if not key:
        raise FusionInvalidRequest("创建请求必须携带 Idempotency-Key")
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise FusionInvalidRequest("Idempotency-Key 过长")
    return key


def _require_revision(value: Optional[str]) -> int:
    """Read the client's expected revision from `If-Match`.

    `*` is refused: "match anything" is precisely the lost update this header
    exists to prevent, and a client that sends it has not read the row it is
    about to overwrite.
    """
    raw = (value or "").strip().replace('W/', '').replace('"', '')
    if not raw:
        raise FusionInvalidRequest("写入请求必须携带 If-Match（当前 revision）")
    if raw == "*":
        raise FusionInvalidRequest("If-Match 不接受 *，请传回你读到的 revision")
    try:
        revision = int(raw)
    except ValueError as exc:
        raise FusionInvalidRequest("If-Match 必须是正整数 revision") from exc
    if revision < 1:
        raise FusionInvalidRequest("If-Match 必须是正整数 revision")
    return revision


def _limit(value: int) -> int:
    return max(1, min(int(value), MAX_PAGE_LIMIT))


def _workspace_out(payload: Dict[str, Any]) -> WorkspaceOut:
    return WorkspaceOut(**{k: payload[k] for k in WorkspaceOut.model_fields if k in payload})


def _stage_summary(payload: Dict[str, Any]) -> StageSummaryOut:
    return StageSummaryOut(**{k: payload[k] for k in StageSummaryOut.model_fields if k in payload})


# ===== workspaces =====


@router.get("/{course_id}/workspaces", response_model=WorkspaceListOut)
async def list_workspaces(
    course_id: str,
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[str] = Query(None, max_length=512),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> WorkspaceListOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    payload = await client.list_workspaces(
        user_id=str(user.id), course_id=course_id, limit=_limit(limit), cursor=cursor
    )
    return WorkspaceListOut(
        items=[_workspace_out(item) for item in payload.get("items", [])],
        next_cursor=payload.get("next_cursor"),
    )


@router.post("/{course_id}/workspaces", response_model=WorkspaceOut, status_code=201)
async def create_workspace(
    course_id: str,
    body: WorkspaceCreateIn,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> WorkspaceOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    payload = await client.create_workspace(
        user_id=str(user.id),
        course_id=course_id,
        name=body.name,
        description=body.description,
        folder_id=body.folder_id,
        idempotency_key=_require_idempotency_key(idempotency_key),
    )
    return _workspace_out(payload)


@router.get("/{course_id}/workspaces/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(
    course_id: str,
    workspace_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> WorkspaceOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    return _workspace_out(
        await client.get_workspace(user_id=str(user.id), course_id=course_id, workspace_id=workspace_id)
    )


@router.patch("/{course_id}/workspaces/{workspace_id}", response_model=WorkspaceOut)
async def update_workspace(
    course_id: str,
    workspace_id: str,
    body: WorkspaceUpdateIn,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> WorkspaceOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    provides_folder = "folder_id" in body.model_fields_set
    if body.name is None and body.description is None and not provides_folder:
        raise FusionInvalidRequest("没有需要更新的字段")
    return _workspace_out(
        await client.update_workspace(
            user_id=str(user.id),
            course_id=course_id,
            workspace_id=workspace_id,
            revision=_require_revision(if_match),
            name=body.name,
            description=body.description,
            # `None` here means the client explicitly sent null = unfile.
            folder_id=body.folder_id if provides_folder else UNSET,
        )
    )


@router.delete("/{course_id}/workspaces/{workspace_id}")
async def delete_workspace(
    course_id: str,
    workspace_id: str,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> Dict[str, Any]:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    await client.delete_workspace(
        user_id=str(user.id),
        course_id=course_id,
        workspace_id=workspace_id,
        revision=_require_revision(if_match),
    )
    return {"deleted": True}


# ===== stages =====


@router.get("/{course_id}/workspaces/{workspace_id}/stages", response_model=StageListOut)
async def list_stages(
    course_id: str,
    workspace_id: str,
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[str] = Query(None, max_length=512),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> StageListOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    payload = await client.list_stages(
        user_id=str(user.id),
        course_id=course_id,
        workspace_id=workspace_id,
        limit=_limit(limit),
        cursor=cursor,
    )
    return StageListOut(
        items=[_stage_summary(item) for item in payload.get("items", [])],
        next_cursor=payload.get("next_cursor"),
    )


@router.post("/{course_id}/workspaces/{workspace_id}/stages", response_model=StageOut, status_code=201)
async def create_stage(
    course_id: str,
    workspace_id: str,
    body: StageCreateIn = Body(...),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> StageOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    payload = await client.create_stage(
        user_id=str(user.id),
        course_id=course_id,
        workspace_id=workspace_id,
        title=body.title,
        document=body.document,
        idempotency_key=_require_idempotency_key(idempotency_key),
    )
    return StageOut(**payload)


@router.get("/{course_id}/workspaces/{workspace_id}/stages/{stage_id}", response_model=StageOut)
async def get_stage(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> StageOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    return StageOut(
        **await client.get_stage(
            user_id=str(user.id), course_id=course_id, workspace_id=workspace_id, stage_id=stage_id
        )
    )


@router.put("/{course_id}/workspaces/{workspace_id}/stages/{stage_id}", response_model=StageOut)
async def replace_stage(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    body: StageReplaceIn,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> StageOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    return StageOut(
        **await client.replace_stage(
            user_id=str(user.id),
            course_id=course_id,
            workspace_id=workspace_id,
            stage_id=stage_id,
            revision=_require_revision(if_match),
            document=body.document,
            title=body.title,
        )
    )


@router.delete("/{course_id}/workspaces/{workspace_id}/stages/{stage_id}")
async def delete_stage(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> Dict[str, Any]:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    await client.delete_stage(
        user_id=str(user.id),
        course_id=course_id,
        workspace_id=workspace_id,
        stage_id=stage_id,
        revision=_require_revision(if_match),
    )
    return {"deleted": True}


__all__ = ["router", "DEFAULT_PAGE_LIMIT", "MAX_PAGE_LIMIT"]
