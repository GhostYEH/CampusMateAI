"""管理员观测 API 测试 —— 鉴权、聚合、隐私与查询边界。

三条硬约束:
1. 只有 admin 能访问;学生与教师一律 403,未登录 401;
2. 聚合值必须真实反映队列、成功率、耗时、Token、工具失败、重试与审批等待;
3. 响应中不得出现 prompt / model_response / credential / memory_content / raw_arguments 等字段。
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests

_SENSITIVE_KEYS = (
    "prompt",
    "model_response",
    "credential",
    "memory_content",
    "raw_arguments",
    "arguments",
    "hidden_reasoning",
)


@pytest.fixture
def env():
    container = reset_container_for_tests(
        Settings(
            app_env="test",
            database_url="sqlite:///:memory:",
            auto_seed_demo_users=False,
            auto_import_demo=False,
            llm_provider="none",
        )
    )
    users = {}
    for username, role in (
        ("obs_admin", "admin"),
        ("obs_student", "student"),
        ("obs_teacher", "teacher"),
    ):
        users[role] = container.user_repository.create_user(
            username=username, password_hash=hash_password("Demo123456"), role=role
        )
    client = TestClient(create_app())
    headers = {}
    for role, username in (("admin", "obs_admin"), ("student", "obs_student"), ("teacher", "obs_teacher")):
        token = client.post(
            "/api/v1/auth/login", json={"username": username, "password": "Demo123456"}
        ).json()["access_token"]
        headers[role] = {"Authorization": f"Bearer {token}"}
    return container, client, headers, users


def _seed_run(container, user_id, *, status="SUCCEEDED", attempt_no=1):
    repo = container.agent_runtime_repository
    job_id = repo.create_job(user_id=user_id, job_kind="learning_goal")
    run_id = repo.create_run(job_id=job_id, user_id=user_id, handler_code="learning_goal")
    repo.update_run(
        run_id, status=status, phase="IDLE",
        started_at="2026-09-14T10:00:00+00:00", finished_at="2026-09-14T10:00:01+00:00",
    )
    with container.db.transaction() as conn:
        conn.execute(
            "UPDATE agent_runs SET attempt_no = ? WHERE run_id = ?", (attempt_no, run_id)
        )
    return run_id


class TestAuthorization:
    def test_anonymous_rejected(self, env):
        _, client, _, _ = env
        resp = client.get("/api/v1/admin/agent-runtime/overview")
        assert resp.status_code == 401

    def test_student_rejected(self, env):
        _, client, headers, _ = env
        resp = client.get("/api/v1/admin/agent-runtime/overview", headers=headers["student"])
        assert resp.status_code == 403
        assert resp.json()["code"] == "AGENT_PERMISSION_DENIED"

    def test_teacher_rejected(self, env):
        _, client, headers, _ = env
        resp = client.get("/api/v1/admin/agent-runtime/overview", headers=headers["teacher"])
        assert resp.status_code == 403

    def test_trace_requires_admin(self, env):
        container, client, headers, users = env
        run_id = _seed_run(container, users["student"].id)
        resp = client.get(
            f"/api/v1/admin/agent-runtime/runs/{run_id}/trace", headers=headers["student"]
        )
        assert resp.status_code == 403

    def test_admin_can_read_overview(self, env):
        _, client, headers, _ = env
        resp = client.get("/api/v1/admin/agent-runtime/overview", headers=headers["admin"])
        assert resp.status_code == 200
        body = resp.json()
        assert body["window_hours"] == 24
        assert "status_distribution" in body


class TestAggregates:
    def test_overview_reflects_runtime_state(self, env):
        container, client, headers, users = env
        repo = container.agent_runtime_repository
        _seed_run(container, users["student"].id, status="SUCCEEDED")
        _seed_run(container, users["student"].id, status="FAILED", attempt_no=3)

        # 队列里放一个待执行 Run,并制造一个陈旧租约
        queued = _seed_run(container, users["student"].id, status="QUEUED")
        with container.db.transaction() as conn:
            conn.execute(
                "UPDATE agent_runs SET lease_owner = 'w_stale', lease_expires_at = ? "
                "WHERE run_id = ?",
                ("2020-01-01T00:00:00+00:00", queued),
            )

        # 模型调用与工具失败
        repo.record_model_call(
            run_id=queued, provider="fake", route_policy="fast_structured", model="m",
            latency_ms=120, prompt_tokens=10, completion_tokens=5, total_tokens=15,
            status="completed",
        )
        repo.record_tool_call_start(
            run_id=queued, tool_name="plan.propose", request_hash="h", idempotency_key="k"
        )

        body = client.get(
            "/api/v1/admin/agent-runtime/overview", headers=headers["admin"]
        ).json()
        assert body["queue_depth"] == 1
        assert body["stale_lease_count"] == 1
        assert body["status_distribution"]["SUCCEEDED"] == 1
        assert body["status_distribution"]["FAILED"] == 1
        assert body["success_rate"] == 0.5
        assert body["retry_count"] == 1
        assert body["token_usage"]["total_tokens"] == 15
        assert body["duration_ms"]["samples"] == 2
        assert body["model_latency_ms"]["p50"] == 120

    def test_trace_returns_safe_timeline(self, env):
        container, client, headers, users = env
        run_id = _seed_run(container, users["student"].id)
        resp = client.get(
            f"/api/v1/admin/agent-runtime/runs/{run_id}/trace", headers=headers["admin"]
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["run"]["run_id"] == run_id
        assert body["run"]["handler_code"] == "learning_goal"
        assert body["run"]["duration_ms"] == pytest.approx(1000.0)
        assert isinstance(body["events"], list)

    def test_unknown_run_returns_404(self, env):
        _, client, headers, _ = env
        resp = client.get(
            "/api/v1/admin/agent-runtime/runs/run_missing/trace", headers=headers["admin"]
        )
        assert resp.status_code == 404


class TestPrivacy:
    def test_overview_has_no_sensitive_fields(self, env):
        _, client, headers, _ = env
        raw = client.get(
            "/api/v1/admin/agent-runtime/overview", headers=headers["admin"]
        ).text
        for key in _SENSITIVE_KEYS:
            assert key not in raw, f"观测响应不得包含 {key}"

    def test_trace_has_no_sensitive_fields(self, env):
        container, client, headers, users = env
        run_id = _seed_run(container, users["student"].id)
        repo = container.agent_runtime_repository
        repo.save_memory(
            user_id=users["student"].id, kind="CONFIRMED_PREFERENCE",
            content_summary="secret-memory-content", sensitivity="high",
            confirmed=True, model_may_consume=True, provenance="user_explicit",
        )
        raw = client.get(
            f"/api/v1/admin/agent-runtime/runs/{run_id}/trace", headers=headers["admin"]
        ).text
        for key in _SENSITIVE_KEYS:
            assert key not in raw, f"观测响应不得包含 {key}"
        assert "secret-memory-content" not in raw

    def test_trace_does_not_echo_tool_arguments(self, env):
        container, client, headers, users = env
        run_id = _seed_run(container, users["student"].id)
        repo = container.agent_runtime_repository
        repo.record_tool_call_start(
            run_id=run_id, tool_name="plan.propose",
            request_hash="hash-only", idempotency_key="k1",
        )
        body = client.get(
            f"/api/v1/admin/agent-runtime/runs/{run_id}/trace", headers=headers["admin"]
        ).json()
        serialized = json.dumps(body, ensure_ascii=False)
        assert "hash-only" not in serialized
        assert all("arguments" not in call for call in body["tool_calls"])


class TestQueryBounds:
    def test_observability_queries_use_indexes(self, env):
        """时间窗聚合必须走索引区间扫描,不能退化成无界全表扫描。"""
        container, _, _, _ = env
        conn = container.db._connect()
        try:
            plans = {}
            for label, sql, param in (
                (
                    "agent_runs",
                    "EXPLAIN QUERY PLAN SELECT run_id FROM agent_runs "
                    "WHERE created_at >= ? ORDER BY created_at DESC LIMIT 5000",
                    "2026-01-01T00:00:00+00:00",
                ),
                (
                    "agent_model_calls",
                    "EXPLAIN QUERY PLAN SELECT call_id FROM agent_model_calls "
                    "WHERE started_at >= ? ORDER BY started_at DESC LIMIT 100",
                    "2026-01-01T00:00:00+00:00",
                ),
                (
                    "agent_tool_calls",
                    "EXPLAIN QUERY PLAN SELECT call_id FROM agent_tool_calls "
                    "WHERE started_at >= ? ORDER BY started_at DESC LIMIT 100",
                    "2026-01-01T00:00:00+00:00",
                ),
                (
                    "agent_approvals",
                    "EXPLAIN QUERY PLAN SELECT approval_id FROM agent_approvals "
                    "WHERE created_at >= ? ORDER BY created_at DESC LIMIT 100",
                    "2026-01-01T00:00:00+00:00",
                ),
            ):
                plans[label] = " ".join(
                    str(row["detail"]) for row in conn.execute(sql, (param,)).fetchall()
                )
        finally:
            container.db._release(conn)
        for label, detail in plans.items():
            assert "idx_" in detail, f"{label} 的时间窗查询未使用索引: {detail}"
            assert "SCAN " + label not in detail, f"{label} 出现全表扫描: {detail}"

    def test_window_is_clamped(self, env):
        _, client, headers, _ = env
        too_small = client.get(
            "/api/v1/admin/agent-runtime/overview?since_hours=0", headers=headers["admin"]
        )
        assert too_small.status_code == 422
        too_large = client.get(
            "/api/v1/admin/agent-runtime/overview?since_hours=100000", headers=headers["admin"]
        )
        assert too_large.status_code == 422
