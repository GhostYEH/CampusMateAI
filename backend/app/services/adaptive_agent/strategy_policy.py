"""StrategyPolicy —— 有限、版本化、确定性的干预策略目录。

策略是**有限枚举**：LLM 不能创造策略码，也不能修改 `planning_parameters`。
规则按固定优先级求值，第一个命中的规则胜出，因此结果不依赖字典顺序、时间或随机数。

规则表（priority 越小优先级越高）：

| priority | 策略 | 触发条件 |
| --- | --- | --- |
| 1 | BALANCED_PROGRESS | 证据不足 / 状态不可用（不能拿缺失数据做激进判断） |
| 2 | WORKLOAD_REDUCTION | 工作量压力高 或 存在时间冲突（优先级高于挑战升级） |
| 3 | PACE_RECOVERY | 执行一致性低 / 目标停滞 / 节奏不稳 |
| 4 | FOUNDATION_REINFORCEMENT | 有可靠的知识薄弱证据 |
| 5 | CHALLENGE_UPSHIFT | 知识掌握好 + 执行高 + 压力低 + 置信度达标 |
| 6 | BALANCED_PROGRESS | 状态正常，保守沿用现有规划规则 |

`rationale_codes` 全部直接取自 assessment 的 reason codes，不新造理由；
知识薄弱 + 高压力时会选择减负/恢复节奏，但知识薄弱信号仍保留在理由里。
"""
from __future__ import annotations

from typing import Any, Sequence

from ...schemas.adaptive_intervention import (
    CHALLENGE_CONFIDENCE_FLOOR,
    STRATEGY_VERSION,
    StrategyDecision,
    StrategyPlanningParameters,
)

BASELINE_ITEM_MINUTES = 30
MAX_PLAN_ITEMS_LIMIT = 50
# foundation_emphasis 达到该阈值时，规划器才会新增基础复习项。
FOUNDATION_EMPHASIS_ITEM_THRESHOLD = 0.5

# 固定求值顺序，避免依赖 set/dict 的迭代顺序。
_PROBLEM_ORDER: tuple[str, ...] = (
    "WORKLOAD_PRESSURE_HIGH",
    "SCHEDULE_CONFLICT_PRESENT",
    "EXECUTION_CONSISTENCY_LOW",
    "GOAL_PROGRESS_STALLED",
    "ROUTINE_UNSTABLE",
    "KNOWLEDGE_FOUNDATION_WEAK",
    "INSUFFICIENT_EVIDENCE",
    "READY_FOR_CHALLENGE",
)

# 有限参数表：数值全部落在 schema 的上下界内。
_STRATEGY_PARAMETERS: dict[str, dict[str, Any]] = {
    "FOUNDATION_REINFORCEMENT": {
        "max_plan_items": 5, "target_item_minutes": 25, "workload_scale": 1.0,
        "foundation_emphasis": 0.7, "challenge_level": "REDUCED", "pacing_mode": "STEADY",
    },
    "WORKLOAD_REDUCTION": {
        "max_plan_items": 3, "target_item_minutes": 20, "workload_scale": 0.75,
        "foundation_emphasis": 0.4, "challenge_level": "REDUCED", "pacing_mode": "COMPRESSED",
    },
    "PACE_RECOVERY": {
        "max_plan_items": 3, "target_item_minutes": 15, "workload_scale": 0.7,
        "foundation_emphasis": 0.3, "challenge_level": "REDUCED", "pacing_mode": "COMPRESSED",
    },
    "BALANCED_PROGRESS": {
        "max_plan_items": MAX_PLAN_ITEMS_LIMIT, "target_item_minutes": BASELINE_ITEM_MINUTES,
        "workload_scale": 1.0, "foundation_emphasis": 0.2,
        "challenge_level": "BASELINE", "pacing_mode": "STEADY",
    },
    "CHALLENGE_UPSHIFT": {
        "max_plan_items": 10, "target_item_minutes": BASELINE_ITEM_MINUTES, "workload_scale": 1.15,
        "foundation_emphasis": 0.1, "challenge_level": "ELEVATED", "pacing_mode": "AMBITIOUS",
    },
}

_STRATEGY_EXPECTED_OUTCOMES: dict[str, list[str]] = {
    "FOUNDATION_REINFORCEMENT": ["FOUNDATION_REVIEW_INCREASED", "DEADLINE_PRIORITY_PRESERVED"],
    "WORKLOAD_REDUCTION": ["TOTAL_WORKLOAD_REDUCED", "ITEM_COUNT_REDUCED", "DEADLINE_PRIORITY_PRESERVED"],
    "PACE_RECOVERY": ["SHORT_ITEM_PRIORITIZED", "ITEM_COUNT_REDUCED", "EXECUTION_CONTINUITY_RESTORED"],
    "BALANCED_PROGRESS": ["BASELINE_RULES_PRESERVED", "DEADLINE_PRIORITY_PRESERVED"],
    "CHALLENGE_UPSHIFT": ["CHALLENGE_INCREASED", "DEADLINE_PRIORITY_PRESERVED"],
}


class StrategyPolicy:
    """从有限策略目录里按稳定优先级选出策略。"""

    version = STRATEGY_VERSION

    def select(
        self,
        *,
        assessment: Any,
        goal: Any = None,
        available_minutes: int = 60,
    ) -> StrategyDecision:
        problems = set(getattr(assessment, "problem_types", ()) or ())
        strengths = set(getattr(assessment, "strengths", ()) or ())
        quality = getattr(assessment, "data_quality", "unavailable")
        confidence = float(getattr(assessment, "overall_confidence", 0.0) or 0.0)

        if "INSUFFICIENT_EVIDENCE" in problems or quality == "unavailable":
            return self._decision(
                "BALANCED_PROGRESS", priority=1, assessment=assessment,
                available_minutes=available_minutes, extra_warnings=["insufficient_evidence"],
            )
        if "WORKLOAD_PRESSURE_HIGH" in problems or "SCHEDULE_CONFLICT_PRESENT" in problems:
            return self._decision(
                "WORKLOAD_REDUCTION", priority=2, assessment=assessment,
                available_minutes=available_minutes, extra_warnings=["workload_reduction_applied"],
            )
        if {"EXECUTION_CONSISTENCY_LOW", "GOAL_PROGRESS_STALLED", "ROUTINE_UNSTABLE"} & problems:
            return self._decision(
                "PACE_RECOVERY", priority=3, assessment=assessment,
                available_minutes=available_minutes, extra_warnings=["pace_recovery_applied"],
            )
        if "KNOWLEDGE_FOUNDATION_WEAK" in problems:
            return self._decision(
                "FOUNDATION_REINFORCEMENT", priority=4, assessment=assessment,
                available_minutes=available_minutes, extra_warnings=["foundation_reinforcement_applied"],
            )
        if (
            "READY_FOR_CHALLENGE" in problems
            and "EXECUTION_CONSISTENCY_HIGH" in strengths
            and "KNOWLEDGE_MASTERY_RELATIVELY_STRONG" in strengths
            and "WORKLOAD_MANAGEABLE" in strengths
            and quality in {"verified", "partial"}
            and confidence >= CHALLENGE_CONFIDENCE_FLOOR
        ):
            return self._decision(
                "CHALLENGE_UPSHIFT", priority=5, assessment=assessment,
                available_minutes=available_minutes, extra_warnings=["challenge_upshift_applied"],
            )
        return self._decision(
            "BALANCED_PROGRESS", priority=6, assessment=assessment,
            available_minutes=available_minutes, extra_warnings=[],
        )

    # ------------------------------------------------------------------ 内部

    def _decision(
        self,
        strategy_code: str,
        *,
        priority: int,
        assessment: Any,
        available_minutes: int,
        extra_warnings: Sequence[str],
    ) -> StrategyDecision:
        warnings = list(dict.fromkeys(extra_warnings))
        if getattr(assessment, "data_quality", "unavailable") in {"stale", "unavailable"}:
            warnings.append("strategy_from_degraded_state")
        elif "data_quality_degraded" in (getattr(assessment, "warning_codes", ()) or ()):
            warnings.append("strategy_from_degraded_state")
        return StrategyDecision(
            strategy_code=strategy_code,  # type: ignore[arg-type]
            strategy_version=self.version,
            priority=priority,
            rationale_codes=self._rationale(assessment),
            supporting_state_types=self._supporting_state_types(assessment),
            confidence=round(float(getattr(assessment, "overall_confidence", 0.0) or 0.0), 4),
            expected_outcomes=_STRATEGY_EXPECTED_OUTCOMES[strategy_code],  # type: ignore[arg-type]
            planning_parameters=self._parameters(strategy_code, available_minutes),
            warning_codes=list(dict.fromkeys(warnings)),
        )

    @staticmethod
    def _rationale(assessment: Any) -> list[str]:
        """理由只来自 assessment 的 reason codes，顺序固定。"""
        reason_codes = getattr(assessment, "reason_codes", {}) or {}
        problems = set(getattr(assessment, "problem_types", ()) or ())
        rationale: list[str] = []
        for code in _PROBLEM_ORDER:
            if code not in problems:
                continue
            for reason in reason_codes.get(code, ()) or ():
                if reason not in rationale:
                    rationale.append(reason)
        if not rationale:
            # 状态正常（只有正向信号）时，用正向 reason code 作为理由，不编造负面结论。
            for code in sorted(getattr(assessment, "strengths", ()) or ()):
                for reason in reason_codes.get(code, ()) or ():
                    if reason not in rationale:
                        rationale.append(reason)
        for signal in getattr(assessment, "risk_signals", ()) or ():
            for reason in getattr(signal, "reason_codes", ()) or ():
                if reason not in rationale:
                    rationale.append(reason)
        if not rationale:
            # assessment 校验器保证每个 problem/strength 都有 reason code；这里只是防御。
            rationale = ["evidence_insufficient"]
        return rationale[:16]

    @staticmethod
    def _supporting_state_types(assessment: Any) -> list[str]:
        codes = set(getattr(assessment, "problem_types", ()) or ())
        codes.update(getattr(assessment, "strengths", ()) or ())
        codes.update(getattr(signal, "code", "") for signal in getattr(assessment, "risk_signals", ()) or ())
        state_types = {
            ref.state_type
            for ref in getattr(assessment, "evidence_refs", ()) or ()
            if ref.code in codes and ref.state_type
        }
        return sorted(state_types)[:16]

    @staticmethod
    def _parameters(strategy_code: str, available_minutes: int) -> StrategyPlanningParameters:
        base = dict(_STRATEGY_PARAMETERS[strategy_code])
        minutes = max(1, min(int(available_minutes or 1), 1440))
        # 单项时长既不能超过总可用时长，也不能小于 5 分钟。
        # 计划项数量由 workload_scale 推导出的时长预算与 max_plan_items 共同约束，
        # 这里不再用 capacity 二次收紧，避免"每项 25 分钟却只允许 2 项"这类自相矛盾的组合。
        base["target_item_minutes"] = max(5, min(int(base["target_item_minutes"]), max(5, minutes)))
        return StrategyPlanningParameters(**base)


__all__ = [
    "StrategyPolicy",
    "BASELINE_ITEM_MINUTES",
    "FOUNDATION_EMPHASIS_ITEM_THRESHOLD",
]
