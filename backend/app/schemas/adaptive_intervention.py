"""状态驱动干预的 schema —— 状态分析、策略决策与干预记录。

设计边界(与仓库既有约定一致):

- 状态分析只描述**可观测的学习状态**(工作量、执行、节奏、知识掌握观测)，
  不对人格、智力、意志力或心理状态做任何推断。
- `problem_types` / `strengths` / `risk_signals` 都是有限枚举，逻辑分支不得依赖自由文本。
- 每个 problem/strength 必须带至少一条 `reason_codes` 与至少一条 `evidence_refs`，
  由 `StudentStateAssessment` 的校验器强制，避免出现"只有文字解释没有证据码"的结论。
- `unavailable` 状态不参与任何数值判断(不当作 0)，其对应特征保持 `None`。
- 策略是版本化的有限集合；LLM 只能转写说明文本，不能决定策略或修改计划结构。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ANALYZER_VERSION = "adaptive-state-analyzer-v1"
STRATEGY_VERSION = "adaptive-strategy-v1"

# 触发 INSUFFICIENT_EVIDENCE 的置信度上限。
INSUFFICIENT_EVIDENCE_CONFIDENCE_CEILING = 0.4
# CHALLENGE_UPSHIFT / READY_FOR_CHALLENGE 要求的最低置信度。
CHALLENGE_CONFIDENCE_FLOOR = 0.7

StateQuality = Literal["verified", "partial", "stale", "unavailable"]
Severity = Literal["LOW", "MODERATE", "HIGH"]

ProblemType = Literal[
    "KNOWLEDGE_FOUNDATION_WEAK",
    "EXECUTION_CONSISTENCY_LOW",
    "WORKLOAD_PRESSURE_HIGH",
    "SCHEDULE_CONFLICT_PRESENT",
    "GOAL_PROGRESS_STALLED",
    "ROUTINE_UNSTABLE",
    "READY_FOR_CHALLENGE",
    "INSUFFICIENT_EVIDENCE",
]

StrengthCode = Literal[
    "KNOWLEDGE_MASTERY_RELATIVELY_STRONG",
    "EXECUTION_CONSISTENCY_HIGH",
    "WORKLOAD_MANAGEABLE",
    "ROUTINE_STABLE",
    "GOAL_PROGRESS_ON_TRACK",
    "SCHEDULE_ROOM_AVAILABLE",
]

RiskSignalCode = Literal[
    "DEADLINE_CONCENTRATION",
    "UPCOMING_EXAM_DENSE",
    "EXECUTION_GAP",
    "KNOWLEDGE_GAP_OBSERVED",
    "SCHEDULE_DENSITY_HIGH",
    "GOAL_STAGNATION",
    "RHYTHM_VARIABILITY",
    "DATA_QUALITY_DEGRADED",
    "EVIDENCE_SPARSE",
]

# 有限理由码：所有 problem/strength 的解释只能取自这里。
ReasonCode = Literal[
    "workload_pressure_high",
    "workload_pressure_very_high",
    "deadline_concentration_observed",
    "upcoming_exam_exposure",
    "schedule_conflict_observed",
    "schedule_room_available",
    "schedule_density_high",
    "execution_consistency_low",
    "execution_consistency_high",
    "execution_no_plan_observed",
    "goal_progress_stalled",
    "goal_progress_on_track",
    "goal_deadline_near",
    "rhythm_unstable",
    "rhythm_stable",
    "rhythm_unknown",
    "knowledge_mastery_below_class",
    "knowledge_mastery_low",
    "knowledge_mastery_strong",
    "knowledge_evidence_available",
    "knowledge_evidence_missing",
    "workload_manageable",
    "data_quality_degraded",
    "evidence_insufficient",
    "state_unavailable",
    "forecast_pressure_high",
    "forecast_deadline_risk_high",
    "forecast_routine_variable",
]

StrategyCode = Literal[
    "FOUNDATION_REINFORCEMENT",
    "WORKLOAD_REDUCTION",
    "PACE_RECOVERY",
    "BALANCED_PROGRESS",
    "CHALLENGE_UPSHIFT",
]

ExpectedOutcomeCode = Literal[
    "FOUNDATION_REVIEW_INCREASED",
    "TOTAL_WORKLOAD_REDUCED",
    "ITEM_COUNT_REDUCED",
    "SHORT_ITEM_PRIORITIZED",
    "EXECUTION_CONTINUITY_RESTORED",
    "BASELINE_RULES_PRESERVED",
    "CHALLENGE_INCREASED",
    "DEADLINE_PRIORITY_PRESERVED",
]

# 有限状态特征键：只允许这些键，避免响应里出现任意结构。
STATE_FEATURE_KEYS = frozenset({
    "workload_pressure_band",
    "upcoming_task_count",
    "upcoming_exam_count",
    "exam_within_7d_count",
    "execution_consistency_ratio",
    "execution_consistency_band",
    "goal_progress_percent",
    "goal_days_remaining",
    "rhythm_stability",
    "knowledge_own_mastery_rate",
    "knowledge_mastery_gap_vs_class",
    "knowledge_point_count",
    "schedule_conflict_count",
    "available_window_count",
    "verified_snapshot_count",
    "partial_snapshot_count",
    "stale_snapshot_count",
    "unavailable_snapshot_count",
    "forecast_workload_pressure_band",
    "forecast_deadline_risk_band",
})


class StateEvidenceRef(BaseModel):
    """安全证据引用：只保存引用与质量，不复制原始内容。"""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=64)
    projection_kind: Literal["CORE", "ACADEMIC", "WORLD", "FORECAST", "GOAL"]
    relation: Literal["SUPPORTS", "LIMITS"] = "SUPPORTS"
    run_id: str | None = Field(None, max_length=64)
    snapshot_id: str | None = Field(None, max_length=64)
    state_type: str | None = Field(None, max_length=64)
    scope_type: str | None = Field(None, max_length=32)
    scope_id: str | None = Field(None, max_length=128)
    data_quality: StateQuality | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)


class StateRiskSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: RiskSignalCode
    severity: Severity
    reason_codes: list[ReasonCode] = Field(..., min_length=1, max_length=8)
    evidence_refs: list[StateEvidenceRef] = Field(..., min_length=1, max_length=8)


class StudentStateAssessment(BaseModel):
    """确定性、可解释的学生状态评估。

    `user_id` 只用于服务端内部编排与按用户隔离，不进入面向客户端的响应。
    """

    model_config = ConfigDict(extra="forbid")

    assessment_id: str = Field(..., min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    goal_id: str | None = Field(None, max_length=128)
    as_of: str = Field(..., min_length=1, max_length=64)

    core_run_id: str | None = Field(None, max_length=64)
    academic_run_id: str | None = Field(None, max_length=64)
    world_run_id: str | None = Field(None, max_length=64)

    problem_types: list[ProblemType] = Field(default_factory=list, max_length=8)
    strengths: list[StrengthCode] = Field(default_factory=list, max_length=6)
    risk_signals: list[StateRiskSignal] = Field(default_factory=list, max_length=9)

    state_features: dict[str, float | int | str | None] = Field(default_factory=dict)
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    data_quality: StateQuality
    evidence_refs: list[StateEvidenceRef] = Field(default_factory=list, max_length=64)
    reason_codes: dict[str, list[ReasonCode]] = Field(default_factory=dict)
    warning_codes: list[str] = Field(default_factory=list, max_length=32)
    analyzer_version: str = ANALYZER_VERSION

    @model_validator(mode="after")
    def _validate_consistency(self) -> "StudentStateAssessment":
        if len(set(self.problem_types)) != len(self.problem_types):
            raise ValueError("problem_types 不得重复")
        if len(set(self.strengths)) != len(self.strengths):
            raise ValueError("strengths 不得重复")
        unknown_features = set(self.state_features) - STATE_FEATURE_KEYS
        if unknown_features:
            raise ValueError(f"state_features 含未登记键: {sorted(unknown_features)}")

        refs_by_code: dict[str, int] = {}
        for ref in self.evidence_refs:
            refs_by_code[ref.code] = refs_by_code.get(ref.code, 0) + 1
        for code in [*self.problem_types, *self.strengths]:
            if not self.reason_codes.get(code):
                raise ValueError(f"{code} 缺少 reason_codes")
            if not refs_by_code.get(code):
                raise ValueError(f"{code} 缺少 evidence_refs")
        # 风险信号自带 evidence_refs（schema 已强制非空），不再要求重复出现在顶层列表。

        # 证据不足必须同时体现在置信度上，否则策略层会拿它去触发激进策略。
        if "INSUFFICIENT_EVIDENCE" in self.problem_types:
            if self.overall_confidence > INSUFFICIENT_EVIDENCE_CONFIDENCE_CEILING:
                raise ValueError("INSUFFICIENT_EVIDENCE 必须伴随低置信度")
        # READY_FOR_CHALLENGE 只能在质量可靠时出现。
        if "READY_FOR_CHALLENGE" in self.problem_types:
            if self.data_quality not in {"verified", "partial"}:
                raise ValueError("READY_FOR_CHALLENGE 要求可靠的数据质量")
            if self.overall_confidence < CHALLENGE_CONFIDENCE_FLOOR:
                raise ValueError("READY_FOR_CHALLENGE 要求足够的置信度")
        return self

    def safe_summary(self) -> dict[str, Any]:
        """面向客户端的摘要：只有枚举码、置信度与质量，不含内部 id 与原始 JSON。"""
        return {
            "assessment_id": self.assessment_id,
            "goal_id": self.goal_id,
            "as_of": self.as_of,
            "problem_types": list(self.problem_types),
            "strengths": list(self.strengths),
            "risk_signals": [s.code for s in self.risk_signals],
            "data_quality": self.data_quality,
            "overall_confidence": self.overall_confidence,
            "warning_codes": list(self.warning_codes),
            "analyzer_version": self.analyzer_version,
        }


class StrategyPlanningParameters(BaseModel):
    """受约束的规划参数：全部有上下界，直接进入计划 input digest。"""

    model_config = ConfigDict(extra="forbid")

    max_plan_items: int = Field(..., ge=1, le=50)
    target_item_minutes: int = Field(..., ge=5, le=120)
    workload_scale: float = Field(..., ge=0.2, le=1.5)
    foundation_emphasis: float = Field(..., ge=0.0, le=1.0)
    challenge_level: Literal["REDUCED", "BASELINE", "ELEVATED"]
    pacing_mode: Literal["COMPRESSED", "STEADY", "AMBITIOUS"]


class StrategyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_code: StrategyCode
    strategy_version: str = STRATEGY_VERSION
    priority: int = Field(..., ge=1, le=99)
    rationale_codes: list[ReasonCode] = Field(..., min_length=1, max_length=16)
    supporting_state_types: list[str] = Field(default_factory=list, max_length=16)
    confidence: float = Field(..., ge=0.0, le=1.0)
    expected_outcomes: list[ExpectedOutcomeCode] = Field(..., min_length=1, max_length=8)
    planning_parameters: StrategyPlanningParameters
    warning_codes: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def _validate_strategy_semantics(self) -> "StrategyDecision":
        if self.strategy_code == "WORKLOAD_REDUCTION":
            if not {"workload_pressure_high", "schedule_conflict_observed"} & set(self.rationale_codes):
                raise ValueError("WORKLOAD_REDUCTION 必须由压力或冲突信号支撑")
        if self.strategy_code == "CHALLENGE_UPSHIFT":
            if self.confidence < CHALLENGE_CONFIDENCE_FLOOR:
                raise ValueError("CHALLENGE_UPSHIFT 要求足够的置信度")
        return self


class PlanningStrategyContext(BaseModel):
    """传给 LearningPlannerService 的策略上下文（只含安全字段）。"""

    model_config = ConfigDict(extra="forbid")

    strategy_code: StrategyCode
    strategy_version: str = STRATEGY_VERSION
    planning_parameters: StrategyPlanningParameters
    intervention_id: str | None = Field(None, max_length=64)
    baseline_core_run_id: str | None = Field(None, max_length=64)
    baseline_academic_run_id: str | None = Field(None, max_length=64)
    baseline_world_run_id: str | None = Field(None, max_length=64)
    rationale_codes: list[ReasonCode] = Field(default_factory=list, max_length=16)

    def digest_payload(self) -> dict[str, Any]:
        """进入计划 input digest 的稳定子集：策略规则一变，旧计划即失效。"""
        return {
            "strategy_code": self.strategy_code,
            "strategy_version": self.strategy_version,
            "planning_parameters": self.planning_parameters.model_dump(mode="json"),
        }

    def binding_payload(self) -> dict[str, Any]:
        """写入 learning_plan_runs.knowledge_bindings 的安全绑定。"""
        return {
            "intervention_id": self.intervention_id,
            "strategy_code": self.strategy_code,
            "strategy_version": self.strategy_version,
            "baseline_state_runs": {
                "core": self.baseline_core_run_id,
                "academic": self.baseline_academic_run_id,
                "world": self.baseline_world_run_id,
            },
        }


class AdaptiveInterventionOut(BaseModel):
    """学生本人可读的干预记录视图：不含 user_id、原始 JSON 或敏感证据。"""

    model_config = ConfigDict(extra="forbid")

    intervention_id: str
    goal_id: str
    plan_id: str | None = None
    status: str
    strategy_code: str
    strategy_version: str
    rationale_codes: list[str] = Field(default_factory=list)
    expected_outcomes: list[str] = Field(default_factory=list)
    baseline_core_run_id: str | None = None
    baseline_academic_run_id: str | None = None
    baseline_world_run_id: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    problem_types: list[str] = Field(default_factory=list)
    data_quality: str | None = None
    warning_codes: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class AdaptiveInterventionPage(BaseModel):
    items: list[AdaptiveInterventionOut]
    total: int
    page: int
    page_size: int
    has_more: bool


__all__ = [
    "ANALYZER_VERSION",
    "STRATEGY_VERSION",
    "INSUFFICIENT_EVIDENCE_CONFIDENCE_CEILING",
    "CHALLENGE_CONFIDENCE_FLOOR",
    "STATE_FEATURE_KEYS",
    "StateQuality",
    "Severity",
    "ProblemType",
    "StrengthCode",
    "RiskSignalCode",
    "ReasonCode",
    "StrategyCode",
    "ExpectedOutcomeCode",
    "StateEvidenceRef",
    "StateRiskSignal",
    "StudentStateAssessment",
    "StrategyPlanningParameters",
    "StrategyDecision",
    "PlanningStrategyContext",
    "AdaptiveInterventionOut",
    "AdaptiveInterventionPage",
]
