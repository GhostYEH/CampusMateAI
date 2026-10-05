"""个人中心路由 —— 用户私有文件与跨模块收藏。

权限:
- 所有接口必须 JWT 认证
- 数据按 `user_id` 隔离,JWT 用户只能读写自己的文件 / 收藏
- 跨用户访问统一返回 404(不泄露存在性)

映射到安卓端「我的文件」「收藏夹」两个分区。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

from ...core.exceptions import NotFoundError
from ...models.multi_role import UserRow
from ...schemas.personal_hub import (
    FavoriteCreate,
    FavoriteOut,
    PersonalFileCreate,
    PersonalFileOut,
    PersonalFileUpdate,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user

router = APIRouter(prefix="/personal-hub", tags=["个人中心"])


def _container() -> ServiceContainer:
    return get_container()


def _file_to_out(row) -> PersonalFileOut:
    return PersonalFileOut(
        id=row.id,
        name=row.name,
        category=row.category,
        size_label=row.size_label,
        updated_at=row.updated_at,
        source=row.source,
        is_favorite=row.is_favorite,
    )


def _favorite_to_out(row) -> FavoriteOut:
    return FavoriteOut(
        id=row.id,
        title=row.title,
        type=row.type,
        subtitle=row.subtitle,
        saved_at=row.saved_at,
        source_route=row.source_route,
    )


# ===== 我的文件 =====


@router.get(
    "/files",
    response_model=list[PersonalFileOut],
    summary="列出个人文件",
    responses={
        200: {
            "description": "返回当前用户的个人文件列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "个人文件列表",
                            "value": [
                                {
                                    "id": "file_practice_cert",
                                    "name": "暑期实践证明.pdf",
                                    "category": "证明文件",
                                    "size_label": "1.2 MB",
                                    "updated_at": "2026-10-05T20:10:00+08:00",
                                    "source": "personal_hub",
                                    "is_favorite": True,
                                }
                            ],
                        }
                    }
                }
            },
        },
    },
)
def list_files(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> list[PersonalFileOut]:
    """列出当前用户的个人文件。"""
    rows = container.personal_file_repository.list_files(user.id)
    return [_file_to_out(r) for r in rows]


@router.post(
    "/files",
    response_model=PersonalFileOut,
    status_code=201,
    summary="创建个人文件",
    responses={
        201: {
            "description": "创建成功，返回新建的个人文件",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "新建的个人文件",
                            "value": {
                                "id": "file_practice_cert",
                                "name": "暑期实践证明.pdf",
                                "category": "证明文件",
                                "size_label": "1.2 MB",
                                "updated_at": "2026-10-05T20:10:00+08:00",
                                "source": "personal_hub",
                                "is_favorite": False,
                            },
                        }
                    }
                }
            },
        },
    },
)
def create_file(
    req: Annotated[
        PersonalFileCreate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "创建证明文件",
                    "value": {
                        "name": "暑期实践证明.pdf",
                        "category": "证明文件",
                        "source": "personal_hub",
                        "size_label": "1.2 MB",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> PersonalFileOut:
    """为当前用户创建一条个人文件记录，返回创建结果。"""
    row = container.personal_file_repository.create_file(
        user_id=user.id,
        name=req.name,
        category=req.category,
        source=req.source,
        size_label=req.size_label,
    )
    return _file_to_out(row)


@router.patch(
    "/files/{file_id}",
    response_model=PersonalFileOut,
    summary="更新个人文件",
    responses={
        200: {
            "description": "更新成功，返回最新的个人文件",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "更新后的个人文件",
                            "value": {
                                "id": "file_practice_cert",
                                "name": "暑期实践证明(终版).pdf",
                                "category": "证明文件",
                                "size_label": "1.2 MB",
                                "updated_at": "2026-10-06T09:00:00+08:00",
                                "source": "personal_hub",
                                "is_favorite": True,
                            },
                        }
                    }
                }
            },
        },
    },
)
def update_file(
    file_id: str,
    req: Annotated[
        PersonalFileUpdate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "重命名文件",
                    "value": {"name": "暑期实践证明(终版).pdf", "category": "证明文件"},
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> PersonalFileOut:
    """按字段更新当前用户的个人文件；文件不存在或不属于当前用户返回 404。"""
    row = container.personal_file_repository.update_file(
        file_id, user_id=user.id, fields=req.model_dump(exclude_unset=True)
    )
    if row is None:
        raise NotFoundError("文件不存在")
    return _file_to_out(row)


class FileFavoriteToggle(BaseModel):
    favorite: bool


@router.post(
    "/files/{file_id}/favorite",
    response_model=PersonalFileOut,
    summary="设置文件收藏状态",
    responses={
        200: {
            "description": "返回更新收藏状态后的个人文件",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "已取消收藏的文件",
                            "value": {
                                "id": "file_practice_cert",
                                "name": "暑期实践证明.pdf",
                                "category": "证明文件",
                                "size_label": "1.2 MB",
                                "updated_at": "2026-10-06T09:05:00+08:00",
                                "source": "personal_hub",
                                "is_favorite": False,
                            },
                        }
                    }
                }
            },
        },
    },
)
def toggle_file_favorite(
    file_id: str,
    req: Annotated[
        FileFavoriteToggle,
        Body(
            openapi_examples={
                "成功": {"summary": "取消收藏", "value": {"favorite": False}}
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> PersonalFileOut:
    """设置文件收藏状态(同步移除/加入收藏夹由客户端维护)。"""
    row = container.personal_file_repository.set_favorite(
        file_id, user_id=user.id, favorite=req.favorite
    )
    if row is None:
        raise NotFoundError("文件不存在")
    return _file_to_out(row)


@router.delete(
    "/files/{file_id}",
    summary="删除个人文件",
    responses={
        200: {
            "description": "删除成功，并同步清理该文件对应的收藏",
            "content": {
                "application/json": {
                    "examples": {"成功": {"summary": "删除成功", "value": {"ok": True}}}
                }
            },
        },
    },
)
def delete_file(
    file_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> dict:
    """删除当前用户的个人文件，并同步清理该文件的收藏；不存在返回 404。"""
    ok = container.personal_file_repository.delete_file(file_id, user_id=user.id)
    if not ok:
        raise NotFoundError("文件不存在")
    # 同步清理该用户对该文件的收藏
    container.favorite_repository.remove_favorite(f"file:{file_id}", user_id=user.id)
    return {"ok": True}


# ===== 收藏夹 =====


@router.get(
    "/favorites",
    response_model=list[FavoriteOut],
    summary="列出收藏",
    responses={
        200: {
            "description": "返回当前用户的收藏列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "收藏列表",
                            "value": [
                                {
                                    "id": "file:file_practice_cert",
                                    "title": "暑期实践证明.pdf",
                                    "type": "file",
                                    "subtitle": "证明文件",
                                    "saved_at": "2026-10-05T20:12:00+08:00",
                                    "source_route": "/profile/files",
                                }
                            ],
                        }
                    }
                }
            },
        },
    },
)
def list_favorites(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> list[FavoriteOut]:
    """列出当前用户的收藏。"""
    rows = container.favorite_repository.list_favorites(user.id)
    return [_favorite_to_out(r) for r in rows]


@router.post(
    "/favorites",
    response_model=FavoriteOut,
    status_code=201,
    summary="添加收藏",
    responses={
        201: {
            "description": "添加成功，返回新建的收藏记录",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "新建的收藏",
                            "value": {
                                "id": "file:file_practice_cert",
                                "title": "暑期实践证明.pdf",
                                "type": "file",
                                "subtitle": "证明文件",
                                "saved_at": "2026-10-05T20:12:00+08:00",
                                "source_route": "/profile/files",
                            },
                        }
                    }
                }
            },
        },
    },
)
def add_favorite(
    req: Annotated[
        FavoriteCreate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "收藏个人文件",
                    "value": {
                        "id": "file:file_practice_cert",
                        "title": "暑期实践证明.pdf",
                        "type": "file",
                        "subtitle": "证明文件",
                        "saved_at": "2026-10-05T20:12:00+08:00",
                        "source_route": "/profile/files",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> FavoriteOut:
    """添加一条收藏记录并返回创建结果。"""
    row = container.favorite_repository.add_favorite(
        user_id=user.id,
        favorite_id=req.id,
        title=req.title,
        type=req.type,
        subtitle=req.subtitle,
        saved_at=req.saved_at,
        source_route=req.source_route,
    )
    return _favorite_to_out(row)


@router.delete(
    "/favorites/{favorite_id}",
    summary="移除收藏",
    responses={
        200: {
            "description": "移除成功",
            "content": {
                "application/json": {
                    "examples": {"成功": {"summary": "移除成功", "value": {"ok": True}}}
                }
            },
        },
    },
)
def remove_favorite(
    favorite_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> dict:
    """移除当前用户的一条收藏；不存在或不属于当前用户返回 404。"""
    ok = container.favorite_repository.remove_favorite(favorite_id, user_id=user.id)
    if not ok:
        raise NotFoundError("收藏不存在")
    return {"ok": True}


__all__ = ["router"]
