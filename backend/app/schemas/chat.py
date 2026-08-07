"""AI 导员聊天的请求与响应 schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ChatSource(BaseModel):
    """知识库引用来源(对齐移动端 KnowledgeSource + 扩展字段)。"""
    document_id: str
    title: str
    section: Optional[str] = None
    source_department: Optional[str] = None
    published_at: Optional[datetime] = None
    version: Optional[str] = None
    applicable_students: Optional[str] = None
    excerpt: str = Field(..., description="引用片段(已截断)")
    relevance_score: float = Field(0.0, ge=0.0, le=1.0)
    is_official: bool = False
    is_expired: bool = False
    is_demo: bool = False


class SuggestedAction(BaseModel):
    id: str
    label: str
    type: str = "none"  # navigate|prefillQuestion|createTask|none
    payload: Optional[str] = None


class CounselorRecentTask(BaseModel):
    """AI 导员上下文中的"最近待办"条目 — 仅表示 PersonalTask。

    重要(对齐用户要求):
    - recent_tasks 现在只表示 PersonalTask(用户个人待办),不表示 Assignment。
    - 教师作业只能通过 assignment_id 传递。
    - 客户端传入的 title/deadline/priority/status 一律视为 hint,
      后端不得作为事实使用;后端必须通过 PersonalTaskRepository 重新查询,
      使用数据库权威字段覆盖。
    - 未登录用户: 全部忽略 + warning。
    - 已登录用户: 后端按 user_id 查询;不存在 / 越权 / 已软删除的任务不得进入上下文。
    """
    id: str = Field(..., min_length=1, description="PersonalTask ID")
    title: Optional[str] = Field(
        None, description="客户端 hint,后端不信任,仅作 debug 用途"
    )
    deadline: Optional[str] = Field(
        None, description="客户端 hint,后端不信任"
    )
    priority: Optional[str] = Field(
        None, description="客户端 hint,后端不信任"
    )
    status: Optional[str] = Field(
        None, description="客户端 hint,后端不信任"
    )

    model_config = {"extra": "ignore"}


class ChatRequest(BaseModel):
    """AI 导员聊天请求 — 统一上下文 API Schema。

    前端必须在 JSON Body 中发送独立上下文字段,不得把上下文编码进 conversation_id。
    """
    message: str = Field(..., min_length=1, description="用户问题")
    conversation_id: Optional[str] = Field(None, description="会话 ID(仅作会话标识)")
    recent_tasks: List[CounselorRecentTask] = Field(
        default_factory=list,
        description="最近待办(仅 PersonalTask,id 为必填,其他字段为 hint),"
        "后端会通过 PersonalTaskRepository 校验归属,越权/不存在/已删除的条目会被忽略",
    )
    stream: bool = Field(True, description="是否使用 SSE 流式响应")
    # 多角色上下文(可选): 后端会校验当前用户是否有权访问这些资源,
    # 不存在/越权/已删除的对象将被忽略并生成 warning
    course_id: Optional[str] = Field(None, description="课程 ID(需有权限)")
    class_id: Optional[str] = Field(None, description="班级 ID(需有权限)")
    assignment_id: Optional[str] = Field(None, description="任务 ID(需有权限)")
    announcement_id: Optional[str] = Field(None, description="通知 ID(需有权限)")
    # 学习会话上下文(可选): 用于结合学习状态给出执行建议
    study_session_id: Optional[str] = Field(
        None, description="当前学习会话 ID(可选,用于学习陪伴场景)"
    )
    # 用户自报状态(可选): 用户主动填写的当前学习感受/状态
    self_report: Optional[str] = Field(
        None,
        description="用户自报状态(如'有些疲惫'),仅作个性化参考,"
        "不得作为校园规则事实,不得绕过 RAG 拒答规则",
        max_length=500,
    )
    # 表情信号(可选): 仅接收客户端 CNN 的稳定标签与置信度,不接收图像
    expression_signal: Optional[Dict[str, Any]] = Field(
        None,
        description="CNN 观察到的可见表情信号。后端会白名单校验并仅用于调整措辞，"
        "不用于心理或医学判断，不保存原始图像",
    )

    @field_validator("self_report", mode="before")
    @classmethod
    def _normalize_self_report(cls, v: Any) -> Optional[str]:
        """self_report 后端 Schema 必须满足:
        - Optional
        - 最大 500 字(由 max_length 强制,Pydantic 在 strip 前校验长度,
          故客户端应在发送前自行 trim;此处再 strip 一次以保证存储一致)
        - strip 首尾空白
        - 空字符串转换为 null
        """
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("self_report 必须是字符串")
        s = v.strip()
        if not s:
            return None
        return s


class ChatFinalMeta(BaseModel):
    """非流式响应 / SSE 最终事件携带的元数据。"""
    answer: str
    sources: List[ChatSource] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    evidence_level: str = Field(
        "low",
        description="high|medium|low|none",
    )
    needs_human_confirmation: bool = False
    suggested_actions: List[SuggestedAction] = Field(default_factory=list)
    conversation_id: str
    mode: str = Field(..., description="llm|retrieval_summary|no_knowledge|chat")
    warnings: List[str] = Field(default_factory=list)
    # 上下文使用情况(对齐用户新要求):
    # 只回传聚合 count 与 self_report_present 标志,
    # 不回传 self_report 原文,不回传 expression_signal 内容,
    # 不回传 recent_tasks 的具体字段。
    context_used: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "实际采纳的上下文摘要。推荐字段: "
            "recent_tasks_count / recent_tasks_accepted_count / "
            "recent_tasks_ignored_count / self_report_present。"
            "不回传 self_report 原文,不回传 expression_signal 内容。"
        ),
    )
    context_warnings: List[str] = Field(
        default_factory=list,
        description="上下文相关告警(越权/不存在/草稿/expression_signal 已忽略等)",
    )


__all__ = [
    "ChatSource",
    "SuggestedAction",
    "CounselorRecentTask",
    "ChatRequest",
    "ChatFinalMeta",
]
