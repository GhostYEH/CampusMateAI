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

from pydantic import BaseModel, Field


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
    reminder_minutes: Optional[int] = Field(
        None, ge=0, le=60 * 24 * 30, description="提前提醒分钟数(0 表示按 deadline 精确触发)"
    )


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
    reminder_minutes: Optional[int] = Field(None, ge=0, le=60 * 24 * 30)


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
    status: str
    reminder_minutes: Optional[int] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    deleted_at: Optional[str] = None


__all__ = [
    "PersonalTaskCreate",
    "PersonalTaskUpdate",
    "PersonalTaskOut",
]
