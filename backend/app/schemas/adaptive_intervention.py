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
OUTCOME_EVALUATOR_VERSION = "adaptive-intervention-outcome-v1"

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


# ------------------------------------------------------------------ 结果反馈与评估
#
# 评估只做两件可验证的事：
#   1. **计划结构对账**：策略声明要达成的效果，是否真的落到了生成的计划上（fidelity）。
#   2. **真实执行观测**：计划项与由计划创建的个人待办，是否真的被推进（adoption）。
#
# 刻意不做的事：不重新投影状态后把"状态变好"归因给本次干预。观测到的状态变化
# 与本次干预之间没有可验证的因果链，写进结论就是编造。因此评估结论只由
# `expected_outcomes` 对账与执行信号共同决定，且每个判定都必须带证据引用。

# 观测是否已经收集完整。
ObservationStatus = Literal["NOT_STARTED", "IN_PROGRESS", "COMPLETE"]
# 执行信号：计划是否被真的推进。UNAVAILABLE 表示拿不到计划，不是"没执行"。
ExecutionSignal = Literal["NOT_STARTED", "IN_PROGRESS", "COMPLETED", "UNAVAILABLE"]
# 执行采纳与计划结构对账不同：任务完成只说明学生采纳了计划。
AdoptionStatus = ExecutionSignal
# 只有可比较的前后状态证据才能得出状态结果；完成任务本身不是状态改善。
ObservedOutcome = Literal["IMPROVED", "STABLE", "DECLINED", "INSUFFICIENT_EVIDENCE"]
CausalClaim = Literal["NOT_ESTIMATED"]
# 策略声明与计划实际结构的一致程度。三值各有明确含义，不留"部分一致"这种含糊档位：
# MATCHED = 没有未通过的判定且至少一条可判定；MISMATCHED = 至少一条未通过；
# UNVERIFIABLE = 一条都判不了（没有计划或没有可判定的期望结果）。
PlanFidelity = Literal["MATCHED", "MISMATCHED", "UNVERIFIABLE"]
# 单条期望结果的对账判定。
OutcomeCheckVerdict = Literal["REALIZED", "NOT_REALIZED", "UNVERIFIABLE"]
# 本次干预是否有效的整体结论。
OutcomeVerdict = Literal[
    "NOT_OBSERVED", "EFFECTIVE", "PARTIALLY_EFFECTIVE", "INEFFECTIVE", "INCONCLUSIVE"
]

# 有限判定理由码：每条对账结论的解释只能取自这里。
OutcomeCheckReasonCode = Literal[
    "foundation_review_items_present",
    "foundation_review_items_missing",
    "allocated_below_available",
    "allocated_equals_available",
    "item_count_within_strategy_cap",
    "item_count_exceeds_strategy_cap",
    "item_minutes_within_target",
    "item_minutes_exceed_target",
    "execution_observed_on_plan",
    "execution_not_observed_on_plan",
    "strategy_parameters_baseline",
    "strategy_parameters_modified",
    "challenge_parameters_elevated",
    "challenge_parameters_not_elevated",
    "deadline_driven_items_present",
    "deadline_driven_items_missing",
    "no_plan_bound",
    "plan_not_found",
    "plan_has_no_items",
    "no_prior_deadline_pressure",
    "no_execution_signal_yet",
]

# 证据引用类型：只允许指向既有结构化对象，不复制正文。
OutcomeEvidenceKind = Literal[
    "INTERVENTION", "PLAN_RUN", "PLAN_ITEM", "PLAN_EVALUATION", "STRATEGY_DECISION"
]

# 执行信号的有限键集合：响应里不允许出现任意结构。
EXECUTION_SIGNAL_KEYS = frozenset({
    "planned_item_count",
    "executed_item_count",
    "failed_item_count",
    "skipped_item_count",
    "completed_plan_task_count",
    "evidence_coverage",
    "allocated_minutes",
    "available_minutes",
    "window_elapsed",
})

# 计划项上表示"由截止时间驱动"的解释码（规划器实际会写出的值）。
DEADLINE_DRIVEN_EXPLANATION_CODES = frozenset({
    "deadline_urgent",
    "upcoming_exam_exposure",
})
# 评估结论为 INEFFECTIVE 时的收口理由：窗口已过但零执行。
NO_ADOPTION_WARNING = "adoption_not_observed"


class OutcomeEvidenceRef(BaseModel):
    """结果评估的证据引用：只保存引用与判定依据码。"""

    model_config = ConfigDict(extra="forbid")

    kind: OutcomeEvidenceKind
    reference_id: str = Field(..., min_length=1, max_length=64)
    detail_code: str = Field(..., min_length=1, max_length=64)


class OutcomeCheck(BaseModel):
    """单条 `expected_outcomes` 的对账结果。"""

    model_config = ConfigDict(extra="forbid")

    code: ExpectedOutcomeCode
    verdict: OutcomeCheckVerdict
    reason_code: OutcomeCheckReasonCode
    evidence_refs: list[OutcomeEvidenceRef] = Field(..., min_length=1, max_length=8)


class InterventionEvaluation(BaseModel):
    """一次干预的结果评估。

    只描述"策略是否落到计划上"与"计划是否被推进"，不对未观测到的因果做断言。
    `user_id` 只用于服务端按用户隔离，不进入面向客户端的响应。
    """

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str = Field(..., min_length=1, max_length=64)
    intervention_id: str = Field(..., min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    goal_id: str = Field(..., min_length=1, max_length=128)
    plan_id: str | None = Field(None, max_length=64)
    as_of: str = Field(..., min_length=1, max_length=64)
    window_start: str | None = Field(None, max_length=64)
    window_end: str | None = Field(None, max_length=64)

    observation_status: ObservationStatus
    execution_signal: ExecutionSignal
    adoption: AdoptionStatus = "UNAVAILABLE"
    plan_fidelity: PlanFidelity
    verdict: OutcomeVerdict
    observed_outcome: ObservedOutcome = "INSUFFICIENT_EVIDENCE"
    causal_claim: CausalClaim = "NOT_ESTIMATED"
    state_comparison: dict[str, Any] = Field(default_factory=dict)

    outcome_checks: list[OutcomeCheck] = Field(default_factory=list, max_length=8)
    execution_signals: dict[str, float | int | str | bool | None] = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)
    data_quality: StateQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)
    evaluator_version: str = OUTCOME_EVALUATOR_VERSION

    @model_validator(mode="after")
    def _validate_consistency(self) -> "InterventionEvaluation":
        if len({check.code for check in self.outcome_checks}) != len(self.outcome_checks):
            raise ValueError("outcome_checks 不得重复同一个期望结果码")
        unknown = set(self.execution_signals) - EXECUTION_SIGNAL_KEYS
        if unknown:
            raise ValueError(f"execution_signals 含未登记键: {sorted(unknown)}")

        realized = [c for c in self.outcome_checks if c.verdict == "REALIZED"]
        not_realized = [c for c in self.outcome_checks if c.verdict == "NOT_REALIZED"]
        decidable = [c for c in self.outcome_checks if c.verdict != "UNVERIFIABLE"]

        # 结论必须能被对账结果与执行信号解释，不能出现"没有依据的有效"。
        # Legacy rows did not have observed_outcome.  A fully completed,
        # structure-matched legacy EFFECTIVE row has enough local evidence to
        # map to the new observed IMPROVED label; all other legacy verdicts
        # fall back conservatively below.
        if "observed_outcome" not in self.model_fields_set and self.verdict == "EFFECTIVE":
            if not (self.execution_signal == "COMPLETED" and self.plan_fidelity == "MATCHED" and self.outcome_checks and all(check.verdict == "REALIZED" for check in self.outcome_checks)):
                raise ValueError("EFFECTIVE legacy verdict lacks a complete structural evidence mapping")
            self.observed_outcome = "IMPROVED"
        if self.observed_outcome == "INSUFFICIENT_EVIDENCE" and self.verdict != "INCONCLUSIVE":
            self.verdict = "INCONCLUSIVE"
        if self.observed_outcome in {"DECLINED", "STABLE"} and self.verdict == "EFFECTIVE":
            self.verdict = "INCONCLUSIVE"
        if self.verdict == "EFFECTIVE":
            if self.observed_outcome != "IMPROVED":
                raise ValueError("EFFECTIVE 只能在观测到 IMPROVED 时出现")
            if self.plan_fidelity != "MATCHED":
                raise ValueError("EFFECTIVE 要求计划结构对账全部通过")
            if self.execution_signal != "COMPLETED":
                raise ValueError("EFFECTIVE 要求计划执行完成")
            if not decidable or len(realized) != len(decidable):
                raise ValueError("EFFECTIVE 不允许存在未通过的期望结果")
        if self.verdict == "NOT_OBSERVED" and self.execution_signal != "NOT_STARTED":
            raise ValueError("NOT_OBSERVED 只适用于尚未观测到执行的情况")
        if self.verdict == "INCONCLUSIVE":
            if self.observed_outcome == "IMPROVED" and self.execution_signal != "UNAVAILABLE" and decidable:
                raise ValueError("INCONCLUSIVE 要求缺少状态结果证据或拿不到计划")
        if self.observed_outcome == "IMPROVED" and self.causal_claim != "NOT_ESTIMATED":
            raise ValueError("IMPROVED 仍不能估计因果")
        if self.verdict == "PARTIALLY_EFFECTIVE" and not realized:
            raise ValueError("PARTIALLY_EFFECTIVE 要求至少一条期望结果通过")

        # 结构一致程度必须与逐条判定一致。
        if self.plan_fidelity == "MATCHED" and (not realized or not_realized):
            raise ValueError("MATCHED 要求没有未通过的判定且至少一条通过")
        if self.plan_fidelity == "MISMATCHED" and not not_realized:
            raise ValueError("MISMATCHED 要求至少一条判定为未通过")
        if self.plan_fidelity == "UNVERIFIABLE" and realized:
            raise ValueError("UNVERIFIABLE 不允许存在通过的判定")
        # 观测状态与执行信号不能互相矛盾：
        # COMPLETE 表示观测窗口已经完整覆盖，可以与"零执行"共存（那正是 INEFFECTIVE 的依据），
        # 但不可能与"拿不到计划"共存；NOT_STARTED 只能对应尚未开始执行。
        if self.observation_status == "COMPLETE" and self.execution_signal == "UNAVAILABLE":
            raise ValueError("UNAVAILABLE 不能标记为 COMPLETE 观测")
        if self.observation_status == "NOT_STARTED" and self.execution_signal not in {"NOT_STARTED", "UNAVAILABLE"}:
            raise ValueError("已观测到执行时观测状态不能是 NOT_STARTED")
        return self

    def safe_summary(self) -> dict[str, Any]:
        """面向客户端的摘要：枚举码 + 有限数值，不含内部 id 与原始 JSON。"""
        return {
            "intervention_id": self.intervention_id,
            "goal_id": self.goal_id,
            "plan_id": self.plan_id,
            "as_of": self.as_of,
            "observation_status": self.observation_status,
            "execution_signal": self.execution_signal,
            "adoption": self.adoption,
            "plan_fidelity": self.plan_fidelity,
            "verdict": self.verdict,
            "observed_outcome": self.observed_outcome,
            "causal_claim": self.causal_claim,
            "outcome_checks": [
                {"code": c.code, "verdict": c.verdict, "reason_code": c.reason_code}
                for c in self.outcome_checks
            ],
            "execution_signals": {
                key: self.execution_signals[key] for key in sorted(self.execution_signals)
            },
            "confidence": self.confidence,
            "data_quality": self.data_quality,
            "warning_codes": list(self.warning_codes),
            "evaluator_version": self.evaluator_version,
        }


class AdaptiveInterventionOutcomeOut(BaseModel):
    """学生本人可读的结果评估视图：不含 user_id、证据引用或原始 JSON。"""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    intervention_id: str
    goal_id: str
    plan_id: str | None = None
    # 这条干预的归因范围：
    # - `GOAL`：绑定真实学生目标，比较器按该策略的期望维度做归因；
    # - `PLAN`：普通计划未绑定目标，scope 是**这份计划本身**（`goal_id` 为 `plan:{plan_id}`）。
    #   它同样进入观测/评估/重规划闭环，只是归因范围按计划而非按目标。
    # 出网是为了让三端不必去猜 `goal_id` 的字符串前缀。
    scope_type: str = "GOAL"
    as_of: str
    window_start: str | None = None
    window_end: str | None = None
    observation_status: str
    execution_signal: str
    adoption: str
    plan_fidelity: str
    verdict: str
    observed_outcome: str = "INSUFFICIENT_EVIDENCE"
    causal_claim: str = "NOT_ESTIMATED"
    state_comparison: dict[str, Any] = Field(default_factory=dict)
    decision: str | None = None
    decision_reason_codes: list[str] = Field(default_factory=list)
    suggested_adjustments: list[str] = Field(default_factory=list)
    decision_confidence: float | None = Field(None, ge=0.0, le=1.0)
    decision_status: str | None = None
    lineage: dict[str, str | None] = Field(default_factory=dict)
    observation_due_at: str | None = None
    outcome_checks: list[dict[str, str]] = Field(default_factory=list)
    execution_signals: dict[str, float | int | str | bool | None] = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)
    data_quality: str | None = None
    warning_codes: list[str] = Field(default_factory=list)
    evaluator_version: str
    created_at: str


class AdaptiveInterventionOut(BaseModel):
    """学生本人可读的干预记录视图：不含 user_id、原始 JSON 或敏感证据。"""

    model_config = ConfigDict(extra="forbid")

    intervention_id: str
    goal_id: str
    plan_id: str | None = None
    # 见 AdaptiveInterventionOutcomeOut.scope_type。
    scope_type: str = "GOAL"
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
    observation_started_at: str | None = None
    observation_due_at: str | None = None
    evaluated_at: str | None = None
    outcome_verdict: str | None = None
    supersedes_intervention_id: str | None = None
    superseded_by_intervention_id: str | None = None
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
    "OUTCOME_EVALUATOR_VERSION",
    "INSUFFICIENT_EVIDENCE_CONFIDENCE_CEILING",
    "CHALLENGE_CONFIDENCE_FLOOR",
    "STATE_FEATURE_KEYS",
    "EXECUTION_SIGNAL_KEYS",
    "DEADLINE_DRIVEN_EXPLANATION_CODES",
    "NO_ADOPTION_WARNING",
    "StateQuality",
    "Severity",
    "ProblemType",
    "StrengthCode",
    "RiskSignalCode",
    "ReasonCode",
    "StrategyCode",
    "ExpectedOutcomeCode",
    "ObservationStatus",
    "ExecutionSignal",
    "AdoptionStatus",
    "ObservedOutcome",
    "CausalClaim",
    "PlanFidelity",
    "OutcomeCheckVerdict",
    "OutcomeVerdict",
    "OutcomeCheckReasonCode",
    "OutcomeEvidenceKind",
    "StateEvidenceRef",
    "StateRiskSignal",
    "StudentStateAssessment",
    "StrategyPlanningParameters",
    "StrategyDecision",
    "PlanningStrategyContext",
    "OutcomeEvidenceRef",
    "OutcomeCheck",
    "InterventionEvaluation",
    "AdaptiveInterventionOut",
    "AdaptiveInterventionOutcomeOut",
    "AdaptiveInterventionPage",
]
