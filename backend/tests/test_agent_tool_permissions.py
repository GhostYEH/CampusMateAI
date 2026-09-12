"""Tool permissions 测试 —— action-level 工具注册 + 角色校验。"""
from __future__ import annotations

import pytest

from app.core.exceptions import AgentToolRejected
from app.services.agent_runtime.agent_registry import AgentRegistry
from app.services.agent_runtime.tool_registry import ToolRegistry


def test_default_roles_registered():
    reg = AgentRegistry()
    for code in [
        "planner", "analyzer", "notice_interpreter", "workflow_planner",
        "coordinator", "course_researcher", "web_researcher",
        "citation_verifier", "tutor", "critic", "synthesizer",
    ]:
        assert reg.get(code) is not None, f"缺失角色: {code}"


def test_default_tools_registered():
    tools = ToolRegistry()
    for code in [
        "student.read", "course.read", "exam.read", "schedule.read",
        "learner_state.read", "knowledge.search", "task.propose",
        "task.create", "task.update", "plan.propose", "plan.activate",
        "reminder.schedule", "research.source.fetch", "research.report.create",
        "external_submission.prepare",
    ]:
        assert tools.get(code) is not None, f"缺失工具: {code}"


def test_tool_validate_success():
    tools = ToolRegistry()
    spec = tools.validate(
        tool_code="course.read",
        role_tools=("course.read", "exam.read"),
        args={"course_id": "c1"},
    )
    assert spec.tool_code == "course.read"


def test_tool_validate_rejects_unregistered():
    tools = ToolRegistry()
    with pytest.raises(AgentToolRejected):
        tools.validate(
            tool_code="arbitrary.sql",
            role_tools=("course.read",),
            args={},
        )


def test_tool_validate_rejects_role_without_tool():
    tools = ToolRegistry()
    with pytest.raises(AgentToolRejected) as exc:
        tools.validate(
            tool_code="plan.activate",
            role_tools=("course.read",),  # 角色没有 plan.activate
            args={},
        )
    assert exc.value.code == "AGENT_TOOL_REJECTED"


def test_tool_validate_rejects_oversized_args():
    tools = ToolRegistry()
    with pytest.raises(AgentToolRejected):
        tools.validate(
            tool_code="course.read",
            role_tools=("course.read",),
            args={"data": "x" * 10000},
        )


def test_external_submission_is_manual_only():
    tools = ToolRegistry()
    spec = tools.get("external_submission.prepare")
    assert spec.risk_level.value == "MANUAL_ONLY"
    assert spec.requires_approval is True


def test_plan_activate_requires_approval():
    tools = ToolRegistry()
    spec = tools.get("plan.activate")
    assert spec.risk_level.value == "CONFIRM_REQUIRED"
    assert spec.requires_approval is True


def test_role_has_capability_and_tool():
    reg = AgentRegistry()
    assert reg.has_capability("planner", "plan.generate")
    assert reg.has_tool("planner", "course.read")
    assert not reg.has_capability("planner", "arbitrary.execute")
    assert not reg.has_tool("planner", "external_submission.prepare")