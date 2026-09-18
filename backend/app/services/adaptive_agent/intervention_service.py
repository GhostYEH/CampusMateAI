"""AdaptiveInterventionService —— 状态驱动干预的唯一编排入口。

数据流（Handler 只调用这里，不自己承担分析/策略/持久化/规划细节）：

    服务端状态投影(CORE/ACADEMIC/WORLD) + 预测 + 当前目标
      -> StudentStateAnalyzer        (结构化、可解释的状态评估)
      -> StrategyPolicy              (有限策略目录 + 稳定优先级)
      -> Adaptive Intervention Record(保存决策当时的基线状态 run 引用)
      -> LearningPlannerService      (按策略生成差异化计划)
      -> plan_id 回写干预记录

结果反馈与评估（第二阶段）：

    Adaptive Intervention Record + 计划观测(条目状态 + 计划级执行指标)
      -> InterventionOutcomeEvaluator(期望结果对账 + 执行信号 -> 可解释结论)
      -> intervention_evaluations    (同一份观测只落一行，按 input_digest 幂等)
      -> 干预记录推进 OBSERVING / EVALUATED

幂等性：计划生成以 `idempotency_key`（Agent Runtime 里按 Run 维度生成）为唯一键。
重放时复用既有干预记录与其中已固化的策略，不会产生第二条记录或第二个计划；
计划生成失败时把记录置为 CANCELLED，状态明确且不留无归属计划。
评估以 `input_digest`（观测输入摘要）为唯一键，同一份观测重复请求不会重复落库。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from ...models.adaptive_intervention import AdaptiveInterventionRow
from ...repositories.adaptive_intervention_repository import AdaptiveInterventionRepository
from ...schemas.adaptive_intervention import (
    InterventionEvaluation,
    PlanningStrategyContext,
    StrategyDecision,
    StudentStateAssessment,
)
from .outcome_evaluator import InterventionOutcomeEvaluator, PlanObservation
from .observation_window import ObservationWindowPolicy
from .state_analyzer import StudentStateAnalyzer
from .strategy_policy import StrategyPolicy

FORECAST_TYPES = (
    "DEADLINE_COMPLETION_RISK",
    "UPCOMING_WORKLOAD",
    "SCHEDULE_CONFLICT_RISK",
    "GOAL_PROGRESS_OUTLOOK",
    "ROUTINE_CONTINUITY",
)

# 观测窗口未结束但已经能下结论时的状态：正在收集结果信号。
OBSERVING_STATUS = "OBSERVING"
# 观测完整（执行完成或窗口已结束）时的状态。
EVALUATED_STATUS = "EVALUATED"
REPLAN_COOLDOWN_HOURS = 12
REPLAN_DAILY_LIMIT = 2
MAX_REPLAN_CHAIN_DEPTH = 3
# 这两类结论不落库、不推进状态：没有可评估的对象，或还没有开始执行。
_NON_PERSISTED_VERDICTS = frozenset({"NOT_OBSERVED"})


@dataclass(frozen=True)
class InterventionPlanResult:
    """一次状态驱动干预的可追踪结果。"""

    intervention: AdaptiveInterventionRow
    plan: Any
    assessment: StudentStateAssessment
    strategy: StrategyDecision
    reused_intervention: bool


@dataclass(frozen=True)
class InterventionOutcomeResult:
    """一次结果评估请求的返回。

    `evaluation` 总有值（干预记录不存在时整个返回为 None）：即使没有落库，
    调用方也能拿到"当前这份观测算出来的结论"。`persisted` 说明这份结论有没有
    真的写进 `intervention_evaluations` 并推进了干预状态。
    """

    intervention: AdaptiveInterventionRow
    evaluation: InterventionEvaluation
    persisted: bool
    reused_evaluation: bool


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
        outcome_evaluator: InterventionOutcomeEvaluator | None = None,
        observation_window_policy: ObservationWindowPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._analyzer = analyzer
        self._policy = policy
        self._planner = planner
        self._state_service = state_service
        self._forecast_service = forecast_service
        self._student_goal_repository = student_goal_repository
        # 评估器是无状态纯函数对象，缺省自带一个实例，避免调用方必须知道它存在。
        self._outcome_evaluator = outcome_evaluator or InterventionOutcomeEvaluator()
        self._observation_window_policy = observation_window_policy or ObservationWindowPolicy()

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

    def observe_and_evaluate(
        self,
        *,
        user_id: str,
        intervention_id: str,
        as_of: datetime | None = None,
        plan_metrics: dict[str, Any] | None = None,
    ) -> InterventionOutcomeResult | None:
        """对一条干预记录做结果评估，并把状态推进到 OBSERVING / EVALUATED。

        步骤：

        1. 读取干预记录与它绑定的计划（跨用户返回 None，由路由映射成 404）。
        2. 收集**真实执行信号**：计划条目状态直接来自 `learning_plan_items`；
           "由计划创建的个人待办是否被真的完成"复用 `LearningPlannerService.evaluate`
           的计划级观测，不在这里重算一遍任务归属。
        3. 交给 `InterventionOutcomeEvaluator` 做确定性对账。
        4. 只有结论**可落库**时才写库：
           - `INCONCLUSIVE`（拿不到计划 / 一条都判不了）不落库；
           - `NOT_OBSERVED`（窗口未结束且零执行）不落库；
           - 其余按观测是否完整推进到 `OBSERVING` 或 `EVALUATED`。

        `plan_metrics` 只用于测试注入；正常调用留空即可。

        刻意不触发任何 Agent 事件：评估是只读接口触发的观测动作，不是 Agent Runtime
        的执行阶段。新增事件类型会牵动跨端契约，属于另一个切片。
        """
        now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
        row = self._repository.get(user_id=user_id, intervention_id=intervention_id)
        if row is None:
            return None

        plan = self._load_plan(user_id=user_id, plan_id=row.plan_id) if row.plan_id else None
        metrics = plan_metrics if plan_metrics is not None else self._plan_metrics(user_id=user_id, row=row)
        observation = self._build_observation(row=row, plan=plan, metrics=metrics)
        result = self._outcome_evaluator.evaluate(intervention=row, observation=observation, as_of=now)

        incomplete_without_adoption = (
            result.evaluation.observed_outcome == "INSUFFICIENT_EVIDENCE"
            and result.evaluation.execution_signal in {"NOT_STARTED", "UNAVAILABLE"}
            and not bool(result.evaluation.execution_signals.get("window_elapsed"))
        )
        if row.status == "CANCELLED" or result.evaluation.verdict in _NON_PERSISTED_VERDICTS or incomplete_without_adoption:
            # 已取消：不复活、不覆盖既有评估。结论不落库：没有可评估的对象或还没开始执行。
            stored = self._repository.get_evaluation(user_id=user_id, intervention_id=intervention_id)
            return InterventionOutcomeResult(
                intervention=row, evaluation=result.evaluation,
                persisted=False, reused_evaluation=stored is not None,
            )

        existing = self._repository.find_evaluation_by_digest(
            user_id=user_id, intervention_id=intervention_id,
            evaluator_version=result.evaluation.evaluator_version,
            input_digest=result.input_digest,
        )
        if existing is not None:
            # 同一份观测已经评估过：复用，不重复写库也不重复推进状态。
            current = self._repository.get(user_id=user_id, intervention_id=intervention_id) or row
            return InterventionOutcomeResult(
                intervention=current, evaluation=self._restore_evaluation(existing),
                persisted=False, reused_evaluation=True,
            )

        target = EVALUATED_STATUS if bool(result.evaluation.execution_signals.get("window_elapsed")) else OBSERVING_STATUS
        self._repository.save_evaluation(
            user_id=user_id, intervention_id=intervention_id,
            evaluation=result.evaluation, input_digest=result.input_digest, status=target,
        )
        current = self._repository.get(user_id=user_id, intervention_id=intervention_id) or row
        return InterventionOutcomeResult(
            intervention=current, evaluation=result.evaluation,
            persisted=True, reused_evaluation=False,
        )

    def replan_from_evaluation(
        self, *, user_id: str, intervention_id: str, evaluation_id: str,
        decision_id: str, reason_codes: list[str], as_of: datetime,
    ) -> InterventionPlanResult | None:
        """Create and bind the successor before superseding the current intervention."""
        old = self._repository.get(user_id=user_id, intervention_id=intervention_id)
        if old is None or not old.plan_id or old.status in {"CANCELLED", "SUPERSEDED"}:
            return None
        if old.chain_depth >= MAX_REPLAN_CHAIN_DEPTH:
            return None
        day_start = as_of.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        if self._repository.has_replan_guard_violation(
            user_id=user_id, goal_id=old.goal_id, old_intervention_id=old.intervention_id,
            since=(as_of - timedelta(hours=REPLAN_COOLDOWN_HOURS)).isoformat(),
            day_start=day_start.isoformat(), daily_limit=REPLAN_DAILY_LIMIT,
        ):
            return None
        plan = self._load_plan(user_id=user_id, plan_id=old.plan_id)
        available = int(getattr(getattr(plan, "run", None), "available_minutes", 60) or 60)
        successor = self.plan_for_goal(
            user_id=user_id, goal_id=old.goal_id, available_minutes=available,
            idempotency_key=f"replan-evaluation:{evaluation_id}", as_of=as_of,
            supersedes_plan_id=old.plan_id, force_new=True,
        )
        self._repository.link_replanned(
            user_id=user_id, old_intervention_id=old.intervention_id,
            new_intervention_id=successor.intervention.intervention_id, evaluation_id=evaluation_id,
            decision_id=decision_id, reason_codes=reason_codes,
        )
        return successor

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
        due_at = self._observation_window_policy.due_at(
            planned_end=getattr(getattr(plan, "run", None), "window_end", None), generated_at=as_of,
        )
        bound = self._repository.bind_plan(
            user_id=user_id, intervention_id=intervention.intervention_id, plan_id=str(plan_id),
            observation_due_at=due_at.isoformat(),
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

    def _plan_metrics(self, *, user_id: str, row: AdaptiveInterventionRow) -> dict[str, Any] | None:
        """复用计划级观测拿"计划创建的任务是否被真的完成"。

        这是唯一能回答"学生是否真的做了"的既有信号：`learning_plan_items.execution_status`
        只反映待办有没有被建出来。观测失败时返回 None，让评估器把结论降级为"判不了"，
        而不是把"没拿到数据"当成"没有执行"。
        """
        if not row.plan_id:
            return None
        evaluate = getattr(self._planner, "evaluate", None)
        if evaluate is None:
            return None
        try:
            metrics = evaluate(user_id=user_id, plan_id=row.plan_id)
        except Exception:  # noqa: BLE001 - 计划级观测是增强项，缺失不能让结果接口 500
            return None
        return metrics if isinstance(metrics, dict) else None

    @staticmethod
    def _build_observation(*, row: AdaptiveInterventionRow, plan: Any, metrics: dict[str, Any] | None) -> PlanObservation | None:
        """把计划行转成评估器需要的观测输入；计划不存在时返回 None。"""
        if plan is None:
            return None
        run = plan.run
        items = tuple(
            {
                "item_id": item.item_id,
                "item_type": item.item_type,
                "estimated_minutes": int(item.estimated_minutes or 0),
                "execution_status": item.execution_status,
                "explanation_codes": tuple(item.explanation_codes or ()),
            }
            for item in (plan.items or [])
        )
        return PlanObservation(
            plan_id=plan.plan_id,
            run_id=run.run_id,
            allocated_minutes=int(run.allocated_minutes or 0),
            available_minutes=int(run.available_minutes or 0),
            # plan.valid_until 仅是规划输入的新鲜度；效果观测窗口由独立策略持久化。
            window_start=row.observation_started_at or row.created_at,
            window_end=row.observation_due_at,
            items=items,
            metrics=metrics,
        )

    @staticmethod
    def _restore_evaluation(row: InterventionEvaluationRow) -> InterventionEvaluation:
        return InterventionEvaluation.model_validate(json.loads(row.evaluation_json or "{}"))

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


__all__ = [
    "AdaptiveInterventionService",
    "InterventionPlanResult",
    "InterventionOutcomeResult",
    "FORECAST_TYPES",
]
