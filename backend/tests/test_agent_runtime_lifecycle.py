from __future__ import annotations

import pytest

from app.core.exceptions import AgentRuntimeError
from app.database.sqlite_db import reset_db_for_tests
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.services.agent_runtime.event_store import AgentEventStore
from app.services.agent_runtime.run_manager import RunManager


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
    manager = RunManager(repo, AgentEventStore(repo))
    return repo, manager


def _run(repo: AgentRuntimeRepository, manager: RunManager) -> str:
    job_id = repo.create_job(user_id="u1", job_kind="learning_goal")
    run_id = repo.create_run(job_id=job_id, user_id="u1")
    manager.transition(run_id, "RUNNING", phase="WAITING_FOR_MODEL")
    return run_id


def test_run_can_pause_and_resume(runtime):
    repo, manager = runtime
    run_id = _run(repo, manager)

    assert manager.pause(run_id, reason="用户暂时离开")['status'] == "PAUSED"
    assert manager.resume(run_id)['status'] == "RUNNING"


def test_retry_creates_new_run_with_lineage(runtime):
    repo, manager = runtime
    run_id = _run(repo, manager)
    manager.transition(run_id, "FAILED", phase="IDLE", error_code="AGENT_PROVIDER_UNAVAILABLE")

    retried = manager.retry(run_id, idempotency_key="retry-1")

    assert retried["run_id"] != run_id
    assert retried["retry_of"] == run_id
    assert retried["status"] == "QUEUED"


def test_retrying_successful_run_is_rejected(runtime):
    repo, manager = runtime
    run_id = _run(repo, manager)
    manager.transition(run_id, "SUCCEEDED", phase="IDLE")

    with pytest.raises(AgentRuntimeError) as exc:
        manager.retry(run_id, idempotency_key="retry-success")
    assert exc.value.code == "AGENT_INVALID_STATE"


def test_job_and_run_queries_are_available_for_task_center(runtime):
    repo, manager = runtime
    run_id = _run(repo, manager)
    run = repo.get_run(run_id)

    assert repo.list_jobs("u1")
    assert repo.list_runs_for_user("u1")
    assert repo.list_runs_by_job(run["job_id"])[0]["run_id"] == run_id
