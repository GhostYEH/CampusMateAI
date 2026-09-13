"""硬拒绝层:不可被角色授权、automation 或审批覆盖(§5.5)。

对应设计约束"MANUAL_ONLY 永不自动执行":风险分级决定"谁来确认",
硬拒绝决定"无论如何都不做"。
"""
from __future__ import annotations

import pytest

from app.core.exceptions import AgentToolRejected
from app.services.agent_runtime.hard_deny import check_hard_deny, hard_deny_reason
from app.services.agent_runtime.risk_engine import RiskEngine
from app.services.agent_runtime.tool_registry import ToolRegistry


def test_hard_deny_runs_before_registration_and_role_checks():
    """命中硬拒绝的动作,即使未注册、角色未声明,也必须报硬拒绝原因。"""
    registry = ToolRegistry()
    with pytest.raises(AgentToolRejected) as excinfo:
        registry.validate(tool_code="payment.pay", role_tools=(), args={})
    assert "硬拒绝" in str(excinfo.value)


def test_hard_deny_blocks_sensitive_arguments_on_otherwise_safe_tool():
    """工具本身安全,但参数出现验证码语义时同样拒绝。"""
    registry = ToolRegistry()
    with pytest.raises(AgentToolRejected) as excinfo:
        registry.validate(
            tool_code="task.create",
            role_tools=("task.create",),
            args={"title": "把收到的验证码填进学校系统"},
        )
    assert "硬拒绝" in str(excinfo.value)


def test_hard_deny_allows_normal_arguments():
    registry = ToolRegistry()
    spec = registry.validate(
        tool_code="task.create",
        role_tools=("task.create",),
        args={"title": "复习数据库事务隔离级别"},
    )
    assert spec.tool_code == "task.create"


def test_confirm_required_tool_is_not_hard_denied():
    """需要确认≠永不执行:研究抓取与外部表单准备仍允许走审批。"""
    assert hard_deny_reason("research.source.fetch") is None
    assert hard_deny_reason("external_submission.prepare") is None


def test_hard_deny_does_not_depend_on_risk_assessment():
    engine = RiskEngine()
    assessment = engine.assess("payment.pay", user_enabled_auto=True)
    # 即使调用方声称"用户已开启自动",也不会变成可自动执行
    assert engine.can_auto_execute(assessment) is False
    # 硬拒绝独立于风险分级:不经过 assess 也直接拒绝
    with pytest.raises(AgentToolRejected):
        check_hard_deny("school_system.mutate", {"table": "grades"})
