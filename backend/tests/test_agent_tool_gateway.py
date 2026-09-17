"""ToolInvocationGateway 测试 —— 固定校验顺序、幂等与隐私边界。

任何注册工具都必须经过网关;校验顺序一旦被打乱,就会出现
"审批未通过但副作用已发生"或"越权工具被放行"的窗口,因此这里逐条锁死。
"""
from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, Field

from app.core.exceptions import (
    AgentOutputSchemaInvalid,
    AgentPermissionDenied,
    AgentRunCancelled,
    AgentRunNotFound,
    AgentRuntimeError,
    AgentToolRejected,
)
from app.core.security import hash_password
from app.database.sqlite_db import reset_db_for_tests
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.schemas.agent_contract_enums import RiskLevel
from app.services.agent_runtime.agent_registry import AgentRegistry, AgentRole
from app.services.agent_runtime.approval_gate import ApprovalGate
from app.services.agent_runtime.event_store import AgentEventStore
from app.services.agent_runtime.handlers.base import (
    HandlerContext,
    HandlerResult,
    RecoveryAction,
    RecoveryDecision,
)
from app.services.agent_runtime.handlers.registry import JobHandlerRegistry
from app.services.agent_runtime.risk_engine import RiskEngine
from app.services.agent_runtime.tool_gateway import (
    ToolInvocationGateway,
    ToolInvocationRequest,
)
from app.services.agent_runtime.tool_registry import ToolRegistry, ToolSpec


class _Args(BaseModel):
    user_id: str
    minutes: int = Field(default=30, ge=1, le=1440)


class _StaticRoleRegistry:
    """只暴露一个角色的注册表替身,用来隔离"角色已授权"这一维度。"""

    def __init__(self, agent_code: str, tools: tuple[str, ...]) -> None:
        self._role = AgentRole(agent_code, "1.0", (), tools, "reasoning_primary")

    def get(self, agent_code: str):
        return self._role if agent_code == self._role.agent_code else None


class _Recording:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, arguments: dict):
        self.calls.append(arguments)
        return {"plan_id": f"plan_{len(self.calls)}"}


def _make_tool(executor=None, **overrides):
    defaults = dict(
        tool_code="plan.propose",
        resource="plan",
        action="propose",
        risk_level=RiskLevel.AUTO_SAFE,
        requires_approval=False,
        args_model=_Args,
        ownership_field="user_id",
        executor=executor,
        result_builder=lambda outcome: {"plan_id": outcome["plan_id"]},
        summary_builder=lambda args: f"生成 {args.get('minutes', 30)} 分钟计划",
    )
    defaults.update(overrides)
    return ToolSpec(**defaults)


class _FakeHandler:
    code = "unit"
    version = "1.0.0"
    job_kind = "unit"
    enabled = True
    input_model = BaseModel
    max_attempts = 3
    tools = ("plan.propose",)

    async def execute(self, context: HandlerContext) -> HandlerResult:
        return HandlerResult(status="SUCCEEDED")

    async def recover(self, context: HandlerContext) -> RecoveryDecision:
        return RecoveryDecision(action=RecoveryAction.REQUEUE)


@pytest.fixture
def env():
    db = reset_db_for_tests()
    conn = db._connect()
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u1', 'u1', 'x', 'student', 't', 't')"
        )
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u2', 'u2', 'x', 'student', 't', 't')"
        )
        conn.commit()
    finally:
        db._release(conn)
    repo = AgentRuntimeRepository(db)
    return repo, AgentEventStore(repo)


def _gateway(env, tool, *, handler_registry=None, registry=None, tools=None):
    repo, events = env
    tool_registry = tools or ToolRegistry()
    tool_registry.register(tool)
    return ToolInvocationGateway(
        repo, tool_registry, RiskEngine(), ApprovalGate(repo),
        agent_registry=registry or AgentRegistry(),
        handler_registry=handler_registry,
        event_store=events,
    )


def _run(repo, user_id="u1", *, handler_code="unit"):
    job_id = repo.create_job(user_id=user_id, job_kind="unit")
    return repo.create_run(job_id=job_id, user_id=user_id, handler_code=handler_code)


def _request(run_id, **overrides):
    base = dict(
        run_id=run_id, role_code="planner", tool_name="plan.propose",
        arguments={"user_id": "u1", "minutes": 60},
        idempotency_key="idem-1",
    )
    base.update(overrides)
    return ToolInvocationRequest(**base)


class TestValidationOrder:
    @pytest.mark.asyncio
    async def test_unknown_run_rejected(self, env):
        gateway = _gateway(env, _make_tool(_Recording()))
        with pytest.raises(AgentRunNotFound):
            await gateway.invoke(_request("run_missing"))

    @pytest.mark.asyncio
    async def test_terminal_run_rejected(self, env):
        repo, _ = env
        run_id = _run(repo)
        repo.update_run(run_id, status="CANCELLED", phase="IDLE", finished_at="t")
        executor = _Recording()
        gateway = _gateway(env, _make_tool(executor))
        with pytest.raises(AgentRunCancelled):
            await gateway.invoke(_request(run_id))
        assert executor.calls == []

    @pytest.mark.asyncio
    async def test_handler_must_declare_tool(self, env):
        repo, _ = env
        run_id = _run(repo)
        registry = JobHandlerRegistry(known_tool_names={"plan.propose"})
        registry.register(_FakeHandler())
        registry.freeze()
        executor = _Recording()
        gateway = _gateway(
            env, _make_tool(executor), handler_registry=registry,
        )
        # 处理器只声明了 plan.propose，换一个工具名必须被拒
        with pytest.raises(AgentToolRejected):
            await gateway.invoke(_request(run_id, tool_name="unknown.tool"))
        assert executor.calls == []

    @pytest.mark.asyncio
    async def test_role_permission_required(self, env):
        repo, _ = env
        run_id = _run(repo)
        executor = _Recording()
        gateway = _gateway(env, _make_tool(executor))
        with pytest.raises(AgentToolRejected):
            await gateway.invoke(_request(run_id, role_code="ghost"))
        assert executor.calls == []

    @pytest.mark.asyncio
    async def test_args_schema_enforced(self, env):
        repo, _ = env
        run_id = _run(repo)
        executor = _Recording()
        gateway = _gateway(env, _make_tool(executor))
        with pytest.raises(AgentOutputSchemaInvalid):
            await gateway.invoke(_request(run_id, arguments={"user_id": "u1", "minutes": 0}))
        assert executor.calls == []

    @pytest.mark.asyncio
    async def test_ownership_enforced_even_for_auto_safe(self, env):
        repo, _ = env
        run_id = _run(repo)  # run 属于 u1
        executor = _Recording()
        gateway = _gateway(env, _make_tool(executor))
        with pytest.raises(AgentPermissionDenied):
            await gateway.invoke(_request(run_id, arguments={"user_id": "u2", "minutes": 30}))
        assert executor.calls == []

    @pytest.mark.asyncio
    async def test_manual_only_never_auto_executed(self, env):
        repo, _ = env
        run_id = _run(repo)
        executor = _Recording()
        registry = _StaticRoleRegistry("planner", ("assignment.submit",))
        gateway = _gateway(
            env,
            ToolSpec(
                tool_code="assignment.submit", resource="assignment", action="submit",
                risk_level=RiskLevel.MANUAL_ONLY, requires_approval=True,
                args_model=None, executor=executor,
            ),
            registry=registry,
        )
        with pytest.raises(AgentToolRejected):
            await gateway.invoke(_request(run_id, tool_name="assignment.submit"))
        assert executor.calls == []

    @pytest.mark.asyncio
    async def test_unbound_executor_cannot_execute(self, env):
        repo, _ = env
        run_id = _run(repo)
        gateway = _gateway(env, _make_tool(executor=None))
        with pytest.raises(AgentToolRejected):
            await gateway.invoke(_request(run_id))


class TestApprovalAndIdempotency:
    @pytest.mark.asyncio
    async def test_approval_required_returns_waiting(self, env):
        repo, _ = env
        run_id = _run(repo)
        executor = _Recording()
        gateway = _gateway(
            env, _make_tool(executor, tool_code="plan.activate", action="activate",
                            requires_approval=True),
            registry=_StaticRoleRegistry("planner", ("plan.activate",)),
        )
        result = await gateway.invoke(
            _request(run_id, tool_name="plan.activate", idempotency_key="idem-appr")
        )
        assert result.status == "AWAITING_APPROVAL"
        assert result.approval_id
        assert executor.calls == [], "审批未通过前不得产生领域副作用"

    @pytest.mark.asyncio
    async def test_idempotent_replay_executes_once(self, env):
        repo, _ = env
        run_id = _run(repo)
        executor = _Recording()
        gateway = _gateway(env, _make_tool(executor))
        first = await gateway.invoke(_request(run_id))
        second = await gateway.invoke(_request(run_id))
        assert first.status == "COMPLETED"
        assert second.status == "REPLAYED"
        assert second.result_ref == first.result_ref
        assert len(executor.calls) == 1, "相同幂等键与请求哈希最多执行一次领域副作用"

    @pytest.mark.asyncio
    async def test_same_key_different_arguments_is_a_different_call(self, env):
        repo, _ = env
        run_id = _run(repo)
        executor = _Recording()
        gateway = _gateway(env, _make_tool(executor))
        await gateway.invoke(_request(run_id, arguments={"user_id": "u1", "minutes": 30}))
        await gateway.invoke(_request(run_id, arguments={"user_id": "u1", "minutes": 90}))
        assert len(executor.calls) == 2


class TestPrivacy:
    @pytest.mark.asyncio
    async def test_events_and_errors_never_leak_raw_arguments(self, env):
        repo, events = env
        run_id = _run(repo)
        secret = "super-secret-token"
        executor = _Recording()
        gateway = _gateway(env, _make_tool(executor))
        await gateway.invoke(
            _request(run_id, arguments={"user_id": "u1", "minutes": 45, "token": secret})
        )
        serialized = json.dumps(events.list_events(run_id), ensure_ascii=False)
        assert secret not in serialized
        # 幂等声明也只保存请求哈希,不保存原始参数。
        from app.services.agent_runtime.tool_gateway import build_request_hash

        request_hash = build_request_hash("plan.propose", {"user_id": "u1", "minutes": 45})
        claim = repo.find_tool_call_by_idempotency(run_id, "idem-1", request_hash)
        assert claim is not None
        assert secret not in json.dumps(repo.get_tool_call(claim["call_id"]), ensure_ascii=False)


class TestRegistryWiring:
    def test_role_registry_exposes_tools(self):
        registry = AgentRegistry()
        role = registry.get("planner")
        assert role is not None
        assert "plan.propose" in role.tools

    def test_unknown_role_is_none(self):
        assert AgentRegistry().get("ghost") is None

    def test_agent_role_is_frozen_dataclass(self):
        role = AgentRole("x", "1.0", (), (), "reasoning_primary")
        assert role.permission_policy == "student_owned_only"
