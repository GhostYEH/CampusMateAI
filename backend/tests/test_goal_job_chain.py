from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests


def test_learning_goal_job_generates_plan_and_persists_run_lineage() -> None:
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    user = container.user_repository.create_user(
        username="goal_job_student", password_hash=hash_password("Demo123456"), role="student"
    )
    goal = container.student_goal_repository.create_goal(
        user_id=user.id, name="完成数据库期末复习", category="ACADEMIC",
        target_date=(datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat(),
        idempotency_key="goal-job-1",
    )[0]
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/login", json={"username": "goal_job_student", "password": "Demo123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(
        "/api/v1/agent-jobs",
        json={"job_kind": "learning_goal", "input_ref": {"goal_id": goal.goal_id, "available_minutes": 60}},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    job = response.json()
    assert job["status"] == "SUCCEEDED"
    assert job["latest_run_id"]
    assert job["input_ref"]["plan_id"]

    run = client.get(f"/api/v1/agent-runs/{job['latest_run_id']}", headers=headers)
    assert run.status_code == 200
    assert run.json()["status"] == "SUCCEEDED"
    events = client.get(f"/api/v1/agent-runs/{job['latest_run_id']}/events", headers=headers).json()
    assert any(event["type"] == "RUN_COMPLETED" for event in events)


def test_invalid_learning_goal_request_does_not_create_orphan_job() -> None:
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    user = container.user_repository.create_user(
        username="invalid_goal_job_student", password_hash=hash_password("Demo123456"), role="student"
    )
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "Demo123456"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(
        "/api/v1/agent-jobs",
        json={"job_kind": "learning_goal", "input_ref": {"available_minutes": 60}},
        headers=headers,
    )

    assert response.status_code == 422, response.text
    assert container.agent_runtime_repository.list_jobs(user.id) == []
