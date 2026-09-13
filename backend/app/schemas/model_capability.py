from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LearningSummaryInput(_StrictModel):
    plan_id: str = Field(..., max_length=128)
    warning_codes: list[str] = Field(default_factory=list, max_length=20)
    explanation_codes: list[str] = Field(default_factory=list, max_length=20)
    item_type: str = Field(..., max_length=64)
    estimated_minutes: int = Field(..., ge=1, le=1440)
    data_quality: str = Field(..., pattern="^(verified|partial|stale|unavailable)$")
    evidence_count: int = Field(..., ge=0, le=10000)
    deadline_bucket: str = Field(..., max_length=32)
    knowledge_band: str | None = Field(None, max_length=64)
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
