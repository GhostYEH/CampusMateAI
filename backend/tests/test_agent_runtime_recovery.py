"""Agent runtime recovery 测试 —— 中断执行安全收口。"""
from __future__ import annotations

import pytest

from app.core.exceptions import AgentRuntimeError
from app.database.sqlite_db import reset_db_for_tests
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.services.agent_runtime.event_store import AgentEventStore
from app.services.agent_runtime.run_manager import RunManager


@pytest.fixture
def run_manager():
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
    return RunManager(repo, AgentEventStore(repo))


def _create_run(repo):
    job_id = repo.create_job(user_id="u1", job_kind="final_review")
    return repo.create_run(job_id=job_id, user_id="u1")


class TestRunManagerTransitions:
    def test_valid_transition_queued_to_running(self, run_manager):
        repo = run_manager._repo
        run_id = _create_run(repo)
        run = run_manager.transition(run_id, "RUNNING", phase="CONTEXT_BUILDING")
        assert run["status"] == "RUNNING"
        assert run["started_at"] is not None

    def test_valid_transition_running_to_succeeded(self, run_manager):
        repo = run_manager._repo
        run_id = _create_run(repo)
        run_manager.transition(run_id, "RUNNING", phase="CONTEXT_BUILDING")
        run = run_manager.transition(run_id, "SUCCEEDED", phase="IDLE")
        assert run["status"] == "SUCCEEDED"
        assert run["finished_at"] is not None

    def test_invalid_transition_queued_to_succeeded(self, run_manager):
        repo = run_manager._repo
        run_id = _create_run(repo)
        with pytest.raises(AgentRuntimeError) as exc:
            run_manager.transition(run_id, "SUCCEEDED")
        assert exc.value.code == "AGENT_INVALID_STATE"

    def test_terminal_state_cannot_transition(self, run_manager):
        repo = run_manager._repo
        run_id = _create_run(repo)
        run_manager.transition(run_id, "RUNNING")
        run_manager.transition(run_id, "SUCCEEDED")
        with pytest.raises(AgentRuntimeError):
            run_manager.transition(run_id, "RUNNING")

    def test_cancel_non_terminal_run(self, run_manager):
        repo = run_manager._repo
        run_id = _create_run(repo)
        run_manager.transition(run_id, "RUNNING")
        run = run_manager.cancel(run_id, reason="用户取消")
        assert run["status"] == "CANCELLED"

    def test_cancel_already_cancelled_is_noop(self, run_manager):
        repo = run_manager._repo
        run_id = _create_run(repo)
        run_manager.transition(run_id, "RUNNING")
        run_manager.cancel(run_id)
        run = run_manager.cancel(run_id)
        assert run["status"] == "CANCELLED"

    def test_cancel_succeeded_raises(self, run_manager):
        repo = run_manager._repo
        run_id = _create_run(repo)
        run_manager.transition(run_id, "RUNNING")
        run_manager.transition(run_id, "SUCCEEDED")
        with pytest.raises(AgentRuntimeError) as exc:
            run_manager.cancel(run_id)
        assert exc.value.code == "AGENT_RUN_CANCELLED"

    def test_transition_nonexistent_run(self, run_manager):
        with pytest.raises(AgentRuntimeError) as exc:
            run_manager.transition("nonexistent", "RUNNING")
        assert exc.value.code == "AGENT_RUN_NOT_FOUND"


class TestRunManagerRecovery:
    def test_recover_fails_interrupted_runs_without_unsafe_replay(self, run_manager):
        repo = run_manager._repo
        run_id1 = _create_run(repo)
        run_manager.transition(run_id1, "RUNNING", phase="CONTEXT_BUILDING")
        run_id2 = _create_run(repo)
        run_manager.transition(run_id2, "RUNNING", phase="WAITING_FOR_MODEL")
        recovered = run_manager.recover_incomplete_runs()
        assert len(recovered) == 2
        for run in recovered:
            assert run["status"] == "FAILED"
            assert run["phase"] == "IDLE"
            assert run["error_code"] == "AGENT_RECOVERY_UNSUPPORTED"

    def test_recover_skips_terminal_runs(self, run_manager):
        repo = run_manager._repo
        run_id = _create_run(repo)
        run_manager.transition(run_id, "RUNNING")
        run_manager.transition(run_id, "SUCCEEDED")
        recovered = run_manager.recover_incomplete_runs()
        assert len(recovered) == 0

    def test_is_terminal(self):
        assert RunManager.is_terminal("SUCCEEDED")
        assert RunManager.is_terminal("FAILED")
        assert RunManager.is_terminal("CANCELLED")
        assert not RunManager.is_terminal("RUNNING")
        assert not RunManager.is_terminal("QUEUED")
