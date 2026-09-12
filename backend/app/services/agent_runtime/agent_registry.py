"""AgentRegistry —— 逻辑角色注册(§5.3)。

角色是代码拥有的版本化元数据。v1 由一个 AgentExecutor 切换角色执行,
不启动独立进程。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class AgentRole:
    """逻辑角色声明。"""

    agent_code: str
    version: str
    capabilities: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    model_policy: str = "reasoning_primary"
    permission_policy: str = "student_owned_only"


# 初始角色(§5.3)
_DEFAULT_ROLES: tuple[AgentRole, ...] = (
    AgentRole("planner", "1.0", ("plan.generate", "schedule.adapt"), ("course.read", "exam.read", "plan.propose"), "reasoning_primary"),
    AgentRole("analyzer", "1.0", ("plan.analyze",), ("course.read", "exam.read", "plan.propose"), "reasoning_primary"),
    AgentRole("notice_interpreter", "1.0", ("notice.interpret",), ("notice.read",), "fast_structured"),
    AgentRole("workflow_planner", "1.0", ("workflow.plan",), ("task.propose", "reminder.schedule"), "fast_structured"),
    AgentRole("coordinator", "1.0", ("research.coordinate",), ("course.read",), "reasoning_primary"),
    AgentRole("course_researcher", "1.0", ("research.course",), ("course.read", "knowledge.search"), "reasoning_primary"),
    AgentRole("web_researcher", "1.0", ("research.web",), ("research.source.fetch",), "fast_structured"),
    AgentRole("citation_verifier", "1.0", ("citation.verify",), ("research.source.fetch",), "dual_review"),
    AgentRole("tutor", "1.0", ("tutor.explain",), ("course.read", "knowledge.search"), "reasoning_primary"),
    AgentRole("critic", "1.0", ("critic.review",), ("course.read",), "dual_review"),
    AgentRole("synthesizer", "1.0", ("report.synthesize",), ("research.report.create",), "reasoning_primary"),
)


class AgentRegistry:
    """逻辑角色注册表。"""

    def __init__(self) -> None:
        self._roles: dict[str, AgentRole] = {r.agent_code: r for r in _DEFAULT_ROLES}

    def get(self, agent_code: str) -> Optional[AgentRole]:
        return self._roles.get(agent_code)

    def list_roles(self) -> list[AgentRole]:
        return list(self._roles.values())

    def register(self, role: AgentRole) -> None:
        """注册或覆盖角色(版本化)。"""
        self._roles[role.agent_code] = role

    def has_capability(self, agent_code: str, capability: str) -> bool:
        role = self.get(agent_code)
        if not role:
            return False
        return capability in role.capabilities

    def has_tool(self, agent_code: str, tool: str) -> bool:
        role = self.get(agent_code)
        if not role:
            return False
        return tool in role.tools


__all__ = ["AgentRole", "AgentRegistry"]