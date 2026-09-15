"""互动课堂(OpenMAIC 适配层)API schema。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

VALID_MODES = {"adaptive", "explain", "explore", "practice", "project"}


class OpenMAICGenerateRequest(BaseModel):
    mode: str = Field(
        "adaptive",
        description="学习模式：adaptive/explain/explore/practice/project",
    )
    learning_objective: Optional[str] = Field(
        None, max_length=500, description="用户明确选择的学习目标(可选)"
    )

    @field_validator("mode")
    @classmethod
    def _mode_valid(cls, v: str) -> str:
        normalized = (v or "adaptive").strip().lower()
        if normalized not in VALID_MODES:
            raise ValueError(f"不支持的课堂模式: {v}")
        return normalized


class OpenMAICStatusOut(BaseModel):
    enabled: bool
    service: str = "openmaic"
    version: str = ""
    capabilities: Dict[str, bool] = Field(default_factory=dict)
    unavailable: bool = False
    # 未启用时的说明文案
    reason: Optional[str] = None


class OpenMAICSessionOut(BaseModel):
    session_id: str
    course_id: str
    mode: str
    job_id: Optional[str] = None
    status: str
    step: str
    progress: int = 0
    message: str = ""
    error: Optional[str] = None
    classroom_id: Optional[str] = None
    url: Optional[str] = None
    scenes_count: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_session(cls, s) -> "OpenMAICSessionOut":
        return cls(
            session_id=s.session_id,
            course_id=s.course_id,
            mode=s.mode,
            job_id=s.job_id,
            status=s.status,
            step=s.step,
            progress=s.progress,
            message=s.message,
            error=s.error,
            classroom_id=s.classroom_id,
            url=s.classroom_url,
            scenes_count=s.scenes_count,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )


class OpenMAICGenerateOut(BaseModel):
    accepted: bool = True
    session: OpenMAICSessionOut
    poll_interval_ms: int = 5000
    mode: str


class OpenMAICClassroomOut(BaseModel):
    session_id: str
    classroom_id: Optional[str] = None
    url: str
    mode: str
    scenes_count: Optional[int] = None
    created_at: str = ""


class OpenMAICClassroomsOut(BaseModel):
    enabled: bool
    items: List[OpenMAICClassroomOut] = Field(default_factory=list)


__all__ = [
    "OpenMAICGenerateRequest",
    "OpenMAICStatusOut",
    "OpenMAICSessionOut",
    "OpenMAICGenerateOut",
    "OpenMAICClassroomOut",
    "OpenMAICClassroomsOut",
]