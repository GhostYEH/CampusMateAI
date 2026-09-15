"""统一"今日待办"响应 schema (Pydantic v2)。

这是全站唯一的事实源: 首页今日任务区、学习陪伴右侧今日待办、任务总览"今天"分组、
全局待办角标都读同一个接口、同一种 DTO，前端只负责展示与触发操作。

约定:
- 所有时间字段为 ISO 8601 字符串(带时区)；"今天"由后端按 Asia/Shanghai 自然日判定。
- `status` 取值固定为 pending/completed/overdue/submitted/graded。
- `editable` / `completable` 表达操作边界: 学习通作业与考试由学习通决定状态，
  默认只读，不允许在 CampusMate 勾选完成。
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class AgendaSourceState(BaseModel):
    """单个数据来源的健康状态，用于区分"真的没有"与"取不到"。"""

    state: str = "ok"
    # ok | not_bound | never_synced | empty | stale | expired | partial | failed | unavailable
    message: Optional[str] = None
    item_count: int = 0
    last_synced_at: Optional[str] = None
    # 学习通登录态(来自 /chaoxing/status 的进程内缓存，今日待办自身不触网)。
    # online | expired | offline | unavailable | unknown
    auth_state: str = "unknown"


class AgendaSourcesOut(BaseModel):
    chaoxing: AgendaSourceState = Field(default_factory=AgendaSourceState)
    personal: AgendaSourceState = Field(default_factory=AgendaSourceState)
    schedule: AgendaSourceState = Field(default_factory=AgendaSourceState)


class AgendaSummaryOut(BaseModel):
    total: int = 0
    pending: int = 0
    completed: int = 0
    overdue: int = 0


class AgendaItemOut(BaseModel):
    id: str
    # chaoxing | personal | academic
    source: str
    # assignment | exam | personal_task | class
    kind: str
    source_id: str
    course_id: Optional[str] = None
    course_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    starts_at: Optional[str] = None
    deadline: Optional[str] = None
    # pending | completed | overdue | submitted | graded
    status: str = "pending"
    priority: str = "medium"
    editable: bool = False
    completable: bool = False
    route: Optional[str] = None
    source_url: Optional[str] = None
    last_synced_at: Optional[str] = None


class TodayAgendaOut(BaseModel):
    date: str
    timezone: str = "Asia/Shanghai"
    generated_at: str
    last_chaoxing_synced_at: Optional[str] = None
    # 学习通数据已过期(超过新鲜窗口)时为真，客户端应提示"数据可能不是最新"。
    stale: bool = False
    summary: AgendaSummaryOut = Field(default_factory=AgendaSummaryOut)
    sources: AgendaSourcesOut = Field(default_factory=AgendaSourcesOut)
    items: List[AgendaItemOut] = Field(default_factory=list)


__all__ = [
    "AgendaItemOut",
    "AgendaSourceState",
    "AgendaSourcesOut",
    "AgendaSummaryOut",
    "TodayAgendaOut",
]
