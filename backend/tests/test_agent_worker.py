"""AgentWorker 的租约、重试和恢复语义。"""
from __future__ import annotations

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


class _Input(BaseModel):
    value: str = "ok"


class _Handler:
    code = "test"
    version = "1.0.0"
    job_kind = "test"
    enabled = True
    input_model = _Input
    max_attempts = 3
    tools = ()

    def __init__(self, *, failures: int = 0, approval: bool = False):
        self.failures = failures
        self.approval = approval
        self.calls = 0
        self.recoveries = 0

    async def execute(self, context: HandlerContext) -> HandlerResult:
        self.calls += 1
        if self.calls <= self.failures:
            raise AgentRuntimeError(
                "provider unavailable", code="AGENT_PROVIDER_UNAVAILABLE", http_status=503
            )
        if self.approval:
            return HandlerResult(
                status="AWAITING_APPROVAL", checkpoint={"stage": "approval"},
                summary="需要确认",
            )
        return HandlerResult(
            status="SUCCEEDED", checkpoint={"stage": "done"}, summary="完成"
        )

    async def recover(self, context: HandlerContext) -> RecoveryDecision:
        self.recoveries += 1
        return RecoveryDecision(action=RecoveryAction.REQUEUE, checkpoint=context.checkpoint)


class _Clock:
    def __init__(self):
        # 远未来时钟确保新建记录的真实 next_attempt_at 已到期。
        self.value = datetime(2099, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, seconds: int):
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
    repo = AgentRuntimeRepository(db)
    return repo


def _queued(repo: AgentRuntimeRepository) -> str:
    return repo.create_job_with_run_and_event(
        user_id="u1", job_kind="test", input_ref={"value": "ok"}, request_hash="hash",
        handler_code="test", handler_version="1.0.0",
    )["run_id"]


def _worker(repo, handler, clock, *, mode="worker"):
    registry = JobHandlerRegistry()
    registry.register(handler)
    registry.freeze()
    return AgentWorker(
        repo, registry, AgentEventStore(repo), mode=mode, clock=clock,
        lease_seconds=30, heartbeat_seconds=10, poll_interval_seconds=0,
    )


@pytest.mark.asyncio
async def test_worker_claims_and_completes_with_durable_events(runtime):
    run_id = _queued(runtime)
    handler = _Handler()
    worker = _worker(runtime, handler, _Clock())

    report = await worker.run_once()

    assert report.action == "executed"
    assert handler.calls == 1
    assert runtime.get_run(run_id)["status"] == "SUCCEEDED"
    assert [e["type"] for e in runtime.list_events(run_id)] == [
        "RUN_QUEUED", "RUN_STARTED", "RUN_COMPLETED"
    ]


@pytest.mark.asyncio
async def test_worker_retries_with_backoff_then_succeeds(runtime):
    run_id = _queued(runtime)
    clock = _Clock()
    handler = _Handler(failures=2)
    worker = _worker(runtime, handler, clock)

    await worker.run_once()
    assert runtime.get_run(run_id)["status"] == "QUEUED"
    assert runtime.get_run(run_id)["next_attempt_at"].startswith("2099-01-01T00:00:01")

    clock.advance(1)
    await worker.run_once()
    assert runtime.get_run(run_id)["status"] == "QUEUED"
    clock.advance(5)
    await worker.run_once()

    assert handler.calls == 3
    assert runtime.get_run(run_id)["status"] == "SUCCEEDED"
    assert sum(e["type"] == "RUN_RETRY_SCHEDULED" for e in runtime.list_events(run_id)) == 2


@pytest.mark.asyncio
async def test_expired_lease_uses_handler_recovery_before_requeue(runtime):
    run_id = _queued(runtime)
    clock = _Clock()
    handler = _Handler()
    worker_a = _worker(runtime, handler, clock)
    claimed = runtime.claim_next_run(
        owner=worker_a.worker_id, now=clock().isoformat(),
        lease_expires_at=(clock() + timedelta(seconds=30)).isoformat(),
    )
    runtime.save_checkpoint(
        run_id, worker_a.worker_id, {"stage": "checkpoint"}, heartbeat_at=clock().isoformat()
    )

    clock.advance(31)
    worker_b = _worker(runtime, handler, clock)
    report = await worker_b.run_once()

    assert claimed["status"] == "RUNNING"
    assert report.action == "recovered"
    assert handler.recoveries == 1
    assert runtime.get_run(run_id)["status"] == "QUEUED"
    assert runtime.get_run(run_id)["checkpoint_json"] == '{"stage": "checkpoint"}'

    await worker_b.run_once()
    assert runtime.get_run(run_id)["status"] == "SUCCEEDED"


@pytest.mark.asyncio
async def test_awaiting_approval_releases_lease_and_is_not_reclaimed(runtime):
    run_id = _queued(runtime)
    worker = _worker(runtime, _Handler(approval=True), _Clock())

    await worker.run_once()
    run = runtime.get_run(run_id)
    assert run["status"] == "AWAITING_APPROVAL"
    assert run["lease_owner"] is None
    assert (await worker.run_once()).action == "idle"


@pytest.mark.asyncio
async def test_disabled_worker_does_not_claim(runtime):
    run_id = _queued(runtime)
    worker = _worker(runtime, _Handler(), _Clock(), mode="disabled")

    assert (await worker.run_once()).action == "skipped"
    assert runtime.get_run(run_id)["status"] == "QUEUED"
