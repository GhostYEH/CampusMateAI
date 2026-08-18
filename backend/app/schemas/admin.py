from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AdminOverview(BaseModel):
    user_count: int = 0
    student_count: int = 0
    teacher_count: int = 0
    admin_count: int = 0
    active_user_count: int = 0
    inactive_count: int = 0
    today_new_user_count: int = 0
    last_7_days_new_user_count: int = 0
    course_count: int = 0
    active_course_count: int = 0
    class_count: int = 0
    active_student_count: int = 0
    document_count: int = 0
    chunk_count: int = 0
    user_growth: list[dict[str, Any]] = Field(default_factory=list)
    role_distribution: dict[str, int] = Field(default_factory=dict)
    recent_users: list[dict[str, Any]] = Field(default_factory=list)
    recent_admin_operations: list[dict[str, Any]] = Field(default_factory=list)


class AdminSystemStatus(BaseModel):
    api_status: str
    api_version: str
    app_environment: str
    service_started_at: str
    database_status: str
    database_query_latency_ms: float
    knowledge_base_status: str
    knowledge_base_initialized: bool
    document_count: int
    chunk_count: int
    llm_provider: str
    llm_available: bool
    fallback_mode_enabled: bool
    upload_storage_writable: bool
    last_indexed_at: str | None = None
    recent_error_summary: str | None = None
    server_time: str
    scheduler_status: str
