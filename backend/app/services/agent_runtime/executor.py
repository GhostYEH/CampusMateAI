from __future__ import annotations

import hashlib
import json

from ...core.exceptions import AppException
from ...repositories.agent_runtime_repository import AgentRuntimeRepository
from .risk_engine import RiskEngine
from .tool_registry import ToolRegistry


class AgentExecutor:
    def __init__(self, repository: AgentRuntimeRepository, tools: ToolRegistry, risk: RiskEngine) -> None:
        self._repository, self._tools, self._risk = repository, tools, risk

    def authorize_tool(self, *, run_id: str, role: str, tool_name: str, actor_user_id: str,
                       owner_user_id: str, arguments: dict, idempotency_key: str,
                       automation_enabled: bool) -> tuple[object, bool]:
        self._tools.authorize(role=role, tool_name=tool_name, actor_user_id=actor_user_id, owner_user_id=owner_user_id)
        risk = self._risk.classify(tool_name, automation_enabled=automation_enabled)
        if risk.risk_level == "MANUAL_ONLY":
            raise AppException(code="AGENT_TOOL_REJECTED", http_status=403, message="该操作仅支持手工完成")
        if risk.risk_level == "CONFIRM_REQUIRED":
            raise AppException(code="AGENT_APPROVAL_REQUIRED", http_status=409, message="需要用户确认后继续")
        digest = hashlib.sha256(json.dumps(arguments, sort_keys=True).encode()).hexdigest()
        return self._repository.begin_tool_call(
            run_id=run_id, tool_name=tool_name, idempotency_key=idempotency_key, request_hash=digest
        )
