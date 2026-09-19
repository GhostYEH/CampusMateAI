"""CampusMate-facing folder + search routes.

Navigation over a student's own learning content. The gateway owns the same four
things it owns for workspaces, plus one that matters only here:

- **identity** — the acting user is the CampusMate JWT subject and the course is
  the one in the path, re-checked against the unified course-visibility policy
  before anything is sent upstream;
- **retry safety** — folder creation must carry an `Idempotency-Key` (a retried
  create must not clone the tree) and a rename/move/delete must carry `If-Match`;
- **status translation** — the service's 412 becomes a 409 for the browser;
- **input shape** — `folder_id` / `parent_id` distinguish "not provided" from an
  explicit `null` ("unfile" / "move to root"), and a blank search query is
  refused here rather than turned into "return everything";
- **the fusion switch** — when the runtime is off these routes answer 503 rather
  than an empty list, which would read as "you have nothing".
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, Query

from ...core.config import Settings

from ...models.multi_role import UserRow
from ...schemas.openmaic_fusion import (
    FolderCreateIn,
    FolderListOut,
    FolderOut,
    FolderUpdateIn,
    SearchHitOut,
    SearchListOut,
)
from ...services.container import ServiceContainer, get_container
from ...services.openmaic.course_context import assert_course_access
from ...services.openmaic.fusion_client import UNSET, OpenMAICFusionClient
from ...services.openmaic.fusion_errors import FusionInvalidRequest, FusionUnavailable
from ..deps import current_user

router = APIRouter(prefix="/courses", tags=["openmaic-discovery"])

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 50
MAX_IDEMPOTENCY_KEY_LENGTH = 200
MAX_QUERY_LENGTH = 200


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> OpenMAICFusionClient:
    """Build the internal client from the request container, not a module singleton."""
    settings = container.settings
    return OpenMAICFusionClient(
        base_url=settings.openmaic_service_url,
        secret=settings.openmaic_internal_secret,
        timeout_seconds=settings.openmaic_service_timeout_seconds,
    )


def _require_fusion_enabled(settings: Settings) -> None:
    if not settings.openmaic_fusion_enabled:
        # An empty list would read as "you have no folders" — a different and
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
    raw = (value or "").strip().replace("W/", "").replace('"', "")
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


def _require_query(value: Optional[str]) -> str:
    query = (value or "").strip()
    if not query:
        raise FusionInvalidRequest("搜索关键词不能为空")
    if len(query) > MAX_QUERY_LENGTH:
        raise FusionInvalidRequest(f"搜索关键词不能超过 {MAX_QUERY_LENGTH} 个字符")
    return query


def _limit(value: int) -> int:
    return max(1, min(int(value), MAX_PAGE_LIMIT))


def _folder_out(payload: Dict[str, Any]) -> FolderOut:
    return FolderOut(**{k: payload[k] for k in FolderOut.model_fields if k in payload})


def _search_hit(payload: Dict[str, Any]) -> SearchHitOut:
    return SearchHitOut(**{k: payload[k] for k in SearchHitOut.model_fields if k in payload})


# ===== folders =====


@router.get("/{course_id}/folders", response_model=FolderListOut)
async def list_folders(
    course_id: str,
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[str] = Query(None, max_length=512),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> FolderListOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    payload = await client.list_folders(
        user_id=str(user.id), course_id=course_id, limit=_limit(limit), cursor=cursor
    )
    return FolderListOut(
        items=[_folder_out(item) for item in payload.get("items", [])],
        next_cursor=payload.get("next_cursor"),
    )


@router.post("/{course_id}/folders", response_model=FolderOut, status_code=201)
async def create_folder(
    course_id: str,
    body: FolderCreateIn,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> FolderOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    return _folder_out(
        await client.create_folder(
            user_id=str(user.id),
            course_id=course_id,
            name=body.name,
            parent_id=body.parent_id,
            idempotency_key=_require_idempotency_key(idempotency_key),
        )
    )


@router.get("/{course_id}/folders/{folder_id}", response_model=FolderOut)
async def get_folder(
    course_id: str,
    folder_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> FolderOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    return _folder_out(
        await client.get_folder(user_id=str(user.id), course_id=course_id, folder_id=folder_id)
    )


@router.patch("/{course_id}/folders/{folder_id}", response_model=FolderOut)
async def update_folder(
    course_id: str,
    folder_id: str,
    body: FolderUpdateIn,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> FolderOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    provides_parent = "parent_id" in body.model_fields_set
    if body.name is None and not provides_parent:
        raise FusionInvalidRequest("没有需要更新的字段")
    return _folder_out(
        await client.update_folder(
            user_id=str(user.id),
            course_id=course_id,
            folder_id=folder_id,
            revision=_require_revision(if_match),
            name=body.name,
            # `None` here means "the client sent an explicit null" = move to root.
            parent_id=body.parent_id if provides_parent else UNSET,
        )
    )


@router.delete("/{course_id}/folders/{folder_id}")
async def delete_folder(
    course_id: str,
    folder_id: str,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> Dict[str, Any]:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    await client.delete_folder(
        user_id=str(user.id),
        course_id=course_id,
        folder_id=folder_id,
        revision=_require_revision(if_match),
    )
    return {"deleted": True}


# ===== search =====


@router.get("/{course_id}/search", response_model=SearchListOut)
async def search_course_content(
    course_id: str,
    q: Optional[str] = Query(None, max_length=400),
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[str] = Query(None, max_length=512),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> SearchListOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    query = _require_query(q)
    payload = await client.search(
        user_id=str(user.id),
        course_id=course_id,
        query=query,
        limit=_limit(limit),
        cursor=cursor,
    )
    return SearchListOut(
        items=[_search_hit(item) for item in payload.get("items", [])],
        next_cursor=payload.get("next_cursor"),
        query=query,
    )


__all__ = ["router", "DEFAULT_PAGE_LIMIT", "MAX_PAGE_LIMIT", "MAX_QUERY_LENGTH"]
