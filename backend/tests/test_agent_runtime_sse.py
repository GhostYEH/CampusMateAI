"""Agent runtime SSE 测试 —— resumable + sequence + Last-Event-ID。"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client():
    container = reset_container_for_tests(
        Settings(
            app_env="test",
            database_url="sqlite:///:memory:",
            auto_seed_demo_users=True,
            auto_import_demo=False,
            llm_provider="none",
            agent_allow_mock_providers=True,
        )
    )
    seed_demo_data(container, force=True)
    return container, TestClient(create_app())


def _login(client, username="student_demo"):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_sse_requires_auth():
    _, client = _client()
    resp = client.get("/api/v1/agent-runs/nonexistent/events/stream")
    assert resp.status_code == 401


def test_sse_not_found_run():
    _, client = _client()
    headers = _login(client)
    resp = client.get("/api/v1/agent-runs/nonexistent/events/stream", headers=headers)
    assert resp.status_code == 404


def test_sse_stream_events_for_existing_run():
    container, client = _client()
    headers = _login(client)
    # 创建 job + run + 事件
    repo = container.agent_runtime_repository
    user_id = container.user_repository.get_user_by_username("student_demo").id
    job_id = repo.create_job(user_id=user_id, job_kind="final_review")
    run_id = repo.create_run(job_id=job_id, user_id=user_id)
    repo.append_event(
        run_id=run_id, type="RUN_STARTED", status="RUNNING", phase="CONTEXT_BUILDING"
    )
    repo.append_event(
        run_id=run_id, type="MODEL_COMPLETED", status="RUNNING", phase="VALIDATING_OUTPUT"
    )
    # 终态,流应结束
    repo.update_run(run_id, status="SUCCEEDED", phase="IDLE", finished_at="2026-09-12T10:00:00+08:00")
    resp = client.get(f"/api/v1/agent-runs/{run_id}/events/stream", headers=headers)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    # 解析 SSE 行
    text = resp.text
    assert "event: RUN_STARTED" in text
    assert "event: MODEL_COMPLETED" in text


def test_sse_last_event_id_resume():
    container, client = _client()
    headers = _login(client)
    repo = container.agent_runtime_repository
    user_id = container.user_repository.get_user_by_username("student_demo").id
    job_id = repo.create_job(user_id=user_id, job_kind="final_review")
    run_id = repo.create_run(job_id=job_id, user_id=user_id)
    eid1, seq1 = repo.append_event(
        run_id=run_id, type="RUN_STARTED", status="RUNNING", phase="IDLE"
    )
    eid2, seq2 = repo.append_event(
        run_id=run_id, type="MODEL_COMPLETED", status="RUNNING", phase="IDLE"
    )
    repo.update_run(run_id, status="SUCCEEDED", phase="IDLE", finished_at="t")
    # 用 Last-Event-ID 续传,应只收到第二个事件
    resp = client.get(
        f"/api/v1/agent-runs/{run_id}/events/stream",
        headers={**headers, "Last-Event-ID": eid1},
    )
    assert resp.status_code == 200
    text = resp.text
    # 应包含 MODEL_COMPLETED 但不包含 RUN_STARTED(已跳过)
    assert "MODEL_COMPLETED" in text
    assert "RUN_STARTED" not in text


def test_list_events_after_sequence():
    container, client = _client()
    headers = _login(client)
    repo = container.agent_runtime_repository
    user_id = container.user_repository.get_user_by_username("student_demo").id
    job_id = repo.create_job(user_id=user_id, job_kind="final_review")
    run_id = repo.create_run(job_id=job_id, user_id=user_id)
    for _ in range(5):
        repo.append_event(run_id=run_id, type="RUN_STARTED", status="RUNNING", phase="IDLE")
    resp = client.get(
        f"/api/v1/agent-runs/{run_id}/events?after_sequence=2&limit=10",
        headers=headers,
    )
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 4
    assert events[0]["sequence"] == 3
