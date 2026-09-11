from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ResultType = Literal["passed", "failed", "partial"]
CompilerOutcome = Literal["success", "compile_error", "runtime_error", "timeout"]
EvidenceQuality = Literal["partial", "unverified"]


class KnowledgeComponentOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_component_id: str
    code: str
    name: str
    category: str
    description: str
    domain: str
    taxonomy_version: str
    sort_order: int
    active: bool
    parent_code: str | None = None
    prerequisite_codes: list[str] = Field(default_factory=list)


class ExerciseMappingOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: str
    knowledge_component_code: str
    mapping_method: Literal["CURATED", "COURSE_AUTHOR", "STRUCTURED_IMPORT"]
    mapping_confidence: float = Field(ge=0, le=1)
    mapping_version: str


class PracticeAttemptCreate(BaseModel):
    """Structured practice result; raw source, prompt and feedback are forbidden."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, populate_by_name=True)

    client_attempt_id: str = Field(min_length=1, max_length=128)
    course_id: str = Field(min_length=1, max_length=128)
    exercise_id: str = Field(min_length=1, max_length=128)
    occurred_at: datetime
    attempt_no: int = Field(default=1, ge=1, le=10000)
    result_type: ResultType
    score: float = Field(ge=0, le=100000)
    max_score: float = Field(gt=0, le=100000)
    test_count: int = Field(default=0, alias="total_test_count", ge=0, le=10000)
    passed_test_count: int = Field(default=0, ge=0, le=10000)
    compiler_outcome: CompilerOutcome
    error_codes: list[str] = Field(default_factory=list, max_length=8)
    duration_seconds: int | None = Field(default=None, ge=0, le=86400)
    evidence_quality: EvidenceQuality = "partial"
    evidence_origin: Literal["CLIENT"] = "CLIENT"

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must carry timezone")
        normalized = value.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        if normalized > now + timedelta(minutes=5):
            raise ValueError("occurred_at is too far in the future")
        if normalized < now - timedelta(days=365):
            raise ValueError("occurred_at is too old")
        return normalized

    @field_validator("error_codes")
    @classmethod
    def validate_error_codes(cls, value: list[str]) -> list[str]:
        allowed = {
            "pointer_indirection", "array_boundary", "loop_termination",
            "function_parameter", "dynamic_memory", "struct_member",
            "file_io", "type_conversion", "compile_syntax", "uninitialized_value",
        }
        if any(code not in allowed for code in value):
            raise ValueError("error_codes contains an unsupported code")
        if len(set(value)) != len(value):
            raise ValueError("error_codes must be unique")
        return value

    @model_validator(mode="after")
    def validate_result(self) -> "PracticeAttemptCreate":
        if self.score > self.max_score:
            raise ValueError("score cannot exceed max_score")
        if self.passed_test_count > self.test_count:
            raise ValueError("passed_test_count cannot exceed test_count")
        if self.result_type == "passed" and self.score < self.max_score:
            raise ValueError("passed result requires full score")
        if self.result_type == "passed" and self.compiler_outcome != "success":
            raise ValueError("passed result requires successful compiler outcome")
        if self.evidence_quality == "partial" and self.compiler_outcome == "success" and self.result_type == "passed":
            # Client-submitted evidence remains partial even when its structured result is positive.
            return self
        return self


class PracticeAttemptOut(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    attempt_id: str
    client_attempt_id: str
    course_id: str
    exercise_id: str
    occurred_at: datetime
    attempt_no: int
    result_type: ResultType
    score: float
    max_score: float
    test_count: int = Field(alias="total_test_count")
    passed_test_count: int
    compiler_outcome: CompilerOutcome
    error_codes: list[str]
    duration_seconds: int | None = None
    evidence_quality: EvidenceQuality
    evidence_origin: Literal["CLIENT"]
    event_id: str | None = None
    event_created: bool = False


KnowledgeEvidenceSufficiency = Literal["INSUFFICIENT_EVIDENCE", "SUFFICIENT"]
KnowledgeBand = Literal["INSUFFICIENT_EVIDENCE", "EMERGING", "DEVELOPING", "PROFICIENT"]


class KnowledgeMasteryValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimate: float = Field(ge=0, le=1)
    evidence_count: int = Field(ge=0)
    effective_evidence_weight: float = Field(ge=0)
    positive_evidence_weight: float = Field(ge=0)
    negative_evidence_weight: float = Field(ge=0)
    positive_evidence_count: int = Field(ge=0)
    negative_evidence_count: int = Field(ge=0)
    last_practiced_at: datetime | None = None
    evidence_sufficiency: KnowledgeEvidenceSufficiency
    band: KnowledgeBand
    estimator_version: str
    explanation_codes: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("last_practiced_at")
    @classmethod
    def validate_last_practiced_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("datetime must carry timezone")
        return value


class KnowledgeStateOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    run_id: str
    course_id: str
    knowledge_component: KnowledgeComponentOut
    value: KnowledgeMasteryValue
    confidence: float = Field(ge=0, le=1)
    data_quality: Literal["verified", "partial", "stale", "unavailable"]
    observed_from: datetime | None = None
    observed_through: datetime | None = None
    valid_until: datetime | None = None
    computed_at: datetime


HypothesisStatus = Literal["OPEN", "CONFIRMED", "REJECTED", "EXPIRED", "RESOLVED"]


class MisconceptionHypothesisOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str
    course_id: str
    knowledge_component_code: str
    misconception_code: str
    confidence: float = Field(ge=0, le=1)
    supporting_attempt_count: int = Field(ge=0)
    supporting_error_count: int = Field(ge=0)
    supporting_evidence_count: int = Field(ge=0)
    status: HypothesisStatus
    generated_at: datetime
    valid_until: datetime
    estimator_version: str
    decided_at: datetime | None = None


class HypothesisDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["CONFIRM", "REJECT", "CONFIRMED", "REJECTED"]


__all__ = [
    "ExerciseMappingOut", "HypothesisDecision", "KnowledgeComponentOut",
    "KnowledgeMasteryValue", "KnowledgeStateOut", "MisconceptionHypothesisOut",
    "PracticeAttemptCreate", "PracticeAttemptOut",
]
