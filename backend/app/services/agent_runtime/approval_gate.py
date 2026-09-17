"""ApprovalGate —— 过期审批(§5.5)。

为需要确认的动作创建过期审批记录。过期绝不等于批准。
production 不能自动审批高风险动作。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from ...core.exceptions import AgentApprovalRequired, AgentRuntimeError
from ...repositories.agent_runtime_repository import AgentRuntimeRepository
from ...schemas.agent_contract_enums import ApprovalStatus, RiskLevel


class ApprovalGate:
    """审批门。"""

    def __init__(
        self,
        repository: AgentRuntimeRepository,
        *,
        default_ttl_minutes: int = 30,
    ) -> None:
        self._repo = repository
        self._ttl = timedelta(minutes=default_ttl_minutes)

    def require(
        self,
        *,
        run_id: str,
        user_id: str,
        risk_level: RiskLevel,
        action_summary: str,
        ttl_minutes: Optional[int] = None,
        tool_name: Optional[str] = None,
        request_hash: Optional[str] = None,
        call_id: Optional[str] = None,
    ) -> str:
        """创建审批记录。返回 approval_id。

        `tool_name` + `request_hash` 是**必需的安全绑定**：审批只对"这一个工具 +
        这一组参数"有效。缺了它们，一次批准就能被复用到另一门课程、另一种 mode
        或另一组参数上。`call_id` 仅由 Gateway 传入（绑定到具体工具调用）。
        """
        ttl = timedelta(minutes=ttl_minutes) if ttl_minutes else self._ttl
        expires_at = (datetime.now(timezone.utc) + ttl).isoformat()
        return self._repo.create_approval(
            run_id=run_id,
            user_id=user_id,
            risk_level=risk_level.value,
            action_summary=action_summary,
            expires_at=expires_at,
            tool_name=tool_name,
            request_hash=request_hash,
            call_id=call_id,
        )

    def resolve(
        self,
        approval_id: str,
        *,
        decision: str,
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        """处理审批决策。decision 为 APPROVED / REJECTED。

        语义（三条都必须成立）：

        1. **幂等**：同一个决定重复提交返回同一结果（`replayed=True`），
           不再像修复前那样抛 409 —— 客户端重试/网络重发不该被当成失败。
        2. **冲突**：一旦落定，相反的决定一律 409，绝不覆盖先到的决定。
        3. **原子**：并发下只有一个决定能落定（CAS），不会 lost update。
        """
        apv = self._repo.get_approval(approval_id)
        if not apv:
            raise AgentRuntimeError(
                "审批不存在", code="AGENT_RUN_NOT_FOUND", http_status=404
            )
        if user_id and apv.user_id != user_id:
            raise AgentRuntimeError(
                "无权处理该审批", code="AGENT_PERMISSION_DENIED", http_status=403
            )
        target = (
            ApprovalStatus.APPROVED.value
            if decision == "APPROVED"
            else ApprovalStatus.REJECTED.value
        )
        if apv.status != ApprovalStatus.PENDING.value:
            # 已落定：同向 → 幂等重放；反向 → 冲突。EXPIRED 同理（不能被"复活"）。
            if apv.status == target:
                return {
                    "approval_id": approval_id,
                    "status": apv.status,
                    "replayed": True,
                }
            raise AgentRuntimeError(
                f"审批已作出不同决定({apv.status})",
                code="AGENT_APPROVAL_CONFLICT",
                http_status=409,
            )
        # 检查过期
        now = datetime.now(timezone.utc)
        expires = datetime.fromisoformat(apv.expires_at)
        if now > expires:
            self._repo.resolve_approval(approval_id, status=ApprovalStatus.EXPIRED.value)
            raise AgentRuntimeError(
                "审批已过期", code="AGENT_INVALID_STATE", http_status=410
            )
        # MANUAL_ONLY 不能自动审批
        if apv.risk_level == RiskLevel.MANUAL_ONLY.value and decision == ApprovalStatus.APPROVED.value:
            if reason and reason.startswith("auto:"):
                raise AgentRuntimeError(
                    "MANUAL_ONLY 动作不能自动审批",
                    code="AGENT_PERMISSION_DENIED",
                    http_status=403,
                )
        if not self._repo.resolve_approval_if_pending(
            approval_id, status=target, decision_reason=reason
        ):
            # 竞态：另一个请求先落定了。按"已落定"规则收口，绝不覆盖。
            again = self._repo.get_approval(approval_id)
            settled = again.status if again else ApprovalStatus.EXPIRED.value
            if settled == target:
                return {"approval_id": approval_id, "status": settled, "replayed": True}
            raise AgentRuntimeError(
                f"审批已被其他请求处理({settled})",
                code="AGENT_APPROVAL_CONFLICT",
                http_status=409,
            )
        return {"approval_id": approval_id, "status": target, "replayed": False}

    def expire_all(self) -> int:
        """过期所有超时审批。返回过期条数。"""
        return self._repo.expire_approvals()


__all__ = ["ApprovalGate"]