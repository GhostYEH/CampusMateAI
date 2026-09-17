"""learning_goal 工作流 —— 由 Handler 承载,不再写在 HTTP 路由里。

计划生成本身由 `LearningPlannerService` 负责,并且它已经按 `idempotency_key`
做了计划级幂等:相同键重复调用会返回首次生成的计划,不会重复落库。
因此崩溃后重排是安全的,Handler 的 `recover()` 默认选择重新入队。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from ....core.exceptions import AgentRuntimeError
from ...agent_runtime.event_store import AgentEventStore
from .base import HandlerContext, HandlerResult, RecoveryAction, RecoveryDecision

DEFAULT_AVAILABLE_MINUTES = 60


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
    """生成学习计划草案,并把 `plan_id` 作为业务引用写回 Job。"""

    code = "learning_goal"
    version = "1.0.0"
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
        enabled: bool = True,
    ) -> None:
        self._planner = planner
        self._events = event_store
        self.enabled = enabled

    @staticmethod
    def _planner_idempotency_key(context: HandlerContext) -> str:
        """按 Run 维度固定幂等键:崩溃重放复用同一计划,UI 重试(新 Run)会重新生成。"""
        return f"run:{context.run_id}"

    def _emit(self, context: HandlerContext, *, type: str, summary: str, phase: str) -> None:
        # 进度事件不伴随状态变化,可以直接 append;状态事件由 Worker 原子写入。
        if self._events is None:
            return
        self._events.append(
            run_id=context.run_id, type=type, status="RUNNING", phase=phase,
            role="planner", summary=summary,
        )

    async def execute(self, context: HandlerContext) -> HandlerResult:
        payload = self.input_model.model_validate(context.input_ref)
        # 从恢复点继续: 计划已经生成过就只补写回, 不再触发第二次领域副作用。
        resumed_plan_id = (context.checkpoint or {}).get("plan_id")
        if isinstance(resumed_plan_id, str) and resumed_plan_id:
            return HandlerResult(
                status="SUCCEEDED",
                job_output_patch={"plan_id": resumed_plan_id},
                checkpoint={"stage": "PLAN_GENERATED", "plan_id": resumed_plan_id},
                summary="计划草案已生成，等待学生确认",
            )

        self._emit(
            context, type="CONTEXT_READY", phase="CONTEXT_BUILDING",
            summary="正在汇总课程、截止时间、学习状态与个人任务",
        )
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
