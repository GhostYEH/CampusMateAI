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

from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, Header, Query

from ...core.config import Settings

from ...models.multi_role import UserRow
from ...schemas.magicclass_fusion import (
    FolderCreateIn,
    FolderListOut,
    FolderOut,
    FolderUpdateIn,
    SearchHitOut,
    SearchListOut,
)
from ...services.container import ServiceContainer, get_container
from ...services.magicclass.course_context import assert_course_access
from ...services.magicclass.fusion_client import UNSET, MagicClassFusionClient
from ...services.magicclass.fusion_errors import FusionInvalidRequest, FusionUnavailable
from ..deps import current_user
from ..magicclass_gateway import build_fusion_client, require_idempotency_key, require_revision

router = APIRouter(prefix="/courses", tags=["课堂发现"])

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 50
MAX_IDEMPOTENCY_KEY_LENGTH = 200
MAX_QUERY_LENGTH = 200


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> MagicClassFusionClient:
    """Build the internal client from the request container, not a module singleton."""
    return build_fusion_client(container, client_type=MagicClassFusionClient)


def _require_fusion_enabled(settings: Settings) -> None:
    if not settings.magicclass_fusion_enabled:
        # An empty list would read as "you have no folders" — a different and
        # wrong answer when the runtime is simply switched off.
        raise FusionUnavailable("受管 magic class 服务未启用")


def _require_idempotency_key(value: Optional[str]) -> str:
    return require_idempotency_key(
        value,
        missing_message="创建请求必须携带 Idempotency-Key",
        max_length=MAX_IDEMPOTENCY_KEY_LENGTH,
    )


def _require_revision(value: Optional[str]) -> int:
    return require_revision(value)


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


@router.get(
    "/{course_id}/folders",
    response_model=FolderListOut,
    summary="列出课程文件夹",
    responses={
        200: {
            "description": "文件夹列表，按不透明游标分页",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "列出课程文件夹",
                            "value": {
                                "items": [
                                    {
                                        "id": "fd_001",
                                        "course_id": "course_001",
                                        "parent_id": None,
                                        "name": "期末复习",
                                        "revision": 1,
                                        "created_at": "2026-09-01T08:00:00+00:00",
                                        "updated_at": "2026-09-01T08:00:00+00:00",
                                        "workspace_count": 4,
                                    }
                                ],
                                "next_cursor": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def list_folders(
    course_id: str,
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[str] = Query(None, max_length=512),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> FolderListOut:
    """列出当前课程下用户可见的文件夹。

    - 仅返回调用者自己的文件夹，游标只在归属范围内收窄。
    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    payload = await client.list_folders(
        user_id=str(user.id), course_id=course_id, limit=_limit(limit), cursor=cursor
    )
    return FolderListOut(
        items=[_folder_out(item) for item in payload.get("items", [])],
        next_cursor=payload.get("next_cursor"),
    )


@router.post(
    "/{course_id}/folders",
    response_model=FolderOut,
    status_code=201,
    summary="创建课程文件夹",
    responses={
        201: {
            "description": "创建文件夹成功，返回文件夹详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "创建课程文件夹",
                            "value": {
                                "id": "fd_001",
                                "course_id": "course_001",
                                "parent_id": None,
                                "name": "期末复习",
                                "revision": 1,
                                "created_at": "2026-10-05T09:30:00+00:00",
                                "updated_at": "2026-10-05T09:30:00+00:00",
                                "workspace_count": 0,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def create_folder(
    course_id: str,
    body: Annotated[
        FolderCreateIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "创建课程文件夹",
                    "value": {"name": "期末复习"},
                }
            }
        ),
    ],
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> FolderOut:
    """在当前课程下创建一个文件夹。

    - 必须携带 Idempotency-Key；缺失返回 400（MAGICCLASS_INVALID_REQUEST）。
    - parent_id 省略或在根层时位于根目录；需要已登录且对该课程有访问权限。
    - 受管 magic class 服务未启用时返回 503。
    """
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


@router.get(
    "/{course_id}/folders/{folder_id}",
    response_model=FolderOut,
    summary="读取课程文件夹",
    responses={
        200: {
            "description": "返回指定文件夹详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取课程文件夹",
                            "value": {
                                "id": "fd_001",
                                "course_id": "course_001",
                                "parent_id": None,
                                "name": "期末复习",
                                "revision": 1,
                                "created_at": "2026-09-01T08:00:00+00:00",
                                "updated_at": "2026-09-01T08:00:00+00:00",
                                "workspace_count": 4,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def get_folder(
    course_id: str,
    folder_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> FolderOut:
    """读取指定文件夹的详情。

    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    return _folder_out(
        await client.get_folder(user_id=str(user.id), course_id=course_id, folder_id=folder_id)
    )


@router.patch(
    "/{course_id}/folders/{folder_id}",
    response_model=FolderOut,
    summary="更新课程文件夹",
    responses={
        200: {
            "description": "更新文件夹成功，返回更新后的文件夹详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "更新课程文件夹",
                            "value": {
                                "id": "fd_001",
                                "course_id": "course_001",
                                "parent_id": None,
                                "name": "期末冲刺复习",
                                "revision": 2,
                                "created_at": "2026-09-01T08:00:00+00:00",
                                "updated_at": "2026-10-06T10:15:00+00:00",
                                "workspace_count": 4,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def update_folder(
    course_id: str,
    folder_id: str,
    body: Annotated[
        FolderUpdateIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "重命名文件夹",
                    "value": {"name": "期末冲刺复习"},
                }
            }
        ),
    ],
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> FolderOut:
    """更新文件夹的名称或父级（移动位置）。

    - 必须携带 If-Match（当前 revision），不接受 `*`；缺失或非法返回 400（MAGICCLASS_INVALID_REQUEST）。
    - 至少要提供一个可更新字段，否则返回 400；显式 null 的 parent_id 表示移动到根层。
    - 服务端 revision 不一致返回 409（MAGICCLASS_REVISION_CONFLICT）；受管服务未启用时返回 503。
    """
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


@router.delete(
    "/{course_id}/folders/{folder_id}",
    summary="删除课程文件夹",
    responses={
        200: {
            "description": "删除文件夹成功",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "删除课程文件夹",
                            "value": {"deleted": True},
                        }
                    }
                }
            },
        }
    },
)
async def delete_folder(
    course_id: str,
    folder_id: str,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """删除指定文件夹。

    - 必须携带 If-Match（当前 revision），不接受 `*`；缺失或非法返回 400（MAGICCLASS_INVALID_REQUEST）。
    - 服务端 revision 不一致返回 409（MAGICCLASS_REVISION_CONFLICT）。
    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
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


@router.get(
    "/{course_id}/search",
    response_model=SearchListOut,
    summary="搜索课程内容",
    responses={
        200: {
            "description": "搜索命中列表，含服务端生成的站内深链",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "搜索课程内容",
                            "value": {
                                "items": [
                                    {
                                        "kind": "stage",
                                        "workspace_id": "ws_001",
                                        "stage_id": "stg_001",
                                        "title": "第一讲·极限与连续",
                                        "snippet": "……极限的四则运算法则……",
                                        "folder_id": "fd_001",
                                        "updated_at": "2026-10-05T09:30:00+00:00",
                                        "path": "/courses/course_001/workspaces/ws_001/stages/stg_001",
                                    }
                                ],
                                "next_cursor": None,
                                "query": "极限",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def search_course_content(
    course_id: str,
    q: Optional[str] = Query(None, max_length=400),
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[str] = Query(None, max_length=512),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> SearchListOut:
    """在当前课程内搜索工作台与舞台内容。

    - 关键词去掉首尾空白后不能为空，否则返回 400（MAGICCLASS_INVALID_REQUEST）；长度上限 200。
    - 结果按归属过滤；需要已登录且对该课程有访问权限；受管服务未启用时返回 503。
    """
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
