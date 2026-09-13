from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests


def _setup() -> tuple[TestClient, object, dict[str, str], dict[str, str]]:
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    student = container.user_repository.create_user(
        username="goal_center_student", password_hash=hash_password("Demo123456"), role="student"
    )
    other = container.user_repository.create_user(
        username="goal_center_other", password_hash=hash_password("Demo123456"), role="student"
    )
    client = TestClient(create_app())

    def login(username: str) -> dict[str, str]:
        response = client.post("/api/v1/auth/login", json={"username": username, "password": "Demo123456"})
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return client, container, login(student.username), login(other.username)


def test_generated_plan_is_bound_to_selected_goal() -> None:
    client, container, headers, _ = _setup()
    user_id = container.user_repository.get_user_by_username("goal_center_student").id
    goal = container.student_goal_repository.create_goal(
        user_id=user_id,
        name="准备数据库期末",
        category="ACADEMIC",
        target_date=(datetime.now(timezone.utc) + timedelta(days=14)).date().isoformat(),
        idempotency_key="goal-1",
    )[0]
    container.personal_task_repository.create_task(user_id=user_id, title="复习索引", course_id="db")

    response = client.post(
        "/api/v1/learning-plans/generate",
        json={"available_minutes": 60, "goal_id": goal.goal_id},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["goal_id"] == goal.goal_id
    assert any(item["item_type"] == "GOAL_PROGRESS" for item in response.json()["items"])


def test_plan_generation_rejects_another_users_goal() -> None:
    client, container, headers, _ = _setup()
    other_id = container.user_repository.get_user_by_username("goal_center_other").id
    goal = container.student_goal_repository.create_goal(
        user_id=other_id,
        name="其他人的目标",
        category="ACADEMIC",
        target_date=None,
        idempotency_key="other-goal-1",
    )[0]

    response = client.post(
        "/api/v1/learning-plans/generate",
        json={"available_minutes": 60, "goal_id": goal.goal_id},
        headers=headers,
    )

    assert response.status_code in {403, 404, 422}

