"""InterventionOutcomeEvaluator —— 状态驱动干预的结果评估（确定性、无副作用）。

评估只回答两个**可验证**的问题：

1. **策略是否真的落到了计划上**（`plan_fidelity`）
   策略声明了 `expected_outcomes`（例如"总工作量降低""挑战加大"）。这些声明可以
   直接在生成的计划结构上对账：条目数有没有超过策略声明的上限、单项时长有没有
   超过策略声明的目标、加难策略有没有真的抬高挑战档位。对不上就是策略没落地。

2. **计划是否真的被推进**（`execution_signal`）
   计划项是否被物化成个人待办（`learning_plan_items.execution_status`），
   以及由计划创建的个人待办是否被学生真的完成（`completed_plan_task_count`）。
   后者才是"学生真的做了"的信号——计划项状态只反映"待办建出来了"。

**刻意不做的事**：不在观测窗口后重新投影状态、再把"状态变好"归因给本次干预。
观测到的状态变化与本次干预之间没有可验证的因果链（同期可能发生了考试周、换课、
生病等未观测事件），写进结论就是编造。因此结论只由对账结果与执行信号共同决定，
每一条判定都必须带证据引用（指向既有结构化对象，不复制正文）。

不做的事还有：不调用 LLM、不使用随机数、不依赖字典/set 的迭代顺序。
同一份观测输入必须产出完全相同的评估（包括 `evaluation_id`）。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ...models.adaptive_intervention import AdaptiveInterventionRow
from ...models.learning_plan import TASK_CREATING_ITEM_TYPES
from ...schemas.adaptive_intervention import (
    DEADLINE_DRIVEN_EXPLANATION_CODES,
    NO_ADOPTION_WARNING,
    OUTCOME_EVALUATOR_VERSION,
    InterventionEvaluation,
    OutcomeCheck,
    OutcomeEvidenceRef,
    StrategyDecision,
)

# 判定"存在截止时间压力"的理由码（来自 assessment 的 reason codes）。
DEADLINE_PRESSURE_REASON_CODES = frozenset({
    "deadline_concentration_observed",
    "upcoming_exam_exposure",
})
# 数据质量排序：verified 最好。取参与评估的各来源里最差的一个。
_QUALITY_RANK = {"verified": 3, "partial": 2, "stale": 1, "unavailable": 0}

# 评估输入不足时写入的警告码（有限集合，客户端按码展示）。
WARNING_PLAN_METRICS_UNAVAILABLE = "plan_metrics_unavailable"
WARNING_WINDOW_UNPARSABLE = "observation_window_unparsable"


@dataclass(frozen=True)
class PlanObservation:
    """一次评估用到的计划侧观测输入（全部来自既有结构化对象）。"""

    plan_id: str
    run_id: str
    allocated_minutes: int
    available_minutes: int
    window_start: str | None
    window_end: str | None
    core_quality: str
    items: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    metrics: dict[str, Any] | None = None

    @property
    def metrics_available(self) -> bool:
        return self.metrics is not None


@dataclass(frozen=True)
class OutcomeEvaluationResult:
    """评估结果 + 其输入摘要。

    `input_digest` 单独返回而不是塞进 `InterventionEvaluation`：它是持久化的幂等键，
    不是面向客户端的评估内容，放进 schema 会污染响应契约。
    """

    evaluation: InterventionEvaluation
    input_digest: str


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


class InterventionOutcomeEvaluator:
    """把干预记录 + 计划观测换算成一份可解释的结果评估。"""

    version = OUTCOME_EVALUATOR_VERSION

    # ------------------------------------------------------------------ 公开

    def evaluate(
        self,
        *,
        intervention: AdaptiveInterventionRow,
        observation: PlanObservation | None,
        as_of: datetime,
    ) -> OutcomeEvaluationResult:
        as_of = as_of.astimezone(timezone.utc).replace(microsecond=0)
        warnings: list[str] = []

        strategy = StrategyDecision.model_validate(json.loads(intervention.strategy_json or "{}"))
        expected_outcomes = self._expected_outcomes(intervention, strategy)
        rationale_codes = set(self._load_list(intervention.rationale_codes_json))

        if observation is None:
            # 拿不到计划：不是"没执行"，而是"没有可评估的对象"。
            checks = [
                OutcomeCheck(
                    code=code, verdict="UNVERIFIABLE",
                    reason_code="plan_not_found" if intervention.plan_id else "no_plan_bound",
                    evidence_refs=[self._ref("INTERVENTION", intervention.intervention_id, "no_plan")],
                )
                for code in expected_outcomes
            ]
            return self._build(
                intervention=intervention, strategy=strategy, checks=checks, observation=None,
                execution_signal="UNAVAILABLE", window_elapsed=False, warnings=warnings,
                metrics_available=False, as_of=as_of,
            )

        if observation.metrics is None:
            warnings.append(WARNING_PLAN_METRICS_UNAVAILABLE)
        window_end_at = _parse_iso(observation.window_end)
        if observation.window_end and window_end_at is None:
            warnings.append(WARNING_WINDOW_UNPARSABLE)
        # 窗口无法解析时按"未结束"处理：宁可不下"零执行"的结论，也不误判。
        window_elapsed = window_end_at is not None and as_of >= window_end_at

        signal, signals = self._execution_signal(observation)
        checks = [
            self._check(
                code, intervention=intervention, strategy=strategy, observation=observation,
                rationale_codes=rationale_codes, window_elapsed=window_elapsed,
            )
            for code in expected_outcomes
        ]
        return self._build(
            intervention=intervention, strategy=strategy, checks=checks, observation=observation,
            execution_signal=signal, window_elapsed=window_elapsed, warnings=warnings,
            metrics_available=observation.metrics_available, as_of=as_of, signals=signals,
        )

    # ------------------------------------------------------------ 执行信号

    def _execution_signal(self, observation: PlanObservation) -> tuple[str, dict[str, Any]]:
        """从计划项状态与计划级观测换算执行信号。

        `COMPLETED` 需要"由计划创建的任务真的被完成"，因此必须有计划级观测
        （`LearningPlannerService.evaluate` 的指标）。拿不到指标时最多只能到
        `IN_PROGRESS`：只凭"待办建出来了"不能判定干预被执行了。
        """
        items = observation.items
        planned = len(items)
        materialized = sum(1 for item in items if item["execution_status"] == "SUCCEEDED")
        failed = sum(1 for item in items if item["execution_status"] == "FAILED")
        skipped = sum(1 for item in items if item["execution_status"] == "SKIPPED")
        task_items = sum(1 for item in items if item["item_type"] in TASK_CREATING_ITEM_TYPES)

        metrics = observation.metrics or {}
        completed_tasks = int(metrics.get("completed_plan_task_count") or 0)
        executed = int(metrics.get("executed_item_count") or 0) if observation.metrics_available else materialized
        evidence_coverage = float(metrics.get("evidence_coverage") or 0.0) if observation.metrics_available else 0.0

        if task_items > 0:
            if materialized == 0 and completed_tasks == 0:
                signal = "NOT_STARTED"
            elif observation.metrics_available and completed_tasks >= task_items:
                signal = "COMPLETED"
            else:
                signal = "IN_PROGRESS"
        else:
            # 计划里没有"会创建任务"的条目（例如只有复习项）：只能观测物化程度。
            if planned == 0 or materialized == 0:
                signal = "NOT_STARTED"
            elif materialized == planned:
                signal = "COMPLETED"
            else:
                signal = "IN_PROGRESS"

        signals: dict[str, Any] = {
            "planned_item_count": planned,
            "executed_item_count": executed,
            "failed_item_count": failed,
            "skipped_item_count": skipped,
            "completed_plan_task_count": completed_tasks,
            "evidence_coverage": evidence_coverage,
            "allocated_minutes": observation.allocated_minutes,
            "available_minutes": observation.available_minutes,
        }
        return signal, signals

    # ------------------------------------------------------------ 逐条对账

    def _check(
        self,
        code: str,
        *,
        intervention: AdaptiveInterventionRow,
        strategy: StrategyDecision,
        observation: PlanObservation,
        rationale_codes: set[str],
        window_elapsed: bool,
    ) -> OutcomeCheck:
        params = strategy.planning_parameters
        items = observation.items
        plan_ref = self._ref("PLAN_RUN", observation.run_id, "plan_observation")
        strategy_ref = self._ref("STRATEGY_DECISION", intervention.intervention_id, "declared_parameters")

        if not items:
            # 空计划：任何"结构上应该出现"的声明都无法对账。
            return self._check_result(code, "UNVERIFIABLE", "plan_has_no_items", [plan_ref])

        if code == "FOUNDATION_REVIEW_INCREASED":
            review_items = [item for item in items if item["item_type"] == "REVIEW_AND_REFLECT"]
            if review_items:
                return self._check_result(
                    code, "REALIZED", "foundation_review_items_present",
                    [self._ref("PLAN_ITEM", item["item_id"], "review_item") for item in review_items[:4]],
                )
            return self._check_result(code, "NOT_REALIZED", "foundation_review_items_missing", [plan_ref])

        if code == "TOTAL_WORKLOAD_REDUCED":
            if observation.allocated_minutes < observation.available_minutes:
                return self._check_result(code, "REALIZED", "allocated_below_available", [plan_ref])
            return self._check_result(code, "NOT_REALIZED", "allocated_equals_available", [plan_ref])

        if code == "ITEM_COUNT_REDUCED":
            if len(items) <= params.max_plan_items:
                return self._check_result(code, "REALIZED", "item_count_within_strategy_cap", [plan_ref])
            return self._check_result(code, "NOT_REALIZED", "item_count_exceeds_strategy_cap", [plan_ref])

        if code == "SHORT_ITEM_PRIORITIZED":
            longest = max(int(item["estimated_minutes"]) for item in items)
            if longest <= params.target_item_minutes:
                return self._check_result(code, "REALIZED", "item_minutes_within_target", [plan_ref])
            return self._check_result(code, "NOT_REALIZED", "item_minutes_exceed_target", [plan_ref])

        if code == "EXECUTION_CONTINUITY_RESTORED":
            metrics = observation.metrics or {}
            completed_tasks = int(metrics.get("completed_plan_task_count") or 0)
            if completed_tasks >= 1:
                return self._check_result(
                    code, "REALIZED", "execution_observed_on_plan",
                    [self._ref("PLAN_EVALUATION", observation.plan_id, "completed_plan_tasks")],
                )
            if not observation.metrics_available:
                # 拿不到计划级观测就不能说"没有执行"，只能说"判不了"。
                return self._check_result(
                    code, "UNVERIFIABLE", "no_execution_signal_yet", [plan_ref]
                )
            if not window_elapsed:
                return self._check_result(
                    code, "UNVERIFIABLE", "no_execution_signal_yet", [plan_ref]
                )
            return self._check_result(
                code, "NOT_REALIZED", "execution_not_observed_on_plan",
                [self._ref("PLAN_EVALUATION", observation.plan_id, "no_completed_plan_tasks")],
            )

        if code == "BASELINE_RULES_PRESERVED":
            baseline = (
                params.workload_scale == 1.0
                and params.challenge_level == "BASELINE"
                and params.pacing_mode == "STEADY"
                and params.foundation_emphasis < 0.5
            )
            if baseline:
                return self._check_result(code, "REALIZED", "strategy_parameters_baseline", [strategy_ref])
            return self._check_result(code, "NOT_REALIZED", "strategy_parameters_modified", [strategy_ref])

        if code == "CHALLENGE_INCREASED":
            elevated = params.challenge_level == "ELEVATED" and params.workload_scale > 1.0
            if elevated:
                return self._check_result(
                    code, "REALIZED", "challenge_parameters_elevated", [strategy_ref, plan_ref]
                )
            return self._check_result(
                code, "NOT_REALIZED", "challenge_parameters_not_elevated", [strategy_ref]
            )

        if code == "DEADLINE_PRIORITY_PRESERVED":
            if not (rationale_codes & DEADLINE_PRESSURE_REASON_CODES):
                # 当时就没有截止时间压力，谈不上"保留优先级"。
                return self._check_result(
                    code, "UNVERIFIABLE", "no_prior_deadline_pressure", [strategy_ref]
                )
            deadline_items = [
                item for item in items
                if set(item["explanation_codes"]) & DEADLINE_DRIVEN_EXPLANATION_CODES
            ]
            if deadline_items:
                return self._check_result(
                    code, "REALIZED", "deadline_driven_items_present",
                    [self._ref("PLAN_ITEM", item["item_id"], "deadline_driven_item") for item in deadline_items[:4]],
                )
            return self._check_result(code, "NOT_REALIZED", "deadline_driven_items_missing", [plan_ref])

        # 契约是有限枚举；走到这里说明 schema 与评估器不同步。
        raise ValueError(f"未登记的期望结果码: {code}")

    # ---------------------------------------------------------------- 组装

    def _build(
        self,
        *,
        intervention: AdaptiveInterventionRow,
        strategy: StrategyDecision,
        checks: list[OutcomeCheck],
        observation: PlanObservation | None,
        execution_signal: str,
        window_elapsed: bool,
        warnings: list[str],
        metrics_available: bool,
        as_of: datetime,
        signals: dict[str, Any] | None = None,
    ) -> OutcomeEvaluationResult:
        realized = [c for c in checks if c.verdict == "REALIZED"]
        not_realized = [c for c in checks if c.verdict == "NOT_REALIZED"]
        decidable = [c for c in checks if c.verdict != "UNVERIFIABLE"]

        if observation is None:
            fidelity = "UNVERIFIABLE"
        elif not_realized:
            fidelity = "MISMATCHED"
        elif realized:
            fidelity = "MATCHED"
        else:
            fidelity = "UNVERIFIABLE"

        if observation is None or not decidable:
            verdict = "INCONCLUSIVE"
        elif not_realized and not realized:
            verdict = "INEFFECTIVE"
        elif not_realized:
            verdict = "PARTIALLY_EFFECTIVE"
        elif execution_signal == "COMPLETED":
            verdict = "EFFECTIVE"
        elif execution_signal == "NOT_STARTED" and not window_elapsed:
            verdict = "NOT_OBSERVED"
        elif execution_signal == "NOT_STARTED":
            # 观测窗口已经结束却一条执行记录都没有：干预没有被采纳。
            verdict = "INEFFECTIVE"
            warnings.append(NO_ADOPTION_WARNING)
        else:
            verdict = "PARTIALLY_EFFECTIVE"

        if execution_signal == "UNAVAILABLE":
            observation_status = "NOT_STARTED"
        elif execution_signal == "COMPLETED" or window_elapsed:
            # 窗口已经走完就是"观测完整"，即使一条执行记录都没有——那正是 INEFFECTIVE 的依据。
            observation_status = "COMPLETE"
        elif execution_signal == "NOT_STARTED":
            observation_status = "NOT_STARTED"
        else:
            observation_status = "IN_PROGRESS"

        quality = self._data_quality(intervention=intervention, observation=observation,
                                    metrics_available=metrics_available)
        confidence = self._confidence(
            checks=checks, execution_signal=execution_signal, observation=observation
        )

        final_signals: dict[str, Any] = dict(signals or {})
        final_signals.setdefault("planned_item_count", 0)
        final_signals.setdefault("executed_item_count", 0)
        final_signals.setdefault("failed_item_count", 0)
        final_signals.setdefault("skipped_item_count", 0)
        final_signals.setdefault("completed_plan_task_count", 0)
        final_signals.setdefault("evidence_coverage", 0.0)
        final_signals.setdefault("allocated_minutes", 0)
        final_signals.setdefault("available_minutes", 0)
        final_signals["window_elapsed"] = bool(window_elapsed)

        payload = {
            "intervention_id": intervention.intervention_id,
            "evaluator_version": self.version,
            "plan_id": intervention.plan_id,
            "plan_run_id": observation.run_id if observation else None,
            "item_states": [
                [item["item_id"], item["execution_status"]] for item in (observation.items if observation else ())
            ],
            "item_shapes": [
                [item["item_id"], item["item_type"], int(item["estimated_minutes"])]
                for item in (observation.items if observation else ())
            ],
            "plan_totals": (
                [observation.allocated_minutes, observation.available_minutes, observation.window_end]
                if observation else None
            ),
            "metrics": observation.metrics if observation else None,
            "window_elapsed": bool(window_elapsed),
            "expected_outcomes": [check.code for check in checks],
        }
        digest = _digest(payload)

        evaluation = InterventionEvaluation(
            # 由输入摘要派生：同一份观测必然得到同一个 evaluation_id，落库天然幂等。
            evaluation_id=f"inteval_{digest[:16]}",
            intervention_id=intervention.intervention_id,
            user_id=intervention.user_id,
            goal_id=intervention.goal_id,
            plan_id=intervention.plan_id,
            as_of=as_of.isoformat(),
            window_start=observation.window_start if observation else None,
            window_end=observation.window_end if observation else None,
            observation_status=observation_status,
            execution_signal=execution_signal,
            plan_fidelity=fidelity,
            verdict=verdict,
            outcome_checks=checks,
            execution_signals=final_signals,
            confidence=confidence,
            data_quality=quality,
            warning_codes=sorted(set(warnings)),
            evaluator_version=self.version,
        )
        return OutcomeEvaluationResult(evaluation=evaluation, input_digest=digest)

    def _data_quality(
        self, *, intervention: AdaptiveInterventionRow, observation: PlanObservation | None,
        metrics_available: bool,
    ) -> str:
        if observation is None:
            return "unavailable"
        candidates: list[str] = []
        assessment_quality = self._load_dict(intervention.assessment_json).get("data_quality")
        if isinstance(assessment_quality, str) and assessment_quality in _QUALITY_RANK:
            candidates.append(assessment_quality)
        if observation.core_quality in _QUALITY_RANK:
            candidates.append(observation.core_quality)
        if not metrics_available:
            # 计划级观测缺失：评估输入不完整，质量上限是 partial。
            candidates.append("partial")
        if not candidates:
            return "partial"
        return min(candidates, key=lambda value: _QUALITY_RANK[value])

    @staticmethod
    def _confidence(
        *, checks: list[OutcomeCheck], execution_signal: str, observation: PlanObservation | None
    ) -> float:
        """确定性置信度：由"可判定比例"与"执行观测完整度"决定，不含随机项。"""
        if observation is None or not checks:
            return 0.0
        decidable_ratio = len([c for c in checks if c.verdict != "UNVERIFIABLE"]) / len(checks)
        adoption = 1.0 if execution_signal == "COMPLETED" else (0.5 if execution_signal == "IN_PROGRESS" else 0.0)
        return round(min(1.0, 0.3 + 0.5 * decidable_ratio + 0.2 * adoption), 4)

    # ---------------------------------------------------------------- 工具

    @staticmethod
    def _expected_outcomes(intervention: AdaptiveInterventionRow, strategy: StrategyDecision) -> list[str]:
        """以记录里固化的 `expected_outcomes` 为准；缺失时回落到策略声明。

        顺序保持稳定（去重后按首次出现顺序），保证同一记录每次得到相同的对账顺序。
        """
        raw = InterventionOutcomeEvaluator._load_list(intervention.expected_outcomes_json)
        codes = [code for code in raw if isinstance(code, str)]
        if not codes:
            codes = [code for code in strategy.expected_outcomes]
        seen: set[str] = set()
        ordered: list[str] = []
        for code in codes:
            if code not in seen:
                seen.add(code)
                ordered.append(code)
        return ordered[:8]

    @staticmethod
    def _load_list(value: str | None) -> list[Any]:
        try:
            parsed = json.loads(value or "[]")
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []

    @staticmethod
    def _load_dict(value: str | None) -> dict[str, Any]:
        try:
            parsed = json.loads(value or "{}")
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _ref(kind: str, reference_id: str, detail_code: str) -> OutcomeEvidenceRef:
        return OutcomeEvidenceRef(kind=kind, reference_id=reference_id, detail_code=detail_code)

    @staticmethod
    def _check_result(
        code: str, verdict: str, reason_code: str, refs: list[OutcomeEvidenceRef]
    ) -> OutcomeCheck:
        return OutcomeCheck(
            code=code,  # type: ignore[arg-type]
            verdict=verdict,  # type: ignore[arg-type]
            reason_code=reason_code,  # type: ignore[arg-type]
            evidence_refs=refs,
        )


__all__ = [
    "InterventionOutcomeEvaluator",
    "PlanObservation",
    "OutcomeEvaluationResult",
    "DEADLINE_PRESSURE_REASON_CODES",
    "WARNING_PLAN_METRICS_UNAVAILABLE",
    "WARNING_WINDOW_UNPARSABLE",
]
