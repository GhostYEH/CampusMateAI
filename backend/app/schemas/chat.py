"""AI 导员聊天的请求与响应 schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ChatSource(BaseModel):
    """知识库引用来源(对齐 Flutter KnowledgeSource + 扩展字段)。"""
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


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户问题")
    conversation_id: Optional[str] = Field(None, description="会话 ID")
    recent_tasks: List[Any] = Field(
        default_factory=list,
        description="最近待办(JSON 对象列表)，用于个性化提示",
    )
    stream: bool = Field(True, description="是否使用 SSE 流式响应")
    # 多角色上下文(可选): 后端会校验当前用户是否有权访问这些资源
    course_id: Optional[str] = Field(None, description="课程 ID(需有权限)")
    class_id: Optional[str] = Field(None, description="班级 ID(需有权限)")
    assignment_id: Optional[str] = Field(None, description="任务 ID(需有权限)")
    announcement_id: Optional[str] = Field(None, description="通知 ID(需有权限)")


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
    mode: str = Field(..., description="llm|retrieval_summary|no_knowledge")
    warnings: List[str] = Field(default_factory=list)


__all__ = [
    "ChatSource",
    "SuggestedAction",
    "ChatRequest",
    "ChatFinalMeta",
]
