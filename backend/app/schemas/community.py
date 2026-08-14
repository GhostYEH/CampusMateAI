from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

CATEGORIES = "^(campus|study|life|secondhand|question|activity|experience|other)$"

class PostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    content: str = Field(..., min_length=1, max_length=10000)
    category: str = Field("campus", pattern=CATEGORIES)
    images: list[str] = Field(default_factory=list, max_length=4)
    is_anonymous: bool = False

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    parent_comment_id: Optional[str] = None
    is_anonymous: bool = False

class ReportCreate(BaseModel):
    target_type: str = Field(..., pattern="^(post|comment)$")
    target_id: str = Field(..., min_length=1, max_length=128)
    reason: str = Field(..., pattern="^(垃圾广告|辱骂攻击|色情低俗|违法违规|隐私泄露|诈骗|其它)$")
    details: Optional[str] = Field(None, max_length=1000)

