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
    """互动课堂状态契约。

    - configured: 后端是否配置了 OpenMAIC（OPENMAIC_ENABLED + BASE_URL）。
    - available:  当前是否可用（health 可达 且 ACCESS_CODE 已通过）。
    - enabled:    == configured and available，客户端据此决定是否展示生成入口。
    - unavailable: configured and not available。
    - embed_origin: 可信 OpenMAIC Origin（含端口），未配置时为 None（客户端 fail-closed）。
    - browser_embed_available: 学生浏览器能否安全打开/内嵌课堂；服务端可认证不代表浏览器可认证。
    """

    enabled: bool
    configured: bool = False
    available: bool = False
    service: str = "openmaic"
    version: str = ""
    capabilities: Dict[str, bool] = Field(default_factory=dict)
    unavailable: bool = False
    embed_origin: Optional[str] = None
    browser_embed_available: bool = False
    browser_embed_reason: Optional[str] = None
    # 未启用/不可用时的说明文案
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
