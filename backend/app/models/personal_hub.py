"""个人中心数据行模型 —— 用户私有文件与跨模块收藏。

与 `personal_tasks` 一样按 `user_id` 隔离，仅 JWT 持有者可读写。
`favorites.id` 为逻辑标识(如 "file:abc")，
不同用户可收藏同一个对象，因此表使用 (user_id, id) 复合主键。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PersonalFileRow:
    id: str
    user_id: str
    name: str
    category: Optional[str] = None
    size_label: Optional[str] = None
    updated_at: Optional[str] = None
    source: Optional[str] = None
    is_favorite: bool = False
    created_at: str = ""

    @classmethod
    def from_row(cls, row) -> "PersonalFileRow":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            category=row["category"],
            size_label=row["size_label"],
            updated_at=row["updated_at"],
            source=row["source"],
            is_favorite=bool(row["is_favorite"]),
            created_at=row["created_at"],
        )


@dataclass
class FavoriteRow:
    user_id: str
    id: str
    title: str
    type: Optional[str] = None
    subtitle: Optional[str] = None
    saved_at: Optional[str] = None
    source_route: Optional[str] = None
    created_at: str = ""

    @classmethod
    def from_row(cls, row) -> "FavoriteRow":
        return cls(
            user_id=row["user_id"],
            id=row["id"],
            title=row["title"],
            type=row["type"],
            subtitle=row["subtitle"],
            saved_at=row["saved_at"],
            source_route=row["source_route"],
            created_at=row["created_at"],
        )


__all__ = ["PersonalFileRow", "FavoriteRow"]
