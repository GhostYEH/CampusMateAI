"""通知结构化抽取的请求与响应 schema。

字段设计兼容现有移动端 `ExtractedNotice` 模型，并扩展 warnings 字段。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class MaterialItem(BaseModel):
    id: str = Field(..., description="材料 ID(便于客户端引用)")
    name: str = Field(..., description="材料名称")
    required: bool = True


class NoticeOut(BaseModel):
    """校园通知列表项 —— 聚合自当前用户可见班级的已发布通知。"""

    id: str
    title: str
    source: Optional[str] = Field(None, description="来源(班级名 / 课程名 / 作者)")
    time: Optional[str] = Field(None, description="发布时间(ISO 8601)")
    unread: bool = Field(False, description="当前学生视角是否未读")
    category: Optional[str] = Field(None, description="分类(课程名等)")
    content: Optional[str] = Field(None, description="通知正文")
    kind: str = Field("announcement", pattern="^(announcement|unified)$")
    source_url: Optional[str] = Field(None, description="原始通知链接")


class NoticeExtractRequest(BaseModel):
    content: str = Field(..., description="校园通知原文")
    published_at: Optional[datetime] = Field(
        None, description="通知发布时间(ISO 8601，带时区)"
    )
    source_name: Optional[str] = Field(None, description="来源单位/系统名称")
    # 多任务拆分：当通知中存在多个明确截止时间/动作时,允许多任务拆分
    allow_multi_task: bool = Field(
        True,
        description="是否允许拆分为多个任务(默认 True,无法可靠拆分时返回单任务)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content": "请2024级学生于7月30日前填写实践申请表,并将申请表和证明材料提交至学院办公室。",
                "published_at": "2026-07-20T09:00:00+08:00",
                "source_name": "信息工程学院通知",
                "allow_multi_task": True,
            }
        }


class NoticeSemanticType(str, Enum):
    CHAT = "CHAT"
    NOTICE = "NOTICE"
    ACTIONABLE_NOTICE = "ACTIONABLE_NOTICE"
    AMBIGUOUS = "AMBIGUOUS"


class NoticeBatchMessage(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    published_at: Optional[datetime] = None


class NoticeBatchItem(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=200)
    client_fingerprint: str = Field(..., min_length=16, max_length=128)
    source_name: str = Field(..., min_length=1, max_length=200)
    published_at: Optional[datetime] = None
    messages: List[NoticeBatchMessage] = Field(..., min_length=1, max_length=20)

    @property
    def content(self) -> str:
        return "\n".join(message.text for message in self.messages)


class NoticeBatchIngestRequest(BaseModel):
    items: List[NoticeBatchItem] = Field(..., min_length=1, max_length=20)


class NoticeBatchItemResult(BaseModel):
    client_id: str
    client_fingerprint: str
    status: str = Field(..., pattern="^(completed|ignored|retryable|failed)$")
    semantic_type: NoticeSemanticType
    notice_created: bool = False
    tasks_created: int = 0
    duplicate: bool = False
    extraction: Optional["MultiNoticeExtractResponse"] = None
    reason: Optional[str] = None


class NoticeBatchIngestResponse(BaseModel):
    items: List[NoticeBatchItemResult] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)


class RecentNoticeItem(BaseModel):
    """客户端传入的最近通知项(用于重复检测对比)。"""

    notice_id: str = Field(..., description="已存在通知 ID")
    title: Optional[str] = Field(None, description="已存在通知标题")
    task: Optional[str] = Field(None, description="已存在任务名")
    source_name: Optional[str] = None
    source_text: Optional[str] = Field(None, description="通知原文(用于内容哈希对比)")
    deadline: Optional[datetime] = None


class DuplicateNoticeCheckRequest(BaseModel):
    """重复通知检测请求。

    服务端无状态,客户端应将本地已保存的通知列表作为 recent_notices 传入。
    若 recent_notices 为空,则返回 is_duplicate=false(无对比基准)。
    """

    content: str = Field(..., description="通知原文")
    source_name: Optional[str] = Field(None, description="来源名称")
    task_name: Optional[str] = Field(None, description="已抽取的任务名(可选)")
    deadline: Optional[datetime] = Field(None, description="已抽取的截止时间(可选)")
    recent_notices: List[RecentNoticeItem] = Field(
        default_factory=list,
        description="客户端本地已保存的通知列表(用于服务端对比)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content": "请2024级学生于7月30日前提交实践申请表...",
                "source_name": "信息工程学院通知",
                "task_name": "提交实践申请表",
                "recent_notices": [
                    {
                        "notice_id": "task_001",
                        "title": "提交实践申请表",
                        "source_name": "信息工程学院通知",
                        "source_text": "请2024级学生于7月30日前提交实践申请表...",
                        "deadline": "2026-07-30T23:59:00+08:00",
                    }
                ],
            }
        }


class DuplicateNoticeMatch(BaseModel):
    """重复检测命中的已存在通知项。"""

    notice_id: str = Field(..., description="已存在通知 ID")
    title: str = Field(..., description="已存在通知标题")
    source_name: Optional[str] = None
    deadline: Optional[datetime] = None
    similarity: float = Field(..., ge=0.0, le=1.0, description="相似度 0~1")
    reasons: List[str] = Field(
        default_factory=list,
        description="判定为重复的原因(content_hash/source_name/task/deadline)",
    )


class DuplicateNoticeCheckResponse(BaseModel):
    is_duplicate: bool = Field(..., description="是否可能重复")
    matches: List[DuplicateNoticeMatch] = Field(default_factory=list)
    content_hash: str = Field(..., description="当前通知的内容哈希(SHA256)")
    note: str = Field(
        "仅提示可能重复,不会自动覆盖原待办。请人工确认后决定是否继续保存。",
        description="说明文案",
    )


class MultiNoticeExtractResponse(BaseModel):
    """多任务抽取响应。

    当 allow_multi_task=true 且通知中可识别出多个独立任务时,
    返回多个 [NoticeExtractResponse]。无法可靠拆分时返回单个。
    """

    tasks: List[NoticeExtractResponse] = Field(
        default_factory=list,
        description="抽取的任务列表(1 个或多个)",
    )
    split_reason: str = Field(
        "",
        description="拆分说明(如'识别到 2 个独立截止时间'或'合并为单任务')",
    )
    needs_user_confirmation: bool = Field(
        False,
        description="是否建议用户人工确认拆分结果",
    )


class NoticeExtractResponse(BaseModel):
    title: str = Field(..., description="通知标题/任务名(可为空字符串)")
    task: str = Field(..., description="任务名(对齐移动端 taskName)")
    actionable: bool = Field(False, description="是否是明确需要学生执行的行动型通知(普通公告为 false)")
    target_students: Optional[str] = Field(None, description="面向对象")
    deadline: Optional[datetime] = Field(None, description="截止时间(ISO 8601)")
    materials: List[MaterialItem] = Field(default_factory=list)
    submission_method: Optional[str] = Field(None, description="提交方式")
    location: Optional[str] = Field(None, description="办理地点")
    source_name: Optional[str] = Field(None, description="来源单位")
    source_text: str = Field(..., description="通知原文(便于人工复核)")
    importance: str = Field(
        "unknown",
        description="重要程度: urgent|high|important|normal|low|unknown",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="抽取置信度 0~1")
    needs_confirmation: bool = Field(
        ..., description="是否需要人工确认(年份缺失/对象不明等)"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="需要确认的原因列表(温和提示，非错误)",
    )
    extracted_at: datetime = Field(..., description="抽取完成时间(ISO 8601)")
    extractor_mode: str = Field(
        ..., description="抽取器模式: llm|rules (便于客户端区分)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "title": "提交实践申请",
                "task": "提交实践申请",
                "target_students": "2024级",
                "deadline": "2026-07-30T23:59:00+08:00",
                "materials": [
                    {"id": "m_1", "name": "申请表", "required": True},
                    {"id": "m_2", "name": "证明材料", "required": True},
                ],
                "submission_method": "提交纸质版",
                "location": "学院办公室",
                "source_name": "信息工程学院通知",
                "source_text": "...",
                "importance": "important",
                "confidence": 0.82,
                "needs_confirmation": False,
                "warnings": [],
                "extracted_at": "2026-07-25T10:00:00+08:00",
                "extractor_mode": "rules",
            }
        }


__all__ = [
    "MaterialItem",
    "NoticeOut",
    "NoticeExtractRequest",
    "NoticeExtractResponse",
    "RecentNoticeItem",
    "DuplicateNoticeCheckRequest",
    "DuplicateNoticeMatch",
    "DuplicateNoticeCheckResponse",
    "MultiNoticeExtractResponse",
    "NoticeSemanticType",
    "NoticeBatchMessage",
    "NoticeBatchItem",
    "NoticeBatchIngestRequest",
    "NoticeBatchItemResult",
    "NoticeBatchIngestResponse",
]
