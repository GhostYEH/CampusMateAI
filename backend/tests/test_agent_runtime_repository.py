"""Agent runtime 仓储测试。"""
from __future__ import annotations

import pytest

from app.database.sqlite_db import Database, reset_db_for_tests
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.repositories.agent_artifact_repository import AgentArtifactRepository


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


@pytest.fixture
def artifact_repo(tmp_path):
    db = reset_db_for_tests()
    conn = db._connect()
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u1', 'u1', 'x', 'student', 't', 't')"
        )
        conn.execute(
            "INSERT INTO agent_jobs (job_id, user_id, job_kind, status, created_at, updated_at) "
            "VALUES ('j1', 'u1', 'final_review', 'QUEUED', 't', 't')"
        )
        conn.execute(
            "INSERT INTO agent_runs (run_id, job_id, user_id, status, phase, "
            "created_at, updated_at) VALUES ('r1', 'j1', 'u1', 'QUEUED', 'IDLE', 't', 't')"
        )
        conn.commit()
    finally:
        db._release(conn)
    return AgentArtifactRepository(db, tmp_path / "artifacts")


class TestAgentRuntimeRepository:
    def test_create_and_get_job(self, repo):
        job_id = repo.create_job(user_id="u1", job_kind="final_review")
        job = repo.get_job(job_id)
        assert job is not None
        assert job["user_id"] == "u1"
        assert job["job_kind"] == "final_review"
        assert job["status"] == "QUEUED"

    def test_find_job_by_idempotency(self, repo):
        repo.create_job(user_id="u1", job_kind="final_review", idempotency_key="k1")
        found = repo.find_job_by_idempotency("u1", "k1")
        assert found is not None
        assert found["job_kind"] == "final_review"
        assert repo.find_job_by_idempotency("u1", "k2") is None

    def test_create_and_get_run(self, repo):
        job_id = repo.create_job(user_id="u1", job_kind="final_review")
        run_id = repo.create_run(job_id=job_id, user_id="u1")
        run = repo.get_run(run_id)
        assert run is not None
        assert run["status"] == "QUEUED"
        assert run["phase"] == "IDLE"
        # job 状态应更新为 RUNNING
        job = repo.get_job(job_id)
        assert job["status"] == "RUNNING"

    def test_update_run(self, repo):
        job_id = repo.create_job(user_id="u1", job_kind="final_review")
        run_id = repo.create_run(job_id=job_id, user_id="u1")
        repo.update_run(run_id, status="RUNNING", phase="CONTEXT_BUILDING")
        run = repo.get_run(run_id)
        assert run["status"] == "RUNNING"
        assert run["phase"] == "CONTEXT_BUILDING"

    def test_append_event_monotonic_sequence(self, repo):
        job_id = repo.create_job(user_id="u1", job_kind="final_review")
        run_id = repo.create_run(job_id=job_id, user_id="u1")
        eid1, seq1 = repo.append_event(
            run_id=run_id, type="RUN_STARTED", status="RUNNING", phase="CONTEXT_BUILDING"
        )
        eid2, seq2 = repo.append_event(
            run_id=run_id, type="MODEL_COMPLETED", status="RUNNING", phase="VALIDATING_OUTPUT"
        )
        assert seq1 == 1
        assert seq2 == 2
        assert eid1 != eid2

    def test_list_events_after_sequence(self, repo):
        job_id = repo.create_job(user_id="u1", job_kind="final_review")
        run_id = repo.create_run(job_id=job_id, user_id="u1")
        for i in range(5):
            repo.append_event(
                run_id=run_id, type="RUN_STARTED", status="RUNNING", phase="IDLE"
            )
        events = repo.list_events(run_id, after_sequence=2)
        assert len(events) == 3
        assert events[0]["sequence"] == 3

    def test_tool_call_idempotency(self, repo):
        job_id = repo.create_job(user_id="u1", job_kind="final_review")
        run_id = repo.create_run(job_id=job_id, user_id="u1")
        call_id = repo.record_tool_call_start(
            run_id=run_id, tool_name="course.read", request_hash="h1", idempotency_key="k1"
        )
        found = repo.find_tool_call_by_idempotency(run_id, "k1", "h1")
        assert found is not None
        assert found["call_id"] == call_id
        repo.record_tool_call_finish(call_id, status="succeeded", result_digest="d1")
        found = repo.find_tool_call_by_idempotency(run_id, "k1", "h1")
        assert found["status"] == "succeeded"

    def test_record_model_call(self, repo):
        job_id = repo.create_job(user_id="u1", job_kind="final_review")
        run_id = repo.create_run(job_id=job_id, user_id="u1")
        call_id = repo.record_model_call(
            run_id=run_id,
            provider="zhipu",
            route_policy="reasoning_primary",
            model="glm-4",
            status="succeeded",
            latency_ms=1200,
        )
        assert call_id.startswith("mcall_")

    def test_save_and_get_snapshot(self, repo):
        job_id = repo.create_job(user_id="u1", job_kind="final_review")
        run_id = repo.create_run(job_id=job_id, user_id="u1")
        sid = repo.save_snapshot(
            user_id="u1",
            run_id=run_id,
            source_digest="sha256:abc",
            valid_until="2026-09-12T10:15:00+08:00",
            scope={"course_ids": ["c1"]},
            facts={"daily_capacity_minutes": 120},
        )
        snap = repo.get_snapshot(sid)
        assert snap is not None
        assert snap["source_digest"] == "sha256:abc"

    def test_approval_lifecycle(self, repo):
        job_id = repo.create_job(user_id="u1", job_kind="final_review")
        run_id = repo.create_run(job_id=job_id, user_id="u1")
        aid = repo.create_approval(
            run_id=run_id,
            user_id="u1",
            risk_level="CONFIRM_REQUIRED",
            action_summary="激活计划",
            expires_at="2026-09-12T10:18:00+08:00",
        )
        apv = repo.get_approval(aid)
        assert apv.status == "PENDING"
        repo.resolve_approval(aid, status="APPROVED", decision_reason="用户确认")
        apv = repo.get_approval(aid)
        assert apv.status == "APPROVED"
        assert apv.resolved_at is not None

    def test_expire_approvals(self, repo):
        job_id = repo.create_job(user_id="u1", job_kind="final_review")
        run_id = repo.create_run(job_id=job_id, user_id="u1")
        repo.create_approval(
            run_id=run_id,
            user_id="u1",
            risk_level="CONFIRM_REQUIRED",
            action_summary="x",
            expires_at="2020-01-01T00:00:00+08:00",  # 过去
        )
        count = repo.expire_approvals(now="2026-09-12T10:00:00+08:00")
        assert count == 1

    def test_memory_withdraw(self, repo):
        mid = repo.save_memory(
            user_id="u1",
            kind="CONFIRMED_PREFERENCE",
            content_summary="偏好晚上学习",
            confirmed=True,
            model_may_consume=True,
        )
        repo.withdraw_memory(mid)
        mems = repo.list_memories("u1")
        assert mems[0]["withdrawn"] == 1
        assert mems[0]["model_may_consume"] == 0

    def test_list_incomplete_runs(self, repo):
        job_id = repo.create_job(user_id="u1", job_kind="final_review")
        run_id = repo.create_run(job_id=job_id, user_id="u1")
        repo.update_run(run_id, status="RUNNING", phase="CONTEXT_BUILDING")
        incomplete = repo.list_incomplete_runs()
        assert len(incomplete) == 1
        assert incomplete[0]["run_id"] == run_id


class TestAgentArtifactRepository:
    def test_create_and_get_artifact(self, artifact_repo):
        aid = artifact_repo.create_artifact(
            run_id="r1",
            user_id="u1",
            artifact_type="FINAL_REVIEW_PLAN",
            content={"plan": "v1"},
        )
        meta = artifact_repo.get_artifact(aid, "u1")
        assert meta is not None
        assert meta["artifact_type"] == "FINAL_REVIEW_PLAN"
        assert meta["size_bytes"] > 0

    def test_artifact_ownership_isolation(self, artifact_repo):
        aid = artifact_repo.create_artifact(
            run_id="r1",
            user_id="u1",
            artifact_type="FINAL_REVIEW_PLAN",
            content={"x": 1},
        )
        # 其他用户不能读取
        assert artifact_repo.get_artifact(aid, "u2") is None
        assert artifact_repo.read_content(aid, "u2") is None

    def test_artifact_read_content(self, artifact_repo):
        aid = artifact_repo.create_artifact(
            run_id="r1",
            user_id="u1",
            artifact_type="DAILY_AGENDA",
            content="今日待办:复习指针",
            mime_type="text/markdown",
        )
        text = artifact_repo.read_content(aid, "u1")
        assert text is not None
        assert "复习指针" in text

    def test_artifact_soft_delete(self, artifact_repo):
        aid = artifact_repo.create_artifact(
            run_id="r1",
            user_id="u1",
            artifact_type="FINAL_REVIEW_PLAN",
            content={"x": 1},
        )
        assert artifact_repo.soft_delete(aid, "u1") is True
        assert artifact_repo.get_artifact(aid, "u1") is None