import pytest

from app.core.exceptions import AppException
from app.services.agent_runtime.agent_registry import AgentRegistry
from app.services.agent_runtime.tool_registry import ToolRegistry


def test_role_tool_mismatch_and_foreign_resources_are_rejected():
    tools = ToolRegistry(AgentRegistry.default())
    with pytest.raises(AppException) as exc:
        tools.authorize(role="analyzer", tool_name="task.create", actor_user_id="u", owner_user_id="u")
    assert exc.value.code == "AGENT_PERMISSION_DENIED"
    with pytest.raises(AppException) as exc:
        tools.authorize(role="planner", tool_name="task.create", actor_user_id="u", owner_user_id="other")
    assert exc.value.code == "AGENT_PERMISSION_DENIED"


def test_registered_role_can_use_owned_allowlisted_tool():
    tools = ToolRegistry(AgentRegistry.default())
    decision = tools.authorize(role="planner", tool_name="task.create", actor_user_id="u", owner_user_id="u")
    assert decision.allowed is True
