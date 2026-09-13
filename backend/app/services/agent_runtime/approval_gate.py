from __future__ import annotations

from datetime import datetime

from ...core.exceptions import AppException
from ...models.agent_runtime import AgentApprovalRow
from ...repositories.agent_runtime_repository import AgentRuntimeRepository


class ApprovalGate:
    def __init__(self, repository: AgentRuntimeRepository) -> None:
        self._repository = repository

    def create(self, *, run_id: str, user_id: str, action_digest: str, summary: str,
               expires_at: datetime, now: datetime) -> AgentApprovalRow:
        return self._repository.create_approval(
            run_id=run_id, user_id=user_id, risk_level="CONFIRM_REQUIRED",
            action_digest=action_digest, summary=summary,
            expires_at=expires_at.isoformat(), now=now.isoformat(),
        )

    def decide(self, *, approval_id: str, user_id: str, decision: str, now: datetime) -> AgentApprovalRow:
        approval = self._repository.get_approval(approval_id=approval_id, user_id=user_id)
        if approval is None:
            raise AppException(code="AGENT_PERMISSION_DENIED", http_status=404, message="审批不存在")
        if approval.status != "PENDING":
            raise AppException(code="AGENT_INVALID_STATE", http_status=409, message="审批已处理")
        status = "EXPIRED" if now >= datetime.fromisoformat(approval.expires_at) else decision
        if status not in {"APPROVED", "REJECTED", "EXPIRED"}:
            raise AppException(code="AGENT_INVALID_STATE", http_status=422, message="审批决策无效")
        result = self._repository.decide_approval(
            approval_id=approval_id, user_id=user_id, status=status, decided_at=now.isoformat()
        )
        assert result is not None
        return result
