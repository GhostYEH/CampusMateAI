from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


PLAN_ITEM_TYPE_LITERAL = Literal[
    "TASK_FOCUS",
    "EXAM_PREPARATION",
    "CAMPUS_AFFAIRS",
    "GOAL_PROGRESS",
    "RESEARCH_OR_COMPETITION",
    "CAREER_PREPARATION",
    "RECOVERY_BUFFER",
    "REVIEW_AND_REFLECT",
]


class LearningPlanGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available_minutes: int = Field(..., ge=1, le=1440)
    goal_id: str | None = Field(None, min_length=1, max_length=128)
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

    evidence_coverage: float
    warning_codes: list[str]
    evaluator_version: str


class CandidateAnnotationOut(BaseModel):
    """CampusMate-LM 只读金丝雀注解。

    三个必须成立的性质：

    - **可识别**：`capability_name` / `model_key` / `prompt_version` / `inference_source`
      明确标出"这段文字来自候选模型"，绝不与确定性结果混为一谈。
    - **可降级**：门禁未过、未配置、采样未命中、熔断、超时、非法 JSON、策略违规
      一律 `available=False` + 稳定 `reason`，生产响应继续使用确定性结果。
    - **可追溯**：`shadow_run_id` + `input_digest` 指向影子表里的那一次观测。

    `read_only` / `affects_production` 恒为 `True` / `False`：它是展示字段，
    不参与任何状态、计划、任务或决策的写入。
    """

    available: bool
    capability_name: str
    capability_version: str
    reason: str | None = None
    inference_source: str = "DETERMINISTIC_FALLBACK"
    model_key: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    input_digest: str | None = None
    shadow_run_id: str | None = None
    used_fallback: bool = False
    # 已通过 schema + 策略校验的受限投影，不是候选模型的原始补全文本。
    claim_codes: list[str] = Field(default_factory=list)
    summary: str | None = None
    read_only: bool = True
    affects_production: bool = False


class LearningPlanSummaryOut(BaseModel):
    """面向三端的阶段总结；内容是可解释的观测，不宣称因果效果。"""

    plan_id: str
    goal_id: str | None = None
    status: str
    stage: str
    headline: str
    completion_percent: int = Field(..., ge=0, le=100)
    planned_item_count: int = Field(..., ge=0)
    executed_item_count: int = Field(..., ge=0)
    planned_minutes: int = Field(..., ge=0)
    next_action: str
    recommendations: list[str] = Field(default_factory=list)
    warning_codes: list[str] = Field(default_factory=list)
    generated_at: str
    candidate_annotation: CandidateAnnotationOut | None = None


class LearningPlanEvidenceOut(BaseModel):
    evidence_type: str
    relation: str
    relevance_score: float | None = None


class LearningPlanItemOut(BaseModel):
    item_id: str
    item_type: PLAN_ITEM_TYPE_LITERAL
    course_id: str | None = None
    task_id: str | None = None

    estimated_minutes: int
    priority_score: float
    priority_components: dict[str, float]
    explanation_codes: list[str]
    evidence: list[LearningPlanEvidenceOut]
    execution_status: str


class LearningPlanOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    goal_id: str | None = None
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
    "LearningPlanSummaryOut",
    "LearningPlanItemOut", "LearningPlanOut", "LearningPlanPage",
    "PLAN_ITEM_TYPE_LITERAL",
]
