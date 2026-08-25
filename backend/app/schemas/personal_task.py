"""个人待办任务请求/响应 schema (Pydantic v2)。

涵盖: 个人任务 CRUD、完成/恢复、列表筛选。

与 `assignments`(教师发布的班级作业)严格区分:
- 所有字段针对"学生从通知抽取"的待办场景
- `source_text` 必须保留,确保原通知可追溯
- `target_students` / `materials` / `submission_method` 等通知元数据保留

所有时间字段以 ISO 8601 字符串(带时区)表示。
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


_TEXT_FIELDS = (
    "title",
    "description",
    "target_students",
    "submission_method",
    "location",
    "source_name",
    "source_text",
)


def _validate_text_integrity(value: Optional[str]) -> Optional[str]:
    """拒绝明显由字符编码丢失产生的问号文本。

    正常文案中可以包含少量 ASCII 问号，因此只拦截连续丢失字符常见的
    形态：至少 3 个 ``?``，且占去除空白后文本的一半以上。
    """
    if value is None:
        return value
    compact = "".join(value.split())
    question_marks = compact.count("?")
    if question_marks >= 3 and question_marks / len(compact) >= 0.5:
        raise ValueError("文本疑似在传输过程中丢失字符，请确认编码后重新输入")
    return value


def _validate_materials_integrity(value: Optional[List[str]]) -> Optional[List[str]]:
    if value is not None:
        for item in value:
            _validate_text_integrity(item)
    return value


# ===== 创建 =====


class PersonalTaskCreate(BaseModel):
    """创建个人待办请求。

    `source_text` 强烈建议保留(用于原文追溯),但允许手动创建场景下为空。
    `id` 由后端生成,客户端不传;客户端临时 ID 可通过 `client_request_id` 去重(预留)。
    """

    title: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = Field(None, max_length=4000)
    target_students: Optional[str] = Field(
        None, max_length=512, description="通知面向对象(如 '2024级各班')"
    )
    deadline: Optional[str] = Field(
        None, description="ISO 8601 截止时间(带时区)"
    )
    materials: Optional[List[str]] = Field(
        None, max_length=50, description="所需材料名称列表"
    )
    submission_method: Optional[str] = Field(None, max_length=256)
    location: Optional[str] = Field(None, max_length=256)
    source_name: Optional[str] = Field(
        None, max_length=256, description="通知来源(如 '教务处')"
    )
    source_text: Optional[str] = Field(
        None, max_length=10000, description="原通知全文(用于追溯)"
    )
    source_notice_id: Optional[str] = Field(
        None, max_length=128, description="关联通知 ID(可为空)"
    )
    priority: str = Field("medium", pattern="^(low|medium|high)$")
    importance: Optional[str] = Field(
        "unknown",
        pattern="^(urgent|high|important|normal|low|unknown)$",
        description="AI 评定的重要程度标签(交作业=high,填表=low)",
    )
    reminder_minutes: Optional[int] = Field(
        None, ge=0, le=60 * 24 * 30, description="提前提醒分钟数(0 表示按 deadline 精确触发)"
    )

    @field_validator(*_TEXT_FIELDS)
    @classmethod
    def validate_text_integrity(cls, value: Optional[str]) -> Optional[str]:
        return _validate_text_integrity(value)

    @field_validator("materials")
    @classmethod
    def validate_materials_integrity(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        return _validate_materials_integrity(value)


# ===== 更新 =====


class PersonalTaskUpdate(BaseModel):
    """部分更新。所有字段可选。

    注意: `completed_at` / `deleted_at` / `status` 不通过此接口修改,
    请使用 `/complete` / `/restore` / `DELETE` 接口。
    """

    title: Optional[str] = Field(None, min_length=1, max_length=256)
    description: Optional[str] = Field(None, max_length=4000)
    target_students: Optional[str] = Field(None, max_length=512)
    deadline: Optional[str] = None
    materials: Optional[List[str]] = Field(None, max_length=50)
    submission_method: Optional[str] = Field(None, max_length=256)
    location: Optional[str] = Field(None, max_length=256)
    source_name: Optional[str] = Field(None, max_length=256)
    source_text: Optional[str] = Field(None, max_length=10000)
    source_notice_id: Optional[str] = Field(None, max_length=128)
    priority: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    importance: Optional[str] = Field(
        None, pattern="^(urgent|high|important|normal|low|unknown)$"
    )
    reminder_minutes: Optional[int] = Field(None, ge=0, le=60 * 24 * 30)

    @field_validator(*_TEXT_FIELDS)
    @classmethod
    def validate_text_integrity(cls, value: Optional[str]) -> Optional[str]:
        return _validate_text_integrity(value)

    @field_validator("materials")
    @classmethod
    def validate_materials_integrity(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        return _validate_materials_integrity(value)


# ===== 响应 =====


class PersonalTaskOut(BaseModel):
    """个人待办响应。

    `status` 取值: pending / completed / deleted。
    `materials` 解析为字符串数组返回(后端以 JSON 字符串存储)。
    """

    id: str
    user_id: str
    title: str
    description: Optional[str] = None
    target_students: Optional[str] = None
    deadline: Optional[str] = None
    materials: List[str] = Field(default_factory=list)
    submission_method: Optional[str] = None
    location: Optional[str] = None
    source_name: Optional[str] = None
    source_text: Optional[str] = None
    source_notice_id: Optional[str] = None
    priority: str
    importance: str = "unknown"
    status: str
    reminder_minutes: Optional[int] = None
    source: Optional[str] = None
    external_id: Optional[str] = None
    course_id: Optional[str] = None
    source_url: Optional[str] = None
    last_synced_at: Optional[str] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    deleted_at: Optional[str] = None


# ===== 重要程度批量重排 =====


class ImportanceRankItem(BaseModel):
    """单个任务的重要程度评定结果。"""

    task_id: str
    importance: str = Field(..., pattern="^(urgent|high|important|normal|low|unknown)$")
    reason: Optional[str] = Field(None, description="评定理由")
    mode: str = Field(..., description="评定模式: llm|rules")


class ImportanceRankRequest(BaseModel):
    """批量重排任务重要程度请求。

    不传 task_ids 时，对当前用户所有 pending 任务评定(最多 50 条)。
    """

    task_ids: Optional[List[str]] = Field(
        None, max_length=50, description="指定任务 ID 列表(为空则评定全部 pending 任务)"
    )


class ImportanceRankResponse(BaseModel):
    """批量重排响应。"""

    updated: List[ImportanceRankItem] = Field(default_factory=list)
    skipped: List[str] = Field(
        default_factory=list, description="跳过的任务 ID(LLM 不可用或任务不存在)"
    )
    mode: str = Field(..., description="本次评定实际使用模式: llm|rules")
    total: int = Field(0, description="本次评定任务数")


__all__ = [
    "PersonalTaskCreate",
    "PersonalTaskUpdate",
    "PersonalTaskOut",
    "ImportanceRankItem",
    "ImportanceRankRequest",
    "ImportanceRankResponse",
]
