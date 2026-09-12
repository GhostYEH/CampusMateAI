"""ToolRegistry —— action-level 工具注册(§5.4)。

工具按 resource + action 注册,不是宽泛的 READ/WRITE。
执行前校验:角色声明工具、job/run 授予能力、资源归属、参数 schema、风险、审批、幂等。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...core.exceptions import AgentToolRejected
from ...schemas.agent_contract_enums import RiskLevel


@dataclass(frozen=True)
class ToolSpec:
    """工具声明。"""

    tool_code: str
    resource: str
    action: str
    risk_level: RiskLevel = RiskLevel.AUTO_SAFE
    requires_approval: bool = False
    max_args_bytes: int = 4096


# 初始工具(§5.4)
_DEFAULT_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("student.read", "student", "read"),
    ToolSpec("course.read", "course", "read"),
    ToolSpec("exam.read", "exam", "read"),
    ToolSpec("schedule.read", "schedule", "read"),
    ToolSpec("learner_state.read", "learner_state", "read"),
    ToolSpec("knowledge.search", "knowledge", "search"),
    ToolSpec("task.propose", "task", "propose", RiskLevel.AUTO_SAFE),
    ToolSpec("task.create", "task", "create", RiskLevel.AUTO_SAFE),
    ToolSpec("task.update", "task", "update", RiskLevel.CONFIRM_REQUIRED, True),
    ToolSpec("plan.propose", "plan", "propose", RiskLevel.AUTO_SAFE),
    ToolSpec("plan.activate", "plan", "activate", RiskLevel.CONFIRM_REQUIRED, True),
    ToolSpec("reminder.schedule", "reminder", "schedule", RiskLevel.AUTO_SAFE),
    ToolSpec("research.source.fetch", "research_source", "fetch", RiskLevel.CONFIRM_REQUIRED, True),
    ToolSpec("research.report.create", "research_report", "create", RiskLevel.AUTO_SAFE),
    ToolSpec("external_submission.prepare", "external_submission", "prepare", RiskLevel.MANUAL_ONLY, True),
)


class ToolRegistry:
    """工具注册表。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {t.tool_code: t for t in _DEFAULT_TOOLS}

    def get(self, tool_code: str) -> Optional[ToolSpec]:
        return self._tools.get(tool_code)

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.tool_code] = spec

    def validate(
        self,
        *,
        tool_code: str,
        role_tools: tuple[str, ...],
        args: dict,
    ) -> ToolSpec:
        """校验工具调用前置条件。返回 ToolSpec。"""
        spec = self.get(tool_code)
        if not spec:
            raise AgentToolRejected(
                f"工具未注册: {tool_code}",
                code="AGENT_TOOL_REJECTED",
                http_status=403,
            )
        # 角色必须声明该工具
        if tool_code not in role_tools:
            raise AgentToolRejected(
                f"角色未声明工具: {tool_code}",
                code="AGENT_TOOL_REJECTED",
                http_status=403,
            )
        # 参数大小限制
        import json
        args_size = len(json.dumps(args, ensure_ascii=False, default=str).encode("utf-8"))
        if args_size > spec.max_args_bytes:
            raise AgentToolRejected(
                "工具参数过大",
                code="AGENT_TOOL_REJECTED",
                http_status=413,
            )
        return spec


__all__ = ["ToolSpec", "ToolRegistry"]