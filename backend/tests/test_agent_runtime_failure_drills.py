"""Agent Runtime 故障演练(Task 12)。

把上线前必须验证的故障路径固化成可重复的测试:
Handler 异常、模型/工具超时、审批期间重启、租约中断、重复请求、
SSE 断线重连、数据库短时锁竞争。

验收 SLO(在本文件里以可断言的形式表达):
- 重复领域副作用为 0;
- 合法游标恢复无事件缺失;
- 运行不会长期伪装成 RUNNING:要么恢复,要么以稳定错误码明确失败。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import BaseModel

from app.core.exceptions import AgentRuntimeError
from app.database.sqlite_db import reset_db_for_tests
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.services.agent_runtime.event_store import AgentEventStore
from app.services.agent_runtime.handlers.base import (
    HandlerContext,
    HandlerResult,
    RecoveryAction,
    RecoveryDecision,
)
from app.services.agent_runtime.handlers.registry import JobHandlerRegistry
from app.services.agent_runtime.worker import AgentWorker

TERMINAL = {"SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"}


class _Input(BaseModel):
    value: str = "ok"


class _DrillHandler:
    """可配置的演练处理器:记录领域副作用次数,便于断言"只发生一次"。"""

    code = "drill"
    version = "1.0.0"
    job_kind = "drill"
    enabled = True
    input_model = _Input
    max_attempts = 3
    tools = ()

    def __init__(self, *, mode: str = "ok", checkpoint: bool = True) -> None:
        self.mode = mode
        self.checkpoint = checkpoint
        self.side_effects = 0
        self.recover_calls = 0
        self.seen_checkpoints: list[dict | None] = []

    async def execute(self, context: HandlerContext) -> HandlerResult:
        self.seen_checkpoints.append(context.checkpoint)
        # 已经拿到恢复点就只补写结果,不再产生第二次领域副作用。
        if context.checkpoint and context.checkpoint.get("done"):
            return HandlerResult(
                status="SUCCEEDED", job_output_patch={"plan_id": "plan_replayed"},
                checkpoint=context.checkpoint, summary="从恢复点补写结果",
            )
        self.side_effects += 1
        if self.mode == "handler_error":
            raise RuntimeError("handler exploded")
        if self.mode == "model_timeout":
            raise AgentRuntimeError(
                "模型 provider 超时", code="AGENT_PROVIDER_UNAVAILABLE", http_status=503
            )
        if self.mode == "fatal":
            raise AgentRuntimeError("参数非法", code="AGENT_INVALID_STATE", http_status=409)
        if self.mode == "approval":
            return HandlerResult(
                status="AWAITING_APPROVAL",
                checkpoint={"stage": "awaiting_approval"} if self.checkpoint else None,
                summary="需要用户确认",
            )
        return HandlerResult(
            status="SUCCEEDED",
            job_output_patch={"plan_id": f"plan_{self.side_effects}"},
            checkpoint={"stage": "done", "done": True} if self.checkpoint else None,
            summary="完成",
        )

    async def recover(self, context: HandlerContext) -> RecoveryDecision:
        self.recover_calls += 1
        if self.mode == "fatal":
            return RecoveryDecision(action=RecoveryAction.FAIL, error_code="AGENT_INVALID_STATE")
        return RecoveryDecision(action=RecoveryAction.REQUEUE, checkpoint=context.checkpoint)


class _Clock:
    def __init__(self) -> None:
        self.value = datetime(2099, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


@pytest.fixture
def runtime():
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


def _queued(repo, *, key: str = "hash") -> str:
    return repo.create_job_with_run_and_event(
        user_id="u1", job_kind="drill", input_ref={"value": "ok"}, request_hash=key,
        handler_code="drill", handler_version="1.0.0",
    )["run_id"]


def _worker(repo, handler, clock, *, worker_id=None, mode="worker"):
    registry = JobHandlerRegistry()
    registry.register(handler)
    registry.freeze()
    return AgentWorker(
        repo, registry, AgentEventStore(repo), mode=mode, worker_id=worker_id, clock=clock,
        lease_seconds=30, heartbeat_seconds=10, poll_interval_seconds=0,
    )


def _event_types(repo, run_id) -> list[str]:
    return [event["type"] for event in repo.list_events(run_id)]


class TestHandlerAndProviderFailures:
    @pytest.mark.asyncio
    async def test_handler_exception_becomes_stable_failure(self, runtime):
        run_id = _queued(runtime)
        worker = _worker(runtime, _DrillHandler(mode="handler_error"), _Clock())
        await worker.run_once()
        run = runtime.get_run(run_id)
        assert run["status"] == "FAILED"
        assert run["error_code"] == "AGENT_INVALID_STATE"
        assert "RUN_FAILED" in _event_types(runtime, run_id)

    @pytest.mark.asyncio
    async def test_model_timeout_retries_then_fails_without_stuck_running(self, runtime):
        run_id = _queued(runtime)
        clock = _Clock()
        handler = _DrillHandler(mode="model_timeout")
        worker = _worker(runtime, handler, clock)

        for _ in range(5):
            await worker.run_once()
            clock.advance(60)
            if runtime.get_run(run_id)["status"] in TERMINAL:
                break

        run = runtime.get_run(run_id)
        assert run["status"] == "FAILED", "超过最大尝试次数后必须明确失败,不能长期 RUNNING"
        assert run["error_code"] == "AGENT_PROVIDER_UNAVAILABLE"
        assert "RUN_RETRY_SCHEDULED" in _event_types(runtime, run_id)

    @pytest.mark.asyncio
    async def test_non_retryable_error_fails_immediately(self, runtime):
        run_id = _queued(runtime)
        handler = _DrillHandler(mode="fatal")
        worker = _worker(runtime, handler, _Clock())
        await worker.run_once()
        assert runtime.get_run(run_id)["status"] == "FAILED"
        assert "RUN_RETRY_SCHEDULED" not in _event_types(runtime, run_id)


class TestLeaseInterruption:
    @pytest.mark.asyncio
    async def test_worker_crash_then_another_worker_recovers_once(self, runtime):
        """Worker A 写完 checkpoint 后崩溃;租约过期后 Worker B 接管,领域副作用只发生一次。"""
        run_id = _queued(runtime)
        clock = _Clock()
        handler_a = _DrillHandler()
        worker_a = _worker(runtime, handler_a, clock, worker_id="worker_a")

        claimed = runtime.claim_next_run(
            owner="worker_a", now=clock().isoformat(),
            lease_expires_at=(clock() + timedelta(seconds=30)).isoformat(),
        )
        assert claimed["run_id"] == run_id
        runtime.save_checkpoint(
            run_id, "worker_a", {"stage": "done", "done": True},
            heartbeat_at=clock().isoformat(),
        )
        # Worker A 崩溃:不再续租,也不完成运行。
        assert runtime.get_run(run_id)["status"] == "RUNNING"

        clock.advance(31)
        handler_b = _DrillHandler()
        worker_b = _worker(runtime, handler_b, clock, worker_id="worker_b")
        await worker_b.run_once()  # 恢复:重新排队
        await worker_b.run_once()  # 领取并完成

        run = runtime.get_run(run_id)
        assert run["status"] == "SUCCEEDED"
        assert handler_b.recover_calls == 1
        assert handler_b.side_effects == 0, "从 checkpoint 恢复不得重复领域副作用"
        assert "RUN_RECOVERED" in _event_types(runtime, run_id)
        assert worker_a.worker_id != worker_b.worker_id

    @pytest.mark.asyncio
    async def test_valid_lease_is_never_preempted(self, runtime):
        run_id = _queued(runtime)
        clock = _Clock()
        runtime.claim_next_run(
            owner="worker_a", now=clock().isoformat(),
            lease_expires_at=(clock() + timedelta(seconds=30)).isoformat(),
        )
        handler = _DrillHandler()
        worker_b = _worker(runtime, handler, clock, worker_id="worker_b")
        report = await worker_b.run_once()
        assert report.action == "idle", "有效租约不得被抢占"
        assert runtime.get_run(run_id)["status"] == "RUNNING"
        assert handler.recover_calls == 0


class TestApprovalSurvivesRestart:
    @pytest.mark.asyncio
    async def test_approval_run_is_not_claimed_and_resumes_from_checkpoint(self, runtime):
        run_id = _queued(runtime)
        clock = _Clock()
        handler = _DrillHandler(mode="approval")
        worker = _worker(runtime, handler, clock)
        await worker.run_once()

        run = runtime.get_run(run_id)
        assert run["status"] == "AWAITING_APPROVAL"
        assert run["lease_owner"] is None, "审批等待不占 Worker"

        # 模拟进程重启:新 Worker 不得领取审批等待中的运行
        restarted = _worker(runtime, _DrillHandler(), clock, worker_id="worker_restart")
        report = await restarted.run_once()
        assert report.action == "idle"
        assert runtime.get_run(run_id)["status"] == "AWAITING_APPROVAL"

        # 审批通过后重新排队,并从 checkpoint 继续
        resumed_handler = _DrillHandler()
        runtime.transition_run_with_event(
            run_id, "QUEUED", expected_statuses=["AWAITING_APPROVAL"],
            phase="IDLE", clear_lease=True, next_attempt_at=clock().isoformat(),
            event_type="RUN_RESUMED", event_status="QUEUED", event_phase="IDLE",
        )
        resumed_worker = _worker(runtime, resumed_handler, clock, worker_id="worker_resumed")
        await resumed_worker.run_once()
        assert runtime.get_run(run_id)["status"] == "SUCCEEDED"
        assert resumed_handler.seen_checkpoints == [{"stage": "awaiting_approval"}], (
            "审批恢复必须从持久化 checkpoint 继续,而不是从零开始"
        )


class TestDuplicateRequests:
    @pytest.mark.asyncio
    async def test_duplicate_job_creation_does_not_duplicate_work(self, runtime):
        first = runtime.create_job_with_run_and_event(
            user_id="u1", job_kind="drill", input_ref={"value": "ok"}, request_hash="same",
            idempotency_key="idem-1", handler_code="drill", handler_version="1.0.0",
        )
        second = runtime.create_job_with_run_and_event(
            user_id="u1", job_kind="drill", input_ref={"value": "ok"}, request_hash="same",
            idempotency_key="idem-1", handler_code="drill", handler_version="1.0.0",
        )
        assert second["replayed"] is True
        assert second["job_id"] == first["job_id"]

        handler = _DrillHandler()
        worker = _worker(runtime, handler, _Clock())
        await worker.run_once()
        await worker.run_once()  # 队列已空,不应再执行
        assert handler.side_effects == 1
        assert len(runtime.list_runs_by_job(first["job_id"])) == 1


class TestSseReconnect:
    def test_cursor_resume_has_no_missing_events(self, runtime):
        run_id = _queued(runtime)
        events = [("RUN_STARTED", 2), ("MODEL_COMPLETED", 3), ("RUN_COMPLETED", 4)]
        event_ids = []
        for event_type, _ in events:
            event_id, _seq = runtime.append_event(
                run_id=run_id, type=event_type, status="RUNNING", phase="IDLE"
            )
            event_ids.append(event_id)

        # 客户端在收到第 2 条后断线,用 Last-Event-ID 续传
        cursor_sequence = runtime.get_event_sequence(run_id, event_ids[0])
        assert cursor_sequence is not None
        resumed = runtime.list_events(run_id, after_sequence=cursor_sequence)
        assert [e["type"] for e in resumed] == ["MODEL_COMPLETED", "RUN_COMPLETED"]

        # 断线本身不改变运行状态
        assert runtime.get_run(run_id)["status"] == "QUEUED"

    def test_unknown_cursor_is_reported_not_silently_ignored(self, runtime):
        run_id = _queued(runtime)
        assert runtime.get_event_sequence(run_id, "evt_ghost") is None


class TestDatabaseContention:
    def test_claim_survives_short_write_lock(self, runtime, monkeypatch):
        """数据库短时锁竞争:领取抛错后必须安全返回,状态不被破坏,随后仍可领取。"""
        run_id = _queued(runtime)
        # claim_next_run 走 Database.transaction(),因此必须在连接工厂这一层注入故障。
        original = runtime._db._connect
        state = {"raised": False}

        def flaky_connect():
            if not state["raised"]:
                state["raised"] = True
                raise sqlite3.OperationalError("database is locked")
            return original()

        monkeypatch.setattr(runtime._db, "_connect", flaky_connect)
        with pytest.raises(sqlite3.OperationalError):
            runtime.claim_next_run(
                owner="worker_x", now="2099-01-01T00:00:00+00:00",
                lease_expires_at="2099-01-01T00:00:30+00:00",
            )
        # 锁竞争不得留下半更新的运行
        run = runtime.get_run(run_id)
        assert run["status"] == "QUEUED"
        assert run["lease_owner"] is None

        monkeypatch.setattr(runtime._db, "_connect", original)
        claimed = runtime.claim_next_run(
            owner="worker_x", now="2099-01-01T00:00:00+00:00",
            lease_expires_at="2099-01-01T00:00:30+00:00",
        )
        assert claimed is not None
        assert claimed["status"] == "RUNNING"

    @pytest.mark.asyncio
    async def test_worker_loop_survives_transient_database_error(self, runtime, monkeypatch):
        """Worker 循环不得因单次数据库错误退出。"""
        _queued(runtime)
        clock = _Clock()
        handler = _DrillHandler()
        worker = _worker(runtime, handler, clock, worker_id="worker_lock")

        original = runtime._conn
        state = {"raised": False}

        def flaky_conn():
            if not state["raised"]:
                state["raised"] = True
                raise sqlite3.OperationalError("database is locked")
            return original()

        monkeypatch.setattr(runtime, "_conn", flaky_conn)
        with pytest.raises(sqlite3.OperationalError):
            await worker.run_once()

        monkeypatch.setattr(runtime, "_conn", original)
        report = await worker.run_once()
        assert report.action == "executed"
        assert handler.side_effects == 1
