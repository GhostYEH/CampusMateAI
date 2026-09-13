"""AgentRegistry —— 逻辑角色注册(§5.3)。

角色是**声明式元数据**:默认从 roles.default.json 读取,新增校园场景角色时
只改数据文件、不动运行时核心代码(对应 EvoFlow "先写 Skill,别加核心 tool" 的经验)。
文件缺失或损坏时回退到内置定义,保证运行时永远有可用角色。
v1 由一个 AgentExecutor 切换角色执行,不启动独立进程。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
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


_MANIFEST_PATH = Path(__file__).with_name("roles.default.json")


def load_roles_from_manifest(path: Path | str) -> tuple[AgentRole, ...]:
    """从 JSON 清单读取角色定义。清单格式:{"roles": [...]}。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("roles", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("角色清单格式不正确")
    roles: list[AgentRole] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("agent_code"):
            raise ValueError("角色条目缺少 agent_code")
        roles.append(
            AgentRole(
                agent_code=str(item["agent_code"]),
                version=str(item.get("version", "1.0")),
                capabilities=tuple(item.get("capabilities") or ()),
                tools=tuple(item.get("tools") or ()),
                model_policy=str(item.get("model_policy", "reasoning_primary")),
                permission_policy=str(item.get("permission_policy", "student_owned_only")),
            )
        )
    return tuple(roles)


class AgentRegistry:
    """逻辑角色注册表。"""

    def __init__(self, manifest_path: Optional[Path | str] = None) -> None:
        roles = _DEFAULT_ROLES
        path = Path(manifest_path) if manifest_path is not None else _MANIFEST_PATH
        try:
            if path.exists():
                loaded = load_roles_from_manifest(path)
                if loaded:
                    roles = loaded
        except Exception:
            # 清单损坏不能导致运行时没有角色:回退内置定义。
            roles = _DEFAULT_ROLES
        self._roles: dict[str, AgentRole] = {r.agent_code: r for r in roles}

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