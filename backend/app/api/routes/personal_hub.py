"""个人中心路由 —— 用户私有文件与跨模块收藏。

权限:
- 所有接口必须 JWT 认证
- 数据按 `user_id` 隔离,JWT 用户只能读写自己的文件 / 收藏
- 跨用户访问统一返回 404(不泄露存在性)

映射到安卓端「我的文件」「收藏夹」两个分区。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
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

router = APIRouter(prefix="/personal-hub", tags=["personal-hub"])


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


@router.get("/files", response_model=list[PersonalFileOut])
def list_files(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> list[PersonalFileOut]:
    rows = container.personal_file_repository.list_files(user.id)
    return [_file_to_out(r) for r in rows]


@router.post("/files", response_model=PersonalFileOut, status_code=201)
def create_file(
    req: PersonalFileCreate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> PersonalFileOut:
    row = container.personal_file_repository.create_file(
        user_id=user.id,
        name=req.name,
        category=req.category,
        source=req.source,
        size_label=req.size_label,
    )
    return _file_to_out(row)


@router.patch("/files/{file_id}", response_model=PersonalFileOut)
def update_file(
    file_id: str,
    req: PersonalFileUpdate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> PersonalFileOut:
    row = container.personal_file_repository.update_file(
        file_id, user_id=user.id, fields=req.model_dump(exclude_unset=True)
    )
    if row is None:
        raise NotFoundError("文件不存在")
    return _file_to_out(row)


class FileFavoriteToggle(BaseModel):
    favorite: bool


@router.post("/files/{file_id}/favorite", response_model=PersonalFileOut)
def toggle_file_favorite(
    file_id: str,
    req: FileFavoriteToggle,
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


@router.delete("/files/{file_id}")
def delete_file(
    file_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> dict:
    ok = container.personal_file_repository.delete_file(file_id, user_id=user.id)
    if not ok:
        raise NotFoundError("文件不存在")
    # 同步清理该用户对该文件的收藏
    container.favorite_repository.remove_favorite(f"file:{file_id}", user_id=user.id)
    return {"ok": True}


# ===== 收藏夹 =====


@router.get("/favorites", response_model=list[FavoriteOut])
def list_favorites(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> list[FavoriteOut]:
    rows = container.favorite_repository.list_favorites(user.id)
    return [_favorite_to_out(r) for r in rows]


@router.post("/favorites", response_model=FavoriteOut, status_code=201)
def add_favorite(
    req: FavoriteCreate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> FavoriteOut:
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


@router.delete("/favorites/{favorite_id}")
def remove_favorite(
    favorite_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> dict:
    ok = container.favorite_repository.remove_favorite(favorite_id, user_id=user.id)
    if not ok:
        raise NotFoundError("收藏不存在")
    return {"ok": True}


__all__ = ["router"]
