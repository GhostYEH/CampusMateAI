from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class CourseContentItemOut(BaseModel):
    id: str
    external_id: str
    kind: str
    title: str
    parent_external_id: Optional[str] = None
    description: Optional[str] = None
    author_name: Optional[str] = None
    position: int = 0
    depth: int = 0
    status: str = "unknown"
    starts_at: Optional[str] = None
    deadline: Optional[str] = None
    published_at: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    cached: bool = False
    can_download: bool = False
    can_open: bool = True
    metadata: Optional[dict[str, Any]] = None


class CourseContentPage(BaseModel):
    items: list[CourseContentItemOut] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    has_more: bool


class CourseSectionStatusOut(BaseModel):
    section: str
    status: str
    item_count: int
    last_synced_at: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class CourseContentSummaryOut(BaseModel):
    course_id: str
    provider: Optional[str] = None
    cover_url: Optional[str] = None
    teacher_name: Optional[str] = None
    school_name: Optional[str] = None
    class_name: Optional[str] = None
    student_count: Optional[int] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    last_synced_at: Optional[str] = None
    sections: list[CourseSectionStatusOut] = Field(default_factory=list)
