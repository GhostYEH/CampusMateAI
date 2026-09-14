"""Agent runtime 原子性测试 —— 运行状态、事件、幂等声明必须同事务提交。

这些测试锁定的不变量(§2)：
- `agent_runs.status` 的每次变化与对应 `agent_events` 在同一事务提交。
- Worker 领取任务通过租约，同一 `run_id` 同时只能有一个持有者。
- 幂等键 + 请求哈希相同 -> 重放；相同键不同哈希 -> 冲突，且不留孤儿记录。
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import AgentIdempotencyConflict, AgentRuntimeError
from app.database.sqlite_db import Database
from app.repositories.agent_runtime_repository import AgentRuntimeRepository


def _now(offset_seconds: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).isoformat()


@pytest.fixture
def repo(tmp_path):
    db = Database(tmp_path / "atomic.db")
    conn = db._connect()
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u1', 'u1', 'x', 'student', 't', 't')"
        )
        conn.commit()
    finally:
        db._release(conn)
    yield AgentRuntimeRepository(db)
    db.dispose()


def _job_rows(repo: AgentRuntimeRepository) -> list[dict]:
    conn = repo._conn()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM agent_jobs").fetchall()]
    finally:
        repo._release(conn)


def _run_rows(repo: AgentRuntimeRepository) -> list[dict]:
    conn = repo._conn()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM agent_runs").fetchall()]
    finally:
        repo._release(conn)


def _event_rows(repo: AgentRuntimeRepository) -> list[dict]:
    conn = repo._conn()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM agent_events").fetchall()]
    finally:
        repo._release(conn)


def _break_event_insert(monkeypatch, message: str = "模拟事件写入失败") -> None:
    """让事件写入在状态更新之后失败，用于验证复合写的事务边界。"""

    def failing_insert(self, conn, **_kwargs):  # type: ignore[no-untyped-def]
        raise sqlite3.OperationalError(message)

    monkeypatch.setattr(AgentRuntimeRepository, "_insert_event", failing_insert)


# ===== 创建：Job + Run + 幂等声明 + RUN_QUEUED 事件 =====


class TestCreateJobWithRunAndEvent:
    def test_creates_job_run_and_queued_event(self, repo):
        created = repo.create_job_with_run_and_event(
            user_id="u1", job_kind="learning_goal",
            input_ref={"goal_id": "g1"}, request_hash="h1",
        )
        assert created["replayed"] is False
        assert created["run_id"]
        assert [_e["type"] for _e in _event_rows(repo)] == ["RUN_QUEUED"]
        run = repo.get_run(created["run_id"])
        assert run["status"] == "QUEUED"
        assert run["attempt_no"] == 0
        # Job 在异步模型下保持 QUEUED，不因为创建了 Run 就变成 RUNNING。
        assert repo.get_job(created["job_id"])["status"] == "QUEUED"

    def test_event_failure_leaves_no_orphan_job_or_run(self, repo, monkeypatch):
        _break_event_insert(monkeypatch)
        with pytest.raises(sqlite3.OperationalError):
            repo.create_job_with_run_and_event(
                user_id="u1", job_kind="learning_goal", input_ref={}, request_hash="h1",
            )
        assert _job_rows(repo) == []
        assert _run_rows(repo) == []
        assert _event_rows(repo) == []

    def test_idempotent_replay_returns_same_job(self, repo):
        first = repo.create_job_with_run_and_event(
            user_id="u1", job_kind="learning_goal", input_ref={"goal_id": "g1"},
            idempotency_key="k1", request_hash="h1",
        )
        second = repo.create_job_with_run_and_event(
            user_id="u1", job_kind="learning_goal", input_ref={"goal_id": "g1"},
            idempotency_key="k1", request_hash="h1",
        )
        assert second["replayed"] is True
        assert second["job_id"] == first["job_id"]
        assert second["run_id"] == first["run_id"]
        assert len(_job_rows(repo)) == 1
        assert len(_run_rows(repo)) == 1
        # 重放不得追加第二条 RUN_QUEUED。
        assert len(_event_rows(repo)) == 1

    def test_same_key_different_hash_conflicts(self, repo):
        repo.create_job_with_run_and_event(
            user_id="u1", job_kind="learning_goal", input_ref={"goal_id": "g1"},
            idempotency_key="k1", request_hash="h1",
        )
        with pytest.raises(AgentIdempotencyConflict):
            repo.create_job_with_run_and_event(
                user_id="u1", job_kind="learning_goal", input_ref={"goal_id": "g2"},
                idempotency_key="k1", request_hash="h2",
            )
        assert len(_job_rows(repo)) == 1
        assert len(_event_rows(repo)) == 1

    def test_conflict_leaves_no_orphan_records(self, repo, monkeypatch):
        """冲突路径本身也不能留下声明行。"""
        repo.create_job_with_run_and_event(
            user_id="u1", job_kind="learning_goal", input_ref={},
            idempotency_key="k1", request_hash="h1",
        )
        _break_event_insert(monkeypatch)
        with pytest.raises(sqlite3.OperationalError):
            repo.create_job_with_run_and_event(
                user_id="u1", job_kind="learning_goal", input_ref={},
                idempotency_key="k2", request_hash="h2",
            )
        conn = repo._conn()
        try:
            claims = conn.execute("SELECT * FROM agent_idempotency_claims").fetchall()
        finally:
            repo._release(conn)
        assert [c["idempotency_key"] for c in claims] == ["k1"]

    def test_concurrent_create_single_winner(self, repo):
        """并发相同幂等键只产生一个 Job/Run。"""
        barrier = threading.Barrier(4)
        results: list[dict] = []
        errors: list[BaseException] = []
        lock = threading.Lock()

        def worker() -> None:
            barrier.wait()
            try:
                created = repo.create_job_with_run_and_event(
                    user_id="u1", job_kind="learning_goal", input_ref={"goal_id": "g"},
                    idempotency_key="same", request_hash="h1",
                )
            except BaseException as exc:  # pragma: no cover - 断言在下方
                with lock:
                    errors.append(exc)
                return
            with lock:
                results.append(created)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(results) == 4
        assert {r["job_id"] for r in results} == {results[0]["job_id"]}
        assert len(_job_rows(repo)) == 1
        assert len(_run_rows(repo)) == 1
        assert len(_event_rows(repo)) == 1


# ===== 状态转换 + 事件 =====


class TestTransitionRunWithEvent:
    def _queued_run(self, repo: AgentRuntimeRepository) -> str:
        created = repo.create_job_with_run_and_event(
            user_id="u1", job_kind="learning_goal", input_ref={}, request_hash="h1",
        )
        return created["run_id"]

    def test_status_and_event_commit_together(self, repo):
        run_id = self._queued_run(repo)
        repo.transition_run_with_event(
            run_id, "RUNNING", expected_statuses=["QUEUED"], phase="CONTEXT_BUILDING",
            event_type="RUN_STARTED", event_summary="开始执行",
        )
        run = repo.get_run(run_id)
        assert run["status"] == "RUNNING"
        assert run["phase"] == "CONTEXT_BUILDING"
        events = _event_rows(repo)
        assert [e["type"] for e in events] == ["RUN_QUEUED", "RUN_STARTED"]
        assert events[-1]["status"] == "RUNNING"

    def test_event_failure_keeps_previous_status(self, repo, monkeypatch):
        run_id = self._queued_run(repo)
        _break_event_insert(monkeypatch)
        with pytest.raises(sqlite3.OperationalError):
            repo.transition_run_with_event(
                run_id, "RUNNING", expected_statuses=["QUEUED"],
                event_type="RUN_STARTED",
            )
        assert repo.get_run(run_id)["status"] == "QUEUED"
        assert repo.get_job(repo.get_run(run_id)["job_id"])["status"] == "QUEUED"
        assert [e["type"] for e in _event_rows(repo)] == ["RUN_QUEUED"]

    def test_unexpected_status_raises_invalid_state(self, repo):
        run_id = self._queued_run(repo)
        with pytest.raises(AgentRuntimeError) as exc:
            repo.transition_run_with_event(
                run_id, "RUNNING", expected_statuses=["RUNNING"],
                event_type="RUN_STARTED",
            )
        assert exc.value.code == "AGENT_INVALID_STATE"
        assert repo.get_run(run_id)["status"] == "QUEUED"

    def test_lease_owner_mismatch_raises(self, repo):
        run_id = self._queued_run(repo)
        with pytest.raises(AgentRuntimeError) as exc:
            repo.transition_run_with_event(
                run_id, "RUNNING", lease_owner="worker-2", event_type="RUN_STARTED",
            )
        assert exc.value.code == "AGENT_INVALID_STATE"
        assert repo.get_run(run_id)["status"] == "QUEUED"


# ===== 完成：Job 输出写回 + Run 终态 + 完成事件 =====


class TestCompleteRunWithJobOutput:
    def _claimed(self, repo: AgentRuntimeRepository) -> tuple[str, str]:
        created = repo.create_job_with_run_and_event(
            user_id="u1", job_kind="learning_goal",
            input_ref={"goal_id": "g1"}, request_hash="h1",
        )
        run_id = created["run_id"]
        repo.claim_next_run(owner="w1", now=_now(), lease_expires_at=_now(30))
        return created["job_id"], run_id

    def test_plan_id_visible_with_completed_event(self, repo):
        job_id, run_id = self._claimed(repo)
        repo.complete_run_with_job_output_and_event(
            run_id, "SUCCEEDED", lease_owner="w1",
            job_input_ref_patch={"plan_id": "plan_1"},
            event_summary="计划已生成",
        )
        run = repo.get_run(run_id)
        assert run["status"] == "SUCCEEDED"
        assert run["lease_owner"] is None
        # 完成事件可见后，重新读取 Job 已能看到 plan_id。
        job = repo.get_job(job_id)
        assert job["input_ref_json"] and "plan_id" in job["input_ref_json"]
        events = _event_rows(repo)
        assert events[-1]["type"] == "RUN_COMPLETED"
        assert events[-1]["status"] == "SUCCEEDED"

    def test_event_failure_rolls_back_plan_id_writeback(self, repo, monkeypatch):
        job_id, run_id = self._claimed(repo)
        _break_event_insert(monkeypatch)
        with pytest.raises(sqlite3.OperationalError):
            repo.complete_run_with_job_output_and_event(
                run_id, "SUCCEEDED", lease_owner="w1",
                job_input_ref_patch={"plan_id": "plan_1"},
            )
        assert "plan_id" not in (repo.get_job(job_id)["input_ref_json"] or "")
        assert repo.get_run(run_id)["status"] == "RUNNING"

    def test_unknown_lease_owner_cannot_complete(self, repo):
        _job_id, run_id = self._claimed(repo)
        with pytest.raises(AgentRuntimeError):
            repo.complete_run_with_job_output_and_event(
                run_id, "SUCCEEDED", lease_owner="w2",
                job_input_ref_patch={"plan_id": "plan_1"},
            )
        assert repo.get_run(run_id)["status"] == "RUNNING"


# ===== 租约与领取 =====


class TestLeaseAndClaim:
    def _enqueue(self, repo: AgentRuntimeRepository, n: int = 1) -> list[str]:
        ids = []
        for i in range(n):
            created = repo.create_job_with_run_and_event(
                user_id="u1", job_kind="learning_goal",
                input_ref={"goal_id": f"g{i}"}, request_hash=f"h{i}",
            )
            ids.append(created["run_id"])
        return ids

    def test_claim_sets_lease_and_increments_attempt(self, repo):
        run_id = self._enqueue(repo)[0]
        claimed = repo.claim_next_run(owner="w1", now=_now(), lease_expires_at=_now(30))
        assert claimed is not None
        assert claimed["run_id"] == run_id
        assert claimed["status"] == "RUNNING"
        assert claimed["lease_owner"] == "w1"
        assert claimed["attempt_no"] == 1

    def test_active_lease_blocks_other_workers(self, repo):
        run_id = self._enqueue(repo)[0]
        first = repo.claim_next_run(owner="w1", now=_now(), lease_expires_at=_now(30))
        assert first is not None
        # 租约未过期时,即使时间前进到租约到期之后,运行也不是 QUEUED,不能被直接抢占。
        assert repo.claim_next_run(owner="w2", now=_now(60), lease_expires_at=_now(90)) is None
        assert repo.get_run(run_id)["lease_owner"] == "w1"
        # 崩溃恢复路径: 由 Handler 的 recover() 决策后重新入队,才允许被再次领取。
        repo.transition_run_with_event(
            run_id, "QUEUED", lease_owner="w1", clear_lease=True,
            event_type="RUN_RECOVERED", event_summary="已从恢复点重新入队",
        )
        later = repo.claim_next_run(owner="w2", now=_now(60), lease_expires_at=_now(90))
        assert later is not None and later["run_id"] == run_id
        assert later["attempt_no"] == 2
        assert later["lease_owner"] == "w2"

    def test_expired_lease_requires_recovery_before_reclaim(self, repo):
        """租约过期但仍是 RUNNING 时,恢复前不得被直接领取。"""
        run_id = self._enqueue(repo)[0]
        repo.claim_next_run(owner="w1", now=_now(), lease_expires_at=_now(30))
        stale = repo.list_expired_lease_runs(now=_now(60))
        assert [r["run_id"] for r in stale] == [run_id]
        assert repo.claim_next_run(owner="w2", now=_now(60), lease_expires_at=_now(90)) is None

    def test_concurrent_claim_grants_distinct_runs(self, repo):
        self._enqueue(repo, 4)
        barrier = threading.Barrier(4)
        claimed: list[str] = []
        lock = threading.Lock()

        def worker(name: str) -> None:
            barrier.wait()
            run = repo.claim_next_run(owner=name, now=_now(), lease_expires_at=_now(30))
            if run is not None:
                with lock:
                    claimed.append(run["run_id"])

        threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(claimed) == 4
        assert len(set(claimed)) == 4

    def test_concurrent_claim_after_recovery_has_single_winner(self, repo):
        """恢复重新入队后并发领取，只能有一个赢家。"""
        run_id = self._enqueue(repo)[0]
        repo.claim_next_run(owner="w1", now=_now(), lease_expires_at=_now(30))
        repo.transition_run_with_event(
            run_id, "QUEUED", lease_owner="w1", clear_lease=True,
            event_type="RUN_RECOVERED",
        )
        barrier = threading.Barrier(3)
        winners: list[str] = []
        lock = threading.Lock()

        def worker(name: str) -> None:
            barrier.wait()
            run = repo.claim_next_run(owner=name, now=_now(60), lease_expires_at=_now(90))
            if run is not None:
                with lock:
                    winners.append(run["run_id"])

        threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert winners == [run_id]

    def test_renew_lease_only_for_owner(self, repo):
        run_id = self._enqueue(repo)[0]
        repo.claim_next_run(owner="w1", now=_now(), lease_expires_at=_now(30))
        new_expiry = _now(40)
        repo.renew_run_lease(run_id, "w1", heartbeat_at=_now(10), lease_expires_at=new_expiry)
        assert repo.get_run(run_id)["lease_expires_at"] == new_expiry
        with pytest.raises(AgentRuntimeError):
            repo.renew_run_lease(
                run_id, "w2", heartbeat_at=_now(10), lease_expires_at=new_expiry
            )
        assert repo.get_run(run_id)["lease_expires_at"] == new_expiry

    def test_save_checkpoint_requires_live_lease(self, repo):
        run_id = self._enqueue(repo)[0]
        repo.claim_next_run(owner="w1", now=_now(), lease_expires_at=_now(30))
        repo.save_checkpoint(run_id, "w1", {"stage": "planned"}, heartbeat_at=_now(5))
        assert repo.get_run(run_id)["checkpoint_json"] and "planned" in repo.get_run(run_id)["checkpoint_json"]
        # 租约过期后写 checkpoint 必须失败，避免僵尸 Worker 覆盖新进度。
        with pytest.raises(AgentRuntimeError):
            repo.save_checkpoint(run_id, "w1", {"stage": "stale"}, heartbeat_at=_now(60))

    def test_release_lease_allows_reclaim(self, repo):
        run_id = self._enqueue(repo)[0]
        repo.claim_next_run(owner="w1", now=_now(), lease_expires_at=_now(30))
        repo.release_run_lease(run_id, "w1")
        run = repo.get_run(run_id)
        assert run["lease_owner"] is None
        assert run["status"] == "RUNNING"


# ===== 事件游标 =====


class TestEventSequenceLookup:
    def test_get_event_sequence_by_event_id(self, repo):
        created = repo.create_job_with_run_and_event(
            user_id="u1", job_kind="learning_goal", input_ref={}, request_hash="h1",
        )
        run_id = created["run_id"]
        repo.transition_run_with_event(
            run_id, "RUNNING", expected_statuses=["QUEUED"], event_type="RUN_STARTED",
        )
        events = _event_rows(repo)
        assert repo.get_event_sequence(run_id, events[0]["event_id"]) == 1
        assert repo.get_event_sequence(run_id, events[1]["event_id"]) == 2
        assert repo.get_event_sequence(run_id, "evt_missing") is None
        # 游标不属于该 Run 时不得泄漏其它 Run 的 sequence。
        other = repo.create_job_with_run_and_event(
            user_id="u1", job_kind="learning_goal", input_ref={}, request_hash="h2",
        )
        assert repo.get_event_sequence(other["run_id"], events[0]["event_id"]) is None
