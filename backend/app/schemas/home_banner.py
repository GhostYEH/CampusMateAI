from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


HomeBannerAction = Literal["CPM_ASSISTANT", "CHAOXING", "EDU_SYSTEM", "TASKS", "COMMUNITY"]
HomeBannerTheme = Literal["INDIGO", "CYAN", "VIOLET", "ORANGE", "GREEN"]


class HomeBannerWrite(BaseModel):
    eyebrow: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=80)
    subtitle: str = Field(min_length=1, max_length=160)
    cta_label: str = Field(min_length=1, max_length=30)
    image_url: str = Field(min_length=1, max_length=500)
    action_key: HomeBannerAction
    theme_key: HomeBannerTheme
    sort_order: int = Field(default=0, ge=-10000, le=10000)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_window(self) -> "HomeBannerWrite":
        if self.starts_at is not None and self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        return self


class HomeBannerOut(BaseModel):
    id: str
    eyebrow: str
    title: str
    subtitle: str
    cta_label: str
    image_url: str
    action_key: HomeBannerAction
    theme_key: HomeBannerTheme
    sort_order: int
    status: Literal["DRAFT", "PUBLISHED", "ARCHIVED"]
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    created_at: str
    updated_at: str


class HomeBannerFeed(BaseModel):
    items: list[HomeBannerOut]
    updated_at: Optional[str] = None


class HomeBannerImageOut(BaseModel):
    image_url: str
    filename: str
    size: int


__all__ = ["HomeBannerFeed", "HomeBannerImageOut", "HomeBannerOut", "HomeBannerWrite"]
