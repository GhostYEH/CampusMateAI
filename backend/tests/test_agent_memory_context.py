from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests


def _setup() -> tuple[TestClient, object, dict[str, str], dict[str, str]]:
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    student = container.user_repository.create_user(
        username="memory_student", password_hash=hash_password("Demo123456"), role="student"
    )
    other = container.user_repository.create_user(
        username="memory_other", password_hash=hash_password("Demo123456"), role="student"
    )
    client = TestClient(create_app())

    def login(username: str) -> dict[str, str]:
        response = client.post("/api/v1/auth/login", json={"username": username, "password": "Demo123456"})
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return client, container, login(student.username), login(other.username)


def test_memory_is_explicitly_recorded_listable_and_consumed_in_context() -> None:
    client, container, headers, _ = _setup()
    response = client.post(
        "/api/v1/agent-memories",
        json={
            "kind": "CONFIRMED_PREFERENCE",
            "content_summary": "工作日晚上优先安排短任务",
            "confirmed": True,
            "model_may_consume": True,
            "provenance": "student_settings",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    memory = response.json()
    assert memory["model_may_consume"] is True

    listed = client.get("/api/v1/agent-memories", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["memory_id"] == memory["memory_id"]

    user_id = container.user_repository.get_user_by_username("memory_student").id
    snapshot = container.agent_context_manager.build(user_id=user_id, facts={"goal": "期末复习"})
    assert snapshot.facts["memories"][0]["content_summary"] == "工作日晚上优先安排短任务"


def test_memory_withdraw_is_user_scoped_and_removes_model_consent() -> None:
    client, _, headers, other_headers = _setup()
    created = client.post(
        "/api/v1/agent-memories",
        json={
            "kind": "CONFIRMED_CONSTRAINT",
            "content_summary": "周三不可安排学习",
            "confirmed": True,
            "model_may_consume": True,
        },
        headers=headers,
    ).json()
    memory_id = created["memory_id"]

    forbidden = client.post(f"/api/v1/agent-memories/{memory_id}/withdraw", headers=other_headers)
    assert forbidden.status_code == 404

    withdrawn = client.post(f"/api/v1/agent-memories/{memory_id}/withdraw", headers=headers)
    assert withdrawn.status_code == 200
    assert withdrawn.json()["withdrawn"] is True
    assert withdrawn.json()["model_may_consume"] is False
