"""课程研究/作业辅助 Pydantic 契约(§8.2、§9.5)。

所有模型使用 `extra="forbid"` 防止隐藏字段泄漏。
academic_policy 与 assistance_mode 解耦:受限场景即使请求 FULL_SOLUTION 也降级。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .agent_contract_enums import (
    AcademicPolicy,
    AssistanceMode,
    RunStatus,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ===== 来源策略(§8.2) =====


class SourcePolicyIn(_StrictModel):
    """来源策略(硬约束)。

    - course_material_priority: 课程资料优先(先检索已有课程素材)
    - allow_web: 是否允许公共 Web 检索(禁用时绝不搜索 Web)
    - allow_user_upload: 是否允许用户上传作为来源
    """

    course_material_priority: bool = True
    allow_web: bool = True
    allow_user_upload: bool = True


class SourcePolicyOut(_StrictModel):
    course_material_priority: bool = True
    allow_web: bool = True
    allow_user_upload: bool = True


# ===== 来源 =====


class ResearchSourceOut(_StrictModel):
    """研究来源输出。"""

    source_id: str = Field(..., min_length=1, max_length=64)
    source_type: str = Field(..., pattern="^(course_material|web|user_upload)$")
    title: str = Field(..., max_length=512)
    url: Optional[str] = Field(None, max_length=2048)
    snippet: Optional[str] = Field(None, max_length=2000)
    source_ref: Optional[str] = Field(None, max_length=512)
    accessed_at: str = Field(..., min_length=1, max_length=64)
    is_verified: bool = False
    verification_note: Optional[str] = Field(None, max_length=512)
    supports_claim: Optional[bool] = None
    is_fabricated: bool = False


# ===== Run 创建 =====


class CourseResearchRunCreateIn(_StrictModel):
    """POST /api/v1/course-research/runs 请求体。"""

    course_id: Optional[str] = Field(None, max_length=64)
    question: str = Field(..., min_length=1, max_length=2000)
    assistance_mode: AssistanceMode = AssistanceMode.EXPLAIN
    academic_policy: AcademicPolicy = AcademicPolicy.UNKNOWN
    source_policy: SourcePolicyIn = Field(default_factory=SourcePolicyIn)
    user_upload_refs: list[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


class CourseResearchRunOut(_StrictModel):
    """课程研究 Run 概览。"""

    run_id: str = Field(..., min_length=1, max_length=64)
    session_id: str = Field(..., min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    course_id: Optional[str] = Field(None, max_length=64)
    question: str = Field(..., max_length=2000)
    assistance_mode: AssistanceMode
    academic_policy: AcademicPolicy
    effective_assistance_mode: AssistanceMode
    source_policy: SourcePolicyOut
    status: RunStatus
    created_at: str = Field(..., min_length=1, max_length=64)
    updated_at: str = Field(..., min_length=1, max_length=64)
    finished_at: Optional[str] = Field(None, max_length=64)
    error_code: Optional[str] = Field(None, max_length=64)
    artifact_ids: list[str] = Field(default_factory=list)
    fallback_used: bool = False


class CourseResearchRunCancelIn(_StrictModel):
    reason: Optional[str] = Field(None, max_length=256)
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


# ===== Artifacts =====


class CourseResearchArtifactOut(_StrictModel):
    """研究报告产物。"""

    artifact_id: str = Field(..., min_length=1, max_length=64)
    run_id: str = Field(..., min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    artifact_type: str = Field(..., max_length=64)
    version: int = Field(..., ge=1)
    mime_type: str = Field(..., max_length=64)
    size_bytes: int = Field(..., ge=0)
    content_hash: str = Field(..., min_length=8, max_length=128)
    download_url: Optional[str] = Field(None, max_length=512)
    created_at: str = Field(..., min_length=1, max_length=64)
    content: Optional[str] = None


class CourseResearchArtifactListOut(_StrictModel):
    run_id: str = Field(..., min_length=1, max_length=64)
    artifacts: list[CourseResearchArtifactOut] = Field(default_factory=list)
    sources: list[ResearchSourceOut] = Field(default_factory=list)


__all__ = [
    "SourcePolicyIn",
    "SourcePolicyOut",
    "ResearchSourceOut",
    "CourseResearchRunCreateIn",
    "CourseResearchRunOut",
    "CourseResearchRunCancelIn",
    "CourseResearchArtifactOut",
    "CourseResearchArtifactListOut",
]