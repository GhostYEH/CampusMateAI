"""管理员观测 API 的响应模型(§Task 9)。

**脱敏契约**:这些模型里不存在 prompt、model_response、credential、memory_content、
raw_arguments 等字段。任何新增字段都必须是计数、耗时、状态或安全业务标识;
需要新增敏感字段时应另开受审计的接口,而不是放宽本模块。

所有模型 `extra="forbid"`,防止把上游字典里的多余字段(可能携带敏感内容)顺带序列化出去。
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DurationStats(_Strict):
    p50: Optional[float] = Field(None, ge=0)
    p95: Optional[float] = Field(None, ge=0)
    samples: int = Field(0, ge=0)


class ModelLatencyStats(_Strict):
    p50: Optional[float] = Field(None, ge=0)
    p95: Optional[float] = Field(None, ge=0)
    samples: int = Field(0, ge=0)


class TokenUsage(_Strict):
    total_tokens: int = Field(0, ge=0)
    model_calls: int = Field(0, ge=0)


class ApprovalStats(_Strict):
    pending: int = Field(0, ge=0)
    resolved: int = Field(0, ge=0)
    expired: int = Field(0, ge=0)
    wait_p50_ms: Optional[float] = Field(None, ge=0)
    wait_p95_ms: Optional[float] = Field(None, ge=0)


class AgentRuntimeOverviewOut(_Strict):
    """队列、成功率、耗时、Token、工具、重试与审批等待的聚合视图。"""

    window_hours: int = Field(..., ge=1)
    since: str
    queue_depth: int = Field(0, ge=0)
    stale_lease_count: int = Field(0, ge=0)
    run_count: int = Field(0, ge=0)
    status_distribution: dict[str, int] = Field(default_factory=dict)
    success_rate: Optional[float] = Field(None, ge=0, le=1)
    duration_ms: DurationStats
    model_latency_ms: ModelLatencyStats
    token_usage: TokenUsage
    tool_failure_count: int = Field(0, ge=0)
    tool_call_count: int = Field(0, ge=0)
    retry_count: int = Field(0, ge=0)
    approval: ApprovalStats


class RunTraceHeader(_Strict):
    run_id: str
    job_id: str
    status: str
    phase: str
    risk_level: Optional[str] = None
    handler_code: Optional[str] = None
    handler_version: Optional[str] = None
    attempt_no: int = Field(0, ge=0)
    error_code: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    created_at: str
    updated_at: str
    duration_ms: Optional[float] = Field(None, ge=0)


class RunTraceEvent(_Strict):
    sequence: int = Field(..., ge=0)
    type: str
    status: str
    phase: str
    role: Optional[str] = None
    summary: Optional[str] = None
    created_at: str


class RunTraceToolCall(_Strict):
    call_id: str
    tool_name: str
    status: str
    error_code: Optional[str] = None
    started_at: str
    finished_at: Optional[str] = None
    duration_ms: Optional[float] = Field(None, ge=0)


class RunTraceModelCall(_Strict):
    call_id: str
    provider: str
    model: str
    route_policy: str
    status: str
    latency_ms: Optional[int] = None
    total_tokens: Optional[int] = None
    started_at: str


class RunTraceApproval(_Strict):
    approval_id: str
    status: str
    risk_level: str
    action_summary: str
    wait_ms: Optional[float] = Field(None, ge=0)
    expires_at: str


class AgentRunTraceOut(_Strict):
    """单 Run 时间线。只包含安全摘要、状态、耗时与业务标识。"""

    run: RunTraceHeader
    events: list[RunTraceEvent] = Field(default_factory=list)
    tool_calls: list[RunTraceToolCall] = Field(default_factory=list)
    model_calls: list[RunTraceModelCall] = Field(default_factory=list)
    approvals: list[RunTraceApproval] = Field(default_factory=list)


__all__ = [
    "AgentRunTraceOut",
    "AgentRuntimeOverviewOut",
    "RunTraceHeader",
]
