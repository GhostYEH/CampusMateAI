from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, ValidationError
from fastapi import HTTPException

CATEGORIES = "^(campus|study|life|secondhand|question|activity|experience|recruit|errand|lostfound|other)$"

CATEGORY_META: list[dict[str, Any]] = [
    {"key": "question", "label": "提问", "description": "学习/生活求助问答", "icon": "PhQuestion", "color": "#3b82f6"},
    {"key": "recruit", "label": "招募", "description": "组队/招新/活动招募", "icon": "PhUsers", "color": "#8b5cf6"},
    {"key": "errand", "label": "带价帮忙", "description": "跑腿/代取/带价帮忙", "icon": "PhHandCoins", "color": "#f59e0b"},
    {"key": "lostfound", "label": "失物招领", "description": "寻物/招领", "icon": "PhMagnifyingGlass", "color": "#ef4444"},
    {"key": "campus", "label": "校园动态", "description": "日常校园话题", "icon": "PhBuildings", "color": "#10b981"},
    {"key": "study", "label": "学习交流", "description": "课程/资料/学习方法", "icon": "PhBookOpen", "color": "#06b6d4"},
    {"key": "life", "label": "生活随笔", "description": "生活分享", "icon": "PhCoffee", "color": "#ec4899"},
    {"key": "secondhand", "label": "二手交易", "description": "闲置物品交易", "icon": "PhStorefront", "color": "#6366f1"},
    {"key": "activity", "label": "活动", "description": "活动通知/回顾", "icon": "PhCalendarHeart", "color": "#14b8a6"},
    {"key": "experience", "label": "经验分享", "description": "考研/求职/实习经验", "icon": "PhLightbulb", "color": "#f97316"},
    {"key": "other", "label": "其它", "description": "其它", "icon": "PhDotsThree", "color": "#6b7280"},
]


class RecruitExtra(BaseModel):
    headcount: Optional[int] = Field(None, ge=1, le=100)
    deadline: Optional[str] = Field(None, max_length=32)
    location: Optional[str] = Field(None, max_length=200)


class ErrandExtra(BaseModel):
    price: Optional[float] = Field(None, ge=0)
    location: Optional[str] = Field(None, max_length=200)
    deadline: Optional[str] = Field(None, max_length=32)


class LostFoundExtra(BaseModel):
    kind: str = Field(..., pattern="^(lost|found)$")
    location: Optional[str] = Field(None, max_length=200)
    contact: Optional[str] = Field(None, max_length=200)
    contact_visibility: str = Field("private", pattern="^(private|public)$")


EXTRA_SCHEMAS: dict[str, type[BaseModel]] = {
    "recruit": RecruitExtra,
    "errand": ErrandExtra,
    "lostfound": LostFoundExtra,
}


def validate_extra(category: str, extra: dict | None) -> dict:
    """按分类校验 extra，返回清洗后的 dict。"""
    if extra is None:
        return {}
    schema = EXTRA_SCHEMAS.get(category)
    if schema is None:
        return extra
    try:
        return schema(**extra).model_dump(exclude_none=True)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"extra 校验失败: {e.errors()}")


class PostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    content: str = Field(..., min_length=1, max_length=10000)
    category: str = Field("campus", pattern=CATEGORIES)
    images: list[str] = Field(default_factory=list, max_length=9)
    is_anonymous: bool = False
    extra: Optional[dict[str, Any]] = None


class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=120)
    content: Optional[str] = Field(None, min_length=1, max_length=10000)
    category: Optional[str] = Field(None, pattern=CATEGORIES)
    images: Optional[list[str]] = Field(None, max_length=9)
    is_anonymous: Optional[bool] = None
    extra: Optional[dict[str, Any]] = None


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    parent_comment_id: Optional[str] = None
    is_anonymous: bool = False


class ReportCreate(BaseModel):
    target_type: str = Field(..., pattern="^(post|comment)$")
    target_id: str = Field(..., min_length=1, max_length=128)
    reason: str = Field(..., pattern="^(垃圾广告|辱骂攻击|色情低俗|违法违规|隐私泄露|诈骗|其它)$")
    details: Optional[str] = Field(None, max_length=1000)


class UploadImageResponse(BaseModel):
    url: str
    filename: str
    size: int
