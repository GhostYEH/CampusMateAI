from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests


def test_learning_plan_summary_exposes_stage_and_next_action() -> None:
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    user = container.user_repository.create_user(
        username="summary_student", password_hash=hash_password("Demo123456"), role="student"
    )
    goal = container.student_goal_repository.create_goal(
        user_id=user.id, name="完成高数复习", category="ACADEMIC",
        target_date=(datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat(),
        idempotency_key="summary-goal",
    )[0]
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/login", json={"username": "summary_student", "password": "Demo123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    plan = client.post(
        "/api/v1/learning-plans/generate",
        json={"goal_id": goal.goal_id, "available_minutes": 60}, headers=headers,
    )
    assert plan.status_code == 200, plan.text
    response = client.get(f"/api/v1/learning-plans/{plan.json()['plan_id']}/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["goal_id"] == goal.goal_id
    assert body["stage"] == "AWAITING_CONFIRMATION"
    assert body["next_action"] == "确认计划后创建个人待办"
    assert 0 <= body["completion_percent"] <= 100

