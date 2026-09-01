"""学习陪伴 — 请求/响应 schema (Pydantic v2)。

涵盖: 学习会话 CRUD、状态机动作、休息记录、任务拆解。
所有时间字段以 ISO 8601 字符串(带时区)表示。
"""
from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StudyGoalUpdate(BaseModel):
    target_minutes: int = Field(..., ge=15, le=480)


class StudyGoalOut(BaseModel):
    target_minutes: int
    updated_at: str


# ===== 学习会话 =====


class StudySessionCreate(BaseModel):
    mode: Literal["focus", "short_break", "long_break"] = "focus"
    planned_duration_seconds: Optional[int] = Field(None, ge=300, le=14400)
    goal: Optional[str] = Field(None, max_length=500, description="本次学习目标(自由文本)")
    related_task_id: Optional[str] = Field(
        None, max_length=128,
        description="关联的个人待办 ID(PersonalTask ID,需属于当前用户且未软删除)",
    )


class StudySessionUpdate(BaseModel):
    """部分更新。goal/related_task_id 仅未结束会话可改;
    self_report/self_report_tags/expression_signal 任意状态可改。
    """

    goal: Optional[str] = Field(None, max_length=500)
    related_task_id: Optional[str] = Field(
        None, max_length=128,
        description="关联的个人待办 ID(需属于当前用户且未软删除)",
    )
    self_report: Optional[str] = Field(None, max_length=2000, description="用户主动填写的文字感受")
    self_report_tags: Optional[List[str]] = Field(None, max_length=20)
    expression_signal: Optional[Any] = Field(
        None, description="预留 CNN 表情信号(本轮不实现 CNN,仅透传存储)"
    )


class StudyBehaviorSummary(BaseModel):
    """本机行为辅助的隐私安全聚合；不接收逐帧或图像数据。"""

    model_config = ConfigDict(extra="forbid")

    observed_seconds: int = Field(..., ge=0, le=86400)
    study_seconds: int = Field(..., ge=0, le=86400)
    paused_seconds: int = Field(..., ge=0, le=86400)
    longest_continuous_study_seconds: int = Field(..., ge=0, le=86400)
    meaningful_switch_count: int = Field(..., ge=0, le=10000)
    phone_interaction_count: int = Field(..., ge=0, le=10000)
    possible_distraction_count: int = Field(..., ge=0, le=10000)
    absent_count: int = Field(..., ge=0, le=10000)
    reminder_count: int = Field(..., ge=0, le=10000)
    model_version: str = Field(..., min_length=1, max_length=128)


class StudySessionFinish(BaseModel):
    """结束会话时填写的文字感受(用户主动输入,不根据表情替用户填写)。"""

    self_report: Optional[str] = Field(None, max_length=2000)
    self_report_tags: Optional[List[str]] = Field(None, max_length=20)
    behavior_summary: Optional[StudyBehaviorSummary] = None


class StudyBreakOut(BaseModel):
    id: str
    session_id: str
    started_at: str
    ended_at: Optional[str] = None
    reason: Optional[str] = None
    created_at: str

    @property
    def is_open(self) -> bool:
        return self.ended_at is None


class StudySessionOut(BaseModel):
    id: str
    user_id: str
    mode: str
    goal: Optional[str] = None
    related_task_id: Optional[str] = None
    started_at: str
    paused_at: Optional[str] = None
    ended_at: Optional[str] = None
    planned_duration_seconds: int = 0
    duration_seconds: int = 0
    pause_seconds: int = 0
    status: str
    self_report: Optional[str] = None
    self_report_tags: List[str] = Field(default_factory=list)
    expression_signal: Optional[Any] = None
    behavior_summary: Optional[StudyBehaviorSummary] = None
    created_at: str = ""
    updated_at: str = ""
    breaks: List[StudyBreakOut] = Field(default_factory=list)


# ===== 任务拆解 =====


class TaskBreakdownRequest(BaseModel):
    """任务拆解输入: task_id(个人待办) 或自由文本目标,二选一(可同时提供)。

    - task_id: 个人待办 PersonalTask ID(需属于当前用户)。
      解析成功时使用其 title/description/materials/submission_method/source_text 作为上下文。
      严格区分:不接受教师 Assignment ID。未来若需拆解教师作业,应增加独立 assignment_id 字段。
    - goal: 自由文本目标。task_id 解析失败时以 goal 为准。
    """

    task_id: Optional[str] = Field(None, max_length=128)
    goal: Optional[str] = Field(None, max_length=500)


class TaskBreakdownStep(BaseModel):
    """结构化拆解步骤。"""

    step_number: int = Field(..., ge=1)
    title: str
    description: str
    estimated_minutes: int = Field(..., ge=0, le=600)
    dependencies: List[int] = Field(
        default_factory=list,
        description="依赖的 step_number 列表(必须先完成)",
    )
    completion_criteria: str = Field(
        ..., description="完成判定标准(可观测、可检验)"
    )
    is_policy_step: bool = Field(
        False, description="是否为校园政策相关步骤(依赖知识库)"
    )
    knowledge_source: Optional[str] = Field(
        None, description="政策步骤引用的知识库来源标题"
    )


class TaskBreakdownResponse(BaseModel):
    """任务拆解响应。mode 标注来源: llm | rule_fallback。"""

    mode: str = Field(..., description="llm | rule_fallback")
    steps: List[TaskBreakdownStep]
    goal: str = Field(..., description="实际用于拆解的目标文本")
    related_task_id: Optional[str] = None
    related_task_title: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


__all__ = [
    "StudySessionCreate",
    "StudySessionUpdate",
    "StudySessionFinish",
    "StudyBreakOut",
    "StudySessionOut",
    "TaskBreakdownRequest",
    "TaskBreakdownStep",
    "TaskBreakdownResponse",
]
