from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LearningSummaryInput(_StrictModel):
    """候选模型的受控输入：只含枚举、分桶与计数。

    刻意**不**包含 `plan_id` 或任何稳定的内部标识（plan / user / task / goal / run id）。
    这些 id 一旦外发，就把内部标识变成了外部依赖，也扩大了最小化面；
    本地影子记录与生产响应之间的关联改由 `request_id` + `input_digest` 完成
    （两者都在请求信封/落库侧，不进入发给模型的 messages）。
    """

    warning_codes: list[str] = Field(default_factory=list, max_length=20)
    explanation_codes: list[str] = Field(default_factory=list, max_length=20)
    item_type: str = Field(..., max_length=64)
    estimated_minutes: int = Field(..., ge=1, le=1440)
    data_quality: str = Field(..., pattern="^(verified|partial|stale|unavailable)$")
    evidence_count: int = Field(..., ge=0, le=10000)
    deadline_bucket: str = Field(..., max_length=32)
    state_band: str | None = Field(None, max_length=64)
    confidence_bucket: str = Field(..., pattern="^(HIGH|MEDIUM|LOW|NONE)$")


class LearningSummaryOutput(_StrictModel):
    summary: str = Field(..., min_length=1, max_length=240)
    claim_codes: list[str] = Field(default_factory=list, max_length=5)


class ReadOnlyToolRoutingInput(_StrictModel):
    intent_code: str = Field(..., max_length=64)
    authorized_resource_type: str = Field(..., max_length=64)
    candidate_read_tools: list[str] = Field(default_factory=list, max_length=10)
    parameter_schema: dict[str, Any] = Field(default_factory=dict)
    resource_ownership: str = Field(..., max_length=64)


class ReadOnlyToolRoutingOutput(_StrictModel):
    tool_name: str | None = Field(None, max_length=64)
    arguments: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)
    abstained: bool


__all__ = [
    "LearningSummaryInput", "LearningSummaryOutput", "ReadOnlyToolRoutingInput", "ReadOnlyToolRoutingOutput",
]
