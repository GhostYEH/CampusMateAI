from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .agent_contract_enums import (
    AcademicPolicy,
    AgentApprovalStatus,
    AgentArtifactType,
    AgentRiskLevel,
    AgentRunPhase,
    AgentRunStatus,
    NoticeWorkflowStatus,
    ResearchMode,
)


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class AgentErrorEnvelope(StrictContract):
    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=500)
    request_id: str = Field(min_length=1, max_length=128)
    details: dict[str, Any] | list[Any] | None = None


class AgentProgressOut(StrictContract):
    current: int = Field(ge=0)
    total: int = Field(ge=0)
    percent: int = Field(ge=0, le=100)


class AgentEventOut(StrictContract):
    id: str
    type: str
    run_id: str
    sequence: int = Field(ge=1)
    status: AgentRunStatus
    phase: AgentRunPhase
    role: str | None = None
    summary: str = Field(min_length=1, max_length=500)
    progress: AgentProgressOut
    artifact_id: str | None = None
    approval_id: str | None = None
    created_at: str


class AgentRunOut(StrictContract):
    run_id: str
    job_id: str
    domain: str
    status: AgentRunStatus
    phase: AgentRunPhase
    current_role: str | None = None
    progress: AgentProgressOut
    context_snapshot_id: str | None = None
    created_at: str
    updated_at: str
    finished_at: str | None = None


class AgentRunStepOut(StrictContract):
    step_id: str
    run_id: str
    sequence: int = Field(ge=1)
    role: str
    status: str
    summary: str = Field(min_length=1, max_length=500)
    started_at: str | None = None
    finished_at: str | None = None


class AgentRunStepPage(StrictContract):
    run_id: str
    items: list[AgentRunStepOut]
    total: int = Field(ge=0)


class AgentJobCreate(StrictContract):
    domain: str = Field(min_length=1, max_length=64)
    objective_summary: str = Field(min_length=1, max_length=500)
    total_steps: int = Field(default=1, ge=1, le=100)


class AgentJobOut(StrictContract):
    job_id: str
    domain: str
    objective_summary: str
    status: str
    run: AgentRunOut


class AgentEventPage(StrictContract):
    items: list[AgentEventOut]
    total: int = Field(ge=0)
    has_more: bool


class AgentApprovalDecision(StrictContract):
    decision: str = Field(pattern=r"^(APPROVED|REJECTED)$")


class AgentApprovalOut(StrictContract):
    approval_id: str
    run_id: str
    status: AgentApprovalStatus
    risk_level: AgentRiskLevel
    summary: str = Field(min_length=1, max_length=500)
    expires_at: str
    created_at: str


class AgentArtifactOut(StrictContract):
    artifact_id: str
    run_id: str
    artifact_type: AgentArtifactType
    version: int = Field(ge=1)
    mime_type: str
    size_bytes: int = Field(ge=0)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: str


class SourcePolicy(StrictContract):
    course_material_priority: bool = True
    allow_web: bool = False
    allow_user_upload: bool = False


class FinalReviewContract(StrictContract):
    campaign_id: str
    exam_id: str
    active_version: int = Field(ge=1)
    status: str
    run: AgentRunOut


class CourseResearchContract(StrictContract):
    research_id: str
    course_id: str | None = None
    mode: ResearchMode
    academic_policy: AcademicPolicy
    source_policy: SourcePolicy
    run: AgentRunOut


class NoticeWorkflowContract(StrictContract):
    workflow_id: str
    notice_id: str
    status: NoticeWorkflowStatus
    automation_enabled: bool = False
    run: AgentRunOut


__all__ = [
    "AgentApprovalDecision", "AgentApprovalOut", "AgentArtifactOut", "AgentErrorEnvelope",
    "AgentEventOut", "AgentEventPage", "AgentJobCreate", "AgentJobOut", "AgentProgressOut",
    "AgentRunOut", "AgentRunStepOut", "AgentRunStepPage", "CourseResearchContract",
    "FinalReviewContract", "NoticeWorkflowContract", "SourcePolicy",
]
