"""Internal runtime diagnostics remain bounded and redact sensitive data."""
from __future__ import annotations

import json

import pytest

from app.core.config import Settings
from app.core.security import hash_password
from app.services.container import reset_container_for_tests
from app.services.agent_runtime.observability import AgentObservabilityService

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
    student = container.user_repository.create_user(username="obs_student", password_hash=hash_password("Demo123456"))
    return container, None, None, {"student": student}


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

        body = AgentObservabilityService(container.agent_runtime_repository).overview()
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
        body = AgentObservabilityService(container.agent_runtime_repository).run_trace(run_id)
        assert body["run"]["run_id"] == run_id
        assert body["run"]["handler_code"] == "learning_goal"
        assert body["run"]["duration_ms"] == pytest.approx(1000.0)
        assert isinstance(body["events"], list)

    def test_unknown_run_returns_none(self, env):
        container, _, _, _ = env
        assert AgentObservabilityService(container.agent_runtime_repository).run_trace("run_missing") is None


class TestPrivacy:
    def test_overview_has_no_sensitive_fields(self, env):
        container, _, _, _ = env
        raw = json.dumps(AgentObservabilityService(container.agent_runtime_repository).overview())
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
        raw = json.dumps(AgentObservabilityService(container.agent_runtime_repository).run_trace(run_id))
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
        body = AgentObservabilityService(container.agent_runtime_repository).run_trace(run_id)
        serialized = json.dumps(body, ensure_ascii=False)
        assert "hash-only" not in serialized
        assert all("arguments" not in call for call in body["tool_calls"])
