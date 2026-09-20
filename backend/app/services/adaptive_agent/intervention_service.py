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

from ...core.logging import logger
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
from .strategy_policy import FOUNDATION_EMPHASIS_ITEM_THRESHOLD, StrategyPolicy
from .state_normalizer import AdaptiveStateNormalizer

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
# 普通（非 Agent）计划的采纳幂等键前缀：一份计划最多产生一条干预记录。
PLAN_ADOPTION_KEY_PREFIX = "plan-adoption:"
# 无学生目标的普通计划用计划自身作为干预 scope 键的前缀。
#
# 这个前缀同时是**产品语义的判据**：没有绑定学生目标的计划缺少可归因的期望结果，
# 比较器会给出 `unknown_strategy_code` → INSUFFICIENT_EVIDENCE，决策收敛到
# WAIT_FOR_EVIDENCE。因此这类计划只做**观测 + 保守决策**，不参与自动重规划；
# 对外通过 `replan_supported=false` + `replan_unsupported_reason="no_goal_scope"` 显式说明。
PLAN_SCOPE_GOAL_PREFIX = "plan:"
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


def planner_goal_id(goal_scope: str | None) -> str | None:
    """把干预的 scope 键翻译成**规划器可接受**的 goal id。

    无学生目标的普通计划，scope 键是 `plan:{plan_id}` —— 它不是一个真实的学生目标。
    直接透传给 `LearningPlannerService.generate(goal_id=...)` 会被拒绝
    （`ValueError: goal 不存在、已归档或无权访问`），自动重规划就会在
    `stage=decision` 上以 FAILED 收场，计划永远换不掉。

    这里统一翻译成 `None`：规划器按"无目标计划"生成后继，
    与原始计划（同样无目标）结构可比，血缘照常由调用方在同一事务里写入。
    """
    if goal_scope is None or goal_scope.startswith(PLAN_SCOPE_GOAL_PREFIX):
        return None
    return goal_scope


class InterventionReuseConflict(ValueError):
    """同一幂等键对应的记录已经不可复用（已取消或已被替代）。"""


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
        learner_event_service: Any = None,
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
        self._state_normalizer = AdaptiveStateNormalizer(state_service=state_service)
        self._learner_event_service = learner_event_service

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
        strategy_adjustments: list[str] | None = None,
        force_new: bool = True,
        deferred_activation: bool = False,
        defer_lineage: bool = False,
        on_stage: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> InterventionPlanResult:
        now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)

        existing = self._repository.find_by_idempotency_key(
            user_id=user_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            # 幂等复用是有条件的：已取消/已被替代的记录不是有效结果。
            # 唯一的例外是"从未绑定过计划"的取消记录——那正是计划生成阶段失败后的
            # 重试路径（同一幂等键不能再插一行，只能继续推进既有记录）。
            if existing.status == "SUPERSEDED" or (existing.status == "CANCELLED" and existing.plan_id):
                raise InterventionReuseConflict(
                    f"干预记录 {existing.intervention_id} 处于 {existing.status}，不是有效的幂等后继"
                )
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
                deferred_activation=deferred_activation, strategy_adjustments=strategy_adjustments,
                defer_lineage=defer_lineage,
            )

        # scope 键可能不是真实目标（无目标普通计划用 `plan:{plan_id}`）：
        # 目标事实与目标范围预测都按"无目标"处理，但干预记录仍保留 scope 键。
        bound_goal_id = planner_goal_id(goal_id)
        goal = self._load_goal(user_id=user_id, goal_id=bound_goal_id) if bound_goal_id else None
        core = self._state_service.project_user(user_id, as_of=now, trigger="adaptive_intervention")
        academic = self._state_service.project_academic(user_id, as_of=now, trigger="adaptive_intervention")
        world = self._state_service.project_world(user_id, as_of=now, trigger="adaptive_intervention")
        forecasts = self._collect_forecasts(user_id=user_id, as_of=now, goal_id=bound_goal_id)

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
            strategy=strategy, reused_intervention=False, deferred_activation=deferred_activation,
            strategy_adjustments=strategy_adjustments, defer_lineage=defer_lineage,
        )

    def adopt_plan(
        self, *, user_id: str, plan_id: str, as_of: datetime | None = None
    ) -> AdaptiveInterventionRow | None:
        """把一份**学生已采纳**的既有计划纳入可观测闭环。

        与 `plan_for_goal` 的区别只有两点，正是"普通用户路径"需要的：

        - **不生成第二个计划**：学生已经确认的计划就是这份，不会被替换掉；
        - **不动计划血缘**：这里没有"新旧计划替换"，`supersedes_plan_id` 保持为空。

        其余全部复用同一条链路：三域投影 -> `StudentStateAnalyzer` ->
        `StrategyPolicy` -> 干预记录 -> 观测窗到期后由后台 Worker 评估/重规划。
        因此 CAS、租约、冷却、日上限、链深、事务血缘、幂等与崩溃恢复语义
        全部沿用既有实现，没有第二套规则。

        幂等：`(user_id, idempotency_key=plan-adoption:{plan_id})` 唯一，
        并且先按 `plan_id` 查一次——Agent `learning_goal` 路径已绑定的计划会直接复用。
        中途失败（记录已建、观测窗未写）也能被重试补完，不留"无归属记录"。
        """
        existing = self._repository.find_by_plan(user_id=user_id, plan_id=plan_id)
        if existing is not None:
            return existing
        plan = self._load_plan(user_id=user_id, plan_id=plan_id)
        if plan is None:
            return None

        now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
        plan_goal_id = getattr(getattr(plan, "run", None), "goal_id", None)
        # `adaptive_interventions.goal_id` 非空。普通计划可以不绑定学生目标，
        # 这时用计划自身的稳定 scope 键占位：既能满足约束，也让重规划防抖
        # 按"这份计划"而不是"某个不存在目标"分组。
        # 该前缀同时标记"不支持自动重规划"（见 PLAN_SCOPE_GOAL_PREFIX）。
        goal_id = plan_goal_id or f"{PLAN_SCOPE_GOAL_PREFIX}{plan_id}"
        goal = self._load_goal(user_id=user_id, goal_id=plan_goal_id) if plan_goal_id else None

        core = self._state_service.project_user(user_id, as_of=now, trigger="adaptive_plan_adoption")
        academic = self._state_service.project_academic(user_id, as_of=now, trigger="adaptive_plan_adoption")
        world = self._state_service.project_world(user_id, as_of=now, trigger="adaptive_plan_adoption")
        forecasts = self._collect_forecasts(user_id=user_id, as_of=now, goal_id=plan_goal_id)

        assessment = self._analyzer.analyze(
            user_id=user_id, as_of=now, core=core, academic=academic, world=world,
            forecasts=forecasts, goal=goal,
        )
        available_minutes = int(getattr(getattr(plan, "run", None), "available_minutes", 0) or 60)
        strategy = self._policy.select(
            assessment=assessment, goal=goal, available_minutes=available_minutes
        )
        baseline_digest = _digest({
            "assessment_id": assessment.assessment_id,
            "core_run_id": assessment.core_run_id,
            "academic_run_id": assessment.academic_run_id,
            "world_run_id": assessment.world_run_id,
        })
        intervention = self._repository.create(
            user_id=user_id, goal_id=goal_id, assessment=assessment, strategy=strategy,
            baseline_state_digest=baseline_digest,
            idempotency_key=f"{PLAN_ADOPTION_KEY_PREFIX}{plan_id}",
            status="PLAN_GENERATED", plan_id=plan_id,
        )
        due_at = self._observation_window_policy.due_at(
            planned_end=getattr(getattr(plan, "run", None), "window_end", None), generated_at=now,
        )
        return self._repository.bind_plan(
            user_id=user_id, intervention_id=intervention.intervention_id, plan_id=plan_id,
            observation_due_at=due_at.isoformat(), status="PLAN_GENERATED",
        ) or intervention

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
        # Re-reading an unchanged in-progress observation must be idempotent.
        # In particular, the audit event written after the first save must not
        # create a new projection run and a second evaluation for the same input.
        if row.evaluation_id and row.status == OBSERVING_STATUS:
            stored_row = self._repository.get_evaluation(user_id=user_id, intervention_id=intervention_id)
            if stored_row is not None:
                stored_eval = self._restore_evaluation(stored_row)
                old_signals = stored_eval.execution_signals or {}
                new_signals = self._outcome_evaluator._execution_signal(observation)[1] if observation else {}
                comparable = all(old_signals.get(key) == new_signals.get(key) for key in (
                    "planned_item_count", "completed_plan_task_count", "executed_item_count", "failed_item_count", "skipped_item_count"
                ))
                due = None
                try:
                    due = datetime.fromisoformat(str(row.observation_due_at).replace("Z", "+00:00")) if row.observation_due_at else None
                except ValueError:
                    due = None
                if comparable and (due is None or now < due):
                    current = self._repository.get(user_id=user_id, intervention_id=intervention_id) or row
                    return InterventionOutcomeResult(current, stored_eval, False, True)
        try:
            comparison = self._state_normalizer.compare(
                intervention=row, as_of=now, evaluation_id=row.evaluation_id,
                strategy_code=row.strategy_code,
            )
        except Exception as exc:  # noqa: BLE001 - 比较失败必须保守降级，但不能静默
            # 保守降级：拿不到比较结果时评估器会给出 INSUFFICIENT_EVIDENCE。
            # 但错误必须可观察：记录干预/评估 id、错误码与所处阶段，
            # 不记录学生隐私内容、证据正文或凭据。
            comparison = None
            logger.warning(
                "adaptive_state_comparison_failed stage=compare intervention_id={} evaluation_id={} error_code={}",
                row.intervention_id, row.evaluation_id or "none", type(exc).__name__,
            )
        result = self._outcome_evaluator.evaluate(
            intervention=row, observation=observation, as_of=now, state_comparison=comparison
        )

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
        if self._learner_event_service is not None:
            try:
                self._learner_event_service.record_intervention_event(
                    user_id=row.user_id, event_type="intervention_observed",
                    intervention_id=row.intervention_id, goal_id=row.goal_id,
                    evaluation_id=result.evaluation.evaluation_id,
                    occurred_at=now, outcome="observed_completed",
                    evidence_refs=[result.evaluation.evaluation_id],
                    adoption=result.evaluation.adoption,
                    observed_outcome=result.evaluation.observed_outcome,
                )
            except Exception:
                # The evaluation is durable, but its audit event is part of
                # the worker contract: surface the failure for retry instead
                # of silently claiming a complete observation.
                raise
        current = self._repository.get(user_id=user_id, intervention_id=intervention_id) or row
        return InterventionOutcomeResult(
            intervention=current, evaluation=result.evaluation,
            persisted=True, reused_evaluation=False,
        )

    def replan_from_evaluation(
        self, *, user_id: str, intervention_id: str, evaluation_id: str,
        decision_id: str, reason_codes: list[str], as_of: datetime,
        suggested_adjustments: list[str] | None = None,
    ) -> InterventionPlanResult | None:
        """Create and bind the successor before superseding the current intervention."""
        old = self._repository.get(user_id=user_id, intervention_id=intervention_id)
        if old is None or not old.plan_id:
            return None
        if old.superseded_by_intervention_id:
            successor_row = self._repository.get(user_id=user_id, intervention_id=old.superseded_by_intervention_id)
            if successor_row and successor_row.plan_id:
                assessment, strategy = self._restore(successor_row)
                return InterventionPlanResult(successor_row, self._load_plan(user_id=user_id, plan_id=successor_row.plan_id), assessment, strategy, True)
        if old.status in {"CANCELLED", "SUPERSEDED"}:
            return None
        if old.chain_depth >= MAX_REPLAN_CHAIN_DEPTH:
            return None
        if self.replan_guard_code(
            user_id=user_id, goal_id=old.goal_id, intervention_id=old.intervention_id,
            chain_depth=int(getattr(old, "chain_depth", 0) or 0), as_of=as_of,
        ) is not None:
            return None
        plan = self._load_plan(user_id=user_id, plan_id=old.plan_id)
        available = int(getattr(getattr(plan, "run", None), "available_minutes", 60) or 60)
        successor = self.plan_for_goal(
            user_id=user_id, goal_id=old.goal_id, available_minutes=available,
            idempotency_key=f"replan-decision:{decision_id}", as_of=as_of,
            supersedes_plan_id=old.plan_id, force_new=True,
            strategy_adjustments=suggested_adjustments or [],
            deferred_activation=True,
            # 关键：计划血缘**不能**在这里就落库。它必须和干预血缘在同一个事务里
            # 成对写入，否则一次绑定失败就会留下"计划已切换、干预还是旧的"。
            defer_lineage=True,
        )
        # 原子血缘：计划血缘（旧计划 -> 新计划）与干预血缘（旧干预 -> 新干预）
        # 必须在**同一个事务边界**内完成。任一步失败整体回滚，绝不会留下
        # "计划已切换但干预还没切换"（或反之）的半截状态。
        #
        # 失败时**不取消后继**：后继保持 PROPOSED 暂存态（既不是正式版本，
        # 也没有指向它的血缘），旧干预与旧计划仍然是正式版本。
        # 重试会复用同一个幂等后继，并在这里把血缘补齐。
        new_plan_id = getattr(successor.plan, "plan_id", None)
        with self._repository._db.transaction() as conn:
            if new_plan_id:
                self._planner.repository.link_superseded(
                    old_plan_id=old.plan_id, new_plan_id=str(new_plan_id), user_id=user_id,
                    replan_key=f"replan-decision:{decision_id}", conn=conn,
                )
            self._repository.link_replanned(
                user_id=user_id, old_intervention_id=old.intervention_id,
                new_intervention_id=successor.intervention.intervention_id, evaluation_id=evaluation_id,
                decision_id=decision_id, reason_codes=reason_codes, conn=conn,
            )
        return successor

    def replan_guard_code(
        self, *, user_id: str, goal_id: str, intervention_id: str,
        chain_depth: int, as_of: datetime,
    ) -> str | None:
        """防抖守卫的稳定 reason code；`None` 表示允许重规划。

        冷却 / 日限额 / 链深是**安全策略**而不是基础设施故障：命中时本轮应当
        转成带稳定 reason code 的 SUSPEND（保守等待），而不是记为 FAILED。
        判定顺序由仓储固定为 chain_depth -> daily_limit -> cooldown -> active，
        让每种情形都能被单独触发、单独断言。
        """
        day_start = as_of.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return self._repository.replan_guard_reason(
            user_id=user_id, goal_id=goal_id, old_intervention_id=intervention_id,
            chain_depth=int(chain_depth or 0),
            since=(as_of - timedelta(hours=REPLAN_COOLDOWN_HOURS)).isoformat(),
            day_start=day_start.isoformat(), daily_limit=REPLAN_DAILY_LIMIT,
            max_chain_depth=MAX_REPLAN_CHAIN_DEPTH,
        )

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
        strategy_adjustments: list[str] | None = None,
        force_new: bool,
        on_stage: Callable[[str, dict[str, Any]], None] | None,
        intervention: AdaptiveInterventionRow,
        assessment: StudentStateAssessment,
        strategy: StrategyDecision,
        reused_intervention: bool,
        deferred_activation: bool = False,
        defer_lineage: bool = False,
    ) -> InterventionPlanResult:
        strategy = self._apply_adjustments(strategy, strategy_adjustments or [])
        self._repository.update_strategy(
            user_id=user_id, intervention_id=intervention.intervention_id, strategy=strategy
        )
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
                # scope 键不是真实目标时必须翻译成 None，否则规划器直接拒绝，
                # 自动重规划会以 ValueError 收场（见 planner_goal_id）。
                goal_id=planner_goal_id(goal_id),
                window_start=window_start,
                window_end=window_end,
                idempotency_key=idempotency_key,
                force_new=force_new,
                supersedes_plan_id=supersedes_plan_id,
                replan_key=idempotency_key,
                strategy_context=strategy_context,
                defer_lineage=defer_lineage,
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
        if strategy_adjustments and not self._adjustments_reflected(plan, strategy, strategy_adjustments):
            self._repository.update_status(
                user_id=user_id, intervention_id=intervention.intervention_id, status="CANCELLED"
            )
            raise ValueError("suggested_adjustments_not_reflected")
        due_at = self._observation_window_policy.due_at(
            planned_end=getattr(getattr(plan, "run", None), "window_end", None), generated_at=as_of,
        )
        bound = self._repository.bind_plan(
            user_id=user_id, intervention_id=intervention.intervention_id, plan_id=str(plan_id),
            observation_due_at=due_at.isoformat(), status="PROPOSED" if deferred_activation else "PLAN_GENERATED",
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

    @staticmethod
    def _apply_adjustments(strategy: StrategyDecision, adjustments: list[str]) -> StrategyDecision:
        """Map the finite policy vocabulary to deterministic plan parameters."""
        params = strategy.planning_parameters.model_copy(deep=True)
        codes = set(adjustments)
        if "reduce_workload" in codes:
            params.workload_scale = max(0.2, round(params.workload_scale * 0.75, 3))
            params.max_plan_items = max(1, params.max_plan_items - 1)
        if "split_tasks" in codes:
            params.target_item_minutes = max(5, params.target_item_minutes - 10)
        if "reinforce_foundation" in codes:
            params.foundation_emphasis = min(1.0, round(params.foundation_emphasis + 0.25, 3))
            strategy.strategy_code = "FOUNDATION_REINFORCEMENT"
        if "lower_challenge" in codes:
            params.challenge_level = "REDUCED"
            params.pacing_mode = "STEADY"
        return strategy.model_copy(update={"planning_parameters": params})

    @staticmethod
    def _adjustments_reflected(plan: Any, strategy: StrategyDecision, adjustments: list[str]) -> bool:
        """每条建议必须能在新计划上找到**可验证**的落地效果。

        - `reduce_workload` / `split_tasks` 直接作用于计划结构（分配时长、单项时长），
          必须真的体现在计划上。
        - `reinforce_foundation` 先作用于策略参数：把 `foundation_emphasis` 抬到
          "追加基础复习项"的阈值之上，并把策略码切到 FOUNDATION_REINFORCEMENT。
          复习项本身只有在存在真实知识掌握观测 + 课程内容证据时才会被规划器追加
          （见 `LearningPlannerService._foundation_items`）。没有课程证据时要求
          "必须出现复习项"等于要求规划器编造内容，所以：有课程范围的计划必须出现
          复习项，没有课程范围的计划校验参数确实被抬过了阈值。
        """
        params = strategy.planning_parameters
        items = list(getattr(plan, "items", []) or [])
        run = getattr(plan, "run", None)
        if "reduce_workload" in adjustments and run is not None:
            if int(getattr(run, "allocated_minutes", 0) or 0) >= int(getattr(run, "available_minutes", 0) or 0):
                return False
        if "split_tasks" in adjustments and items:
            if max(int(getattr(item, "estimated_minutes", 0) or 0) for item in items) > params.target_item_minutes:
                return False
        if "reinforce_foundation" in adjustments:
            if params.foundation_emphasis < FOUNDATION_EMPHASIS_ITEM_THRESHOLD:
                return False
            course_scoped = [item for item in items if getattr(item, "course_id", None)]
            if course_scoped and not any(
                getattr(item, "item_type", None) == "REVIEW_AND_REFLECT" for item in items
            ):
                return False
        return True

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
    "PLAN_ADOPTION_KEY_PREFIX",
    "PLAN_SCOPE_GOAL_PREFIX",
]
