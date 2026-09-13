from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentJobRow:
    id: str
    user_id: str
    domain: str
    objective_summary: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class AgentRunRow:
    id: str
    job_id: str
    user_id: str
    domain: str
    status: str
    phase: str
    current_role: str | None
    progress_current: int
    progress_total: int
    context_snapshot_id: str | None
    created_at: str
    updated_at: str
    finished_at: str | None


@dataclass(frozen=True)
class AgentRunStepRow:
    id: str
    run_id: str
    sequence: int
    role: str
    status: str
    safe_summary: str
    started_at: str | None
    finished_at: str | None


@dataclass(frozen=True)
class AgentEventRow:
    id: str
    run_id: str
    sequence: int
    type: str
    status: str
    phase: str
    role: str | None
    summary: str
    progress_current: int
    progress_total: int
    artifact_id: str | None
    approval_id: str | None
    created_at: str


@dataclass(frozen=True)
class AgentToolCallRow:
    id: str
    run_id: str
    tool_name: str
    idempotency_key: str
    request_hash: str
    status: str
    started_at: str
    finished_at: str | None
    result_digest: str | None
    error_code: str | None


@dataclass(frozen=True)
class AgentArtifactRow:
    id: str
    user_id: str
    run_id: str
    artifact_type: str
    content_ref: str
    content_hash: str
    version: int
    mime_type: str
    size_bytes: int
    created_at: str
    deleted_at: str | None


@dataclass(frozen=True)
class AgentApprovalRow:
    id: str
    run_id: str
    user_id: str
    status: str
    risk_level: str
    action_digest: str
    summary: str
    expires_at: str
    decided_at: str | None
    created_at: str
