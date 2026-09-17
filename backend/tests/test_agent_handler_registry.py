"""JobHandlerRegistry 与 learning_goal Handler 测试。

锁定两条边界:
- 注册表在启动时拒绝任何不合规声明(重复 job_kind / 空版本 / 未声明输入模型 / 未知工具);
- Handler 只返回结果,终态与 `plan_id` 写回由 Worker 在同一个事务里提交。
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from app.core.exceptions import AgentRuntimeError
from app.database.sqlite_db import reset_db_for_tests
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.services.agent_runtime.event_store import AgentEventStore
from app.services.agent_runtime.handlers.base import (
    HandlerContext,
    HandlerResult,
    JobHandlerRegistrationError,
    RecoveryAction,
    RecoveryDecision,
)
from app.services.agent_runtime.handlers.learning_goal import (
    LearningGoalHandler,
    LearningGoalInput,
)
from app.services.agent_runtime.handlers.registry import JobHandlerRegistry


class _Input(BaseModel):
    x: int = 1


def _make_handler(
    *, code="h1", version="1.0.0", job_kind="k1", enabled=True,
    input_model=_Input, max_attempts=3, tools=(),
):
    class _Handler:
        pass

    handler = _Handler()
    handler.code = code
    handler.version = version
    handler.job_kind = job_kind
    handler.enabled = enabled
    handler.input_model = input_model
    handler.max_attempts = max_attempts
    handler.tools = tools

    async def execute(context: HandlerContext) -> HandlerResult:
        return HandlerResult(status="SUCCEEDED")

    async def recover(context: HandlerContext) -> RecoveryDecision:
        return RecoveryDecision(action=RecoveryAction.REQUEUE)

    handler.execute = execute
    handler.recover = recover
    return handler


@pytest.fixture
def repo():
    db = reset_db_for_tests()
    conn = db._connect()
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u1', 'u1', 'x', 'student', 't', 't')"
        )
        conn.commit()
    finally:
        db._release(conn)
    return AgentRuntimeRepository(db)


class _FakePlan:
    def __init__(self, plan_id: str) -> None:
        self.plan_id = plan_id


class _FakePlanner:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return _FakePlan(f"plan_{len(self.calls)}")


class TestRegistryValidation:
    def test_duplicate_job_kind_rejected(self):
        registry = JobHandlerRegistry()
        registry.register(_make_handler())
        with pytest.raises(JobHandlerRegistrationError, match="重复注册"):
            registry.register(_make_handler(code="h2"))

    def test_empty_version_rejected(self):
        registry = JobHandlerRegistry()
        with pytest.raises(JobHandlerRegistrationError, match="version"):
            registry.register(_make_handler(version="   "))

    def test_missing_input_model_rejected(self):
        registry = JobHandlerRegistry()
        handler = _make_handler()
        del handler.input_model
        with pytest.raises(JobHandlerRegistrationError, match="input_model"):
            registry.register(handler)

    def test_input_model_must_be_pydantic(self):
        registry = JobHandlerRegistry()
        with pytest.raises(JobHandlerRegistrationError, match="input_model"):
            registry.register(_make_handler(input_model=dict))

    def test_unknown_tool_capability_rejected(self):
        registry = JobHandlerRegistry(known_tool_names={"known.tool"})
        with pytest.raises(JobHandlerRegistrationError, match="未注册的工具能力"):
            registry.register(_make_handler(tools=("ghost.tool",)))

    def test_known_tool_capability_allowed(self):
        registry = JobHandlerRegistry(known_tool_names={"known.tool"})
        registry.register(_make_handler(tools=("known.tool",)))
        assert registry.is_enabled("k1")

    def test_missing_required_attribute_rejected(self):
        registry = JobHandlerRegistry()
        handler = _make_handler()
        del handler.max_attempts
        with pytest.raises(JobHandlerRegistrationError, match="max_attempts"):
            registry.register(handler)

    def test_non_boolean_enabled_rejected(self):
        registry = JobHandlerRegistry()
        with pytest.raises(JobHandlerRegistrationError, match="enabled"):
            registry.register(_make_handler(enabled="yes"))

    def test_invalid_max_attempts_rejected(self):
        registry = JobHandlerRegistry()
        with pytest.raises(JobHandlerRegistrationError, match="max_attempts"):
            registry.register(_make_handler(max_attempts=0))


class TestRegistryLookup:
    def test_unknown_job_kind_raises_capability_disabled(self):
        registry = JobHandlerRegistry()
        with pytest.raises(AgentRuntimeError) as exc:
            registry.require("nope")
        assert exc.value.code == "AGENT_CAPABILITY_DISABLED"
        assert exc.value.http_status == 409

    def test_disabled_handler_raises_capability_disabled(self):
        registry = JobHandlerRegistry()
        registry.register(_make_handler(enabled=False))
        assert registry.is_known("k1") is True
        assert registry.is_enabled("k1") is False
        with pytest.raises(AgentRuntimeError) as exc:
            registry.require("k1")
        assert exc.value.code == "AGENT_CAPABILITY_DISABLED"

    def test_describe_exposes_version_and_state(self):
        registry = JobHandlerRegistry()
        registry.register(_make_handler())
        described = registry.describe()
        assert described == [{
            "code": "h1",
            "version": "1.0.0",
            "job_kind": "k1",
            "enabled": True,
            "max_attempts": 3,
            "tools": [],
        }]


class TestLearningGoalInput:
    def test_rejects_missing_goal_id(self):
        with pytest.raises(ValidationError):
            LearningGoalInput.model_validate({})

    def test_rejects_out_of_range_minutes(self):
        with pytest.raises(ValidationError):
            LearningGoalInput.model_validate({"goal_id": "g1", "available_minutes": 0})
        with pytest.raises(ValidationError):
            LearningGoalInput.model_validate({"goal_id": "g1", "available_minutes": 1441})

    def test_defaults_available_minutes(self):
        payload = LearningGoalInput.model_validate({"goal_id": "g1"})
        assert payload.available_minutes == 60


class TestLearningGoalHandler:
    @staticmethod
    def _context(**overrides) -> HandlerContext:
        base = dict(
            run_id="run_1", job_id="job_1", user_id="u1", job_kind="learning_goal",
            input_ref={"goal_id": "g1", "available_minutes": 90}, checkpoint=None,
            attempt_no=1,
        )
        base.update(overrides)
        return HandlerContext(**base)

    @pytest.mark.asyncio
    async def test_execute_returns_plan_id_patch(self):
        planner = _FakePlanner()
        handler = LearningGoalHandler(planner, None)
        result = await handler.execute(self._context())
        assert result.status == "SUCCEEDED"
        assert result.job_output_patch == {"plan_id": "plan_1"}
        assert result.checkpoint and result.checkpoint["plan_id"] == "plan_1"
        assert planner.calls[0]["available_minutes"] == 90
        assert planner.calls[0]["goal_id"] == "g1"

    @pytest.mark.asyncio
    async def test_execute_is_idempotent_per_run(self):
        """崩溃重放使用同一个 Run 级幂等键,不会生成第二份计划。"""
        planner = _FakePlanner()
        handler = LearningGoalHandler(planner, None)
        await handler.execute(self._context())
        await handler.execute(self._context())
        assert len(planner.calls) == 2
        assert planner.calls[0]["idempotency_key"] == planner.calls[1]["idempotency_key"]

    @pytest.mark.asyncio
    async def test_checkpoint_resume_skips_second_side_effect(self):
        planner = _FakePlanner()
        handler = LearningGoalHandler(planner, None)
        result = await handler.execute(
            self._context(checkpoint={"stage": "PLAN_GENERATED", "plan_id": "plan_old"})
        )
        assert result.job_output_patch == {"plan_id": "plan_old"}
        assert planner.calls == []

    @pytest.mark.asyncio
    async def test_recover_requeues(self):
        handler = LearningGoalHandler(_FakePlanner(), None)
        decision = await handler.recover(self._context())
        assert decision.action is RecoveryAction.REQUEUE

    @pytest.mark.asyncio
    async def test_plan_id_visible_only_after_completion(self, repo):
        """完成事件可见时,重新读取 Job 必须已经包含 plan_id。"""
        created = repo.create_job_with_run_and_event(
            user_id="u1", job_kind="learning_goal",
            input_ref={"goal_id": "g1", "available_minutes": 60}, request_hash="h1",
            handler_code="learning_goal", handler_version="1.0.0",
        )
        run_id = created["run_id"]
        # 时钟必须晚于 Run 创建时写入的 next_attempt_at,否则领取条件不成立。
        repo.claim_next_run(owner="w1", now="2099-01-01T00:00:00+00:00",
                            lease_expires_at="2099-01-01T00:00:30+00:00")
        handler = LearningGoalHandler(_FakePlanner(), AgentEventStore(repo))
        result = await handler.execute(self._context(run_id=run_id, job_id=created["job_id"]))

        # Handler 自己不写状态:完成前 Job 上没有 plan_id,也没有 RUN_COMPLETED。
        assert "plan_id" not in (repo.get_job(created["job_id"])["input_ref_json"] or "")
        assert [e["type"] for e in repo.list_events(run_id)] == [
            "RUN_QUEUED", "RUN_STARTED", "CONTEXT_READY"
        ]

        repo.complete_run_with_job_output_and_event(
            run_id, "SUCCEEDED", lease_owner="w1",
            job_input_ref_patch=result.job_output_patch,
            event_summary=result.summary,
        )
        events = repo.list_events(run_id)
        assert events[-1]["type"] == "RUN_COMPLETED"
        # 完成事件之后重新 GET Job 一定能拿到 plan_id。
        assert "plan_1" in repo.get_job(created["job_id"])["input_ref_json"]

    @pytest.mark.asyncio
    async def test_planner_failure_becomes_runtime_error(self):
        class _Broken:
            def generate(self, **kwargs):
                raise ValueError("state service unavailable")

        handler = LearningGoalHandler(_Broken(), None)
        with pytest.raises(AgentRuntimeError) as exc:
            await handler.execute(self._context())
        assert exc.value.code == "AGENT_INVALID_STATE"
