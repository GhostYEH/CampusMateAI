"""期末复习高风险写操作 —— 由 Handler 承载,经 `ToolInvocationGateway` 执行。

为什么要有这一层:
- 「激活计划版本」与「应用调整提案」会改动学生正在执行的复习计划,属于
  `CONFIRM_REQUIRED` 写操作,必须先由用户确认、再由 Gateway 复核后才落库;
- 迁移前这两步散落在 HTTP 路由里,请求线程直接写计划状态并把 Run 置为终态,
  进程在中间崩溃就会留下"计划已改、Run 未收口"的中间态,无法安全重放;
- 迁移后路由只负责**创建命令**(激活)或**解析用户审批**(调整决策),
  真正的领域副作用在 Handler 里发生,终态由 `AgentWorker` 原子写入。

幂等与恢复:
- 领域副作用由 Gateway 的 `claim_tool_call` 幂等声明保护,同一 Run 重复执行只会
  命中既有声明,不会产生第二次写入;
- Handler 自身再记一层 checkpoint:副作用已完成后即使进程崩溃,
  恢复时直接返回既有结果,不再触碰领域 Service;
- 因此"批准后进程重启"是可恢复的,且激活只会发生一次。

隐私约束:checkpoint 与 job output 只保存业务引用(计划版本、提案 id、状态),
不保存 prompt、模型响应、凭据或原始工具参数。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from ....core.exceptions import AgentRuntimeError
from ....schemas.agent_contract_enums import RiskLevel
from ..tool_gateway import ToolInvocationGateway, ToolInvocationRequest
from ..tool_registry import ToolSpec
from .base import HandlerContext, HandlerResult, RecoveryAction, RecoveryDecision

PLAN_ACTIVATE_TOOL = "final_review.plan.activate"
ADJUST_APPLY_TOOL = "final_review.adjust.apply"

# 每个 Run 只执行一次工具调用:同一 Run 的重放复用同一声明与同一结果。
_STAGE_APPLIED = "APPLIED"
_STAGE_AWAITING_APPROVAL = "AWAITING_APPROVAL"


class PlanActivateArgs(BaseModel):
    """`final_review.plan.activate` 的参数模型。"""

    model_config = ConfigDict(extra="forbid")

    campaign_id: str = Field(..., min_length=1, max_length=128)
    version: int = Field(..., ge=1)
    user_id: str = Field(..., min_length=1, max_length=128)


class AdjustApplyArgs(BaseModel):
    """`final_review.adjust.apply` 的参数模型。"""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(..., min_length=1, max_length=128)
    approved: bool = True
    user_id: str = Field(..., min_length=1, max_length=128)


class FinalReviewActivateInput(BaseModel):
    """`final_review_plan_activate` 的命令输入。未知键保持透传,不破坏旧客户端。"""

    model_config = ConfigDict(extra="allow")

    campaign_id: str = Field(..., min_length=1, max_length=128)
    version: int = Field(..., ge=1)
    approval_id: Optional[str] = None
    user_id: Optional[str] = None


class FinalReviewAdjustApplyInput(BaseModel):
    """`final_review_adjust_apply` 的命令输入。"""

    model_config = ConfigDict(extra="allow")

    proposal_id: str = Field(..., min_length=1, max_length=128)
    approved: bool = True
    approval_id: Optional[str] = None
    user_id: Optional[str] = None


def _owner_from_args(arguments: dict) -> Optional[str]:
    """资源归属解析:命令里的 `user_id` 必须与 Run 的属主一致。"""
    value = (arguments or {}).get("user_id")
    return str(value) if value else None


def build_plan_activate_tool(repository: Any) -> ToolSpec:
    """`final_review.plan.activate` 工具声明与执行器。"""

    def _execute(arguments: dict) -> dict:
        campaign_id = arguments["campaign_id"]
        version = int(arguments["version"])
        row = repository.activate_campaign(
            campaign_id, user_id=arguments["user_id"], version=version
        )
        if row is None:
            raise AgentRuntimeError(
                "campaign 不存在", code="AGENT_RUN_NOT_FOUND", http_status=404
            )
        return {"campaign_id": campaign_id, "active_version": version, "activated": True}

    return ToolSpec(
        tool_code=PLAN_ACTIVATE_TOOL,
        resource="final_review_plan",
        action="activate",
        risk_level=RiskLevel.CONFIRM_REQUIRED,
        requires_approval=True,
        args_model=PlanActivateArgs,
        ownership_resolver=_owner_from_args,
        executor=_execute,
        result_builder=lambda outcome: outcome,
        summary_builder=lambda args: f"激活期末复习计划版本 {args.get('version')}",
    )


def build_adjust_apply_tool(analyzer: Any) -> ToolSpec:
    """`final_review.adjust.apply` 工具声明与执行器。"""

    def _execute(arguments: dict) -> dict:
        return analyzer.apply_proposal(
            proposal_id=arguments["proposal_id"],
            user_id=arguments["user_id"],
            approved=bool(arguments["approved"]),
        )

    return ToolSpec(
        tool_code=ADJUST_APPLY_TOOL,
        resource="final_review_adjustment",
        action="apply",
        risk_level=RiskLevel.CONFIRM_REQUIRED,
        requires_approval=True,
        args_model=AdjustApplyArgs,
        ownership_resolver=_owner_from_args,
        executor=_execute,
        result_builder=lambda outcome: outcome,
        summary_builder=lambda args: f"应用期末复习调整提案 {args.get('proposal_id')}",
    )


class _GovernedFinalReviewHandler:
    """经 Gateway 执行的期末复习写操作基类。子类只声明工具与参数映射。"""

    code = ""
    version = "1.0.0"
    job_kind = ""
    enabled = True
    input_model: type[BaseModel] = FinalReviewActivateInput
    max_attempts = 3
    tools: tuple[str, ...] = ()

    tool_name = ""
    role_code = "planner"

    def __init__(
        self,
        gateway: ToolInvocationGateway,
        *,
        enabled: bool = True,
    ) -> None:
        self._gateway = gateway
        self.enabled = enabled

    # ===== 子类钩子 =====

    def _arguments(self, payload: BaseModel, context: HandlerContext) -> dict[str, Any]:
        raise NotImplementedError

    def _summary(self, payload: BaseModel, result_ref: dict[str, Any]) -> str:
        raise NotImplementedError

    # ===== 执行 =====

    def _idempotency_key(self, context: HandlerContext) -> str:
        """按 Run 维度固定幂等键:崩溃重放复用同一次领域副作用。"""
        return f"run:{context.run_id}"

    async def execute(self, context: HandlerContext) -> HandlerResult:
        payload = self.input_model.model_validate(context.input_ref)
        checkpoint = context.checkpoint or {}
        if checkpoint.get("stage") == _STAGE_APPLIED:
            # 副作用已完成:恢复时直接返回既有结果,不再触碰领域 Service。
            result_ref = dict(checkpoint.get("result") or {})
            return HandlerResult(
                status="SUCCEEDED",
                job_output_patch=result_ref,
                checkpoint=checkpoint,
                summary=self._summary(payload, result_ref),
            )

        approval_id = checkpoint.get("approval_id") or getattr(payload, "approval_id", None)
        outcome = await self._gateway.invoke(
            ToolInvocationRequest(
                run_id=context.run_id,
                role_code=self.role_code,
                tool_name=self.tool_name,
                arguments=self._arguments(payload, context),
                idempotency_key=self._idempotency_key(context),
                approval_id=approval_id,
            )
        )
        if outcome.status == "AWAITING_APPROVAL":
            return HandlerResult(
                status="AWAITING_APPROVAL",
                checkpoint={
                    "stage": _STAGE_AWAITING_APPROVAL,
                    "call_id": outcome.call_id,
                    "approval_id": outcome.approval_id,
                },
                summary="等待用户确认后执行",
            )

        result_ref = dict(outcome.result_ref or {})
        return HandlerResult(
            status="SUCCEEDED",
            job_output_patch=result_ref,
            checkpoint={
                "stage": _STAGE_APPLIED,
                "call_id": outcome.call_id,
                "result": result_ref,
            },
            summary=self._summary(payload, result_ref),
        )

    async def recover(self, context: HandlerContext) -> RecoveryDecision:
        """副作用由 Gateway 幂等声明与 checkpoint 双重保护,任何中断都可安全重排。"""
        return RecoveryDecision(action=RecoveryAction.REQUEUE, checkpoint=context.checkpoint)


class FinalReviewPlanActivateHandler(_GovernedFinalReviewHandler):
    """激活指定计划版本 —— 审批后的实际执行在这里发生。"""

    code = "final_review_plan_activate"
    job_kind = "final_review_plan_activate"
    input_model = FinalReviewActivateInput
    tool_name = PLAN_ACTIVATE_TOOL
    role_code = "planner"
    tools: tuple[str, ...] = (PLAN_ACTIVATE_TOOL,)

    def _arguments(self, payload: FinalReviewActivateInput, context: HandlerContext) -> dict[str, Any]:
        return {
            "campaign_id": payload.campaign_id,
            "version": int(payload.version),
            "user_id": context.user_id,
        }

    def _summary(self, payload: FinalReviewActivateInput, result_ref: dict[str, Any]) -> str:
        version = result_ref.get("active_version", payload.version)
        return f"复习计划版本 {version} 已激活"


class FinalReviewAdjustApplyHandler(_GovernedFinalReviewHandler):
    """应用调整提案(批准后创建新版本并激活)—— 审批后的实际执行在这里发生。"""

    code = "final_review_adjust_apply"
    job_kind = "final_review_adjust_apply"
    input_model = FinalReviewAdjustApplyInput
    tool_name = ADJUST_APPLY_TOOL
    role_code = "analyzer"
    tools: tuple[str, ...] = (ADJUST_APPLY_TOOL,)

    def _arguments(self, payload: FinalReviewAdjustApplyInput, context: HandlerContext) -> dict[str, Any]:
        return {
            "proposal_id": payload.proposal_id,
            "approved": bool(payload.approved),
            "user_id": context.user_id,
        }

    def _summary(self, payload: FinalReviewAdjustApplyInput, result_ref: dict[str, Any]) -> str:
        new_version = result_ref.get("new_version")
        if new_version:
            return f"调整提案已应用，生成计划版本 {new_version}"
        return "调整提案已处理"


__all__ = [
    "ADJUST_APPLY_TOOL",
    "AdjustApplyArgs",
    "FinalReviewActivateInput",
    "FinalReviewAdjustApplyHandler",
    "FinalReviewAdjustApplyInput",
    "FinalReviewPlanActivateHandler",
    "PLAN_ACTIVATE_TOOL",
    "PlanActivateArgs",
    "build_adjust_apply_tool",
    "build_plan_activate_tool",
]
