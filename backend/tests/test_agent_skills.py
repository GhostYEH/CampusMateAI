from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests


def test_skill_manifest_is_declarative_and_contains_goal_center() -> None:
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    container.user_repository.create_user(
        username="skills_student", password_hash=hash_password("Demo123456"), role="student"
    )
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "skills_student", "password": "Demo123456"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/api/v1/agent-runtime/skills", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    goal = next(skill for skill in body["skills"] if skill["skill_code"] == "learning_goal_center")
    assert goal["transport"] == "internal"
    assert "plan.generate" in goal["capabilities"]
    assert "secret" not in str(body).lower()
