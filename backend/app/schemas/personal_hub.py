"""个人中心请求/响应 schema (Pydantic v2)。

涵盖: 用户私有文件 CRUD、跨模块收藏 add/remove。
所有时间字段以 ISO 8601 字符串(带时区)表示。
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PersonalFileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    category: Optional[str] = Field(None, max_length=64)
    source: Optional[str] = Field(None, max_length=128)
    size_label: Optional[str] = Field(None, max_length=32)


class PersonalFileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256)
    category: Optional[str] = Field(None, max_length=64)
    source: Optional[str] = Field(None, max_length=128)
    size_label: Optional[str] = Field(None, max_length=32)


class PersonalFileOut(BaseModel):
    id: str
    name: str
    category: Optional[str] = None
    size_label: Optional[str] = None
    updated_at: Optional[str] = None
    source: Optional[str] = None
    is_favorite: bool = False


class FavoriteCreate(BaseModel):
    """添加收藏。`id` 为客户端逻辑标识(如 "file:abc"、"activity:xyz")。"""
    id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=256)
    type: Optional[str] = Field(None, max_length=32)
    subtitle: Optional[str] = Field(None, max_length=256)
    saved_at: Optional[str] = None
    source_route: Optional[str] = Field(None, max_length=64)


class FavoriteOut(BaseModel):
    id: str
    title: str
    type: Optional[str] = None
    subtitle: Optional[str] = None
    saved_at: Optional[str] = None
    source_route: Optional[str] = None


__all__ = [
    "PersonalFileCreate",
    "PersonalFileUpdate",
    "PersonalFileOut",
    "FavoriteCreate",
    "FavoriteOut",
]
