"""learning_goal 工作流 —— 由 Handler 承载,不再写在 HTTP 路由里。

本 Handler 只做"编排 + 进度上报",业务细节全部交给
`AdaptiveInterventionService`（状态分析 → 策略选择 → 干预记录 → 差异化计划）：

    state snapshot -> assessment -> strategy -> intervention -> plan

幂等性沿用 Run 维度固定键：崩溃重放会复用同一条干预记录与同一份计划，
不会产生第二条 Intervention 或第二个 Plan；checkpoint 同时识别
`intervention_id`（已记录）与 `plan_id`（已生成）两个阶段。
未注入干预服务时退化为历史行为（只调用规划器），保持旧调用方兼容。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from ....core.exceptions import AgentRuntimeError
from ...agent_runtime.event_store import AgentEventStore
from .base import HandlerContext, HandlerResult, RecoveryAction, RecoveryDecision

DEFAULT_AVAILABLE_MINUTES = 60

# 阶段进度：事件只带枚举码与不透明 id，不带任何原始内容。
_STAGE_EVENTS: dict[str, tuple[str, str]] = {
    "STATE_ANALYZED": ("STATE_ANALYSIS", "已完成学习状态分析"),
    "STRATEGY_SELECTED": ("STRATEGY_SELECTION", "已选定干预策略"),
    "INTERVENTION_RECORDED": ("INTERVENTION_RECORD", "已记录本次干预决策"),
    "PLAN_GENERATED": ("PLAN_GENERATION", "计划草案已生成，等待学生确认"),
}


class LearningGoalInput(BaseModel):
    """`learning_goal` 的输入模型。未知键保持透传,不破坏旧客户端。"""

    model_config = ConfigDict(extra="allow")

    goal_id: str = Field(..., min_length=1, max_length=128)
    available_minutes: int = Field(DEFAULT_AVAILABLE_MINUTES, ge=1, le=1440)
    course_id: Optional[str] = None
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    plan_id: Optional[str] = None


class LearningGoalHandler:
    """生成差异化学习计划草案,并把 `plan_id` / `intervention_id` 写回 Job。"""

    code = "learning_goal"
    version = "1.1.0"
    job_kind = "learning_goal"
    enabled = True
    input_model = LearningGoalInput
    max_attempts = 3
    tools: tuple[str, ...] = ()

    def __init__(
        self,
        planner: Any,
        event_store: Optional[AgentEventStore] = None,
        *,
        intervention_service: Any = None,
        enabled: bool = True,
    ) -> None:
        self._planner = planner
        self._events = event_store
        self._intervention_service = intervention_service
        self.enabled = enabled

    @staticmethod
    def _planner_idempotency_key(context: HandlerContext) -> str:
        """按 Run 维度固定幂等键:崩溃重放复用同一计划与同一干预记录。"""
        return f"run:{context.run_id}"

    def _emit(self, context: HandlerContext, *, type: str, summary: str, phase: str) -> None:
        # 进度事件不伴随状态变化,可以直接 append;状态事件由 Worker 原子写入。
        if self._events is None:
            return
        self._events.append(
            run_id=context.run_id, type=type, status="RUNNING", phase=phase,
            role="planner", summary=summary,
        )

    def _emit_stage(self, context: HandlerContext, stage: str, payload: dict[str, Any]) -> None:
        phase, summary = _STAGE_EVENTS.get(stage, ("PLANNING", "干预流程推进中"))
        detail = ""
        if stage == "STRATEGY_SELECTED":
            detail = f"（{payload.get('strategy_code')}）"
        self._emit(context, type=stage, phase=phase, summary=f"{summary}{detail}")

    async def execute(self, context: HandlerContext) -> HandlerResult:
        payload = self.input_model.model_validate(context.input_ref)
        checkpoint = context.checkpoint or {}
        # 从恢复点继续: 计划已经生成过就只补写回, 不再触发第二次领域副作用。
        resumed_plan_id = checkpoint.get("plan_id")
        if isinstance(resumed_plan_id, str) and resumed_plan_id:
            patch: dict[str, Any] = {"plan_id": resumed_plan_id}
            resumed_intervention_id = checkpoint.get("intervention_id")
            if isinstance(resumed_intervention_id, str) and resumed_intervention_id:
                patch["intervention_id"] = resumed_intervention_id
            return HandlerResult(
                status="SUCCEEDED",
                job_output_patch=patch,
                checkpoint=dict(checkpoint),
                summary="计划草案已生成，等待学生确认",
            )

        self._emit(
            context, type="CONTEXT_READY", phase="CONTEXT_BUILDING",
            summary="正在汇总课程、截止时间、学习状态与个人任务",
        )
        if self._intervention_service is None:
            return await self._execute_legacy(context, payload)
        try:
            outcome = self._intervention_service.plan_for_goal(
                user_id=context.user_id,
                goal_id=payload.goal_id,
                available_minutes=payload.available_minutes,
                course_id=payload.course_id,
                window_start=payload.window_start,
                window_end=payload.window_end,
                idempotency_key=self._planner_idempotency_key(context),
                agent_job_id=context.job_id,
                agent_run_id=context.run_id,
                supersedes_plan_id=payload.plan_id,
                on_stage=lambda stage, data: self._emit_stage(context, stage, data),
            )
        except Exception as exc:  # noqa: BLE001 - 统一转成运行时错误,由 Worker 落 FAILED
            if isinstance(exc, AgentRuntimeError):
                raise
            raise AgentRuntimeError(
                "学习目标计划生成失败", code="AGENT_INVALID_STATE", http_status=409
            ) from exc
        plan_id = getattr(getattr(outcome, "plan", None), "plan_id", None)
        intervention_id = getattr(getattr(outcome, "intervention", None), "intervention_id", None)
        if not plan_id or not intervention_id:
            raise AgentRuntimeError(
                "状态驱动干预未返回 plan_id 或 intervention_id",
                code="AGENT_INVALID_STATE", http_status=409,
            )
        return HandlerResult(
            status="SUCCEEDED",
            job_output_patch={"plan_id": plan_id, "intervention_id": intervention_id},
            checkpoint={
                "stage": "PLAN_GENERATED",
                "plan_id": plan_id,
                "intervention_id": intervention_id,
                "intervention_status": getattr(outcome.intervention, "status", None),
                "strategy_code": getattr(outcome.intervention, "strategy_code", None),
            },
            summary="计划草案已生成，等待学生确认",
        )

    async def _execute_legacy(self, context: HandlerContext, payload: LearningGoalInput) -> HandlerResult:
        """未配置干预服务时的兼容路径：直接调用规划器（历史行为）。"""
        try:
            plan = self._planner.generate(
                user_id=context.user_id,
                goal_id=payload.goal_id,
                available_minutes=payload.available_minutes,
                course_id=payload.course_id,
                window_start=payload.window_start,
                window_end=payload.window_end,
                idempotency_key=self._planner_idempotency_key(context),
                force_new=True,
                supersedes_plan_id=payload.plan_id,
                replan_key=self._planner_idempotency_key(context),
            )
        except Exception as exc:  # noqa: BLE001 - 统一转成运行时错误,由 Worker 落 FAILED
            if isinstance(exc, AgentRuntimeError):
                raise
            raise AgentRuntimeError(
                "学习目标计划生成失败", code="AGENT_INVALID_STATE", http_status=409
            ) from exc
        plan_id = getattr(plan, "plan_id", None)
        if not plan_id:
            raise AgentRuntimeError(
                "学习计划服务未返回 plan_id", code="AGENT_INVALID_STATE", http_status=409
            )
        return HandlerResult(
            status="SUCCEEDED",
            job_output_patch={"plan_id": plan_id},
            checkpoint={"stage": "PLAN_GENERATED", "plan_id": plan_id},
            summary="计划草案已生成，等待学生确认",
        )

    async def recover(self, context: HandlerContext) -> RecoveryDecision:
        """计划生成是幂等的,任何中断都可以安全重排。"""
        return RecoveryDecision(action=RecoveryAction.REQUEUE, checkpoint=context.checkpoint)


__all__ = ["LearningGoalHandler", "LearningGoalInput"]
