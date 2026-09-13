from __future__ import annotations

from dataclasses import dataclass

from ...core.exceptions import AppException
from .agent_registry import AgentRegistry


@dataclass(frozen=True)
class ToolAuthorization:
    allowed: bool
    tool_name: str


class ToolRegistry:
    def __init__(self, agents: AgentRegistry) -> None:
        self._agents = agents

    def authorize(self, *, role: str, tool_name: str, actor_user_id: str, owner_user_id: str) -> ToolAuthorization:
        agent = self._agents.get(role)
        if agent is None or tool_name not in agent.tools or actor_user_id != owner_user_id:
            raise AppException(code="AGENT_PERMISSION_DENIED", http_status=403, message="Agent 无权执行该工具")
        return ToolAuthorization(True, tool_name)
