"""AgentExecutor —— 逻辑角色切换(§5.3)。

v1 由一个 executor 切换角色执行阶段,不启动独立进程。
研究角色可 fan out 有界检索调用,但无独立 agent 进程或递归委托。
"""
from __future__ import annotations

from typing import Optional

from ...repositories.agent_runtime_repository import AgentRuntimeRepository
from .agent_registry import AgentRegistry
from .event_store import AgentEventStore
from .tool_registry import ToolRegistry


class AgentExecutor:
    """逻辑角色执行器。"""

    def __init__(
        self,
        repository: AgentRuntimeRepository,
        registry: Optional[AgentRegistry] = None,
        tools: Optional[ToolRegistry] = None,
        event_store: Optional[AgentEventStore] = None,
    ) -> None:
        self._repo = repository
        self._registry = registry or AgentRegistry()
        self._tools = tools or ToolRegistry()
        self._events = event_store or AgentEventStore(repository)

    @property
    def registry(self) -> AgentRegistry:
        return self._registry

    @property
    def tools(self) -> ToolRegistry:
        return self._tools

    def begin_step(
        self,
        *,
        run_id: str,
        role: str,
        phase: str,
        sequence: int,
        summary: Optional[str] = None,
    ) -> str:
        """开始一个步骤。校验角色已注册。"""
        if not self._registry.get(role):
            raise ValueError(f"未知角色: {role}")
        return self._repo.create_step(
            run_id=run_id, role=role, phase=phase, sequence=sequence, summary=summary
        )

    def emit_event(
        self,
        *,
        run_id: str,
        type: str,
        status: str,
        phase: str,
        role: Optional[str] = None,
        summary: Optional[str] = None,
        progress: Optional[dict] = None,
        artifact_id: Optional[str] = None,
        approval_id: Optional[str] = None,
    ) -> tuple[str, int]:
        """发射事件。"""
        return self._events.append(
            run_id=run_id,
            type=type,
            status=status,
            phase=phase,
            role=role,
            summary=summary,
            progress=progress,
            artifact_id=artifact_id,
            approval_id=approval_id,
        )

    def validate_tool_for_role(
        self,
        *,
        role: str,
        tool_code: str,
        args: dict,
    ):
        """校验角色是否有权调用工具。"""
        role_spec = self._registry.get(role)
        if not role_spec:
            raise ValueError(f"未知角色: {role}")
        return self._tools.validate(
            tool_code=tool_code, role_tools=role_spec.tools, args=args
        )


__all__ = ["AgentExecutor"]