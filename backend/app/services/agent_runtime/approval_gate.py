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
    ) -> str:
        """创建审批记录。返回 approval_id。"""
        ttl = timedelta(minutes=ttl_minutes) if ttl_minutes else self._ttl
        expires_at = (datetime.now(timezone.utc) + ttl).isoformat()
        return self._repo.create_approval(
            run_id=run_id,
            user_id=user_id,
            risk_level=risk_level.value,
            action_summary=action_summary,
            expires_at=expires_at,
        )

    def resolve(
        self,
        approval_id: str,
        *,
        decision: str,
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        """处理审批决策。decision 为 APPROVED / REJECTED。"""
        apv = self._repo.get_approval(approval_id)
        if not apv:
            raise AgentRuntimeError(
                "审批不存在", code="AGENT_RUN_NOT_FOUND", http_status=404
            )
        if user_id and apv.user_id != user_id:
            raise AgentRuntimeError(
                "无权处理该审批", code="AGENT_PERMISSION_DENIED", http_status=403
            )
        if apv.status != ApprovalStatus.PENDING.value:
            raise AgentRuntimeError(
                f"审批已处理({apv.status})",
                code="AGENT_INVALID_STATE",
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
        status = (
            ApprovalStatus.APPROVED.value
            if decision == "APPROVED"
            else ApprovalStatus.REJECTED.value
        )
        self._repo.resolve_approval(approval_id, status=status, decision_reason=reason)
        return {"approval_id": approval_id, "status": status}

    def expire_all(self) -> int:
        """过期所有超时审批。返回过期条数。"""
        return self._repo.expire_approvals()


__all__ = ["ApprovalGate"]