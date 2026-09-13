"""CampusAgentRuntime Pydantic 契约模型。

所有模型使用 `extra="forbid"` 防止隐藏字段泄漏(可能携带源码、token 或敏感上下文)。
错误信封包含 request_id,便于跨客户端追踪。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .agent_contract_enums import (
    AGENT_CONTRACT_VERSION,
    AcademicPolicy,
    AgentErrorCode,
    AgentEventType,
    ApprovalStatus,
    ArtifactType,
    AssistanceMode,
    ModelRoutePolicy,
    RiskLevel,
    RunPhase,
    RunStatus,
    SourcePolicy,
)


class _StrictModel(BaseModel):
    """所有契约模型基类:拒绝未知字段。"""

    model_config = ConfigDict(extra="forbid")


# ===== 错误信封(§9.2) =====


class AgentErrorEnvelope(_StrictModel):
    """统一错误响应。

    `details` 仅承载非敏感业务标识(run_id / approval_id 等),
    禁止包含 prompt、完整模型响应、凭据或敏感工具参数。
    """

    code: AgentErrorCode
    message: str = Field(..., max_length=256)
    request_id: str = Field(..., min_length=1, max_length=128)
    details: Optional[dict[str, Any]] = None


# ===== 进度 =====


class AgentProgressOut(_StrictModel):
    """Run 进度(§5.7 SSE event.progress)。"""

    current: int = Field(..., ge=0)
    total: int = Field(..., ge=0)
    percent: int = Field(..., ge=0, le=100)


# ===== 事件 =====


class AgentEventOut(_StrictModel):
    """SSE 事件(§5.7)。

    `summary` 为安全摘要,绝不包含 prompt、隐藏推理、完整模型响应、凭据或敏感工具参数。
    """

    id: str = Field(..., min_length=1, max_length=64)
    type: AgentEventType
    run_id: str = Field(..., min_length=1, max_length=64)
    sequence: int = Field(..., ge=0)
    status: RunStatus
    phase: RunPhase
    role: Optional[str] = Field(None, max_length=64)
    summary: Optional[str] = Field(None, max_length=512)
    progress: Optional[AgentProgressOut] = None
    artifact_id: Optional[str] = Field(None, max_length=64)
    approval_id: Optional[str] = Field(None, max_length=64)
    created_at: str = Field(..., min_length=1, max_length=64)


# ===== 审批 =====


class AgentApprovalOut(_StrictModel):
    """审批记录(§5.5)。过期绝不等于批准。"""

    approval_id: str = Field(..., min_length=1, max_length=64)
    run_id: str = Field(..., min_length=1, max_length=64)
    status: ApprovalStatus
    risk_level: RiskLevel
    action_summary: str = Field(..., max_length=256)
    expires_at: str = Field(..., min_length=1, max_length=64)
    resolved_at: Optional[str] = Field(None, max_length=64)
    decision_reason: Optional[str] = Field(None, max_length=256)


class AgentApprovalDecisionIn(_StrictModel):
    """审批决策请求体。"""

    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    reason: Optional[str] = Field(None, max_length=256)
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


# ===== 产物 =====


class AgentArtifactOut(_StrictModel):
    """产物(§5.9)。读取/下载时重新校验所有权。"""

    artifact_id: str = Field(..., min_length=1, max_length=64)
    run_id: str = Field(..., min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    artifact_type: ArtifactType
    version: int = Field(..., ge=1)
    mime_type: str = Field(..., max_length=64)
    size_bytes: int = Field(..., ge=0)
    content_hash: str = Field(..., min_length=8, max_length=128)
    download_url: Optional[str] = Field(None, max_length=512)
    created_at: str = Field(..., min_length=1, max_length=64)


# ===== Run / Job =====


class AgentJobCreateIn(_StrictModel):
    """创建 Job 请求。"""

    job_kind: str = Field(..., pattern="^(learning_goal|final_review|course_research|notice_workflow)$")
    input_ref: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


class AgentJobOut(_StrictModel):
    """Job 概览。"""

    job_id: str = Field(..., min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    job_kind: str = Field(..., max_length=64)
    status: RunStatus
    created_at: str = Field(..., min_length=1, max_length=64)
    updated_at: str = Field(..., min_length=1, max_length=64)
    latest_run_id: Optional[str] = Field(None, max_length=64)


class AgentRunOut(_StrictModel):
    """Run 详情(§5.6)。"""

    run_id: str = Field(..., min_length=1, max_length=64)
    job_id: str = Field(..., min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    status: RunStatus
    phase: RunPhase
    risk_level: Optional[RiskLevel] = None
    started_at: Optional[str] = Field(None, max_length=64)
    finished_at: Optional[str] = Field(None, max_length=64)
    created_at: str = Field(..., min_length=1, max_length=64)
    updated_at: str = Field(..., min_length=1, max_length=64)
    error: Optional[AgentErrorEnvelope] = None
    artifact_ids: list[str] = Field(default_factory=list)
    retry_of: Optional[str] = Field(None, max_length=64)


class AgentRunCancelIn(_StrictModel):
    """取消 Run 请求。"""

    reason: Optional[str] = Field(None, max_length=256)
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


class AgentRunControlIn(_StrictModel):
    """暂停、恢复和重试的统一控制请求。"""

    reason: Optional[str] = Field(None, max_length=256)
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


# ===== 能力声明 =====


class AgentCapabilityOut(_StrictModel):
    """单个能力声明(/capabilities 端点)。"""

    name: str = Field(..., min_length=1, max_length=64)
    version: str = Field(..., min_length=1, max_length=32)
    route_policy: ModelRoutePolicy
    risk_level: RiskLevel
    requires_approval: bool


class AgentCapabilitiesOut(_StrictModel):
    """能力清单 + 契约版本。"""

    contract_version: str = Field(default=AGENT_CONTRACT_VERSION)
    capabilities: list[AgentCapabilityOut]


# ===== 上下文快照(§5.1) =====


class AgentContextScope(_StrictModel):
    """快照作用域。"""

    user_id: str = Field(..., min_length=1, max_length=64)
    course_ids: list[str] = Field(default_factory=list)
    campaign_id: Optional[str] = Field(None, max_length=64)


class AgentContextSnapshotOut(_StrictModel):
    """不可变有界上下文快照(§5.1)。

    `facts` 仅承载安全投影;日志只记录 snapshot_id / source_digest,
    不记录原始敏感内容。
    """

    snapshot_id: str = Field(..., min_length=1, max_length=64)
    scope: AgentContextScope
    facts: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    source_digest: str = Field(..., min_length=8, max_length=128)
    generated_at: str = Field(..., min_length=1, max_length=64)
    valid_until: str = Field(..., min_length=1, max_length=64)


# ===== 记忆(§5.2) =====


class AgentMemoryOut(_StrictModel):
    """显式记忆记录(§5.2)。"""

    memory_id: str = Field(..., min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    kind: str = Field(
        ...,
        pattern="^(CONFIRMED_PREFERENCE|CONFIRMED_STUDY_GOAL|CONFIRMED_CONSTRAINT|USER_APPROVED_SUMMARY)$",
    )
    content_summary: str = Field(..., max_length=512)
    sensitivity: str = Field(..., pattern="^(low|medium|high)$")
    confirmed: bool
    withdrawn: bool = False
    model_may_consume: bool = False
    created_at: str = Field(..., min_length=1, max_length=64)


class AgentMemoryCreateIn(_StrictModel):
    """创建显式记忆。只有用户明确确认且允许消费时才会进入模型上下文。"""

    kind: str = Field(
        ...,
        pattern="^(CONFIRMED_PREFERENCE|CONFIRMED_STUDY_GOAL|CONFIRMED_CONSTRAINT|USER_APPROVED_SUMMARY)$",
    )
    content_summary: str = Field(..., min_length=1, max_length=512)
    sensitivity: str = Field(default="low", pattern="^(low|medium|high)$")
    confirmed: bool = False
    model_may_consume: bool = False
    provenance: Optional[str] = Field(None, max_length=128)
    valid_until: Optional[str] = Field(None, max_length=64)


# ===== 工具/角色注册(§5.3、§5.4) =====


class AgentRoleOut(_StrictModel):
    """逻辑角色声明(§5.3)。"""

    agent_code: str = Field(..., min_length=1, max_length=64)
    version: str = Field(..., min_length=1, max_length=32)
    capabilities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    model_policy: ModelRoutePolicy
    permission_policy: str = Field(..., max_length=64)


class AgentSkillOut(_StrictModel):
    """声明式 Skill 元数据；不暴露执行地址或凭据。"""

    skill_code: str = Field(..., min_length=1, max_length=64)
    version: str = Field(..., min_length=1, max_length=32)
    description: str = Field(default="", max_length=256)
    capabilities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    transport: str = Field(..., pattern="^(internal|mcp_manifest)$")
    permission_policy: str = Field(..., max_length=64)


class AgentSkillsOut(_StrictModel):
    contract_version: str = Field(default=AGENT_CONTRACT_VERSION)
    skills: list[AgentSkillOut]


class AgentToolOut(_StrictModel):
    """工具声明(§5.4)。"""

    tool_code: str = Field(..., min_length=1, max_length=64)
    resource: str = Field(..., min_length=1, max_length=64)
    action: str = Field(..., min_length=1, max_length=64)
    risk_level: RiskLevel
    requires_approval: bool


# ===== 模型调用摘要(§5.8) =====


class AgentModelCallOut(_StrictModel):
    """模型调用摘要(§5.8)。不包含完整 prompt、隐藏推理或原始响应。"""

    call_id: str = Field(..., min_length=1, max_length=64)
    run_id: str = Field(..., min_length=1, max_length=64)
    provider: str = Field(..., max_length=64)
    route_policy: ModelRoutePolicy
    model: str = Field(..., max_length=64)
    status: str = Field(..., pattern="^(succeeded|failed|fallback|timeout)$")
    latency_ms: int = Field(..., ge=0)
    fallback_reason: Optional[str] = Field(None, max_length=128)
    started_at: str = Field(..., min_length=1, max_length=64)
    finished_at: Optional[str] = Field(None, max_length=64)


class AgentToolCallOut(_StrictModel):
    """工具调用摘要(§5.8)。仅保存 hash、延迟、状态与错误,不保存敏感参数。"""

    call_id: str = Field(..., min_length=1, max_length=64)
    run_id: str = Field(..., min_length=1, max_length=64)
    tool_name: str = Field(..., max_length=64)
    idempotency_key: Optional[str] = Field(None, max_length=128)
    request_hash: str = Field(..., min_length=8, max_length=128)
    status: str = Field(..., pattern="^(succeeded|failed|skipped|replayed)$")
    result_digest: Optional[str] = Field(None, max_length=128)
    error_code: Optional[str] = Field(None, max_length=64)
    started_at: str = Field(..., min_length=1, max_length=64)
    finished_at: Optional[str] = Field(None, max_length=64)


# ===== 课程研究/通知工作流辅助输入 =====


class CourseResearchPolicyIn(_StrictModel):
    """课程研究来源策略(§8.2)。"""

    course_material_priority: bool = True
    allow_web: bool = True
    allow_user_upload: bool = True


class NoticeManualIn(_StrictModel):
    """手动提交通知(§8.3)。"""

    title: str = Field(..., min_length=1, max_length=256)
    content: str = Field(..., min_length=1, max_length=5000)
    source_name: Optional[str] = Field(None, max_length=64)
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


__all__ = [
    "AgentApprovalDecisionIn",
    "AgentApprovalOut",
    "AgentArtifactOut",
    "AgentCapabilitiesOut",
    "AgentCapabilityOut",
    "AgentContextScope",
    "AgentContextSnapshotOut",
    "AgentErrorEnvelope",
    "AgentEventOut",
    "AgentJobCreateIn",
    "AgentJobOut",
    "AgentMemoryCreateIn",
    "AgentMemoryOut",
    "AgentModelCallOut",
    "AgentProgressOut",
    "AgentRoleOut",
    "AgentSkillOut",
    "AgentSkillsOut",
    "AgentRunCancelIn",
    "AgentRunControlIn",
    "AgentRunOut",
    "AgentToolCallOut",
    "AgentToolOut",
    "CourseResearchPolicyIn",
    "NoticeManualIn",
]
