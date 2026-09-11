from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class LearningPlanGenerateRequest(BaseModel):
    available_minutes: int = Field(..., ge=1, le=1440)
    course_id: str | None = Field(None, min_length=1, max_length=128)
    window_start: str | None = Field(None, max_length=64)
    window_end: str | None = Field(None, max_length=64)
    idempotency_key: str | None = Field(None, min_length=1, max_length=128)
    enhance_with_llm: bool = False

    @field_validator("window_end")
    @classmethod
    def _window_requires_start(cls, value: str | None, info):
        if value and not info.data.get("window_start"):
            raise ValueError("window_end requires window_start")
        return value


class LearningPlanDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(ACCEPT|REJECT)$")


class LearningPlanFeedbackRequest(BaseModel):
    feedback: str = Field(..., pattern="^(HELPFUL|NOT_HELPFUL|TOO_LONG|TOO_SHORT|WRONG_PRIORITY|ALREADY_DONE|MISSING_CONTEXT)$")


class LearningPlanFeedbackOut(BaseModel):
    plan_id: str
    feedback: str
    recorded: bool = True


class LearningPlanEvaluationOut(BaseModel):
    plan_id: str
    evaluation_status: str
    baseline_as_of: str
    evaluated_as_of: str
    planned_item_count: int
    executed_item_count: int
    completed_plan_task_count: int
    followup_practice_count: int
    supported_outcome_count: int
    evidence_coverage: float
    warning_codes: list[str]
    evaluator_version: str


class LearningPlanEvidenceOut(BaseModel):
    evidence_type: str
    relation: str
    relevance_score: float | None = None


class LearningPlanItemOut(BaseModel):
    item_id: str
    item_type: str
    course_id: str | None = None
    task_id: str | None = None
    knowledge_component_code: str | None = None
    estimated_minutes: int
    priority_score: float
    priority_components: dict[str, float]
    explanation_codes: list[str]
    evidence: list[LearningPlanEvidenceOut]
    execution_status: str


class LearningPlanOut(BaseModel):
    plan_id: str
    planner_version: str
    input_digest: str
    status: str
    as_of: str
    valid_until: str
    available_minutes: int
    allocated_minutes: int
    warning_codes: list[str]
    created_at: str
    items: list[LearningPlanItemOut]
    llm_summary: str | None = None
    supersedes_plan_id: str | None = None
    superseded_by_plan_id: str | None = None


class LearningPlanPage(BaseModel):
    items: list[LearningPlanOut]
    total: int
    page: int
    page_size: int
    has_more: bool


__all__ = [
    "LearningPlanGenerateRequest", "LearningPlanDecisionRequest", "LearningPlanEvidenceOut",
    "LearningPlanFeedbackRequest", "LearningPlanFeedbackOut", "LearningPlanEvaluationOut",
    "LearningPlanItemOut", "LearningPlanOut", "LearningPlanPage",
]
