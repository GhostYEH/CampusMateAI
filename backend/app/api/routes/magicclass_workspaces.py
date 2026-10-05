"""CampusMate-facing workspace/stage routes.

These are the browser's only door to the managed magicclass runtime's persistence
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

from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, Header, Query

from ...core.config import Settings

from ...models.multi_role import UserRow
from ...schemas.magicclass_fusion import (
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
from ...services.magicclass.course_context import assert_course_access
from ...services.magicclass.fusion_client import UNSET, MagicClassFusionClient
from ...services.magicclass.fusion_errors import FusionInvalidRequest, FusionUnavailable
from ..deps import current_user
from ..magicclass_gateway import build_fusion_client, require_idempotency_key, require_revision

router = APIRouter(prefix="/courses", tags=["课堂工作台"])

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 50
MAX_IDEMPOTENCY_KEY_LENGTH = 200


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> MagicClassFusionClient:
    """构造内部客户端。

    配置取自容器而不是应用级单例：路由的其它依赖都走容器，混用两套配置源会让
    测试里的覆盖静默失效（真实症状是"开关明明是开的却报未启用"）。
    """
    return build_fusion_client(container, client_type=MagicClassFusionClient)


def _require_fusion_enabled(settings: Settings) -> None:
    if not settings.magicclass_fusion_enabled:
        # An empty list would read as "you have no workspaces" — a different and
        # wrong answer when the runtime is simply switched off.
        #
        # `details.reason` is the stable half of the answer: the status route
        # already distinguishes "never enabled" from "cannot reach it", and a
        # 503 body that carries only a sentence forces the client to guess which
        # of the two it got. The reason code travels so the browser can say
        # "this deployment did not enable it" instead of "try again later".
        raise FusionUnavailable("受管 magic class 服务未启用", details={"reason": "fusion_disabled"})


def _require_idempotency_key(value: Optional[str]) -> str:
    return require_idempotency_key(
        value,
        missing_message="创建请求必须携带 Idempotency-Key",
        max_length=MAX_IDEMPOTENCY_KEY_LENGTH,
    )


def _require_revision(value: Optional[str]) -> int:
    """Read the client's expected revision from `If-Match`.

    `*` is refused: "match anything" is precisely the lost update this header
    exists to prevent, and a client that sends it has not read the row it is
    about to overwrite.
    """
    return require_revision(value)


def _limit(value: int) -> int:
    return max(1, min(int(value), MAX_PAGE_LIMIT))


def _workspace_out(payload: Dict[str, Any]) -> WorkspaceOut:
    return WorkspaceOut(**{k: payload[k] for k in WorkspaceOut.model_fields if k in payload})


def _stage_summary(payload: Dict[str, Any]) -> StageSummaryOut:
    return StageSummaryOut(**{k: payload[k] for k in StageSummaryOut.model_fields if k in payload})


# ===== workspaces =====


@router.get(
    "/{course_id}/workspaces",
    response_model=WorkspaceListOut,
    summary="列出工作台",
    responses={
        200: {
            "description": "工作台列表，按不透明游标分页",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "列出工作台",
                            "value": {
                                "items": [
                                    {
                                        "id": "ws_001",
                                        "course_id": "course_001",
                                        "name": "高等数学·期末冲刺",
                                        "description": "按章节整理的高数复习工作台",
                                        "folder_id": "fd_001",
                                        "revision": 3,
                                        "created_at": "2026-09-01T08:00:00+00:00",
                                        "updated_at": "2026-10-05T09:30:00+00:00",
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
async def list_workspaces(
    course_id: str,
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[str] = Query(None, max_length=512),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> WorkspaceListOut:
    """列出当前课程下用户可见的学习工作台。

    - 仅返回归属过滤后的工作台，游标只在归属范围内收窄。
    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    payload = await client.list_workspaces(
        user_id=str(user.id), course_id=course_id, limit=_limit(limit), cursor=cursor
    )
    return WorkspaceListOut(
        items=[_workspace_out(item) for item in payload.get("items", [])],
        next_cursor=payload.get("next_cursor"),
    )


@router.post(
    "/{course_id}/workspaces",
    response_model=WorkspaceOut,
    status_code=201,
    summary="创建工作台",
    responses={
        201: {
            "description": "创建工作台成功，返回工作台详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "创建工作台",
                            "value": {
                                "id": "ws_001",
                                "course_id": "course_001",
                                "name": "高等数学·期末冲刺",
                                "description": "按章节整理的高数复习工作台",
                                "folder_id": "fd_001",
                                "revision": 1,
                                "created_at": "2026-10-05T09:30:00+00:00",
                                "updated_at": "2026-10-05T09:30:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def create_workspace(
    course_id: str,
    body: Annotated[
        WorkspaceCreateIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "创建工作台",
                    "value": {
                        "name": "高等数学·期末冲刺",
                        "description": "按章节整理的高数复习工作台",
                        "folder_id": "fd_001",
                    },
                }
            }
        ),
    ],
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> WorkspaceOut:
    """在当前课程下创建一个学习工作台。

    - 必须携带 Idempotency-Key；缺失返回 400（MAGICCLASS_INVALID_REQUEST）。
    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
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


@router.get(
    "/{course_id}/workspaces/{workspace_id}",
    response_model=WorkspaceOut,
    summary="读取工作台",
    responses={
        200: {
            "description": "返回指定工作台详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取工作台",
                            "value": {
                                "id": "ws_001",
                                "course_id": "course_001",
                                "name": "高等数学·期末冲刺",
                                "description": "按章节整理的高数复习工作台",
                                "folder_id": "fd_001",
                                "revision": 3,
                                "created_at": "2026-09-01T08:00:00+00:00",
                                "updated_at": "2026-10-05T09:30:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def get_workspace(
    course_id: str,
    workspace_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> WorkspaceOut:
    """读取指定工作台的详情。

    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    return _workspace_out(
        await client.get_workspace(user_id=str(user.id), course_id=course_id, workspace_id=workspace_id)
    )


@router.patch(
    "/{course_id}/workspaces/{workspace_id}",
    response_model=WorkspaceOut,
    summary="更新工作台",
    responses={
        200: {
            "description": "更新工作台成功，返回更新后的工作台详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "更新工作台",
                            "value": {
                                "id": "ws_001",
                                "course_id": "course_001",
                                "name": "高等数学·期末冲刺（修订）",
                                "description": "按章节整理的高数复习工作台",
                                "folder_id": "fd_001",
                                "revision": 4,
                                "created_at": "2026-09-01T08:00:00+00:00",
                                "updated_at": "2026-10-06T10:15:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def update_workspace(
    course_id: str,
    workspace_id: str,
    body: Annotated[
        WorkspaceUpdateIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "更新工作台名称",
                    "value": {"name": "高等数学·期末冲刺（修订）"},
                }
            }
        ),
    ],
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> WorkspaceOut:
    """更新工作台的名称、说明或归档位置。

    - 必须携带 If-Match（当前 revision），不接受 `*`；缺失或非法返回 400（MAGICCLASS_INVALID_REQUEST）。
    - 至少要提供一个可更新字段，否则返回 400；服务端 revision 不一致返回 409（MAGICCLASS_REVISION_CONFLICT）。
    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
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


@router.delete(
    "/{course_id}/workspaces/{workspace_id}",
    summary="删除工作台",
    responses={
        200: {
            "description": "删除工作台成功",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "删除工作台",
                            "value": {"deleted": True},
                        }
                    }
                }
            },
        }
    },
)
async def delete_workspace(
    course_id: str,
    workspace_id: str,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """删除指定工作台。

    - 必须携带 If-Match（当前 revision），不接受 `*`；缺失或非法返回 400（MAGICCLASS_INVALID_REQUEST）。
    - 服务端 revision 不一致返回 409（MAGICCLASS_REVISION_CONFLICT）。
    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
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


@router.get(
    "/{course_id}/workspaces/{workspace_id}/stages",
    response_model=StageListOut,
    summary="列出舞台",
    responses={
        200: {
            "description": "舞台列表（摘要，不含 document），按不透明游标分页",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "列出舞台",
                            "value": {
                                "items": [
                                    {
                                        "id": "stg_001",
                                        "workspace_id": "ws_001",
                                        "course_id": "course_001",
                                        "title": "第一讲·极限与连续",
                                        "revision": 2,
                                        "dsl_version": "1.0",
                                        "created_at": "2026-09-20T08:00:00+00:00",
                                        "updated_at": "2026-10-05T09:30:00+00:00",
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
async def list_stages(
    course_id: str,
    workspace_id: str,
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[str] = Query(None, max_length=512),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> StageListOut:
    """列出指定工作台下的舞台摘要（不含 document）。

    - 列表是导航面，只返回摘要；打开单个舞台时才取全文。
    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
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


@router.post(
    "/{course_id}/workspaces/{workspace_id}/stages",
    response_model=StageOut,
    status_code=201,
    summary="创建舞台",
    responses={
        201: {
            "description": "创建舞台成功，返回带完整文档的舞台",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "创建舞台",
                            "value": {
                                "id": "stg_001",
                                "workspace_id": "ws_001",
                                "course_id": "course_001",
                                "title": "第一讲·极限与连续",
                                "revision": 1,
                                "dsl_version": "1.0",
                                "created_at": "2026-10-05T09:30:00+00:00",
                                "updated_at": "2026-10-05T09:30:00+00:00",
                                "document": {"stage": {"id": "stg_001", "name": "第一讲·极限与连续"}, "scenes": []},
                            },
                        }
                    }
                }
            },
        }
    },
)
async def create_stage(
    course_id: str,
    workspace_id: str,
    body: StageCreateIn = Body(
        ...,
        openapi_examples={
            "成功": {
                "summary": "创建舞台",
                "value": {"title": "第一讲·极限与连续"},
            }
        },
    ),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> StageOut:
    """在指定工作台下创建一个舞台。

    - 必须携带 Idempotency-Key；缺失返回 400（MAGICCLASS_INVALID_REQUEST）。
    - 省略 document 表示创建一个只有标题的空舞台。
    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
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


@router.get(
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}",
    response_model=StageOut,
    summary="读取舞台",
    responses={
        200: {
            "description": "返回指定舞台，含完整 DSL 文档",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取舞台",
                            "value": {
                                "id": "stg_001",
                                "workspace_id": "ws_001",
                                "course_id": "course_001",
                                "title": "第一讲·极限与连续",
                                "revision": 2,
                                "dsl_version": "1.0",
                                "created_at": "2026-09-20T08:00:00+00:00",
                                "updated_at": "2026-10-05T09:30:00+00:00",
                                "document": {"stage": {"id": "stg_001", "name": "第一讲·极限与连续"}, "scenes": []},
                            },
                        }
                    }
                }
            },
        }
    },
)
async def get_stage(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> StageOut:
    """读取指定舞台，返回带完整 DSL 文档的舞台。

    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    return StageOut(
        **await client.get_stage(
            user_id=str(user.id), course_id=course_id, workspace_id=workspace_id, stage_id=stage_id
        )
    )


@router.put(
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}",
    response_model=StageOut,
    summary="替换舞台",
    responses={
        200: {
            "description": "整份替换舞台成功，返回替换后的舞台",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "替换舞台",
                            "value": {
                                "id": "stg_001",
                                "workspace_id": "ws_001",
                                "course_id": "course_001",
                                "title": "第一讲·极限与连续（重排）",
                                "revision": 3,
                                "dsl_version": "1.0",
                                "created_at": "2026-09-20T08:00:00+00:00",
                                "updated_at": "2026-10-06T10:15:00+00:00",
                                "document": {"stage": {"id": "stg_001", "name": "第一讲·极限与连续（重排）"}, "scenes": []},
                            },
                        }
                    }
                }
            },
        }
    },
)
async def replace_stage(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    body: Annotated[
        StageReplaceIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "整份替换舞台文档",
                    "value": {
                        "document": {"stage": {"id": "stg_001", "name": "第一讲·极限与连续（重排）"}, "scenes": []},
                        "title": "第一讲·极限与连续（重排）",
                    },
                }
            }
        ),
    ],
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> StageOut:
    """整份替换指定舞台的文档。

    - 必须携带 If-Match（当前 revision），不接受 `*`；缺失或非法返回 400（MAGICCLASS_INVALID_REQUEST）。
    - 服务端 revision 不一致返回 409（MAGICCLASS_REVISION_CONFLICT）。
    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
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


@router.delete(
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}",
    summary="删除舞台",
    responses={
        200: {
            "description": "删除舞台成功",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "删除舞台",
                            "value": {"deleted": True},
                        }
                    }
                }
            },
        }
    },
)
async def delete_stage(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """删除指定舞台。

    - 必须携带 If-Match（当前 revision），不接受 `*`；缺失或非法返回 400（MAGICCLASS_INVALID_REQUEST）。
    - 服务端 revision 不一致返回 409（MAGICCLASS_REVISION_CONFLICT）。
    - 需要已登录且对该课程有访问权限；受管 magic class 服务未启用时返回 503。
    """
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
