"""个人待办任务数据行模型 — 学生从通知抽取生成的个人任务。

与 `AssignmentRow`(教师发布给班级的作业)严格区分:
- `PersonalTaskRow` 绑定单个 user_id,仅 JWT 持有者可读写
- `source_text` 保留原通知文本,确保可追溯
- `deleted_at` 软删除字段,避免立即物理删除

所有时间字段以 ISO 8601 字符串存储(带时区)。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PersonalTaskRow:
    id: str
    user_id: str
    title: str
    description: Optional[str] = None
    target_students: Optional[str] = None
    deadline: Optional[str] = None
    materials: Optional[str] = None  # JSON 数组字符串
    submission_method: Optional[str] = None
    location: Optional[str] = None
    source_name: Optional[str] = None
    source_text: Optional[str] = None
    source_notice_id: Optional[str] = None
    priority: str = "medium"  # low / medium / high
    importance: str = "unknown"  # urgent / high / important / normal / low / unknown (AI 评定)
    status: str = "pending"  # pending / completed / deleted
    reminder_minutes: Optional[int] = None
    source: Optional[str] = None
    external_id: Optional[str] = None
    course_id: Optional[str] = None
    source_url: Optional[str] = None
    last_synced_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    completed_at: Optional[str] = None
    deleted_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "PersonalTaskRow":
        keys = row.keys()
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            description=row["description"],
            target_students=row["target_students"],
            deadline=row["deadline"],
            materials=row["materials"],
            submission_method=row["submission_method"],
            location=row["location"],
            source_name=row["source_name"],
            source_text=row["source_text"],
            source_notice_id=row["source_notice_id"],
            priority=row["priority"],
            importance=row["importance"] if "importance" in keys else "unknown",
            status=row["status"],
            reminder_minutes=row["reminder_minutes"],
            source=row["source"] if "source" in keys else None,
            external_id=row["external_id"] if "external_id" in keys else None,
            course_id=row["course_id"] if "course_id" in keys else None,
            source_url=row["source_url"] if "source_url" in keys else None,
            last_synced_at=row["last_synced_at"] if "last_synced_at" in keys else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            deleted_at=row["deleted_at"],
        )


__all__ = ["PersonalTaskRow"]
