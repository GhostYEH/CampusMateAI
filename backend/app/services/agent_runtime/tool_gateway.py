"""ToolInvocationGateway —— 所有注册工具的唯一入口。

**任何工作流都不得绕过本入口直接执行注册工具。** 校验顺序固定为:

    运行/用户有效性 → Handler capability → Role permission → 参数 Schema
    → 资源归属 → Hard Deny → RiskEngine → ApprovalGate → 幂等原子声明
    → 领域 Service 执行 → 安全事件/审计

顺序不能调换:先做便宜且明确的拒绝,最后才产生副作用;审批与幂等声明之间
不允许插入任何领域写入,否则会留下"审批未通过但副作用已发生"的窗口。

隐私约束:
- 事件、审计与异常中只出现动作摘要、请求哈希、安全业务引用与错误码;
- 绝不写入 prompt、完整模型响应、凭据或原始工具参数。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel, ValidationError

from ...core.exceptions import (
    AgentOutputSchemaInvalid,
    AgentPermissionDenied,
    AgentRunCancelled,
    AgentRunNotFound,
    AgentRuntimeError,
    AgentToolRejected,
)
from ...repositories.agent_runtime_repository import AgentRuntimeRepository
from ...schemas.agent_contract_enums import RiskLevel
from .approval_gate import ApprovalGate
from .hard_deny import check_hard_deny
from .risk_engine import RiskEngine
from .tool_registry import ToolRegistry

# 领域副作用不被允许的状态:取消/终态运行不得再执行工具。
_TERMINAL_STATUSES = {"SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"}


def build_request_hash(tool_name: str, arguments: dict | None) -> str:
    """由规范化后的 `tool_name + arguments` 生成请求哈希(不受键顺序影响)。"""
    normalized = json.dumps(
        {"tool_name": tool_name, "arguments": arguments or {}},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _safe_result_ref(value: Any) -> dict[str, Any]:
    """只保留可安全回显的标量业务引用,禁止塞入整块领域对象或敏感载荷。"""
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, (str, int, float, bool)):
            safe[key] = item
    return safe


class ToolInvocationRequest(BaseModel):
    """一次工具调用请求。"""

    run_id: str
    role_code: str
    tool_name: str
    arguments: dict[str, Any] = {}
    idempotency_key: str


class ToolInvocationResult(BaseModel):
    """调用结果。`REPLAYED` 表示命中幂等声明,未重复执行领域副作用。"""

    status: Literal["COMPLETED", "AWAITING_APPROVAL", "REPLAYED"]
    call_id: str
    result_ref: Optional[dict[str, Any]] = None
    approval_id: Optional[str] = None


class ToolInvocationGateway:
    """固定顺序的工具策略入口。"""

    def __init__(
        self,
        repository: AgentRuntimeRepository,
        tools: ToolRegistry,
        risk_engine: Optional[RiskEngine] = None,
        approval_gate: Optional[ApprovalGate] = None,
        *,
        agent_registry: Any = None,
        handler_registry: Any = None,
        event_store: Any = None,
        approval_ttl_minutes: int = 30,
    ) -> None:
        self._repo = repository
        self._tools = tools
        self._risk = risk_engine or RiskEngine()
        self._approvals = approval_gate or ApprovalGate(repository)
        self._agents = agent_registry
        self._handlers = handler_registry
        self._events = event_store
        self._approval_ttl = approval_ttl_minutes

    async def invoke(self, request: ToolInvocationRequest) -> ToolInvocationResult:
        # 1. 运行/用户有效性
        run = self._repo.get_run(request.run_id)
        if run is None:
            raise AgentRunNotFound("Run 不存在")
        user_id = run["user_id"]
        if run["status"] in _TERMINAL_STATUSES:
            raise AgentRunCancelled(f"Run 已处于终态({run['status']}),不能再执行工具")

        # 2. Handler 必须声明该能力
        handler = None
        if self._handlers is not None:
            handler = self._handlers.get(run.get("handler_code") or "")
            if handler is None:
                raise AgentRuntimeError(
                    "运行对应的处理器不可用", code="AGENT_CAPABILITY_DISABLED", http_status=409
                )
            if request.tool_name not in tuple(getattr(handler, "tools", ()) or ()):
                raise AgentToolRejected(
                    f"处理器 {handler.code} 未声明工具: {request.tool_name}"
                )

        # 3. 角色必须被授权
        role = self._agents.get(request.role_code) if self._agents is not None else None
        if role is None:
            raise AgentToolRejected(f"未注册的角色: {request.role_code}")
        role_tools = tuple(getattr(role, "tools", ()) or ())
        if request.tool_name not in role_tools:
            raise AgentToolRejected(
                f"角色 {request.role_code} 未授权工具: {request.tool_name}"
            )

        # 4. 工具必须注册
        spec = self._tools.get(request.tool_name)
        if spec is None:
            raise AgentToolRejected(f"工具未注册: {request.tool_name}")

        # 5. 参数 Schema(替代"只看字节大小"的旧校验)
        arguments = self._validate_arguments(spec, request.arguments)

        # 6. 资源归属:AUTO_SAFE 也必须校验,不得跳过
        self._assert_ownership(spec, arguments, user_id)

        # 7. Hard Deny(不可被审批、配置或角色覆盖)
        check_hard_deny(request.tool_name, arguments)

        # 8. 风险分级。工具声明(spec)是权威策略,RiskEngine 负责 MANUAL_ONLY 硬前缀,
        #    并只允许"提高"风险,不允许把声明为 AUTO_SAFE 的工具降级放行。
        spec_risk = RiskLevel(spec.risk_level) if isinstance(spec.risk_level, str) else spec.risk_level
        user_enabled_auto = spec_risk is RiskLevel.AUTO_SAFE and not spec.requires_approval
        assessment = self._risk.assess(request.tool_name, user_enabled_auto=user_enabled_auto)
        if assessment.risk_level is RiskLevel.MANUAL_ONLY or spec_risk is RiskLevel.MANUAL_ONLY:
            # MANUAL_ONLY 永不由 Agent 自动执行,连审批都不能由 Agent 发起。
            raise AgentToolRejected(
                f"工具 {request.tool_name} 属于 MANUAL_ONLY,不能由 Agent 自动执行"
            )
        effective_risk = (
            RiskLevel.CONFIRM_REQUIRED
            if spec_risk is RiskLevel.CONFIRM_REQUIRED or assessment.risk_level is RiskLevel.CONFIRM_REQUIRED
            else RiskLevel.AUTO_SAFE
        )
        needs_approval = bool(spec.requires_approval) or effective_risk is RiskLevel.CONFIRM_REQUIRED

        # 9. 幂等原子声明(审批前先声明,避免重复开票)
        request_hash = build_request_hash(request.tool_name, arguments)
        call_id, is_new = self._repo.claim_tool_call(
            run_id=request.run_id,
            tool_name=request.tool_name,
            request_hash=request_hash,
            idempotency_key=request.idempotency_key,
        )
        if not is_new:
            existing = self._repo.get_tool_call(call_id) or {}
            if existing.get("status") == "completed":
                return ToolInvocationResult(
                    status="REPLAYED",
                    call_id=call_id,
                    result_ref=self._decode_result_ref(existing.get("result_digest")),
                )
            if existing.get("status") == "awaiting_approval":
                return ToolInvocationResult(
                    status="AWAITING_APPROVAL",
                    call_id=call_id,
                    approval_id=existing.get("error_code") or None,
                )

        # 10. 审批门:只保存动作摘要与请求哈希,不保存原始参数
        if needs_approval:
            approval_id = self._approvals.require(
                run_id=request.run_id,
                user_id=user_id,
                risk_level=effective_risk,
                action_summary=self._action_summary(spec, arguments),
                ttl_minutes=self._approval_ttl,
            )
            self._repo.record_tool_call_finish(
                call_id, status="awaiting_approval", result_digest=None,
                error_code=approval_id,
            )
            self._emit(request.run_id, "APPROVAL_REQUIRED", run["status"],
                       summary="工具调用需要用户确认", approval_id=approval_id)
            return ToolInvocationResult(
                status="AWAITING_APPROVAL", call_id=call_id, approval_id=approval_id
            )

        # 11. 领域 Service 执行
        if spec.executor is None:
            self._repo.record_tool_call_finish(
                call_id, status="failed", error_code="AGENT_TOOL_REJECTED"
            )
            raise AgentToolRejected(
                f"工具 {request.tool_name} 未绑定执行器,不能绕过领域 Service 直接调用"
            )
        try:
            # 执行器统一接收已校验参数字典,便于领域 Service 自行决定签名。
            outcome = spec.executor(arguments)
            if hasattr(outcome, "__await__"):
                outcome = await outcome
        except AgentRuntimeError as exc:
            self._repo.record_tool_call_finish(
                call_id, status="failed", error_code=exc.code
            )
            self._emit(request.run_id, "TOOL_FAILED", run["status"],
                       summary="工具调用失败")
            raise
        except Exception as exc:  # noqa: BLE001 - 统一收口为工具失败,不泄漏参数
            self._repo.record_tool_call_finish(
                call_id, status="failed", error_code="AGENT_INVALID_STATE"
            )
            self._emit(request.run_id, "TOOL_FAILED", run["status"],
                       summary="工具调用失败")
            raise AgentRuntimeError(
                "工具执行失败", code="AGENT_INVALID_STATE", http_status=409
            ) from exc

        result_ref = _safe_result_ref(getattr(spec, "result_builder", None)(outcome)
                                      if getattr(spec, "result_builder", None) else None)
        self._repo.record_tool_call_finish(
            call_id, status="completed",
            result_digest=json.dumps(result_ref, ensure_ascii=False) if result_ref else None,
        )
        self._emit(request.run_id, "TOOL_COMPLETED", run["status"],
                   summary=self._action_summary(spec, arguments))
        return ToolInvocationResult(
            status="COMPLETED", call_id=call_id, result_ref=result_ref or None
        )

    # ===== 内部步骤 =====

    @staticmethod
    def _validate_arguments(spec, arguments: dict) -> dict:
        model = getattr(spec, "args_model", None)
        if model is None:
            return dict(arguments or {})
        try:
            validated = model.model_validate(arguments or {})
        except ValidationError as exc:
            raise AgentOutputSchemaInvalid("工具参数未通过 Schema 校验") from exc
        return validated.model_dump()

    @staticmethod
    def _assert_ownership(spec, arguments: dict, user_id: str) -> None:
        resolver = getattr(spec, "ownership_resolver", None)
        owner = None
        if resolver is not None:
            owner = resolver(arguments)
        else:
            field = getattr(spec, "ownership_field", "user_id") or "user_id"
            owner = arguments.get(field)
        if owner is None:
            return
        if str(owner) != str(user_id):
            raise AgentPermissionDenied("工具参数引用了不属于当前用户的资源")

    @staticmethod
    def _action_summary(spec, arguments: dict) -> str:
        builder = getattr(spec, "summary_builder", None)
        if builder is not None:
            try:
                return str(builder(arguments))[:256]
            except Exception:  # noqa: BLE001 - 摘要失败不影响安全边界
                pass
        return f"{spec.action}:{spec.resource}"

    @staticmethod
    def _decode_result_ref(raw: Optional[str]) -> Optional[dict[str, Any]]:
        if not raw:
            return None
        try:
            loaded = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return loaded if isinstance(loaded, dict) else None

    def _emit(self, run_id: str, event_type: str, status: str, *, summary: str,
              approval_id: Optional[str] = None) -> None:
        if self._events is None:
            return
        try:
            self._events.append(
                run_id=run_id, type=event_type, status=status, phase="WAITING_FOR_TOOL",
                role="runtime", summary=summary[:256], approval_id=approval_id,
            )
        except Exception:  # noqa: BLE001 - 审计写入失败不得回滚已完成的领域副作用
            pass


__all__ = [
    "ToolInvocationGateway",
    "ToolInvocationRequest",
    "ToolInvocationResult",
    "build_request_hash",
]
