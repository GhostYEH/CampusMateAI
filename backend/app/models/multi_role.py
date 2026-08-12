"""多角色协同平台数据行模型 — 用户 / 课程 / 班级 / 通知 / 任务 / 提交 / 附件。

使用 dataclass 表示行结构，便于将来切换 SQLAlchemy / ORM。
所有时间字段以 ISO 8601 字符串存储(带时区)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class UserRow:
    id: str
    username: str
    password_hash: str
    role: str = "student"  # student / admin (历史 teacher 在运行时降级为 student)
    display_name: Optional[str] = None
    student_number: Optional[str] = None
    teacher_number: Optional[str] = None  # 已废弃,仅为兼容旧数据保留
    college: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "UserRow":
        return cls(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            role=row["role"],
            display_name=row["display_name"],
            student_number=row["student_number"],
            teacher_number=row["teacher_number"],
            college=row["college"],
            major=row["major"],
            grade=row["grade"],
            avatar_url=row["avatar_url"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_public_dict(self) -> dict:
        """返回不含 password_hash 的安全字段(用于响应序列化)。"""
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            # Kept for Android clients that predate the display_name field.
            "name": self.display_name or self.username,
            "display_name": self.display_name,
            "student_number": self.student_number,
            "teacher_number": self.teacher_number,
            "college": self.college,
            "major": self.major,
            "grade": self.grade,
            "avatar_url": self.avatar_url,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class RefreshTokenRow:
    id: str
    user_id: str
    token_hash: str
    expires_at: str
    revoked: bool = False
    created_at: str = ""


@dataclass
class CourseRow:
    id: str
    name: str
    code: Optional[str] = None
    semester: Optional[str] = None
    description: Optional[str] = None
    teacher_id: Optional[str] = None
    status: str = "draft"  # draft / active / archived
    provider: Optional[str] = None
    external_id: Optional[str] = None
    source_url: Optional[str] = None
    last_synced_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "CourseRow":
        def get_col(r, col):
            try:
                return r[col]
            except IndexError:
                return None

        return cls(
            id=row["id"],
            name=row["name"],
            code=row["code"],
            semester=row["semester"],
            description=row["description"],
            teacher_id=row["teacher_id"],
            status=row["status"],
            provider=get_col(row, "provider"),
            external_id=get_col(row, "external_id"),
            source_url=get_col(row, "source_url"),
            last_synced_at=get_col(row, "last_synced_at"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class ClassGroupRow:
    id: str
    course_id: str
    name: str
    class_code: Optional[str] = None
    invite_code: str = ""
    description: Optional[str] = None
    capacity: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "ClassGroupRow":
        return cls(
            id=row["id"],
            course_id=row["course_id"],
            name=row["name"],
            class_code=row["class_code"],
            invite_code=row["invite_code"],
            description=row["description"],
            capacity=row["capacity"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class EnrollmentRow:
    id: str
    class_group_id: str
    user_id: str
    member_role: str = "student"  # student / teaching_assistant
    status: str = "active"  # active / removed
    joined_at: str = ""

    @classmethod
    def from_row(cls, row) -> "EnrollmentRow":
        return cls(
            id=row["id"],
            class_group_id=row["class_group_id"],
            user_id=row["user_id"],
            member_role=row["member_role"],
            status=row["status"],
            joined_at=row["joined_at"],
        )


@dataclass
class AnnouncementRow:
    id: str
    class_group_id: str
    author_id: str
    title: str
    content: str
    require_read: bool = False
    status: str = "draft"  # draft / published / archived
    published_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "AnnouncementRow":
        return cls(
            id=row["id"],
            class_group_id=row["class_group_id"],
            author_id=row["author_id"],
            title=row["title"],
            content=row["content"],
            require_read=bool(row["require_read"]),
            status=row["status"],
            published_at=row["published_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class CampusActivityRow:
    """管理员面向全校发布的活动，与班级通知保持数据边界。"""

    id: str
    author_id: str
    title: str
    summary: Optional[str] = None
    content: str = ""
    category: str = "campus"
    location: Optional[str] = None
    registration_deadline: Optional[str] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    capacity: Optional[int] = None
    status: str = "draft"
    published_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "CampusActivityRow":
        return cls(
            id=row["id"],
            author_id=row["author_id"],
            title=row["title"],
            summary=row["summary"],
            content=row["content"],
            category=row["category"],
            location=row["location"],
            registration_deadline=row["registration_deadline"],
            starts_at=row["starts_at"],
            ends_at=row["ends_at"],
            capacity=row["capacity"],
            status=row["status"],
            published_at=row["published_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class AssignmentRow:
    id: str
    class_group_id: str
    author_id: str
    title: str
    description: Optional[str] = None
    deadline: Optional[str] = None
    submission_types: Optional[str] = None  # JSON 数组字符串
    max_score: Optional[float] = None
    allow_resubmit: bool = True
    status: str = "draft"  # draft / published / closed / archived
    published_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "AssignmentRow":
        return cls(
            id=row["id"],
            class_group_id=row["class_group_id"],
            author_id=row["author_id"],
            title=row["title"],
            description=row["description"],
            deadline=row["deadline"],
            submission_types=row["submission_types"],
            max_score=row["max_score"],
            allow_resubmit=bool(row["allow_resubmit"]),
            status=row["status"],
            published_at=row["published_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class SubmissionRow:
    id: str
    assignment_id: str
    student_id: str
    text_content: Optional[str] = None
    status: str = "draft"  # draft / submitted / resubmitted / late
    submitted_at: Optional[str] = None
    updated_at: str = ""
    score: Optional[float] = None
    teacher_comment: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "SubmissionRow":
        return cls(
            id=row["id"],
            assignment_id=row["assignment_id"],
            student_id=row["student_id"],
            text_content=row["text_content"],
            status=row["status"],
            submitted_at=row["submitted_at"],
            updated_at=row["updated_at"],
            score=row["score"],
            teacher_comment=row["teacher_comment"],
        )


@dataclass
class SubmissionAttachmentRow:
    id: str
    submission_id: str
    original_filename: str
    stored_filename: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    storage_path: str = ""
    created_at: str = ""

    @classmethod
    def from_row(cls, row) -> "SubmissionAttachmentRow":
        return cls(
            id=row["id"],
            submission_id=row["submission_id"],
            original_filename=row["original_filename"],
            stored_filename=row["stored_filename"],
            mime_type=row["mime_type"],
            size_bytes=row["size_bytes"],
            storage_path=row["storage_path"],
            created_at=row["created_at"],
        )


@dataclass
class AssignmentAttachmentRow:
    id: str
    assignment_id: str
    author_id: str
    original_filename: str
    stored_filename: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    storage_path: str = ""
    created_at: str = ""

    @classmethod
    def from_row(cls, row) -> "AssignmentAttachmentRow":
        return cls(
            id=row["id"],
            assignment_id=row["assignment_id"],
            author_id=row["author_id"],
            original_filename=row["original_filename"],
            stored_filename=row["stored_filename"],
            mime_type=row["mime_type"],
            size_bytes=row["size_bytes"],
            storage_path=row["storage_path"],
            created_at=row["created_at"],
        )


@dataclass
class StudentAssignmentStatus:
    """单个任务下学生状态的聚合视图(通过 SQL 聚合生成,不单独建表)。"""

    student_id: str
    student_name: str
    student_number: Optional[str]
    read_status: str  # read / unread / not_required
    submission_status: str  # not_submitted / draft / submitted / resubmitted / late
    submitted_at: Optional[str]
    is_late: bool
    score: Optional[float]


@dataclass
class NoticeRow:
    id: str
    user_id: str
    source: str
    external_id: str
    course_id: Optional[str] = None
    title: str = ""
    content: Optional[str] = None
    published_at: Optional[str] = None
    source_url: Optional[str] = None
    last_synced_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "NoticeRow":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            source=row["source"],
            external_id=row["external_id"],
            course_id=row["course_id"],
            title=row["title"],
            content=row["content"],
            published_at=row["published_at"],
            source_url=row["source_url"],
            last_synced_at=row["last_synced_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


__all__ = [
    "UserRow",
    "RefreshTokenRow",
    "CourseRow",
    "ClassGroupRow",
    "EnrollmentRow",
    "AnnouncementRow",
    "CampusActivityRow",
    "AssignmentRow",
    "SubmissionRow",
    "SubmissionAttachmentRow",
    "AssignmentAttachmentRow",
    "StudentAssignmentStatus",
    "NoticeRow",
]
