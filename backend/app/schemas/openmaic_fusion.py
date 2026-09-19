"""Schemas for the managed OpenMAIC fusion boundary."""

from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class FusionState(str, Enum):
    """受管服务的单一状态判据（客户端只需 switch 这一个字段）。

    - ``disabled``：融合开关关闭，网关**不会**尝试调用受管服务。
    - ``unavailable``：开关开启，但受管服务不可达/未配置/拒绝我们的断言。
    - ``degraded``：受管服务在线，但自身依赖（数据库等）未就绪。
    - ``ready``：受管服务与依赖都就绪，``capabilities`` 可信。
    """

    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    READY = "ready"


class FusionStatus(BaseModel):
    """网关对受管 OpenMAIC 服务的公开状态。

    ``state`` 是唯一判据；``enabled`` / ``available`` 保留为便捷布尔量，
    供只关心"能不能用"的旧客户端使用。``capabilities`` 只在 ``state=ready``
    时非空 —— 依赖没就绪时不得声称任何能力可用。
    """

    enabled: bool
    available: bool
    state: FusionState
    capabilities: List[str] = Field(default_factory=list)
    reason: str


class FusionRecentItem(BaseModel):
    """一条"最近学习内容"，已按服务端权限过滤。

    ``href`` 是 **CampusMate 站内**深链（不是 OpenMAIC 地址），学生点击后
    回到课程详情的智能辅导栏目；``classroom_url`` 才是可选的外部课堂地址，
    且仅在公开 Origin 已配置时才下发。
    """

    kind: Literal["classroom"]
    id: str
    course_id: str
    course_name: str
    title: str
    mode: Optional[str] = None
    status: str
    scenes_count: Optional[int] = None
    href: str
    classroom_url: Optional[str] = None
    classroom_url_unavailable_reason: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class FusionRecentOut(BaseModel):
    items: List[FusionRecentItem] = Field(default_factory=list)
    limit: int
    has_more: bool = False


__all__ = [
    "FusionState",
    "FusionStatus",
    "FusionRecentItem",
    "FusionRecentOut",
]
