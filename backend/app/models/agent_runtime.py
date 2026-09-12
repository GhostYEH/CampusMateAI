"""CampusAgentRuntime 数据行模型(纯数据容器,无 ORM)。

与 `agent_runtime` schema 对齐。trace 字段只保存摘要/hash/延迟,
不保存完整 prompt、隐藏推理或敏感上下文。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentJobRow:
    job_id: str
    user_id: str
    job_kind: str
    status: str
    created_at: str
    updated_at: str
    idempotency_key: Optional[str] = None
    input_ref_json: str = "{}"


@dataclass
class AgentRunRow:
    run_id: str
    job_id: str
    user_id: str
    status: str
    phase: str
    created_at: str
    updated_at: str
    risk_level: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    request_id: Optional[str] = None
    idempotency_key: Optional[str] = None


@dataclass
class AgentRunStepRow:
    step_id: str
    run_id: str
    role: str
    phase: str
    sequence: int
    started_at: str
    status: str = "running"
    finished_at: Optional[str] = None
    summary: Optional[str] = None


@dataclass
class AgentContextSnapshotRow:
    snapshot_id: str
    user_id: str
    source_digest: str
    generated_at: str
    valid_until: str
    created_at: str
    run_id: Optional[str] = None
    scope_json: str = "{}"
    facts_json: str = "{}"
    source_refs_json: str = "[]"


@dataclass
class AgentToolCallRow:
    call_id: str
    run_id: str
    tool_name: str
    request_hash: str
    started_at: str
    status: str = "running"
    step_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    result_digest: Optional[str] = None
    error_code: Optional[str] = None
    finished_at: Optional[str] = None


@dataclass
class AgentModelCallRow:
    call_id: str
    run_id: str
    provider: str
    route_policy: str
    model: str
    started_at: str
    status: str = "running"
    step_id: Optional[str] = None
    latency_ms: Optional[int] = None
    fallback_reason: Optional[str] = None
    finished_at: Optional[str] = None


@dataclass
class AgentEventRow:
    event_id: str
    run_id: str
    sequence: int
    type: str
    status: str
    phase: str
    created_at: str
    role: Optional[str] = None
    summary: Optional[str] = None
    progress_json: Optional[str] = None
    artifact_id: Optional[str] = None
    approval_id: Optional[str] = None


@dataclass
class AgentMemoryRow:
    memory_id: str
    user_id: str
    kind: str
    content_summary: str
    created_at: str
    updated_at: str
    sensitivity: str = "low"
    confirmed: bool = False
    withdrawn: bool = False
    model_may_consume: bool = False
    provenance: Optional[str] = None
    valid_until: Optional[str] = None


@dataclass
class AgentApprovalRow:
    approval_id: str
    run_id: str
    user_id: str
    risk_level: str
    action_summary: str
    expires_at: str
    created_at: str
    status: str = "PENDING"
    resolved_at: Optional[str] = None
    decision_reason: Optional[str] = None


@dataclass
class AgentCitationRow:
    citation_id: str
    run_id: str
    source_type: str
    source_ref: str
    accessed_at: str
    created_at: str
    title: Optional[str] = None
    is_accessible: bool = True


@dataclass
class AgentArtifactRow:
    artifact_id: str
    run_id: str
    user_id: str
    artifact_type: str
    mime_type: str
    content_hash: str
    storage_path: str
    created_at: str
    version: int = 1
    size_bytes: int = 0
    download_url: Optional[str] = None
    deleted_at: Optional[str] = None


__all__ = [
    "AgentJobRow",
    "AgentRunRow",
    "AgentRunStepRow",
    "AgentContextSnapshotRow",
    "AgentToolCallRow",
    "AgentModelCallRow",
    "AgentEventRow",
    "AgentMemoryRow",
    "AgentApprovalRow",
    "AgentCitationRow",
    "AgentArtifactRow",
]