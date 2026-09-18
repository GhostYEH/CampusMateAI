"""AdaptiveInterventionService —— 状态驱动干预的唯一编排入口。

数据流（Handler 只调用这里，不自己承担分析/策略/持久化/规划细节）：

    服务端状态投影(CORE/ACADEMIC/WORLD) + 预测 + 当前目标
      -> StudentStateAnalyzer        (结构化、可解释的状态评估)
      -> StrategyPolicy              (有限策略目录 + 稳定优先级)
      -> Adaptive Intervention Record(保存决策当时的基线状态 run 引用)
      -> LearningPlannerService      (按策略生成差异化计划)
      -> plan_id 回写干预记录

幂等性：以 `idempotency_key`（Agent Runtime 里按 Run 维度生成）为唯一键。
重放时复用既有干预记录与其中已固化的策略，不会产生第二条记录或第二个计划；
计划生成失败时把记录置为 CANCELLED，状态明确且不留无归属计划。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from ...models.adaptive_intervention import AdaptiveInterventionRow
from ...repositories.adaptive_intervention_repository import AdaptiveInterventionRepository
from ...schemas.adaptive_intervention import (
    PlanningStrategyContext,
    StrategyDecision,
    StudentStateAssessment,
)
from .state_analyzer import StudentStateAnalyzer
from .strategy_policy import StrategyPolicy

FORECAST_TYPES = (
    "DEADLINE_COMPLETION_RISK",
    "UPCOMING_WORKLOAD",
    "SCHEDULE_CONFLICT_RISK",
    "GOAL_PROGRESS_OUTLOOK",
    "ROUTINE_CONTINUITY",
)


@dataclass(frozen=True)
class InterventionPlanResult:
    """一次状态驱动干预的可追踪结果。"""

    intervention: AdaptiveInterventionRow
    plan: Any
    assessment: StudentStateAssessment
    strategy: StrategyDecision
    reused_intervention: bool


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AdaptiveInterventionService:
    def __init__(
        self,
        *,
        repository: AdaptiveInterventionRepository,
        analyzer: StudentStateAnalyzer,
        policy: StrategyPolicy,
        planner: Any,
        state_service: Any,
        forecast_service: Any = None,
        student_goal_repository: Any = None,
    ) -> None:
        self._repository = repository
        self._analyzer = analyzer
        self._policy = policy
        self._planner = planner
        self._state_service = state_service
        self._forecast_service = forecast_service
        self._student_goal_repository = student_goal_repository

    # ------------------------------------------------------------------ 公开

    def plan_for_goal(
        self,
        *,
        user_id: str,
        goal_id: str,
        available_minutes: int = 60,
        course_id: str | None = None,
        window_start: str | None = None,
        window_end: str | None = None,
        idempotency_key: str,
        agent_job_id: str | None = None,
        agent_run_id: str | None = None,
        as_of: datetime | None = None,
        supersedes_plan_id: str | None = None,
        force_new: bool = True,
        on_stage: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> InterventionPlanResult:
        now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)

        existing = self._repository.find_by_idempotency_key(
            user_id=user_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            assessment, strategy = self._restore(existing)
            if existing.plan_id:
                plan = self._load_plan(user_id=user_id, plan_id=existing.plan_id)
                if plan is not None:
                    return InterventionPlanResult(
                        intervention=existing, plan=plan, assessment=assessment,
                        strategy=strategy, reused_intervention=True,
                    )
            # 记录存在但计划缺失（上次在计划生成阶段失败）：复用同一记录继续推进。
            return self._generate_plan(
                user_id=user_id, goal_id=goal_id, available_minutes=available_minutes,
                course_id=course_id, window_start=window_start, window_end=window_end,
                idempotency_key=idempotency_key, agent_job_id=agent_job_id,
                agent_run_id=agent_run_id, as_of=now, supersedes_plan_id=supersedes_plan_id,
                force_new=force_new, on_stage=on_stage, intervention=existing,
                assessment=assessment, strategy=strategy, reused_intervention=True,
            )

        goal = self._load_goal(user_id=user_id, goal_id=goal_id)
        core = self._state_service.project_user(user_id, as_of=now, trigger="adaptive_intervention")
        academic = self._state_service.project_academic(user_id, as_of=now, trigger="adaptive_intervention")
        world = self._state_service.project_world(user_id, as_of=now, trigger="adaptive_intervention")
        forecasts = self._collect_forecasts(user_id=user_id, as_of=now, goal_id=goal_id)

        assessment = self._analyzer.analyze(
            user_id=user_id, as_of=now, core=core, academic=academic, world=world,
            forecasts=forecasts, goal=goal,
        )
        self._emit(on_stage, "STATE_ANALYZED", {
            "problem_types": list(assessment.problem_types),
            "data_quality": assessment.data_quality,
            "overall_confidence": assessment.overall_confidence,
        })

        strategy = self._policy.select(
            assessment=assessment, goal=goal, available_minutes=available_minutes
        )
        self._emit(on_stage, "STRATEGY_SELECTED", {
            "strategy_code": strategy.strategy_code,
            "strategy_version": strategy.strategy_version,
            "priority": strategy.priority,
            "confidence": strategy.confidence,
        })

        baseline_digest = _digest({
            "assessment_id": assessment.assessment_id,
            "core_run_id": assessment.core_run_id,
            "academic_run_id": assessment.academic_run_id,
            "world_run_id": assessment.world_run_id,
        })
        intervention = self._repository.create(
            user_id=user_id, goal_id=goal_id, assessment=assessment, strategy=strategy,
            baseline_state_digest=baseline_digest, idempotency_key=idempotency_key,
            agent_job_id=agent_job_id, agent_run_id=agent_run_id,
        )
        self._emit(on_stage, "INTERVENTION_RECORDED", {
            "intervention_id": intervention.intervention_id,
            "strategy_code": intervention.strategy_code,
            "status": intervention.status,
        })

        return self._generate_plan(
            user_id=user_id, goal_id=goal_id, available_minutes=available_minutes,
            course_id=course_id, window_start=window_start, window_end=window_end,
            idempotency_key=idempotency_key, agent_job_id=agent_job_id, agent_run_id=agent_run_id,
            as_of=now, supersedes_plan_id=supersedes_plan_id, force_new=force_new,
            on_stage=on_stage, intervention=intervention, assessment=assessment,
            strategy=strategy, reused_intervention=False,
        )

    def load_intervention(self, *, user_id: str, intervention_id: str) -> AdaptiveInterventionRow | None:
        return self._repository.get(user_id=user_id, intervention_id=intervention_id)

    # ------------------------------------------------------------------ 内部

    def _generate_plan(
        self,
        *,
        user_id: str,
        goal_id: str,
        available_minutes: int,
        course_id: str | None,
        window_start: str | None,
        window_end: str | None,
        idempotency_key: str,
        agent_job_id: str | None,
        agent_run_id: str | None,
        as_of: datetime,
        supersedes_plan_id: str | None,
        force_new: bool,
        on_stage: Callable[[str, dict[str, Any]], None] | None,
        intervention: AdaptiveInterventionRow,
        assessment: StudentStateAssessment,
        strategy: StrategyDecision,
        reused_intervention: bool,
    ) -> InterventionPlanResult:
        strategy_context = PlanningStrategyContext(
            strategy_code=strategy.strategy_code,
            strategy_version=strategy.strategy_version,
            planning_parameters=strategy.planning_parameters,
            intervention_id=intervention.intervention_id,
            baseline_core_run_id=intervention.baseline_core_run_id,
            baseline_academic_run_id=intervention.baseline_academic_run_id,
            baseline_world_run_id=intervention.baseline_world_run_id,
            rationale_codes=list(strategy.rationale_codes),
        )
        try:
            plan = self._planner.generate(
                user_id=user_id,
                available_minutes=available_minutes,
                course_id=course_id,
                goal_id=goal_id,
                window_start=window_start,
                window_end=window_end,
                idempotency_key=idempotency_key,
                force_new=force_new,
                supersedes_plan_id=supersedes_plan_id,
                replan_key=idempotency_key,
                strategy_context=strategy_context,
            )
        except Exception:
            # 计划生成失败：把干预记录收口到明确状态，不留"半生成"记录。
            self._repository.update_status(
                user_id=user_id, intervention_id=intervention.intervention_id, status="CANCELLED"
            )
            raise
        plan_id = getattr(plan, "plan_id", None)
        if not plan_id:
            self._repository.update_status(
                user_id=user_id, intervention_id=intervention.intervention_id, status="CANCELLED"
            )
            raise ValueError("学习计划服务未返回 plan_id")
        bound = self._repository.bind_plan(
            user_id=user_id, intervention_id=intervention.intervention_id, plan_id=str(plan_id)
        ) or intervention
        self._emit(on_stage, "PLAN_GENERATED", {
            "plan_id": str(plan_id),
            "intervention_id": bound.intervention_id,
            "strategy_code": bound.strategy_code,
            "item_count": len(getattr(plan, "items", []) or []),
            "allocated_minutes": int(getattr(getattr(plan, "run", None), "allocated_minutes", 0) or 0),
        })
        return InterventionPlanResult(
            intervention=bound, plan=plan, assessment=assessment, strategy=strategy,
            reused_intervention=reused_intervention,
        )

    def _restore(self, row: AdaptiveInterventionRow) -> tuple[StudentStateAssessment, StrategyDecision]:
        """从既有记录恢复已固化的评估与策略（重放时不重新做决策）。"""
        assessment = StudentStateAssessment.model_validate(json.loads(row.assessment_json or "{}"))
        strategy = StrategyDecision.model_validate(json.loads(row.strategy_json or "{}"))
        return assessment, strategy

    def _load_plan(self, *, user_id: str, plan_id: str) -> Any:
        repository = getattr(self._planner, "repository", None)
        if repository is None:
            return None
        try:
            return repository.get_plan(plan_id, user_id=user_id)
        except Exception:  # noqa: BLE001 - 计划读取失败不应让重放崩掉
            return None

    def _load_goal(self, *, user_id: str, goal_id: str) -> Any:
        if self._student_goal_repository is None:
            return None
        try:
            return self._student_goal_repository.get_goal(user_id=user_id, goal_id=goal_id)
        except Exception:  # noqa: BLE001 - 目标读取失败时降级为"无目标事实"，由规划器决定是否拒绝
            return None

    def _collect_forecasts(self, *, user_id: str, as_of: datetime, goal_id: str | None) -> list[Any]:
        """读取预测（只读增强项）。

        用 `list_forecasts` 一次收集输入算出全部 5 类预测；失败时逐个类型降级，
        任何一个类型不可用都不阻断干预，只是让 assessment 少一个信号。
        """
        if self._forecast_service is None:
            return []
        try:
            results, _total = self._forecast_service.list_forecasts(
                user_id=user_id, as_of=as_of, horizon_days=7, goal_id=goal_id,
                page=1, page_size=len(FORECAST_TYPES),
            )
            if results:
                return list(results)
        except Exception:  # noqa: BLE001 - 预测是增强项，缺失不能阻断干预
            pass
        forecasts: list[Any] = []
        for forecast_type in FORECAST_TYPES:
            try:
                forecasts.append(self._forecast_service.get_forecast(
                    user_id=user_id, as_of=as_of, forecast_type=forecast_type, horizon_days=7,
                    goal_id=goal_id if forecast_type == "GOAL_PROGRESS_OUTLOOK" else None,
                ))
            except Exception:  # noqa: BLE001
                continue
        return forecasts

    @staticmethod
    def _emit(
        on_stage: Callable[[str, dict[str, Any]], None] | None,
        stage: str,
        payload: dict[str, Any],
    ) -> None:
        if on_stage is None:
            return
        on_stage(stage, payload)


__all__ = ["AdaptiveInterventionService", "InterventionPlanResult", "FORECAST_TYPES"]
