from __future__ import annotations

from datetime import datetime, timedelta, timezone


import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests


def _setup() -> tuple[TestClient, object, dict[str, str], dict[str, str]]:
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    student = container.user_repository.create_user(
        username="phase4_student", password_hash=hash_password("Demo123456"), role="student"
    )
    other = container.user_repository.create_user(
        username="phase4_other", password_hash=hash_password("Demo123456"), role="student"
    )
    client = TestClient(create_app())
    def login(username: str) -> dict[str, str]:
        response = client.post("/api/v1/auth/login", json={"username": username, "password": "Demo123456"})
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    return client, container, login(student.username), login(other.username)


def _request(minutes: int = 60, **overrides):
    value = {"available_minutes": minutes}
    value.update(overrides)
    return value


def test_generate_without_llm_is_deterministic_and_budgeted() -> None:
    client, container, headers, _ = _setup()
    task = container.personal_task_repository.create_task(
        user_id=container.user_repository.get_user_by_username("phase4_student").id,
        title="交作业", deadline=(datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(),
        course_id="course-missing",
    )
    first = client.post("/api/v1/learning-plans/generate", json=_request(30), headers=headers)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["allocated_minutes"] <= 30
    assert body["planner_version"]
    assert body["input_digest"]
    assert body["items"]
    assert all("priority_components" in item and "explanation_codes" in item for item in body["items"])
    assert "source_id" not in body and "payload" not in body and "source_text" not in body
    second = client.post("/api/v1/learning-plans/generate", json=_request(30), headers=headers)
    assert second.status_code == 200
    assert second.json()["plan_id"] == body["plan_id"]
    assert task.id in {item.get("task_id") for item in body["items"]}



def test_deadline_change_and_reject_cooldown_create_safe_new_or_suppressed_plan() -> None:
    client, container, headers, _ = _setup()
    user_id = container.user_repository.get_user_by_username("phase4_student").id
    task = container.personal_task_repository.create_task(user_id=user_id, title="复习", deadline="2099-01-01T00:00:00+00:00")
    first = client.post("/api/v1/learning-plans/generate", json=_request(), headers=headers).json()
    client.post(f"/api/v1/learning-plans/{first['plan_id']}/decision", json={"decision": "REJECT"}, headers=headers)
    suppressed = client.post("/api/v1/learning-plans/generate", json=_request(), headers=headers)
    assert suppressed.status_code == 409
    container.personal_task_repository.update_task(task.id, user_id=user_id, fields={"deadline": "2026-09-12T00:00:00+00:00"})
    changed = client.post("/api/v1/learning-plans/generate", json=_request(), headers=headers)
    assert changed.status_code == 200
    assert changed.json()["input_digest"] != first["input_digest"]


def test_plan_lifecycle_is_confirmed_idempotent_and_tamper_resistant() -> None:
    client, container, headers, _ = _setup()
    container.personal_task_repository.create_task(
        user_id=container.user_repository.get_user_by_username("phase4_student").id,
        title="测试任务", source="test", external_id="t1",
    )
    generated = client.post("/api/v1/learning-plans/generate", json=_request(), headers=headers).json()
    plan_id = generated["plan_id"]
    assert client.post(f"/api/v1/learning-plans/{plan_id}/execute", headers=headers).status_code == 409
    assert client.post(f"/api/v1/learning-plans/{plan_id}/decision", json={"decision": "ACCEPT"}, headers=headers).status_code == 200
    tampered = client.post(
        f"/api/v1/learning-plans/{plan_id}/execute",
        json={"items": [{"item_id": "forged", "action_type": "delete_user_data"}]},
        headers=headers,
    )
    assert tampered.status_code in {200, 409}
    assert "delete_user_data" not in tampered.text
    executed = client.post(f"/api/v1/learning-plans/{plan_id}/execute", headers=headers)
    assert executed.status_code == 200
    retried = client.post(f"/api/v1/learning-plans/{plan_id}/execute", headers=headers)
    assert retried.status_code == 200


def test_cross_user_and_non_student_are_denied_without_existence_leak() -> None:
    client, container, headers, other_headers = _setup()
    container.personal_task_repository.create_task(
        user_id=container.user_repository.get_user_by_username("phase4_student").id,
        title="测试任务", source="test", external_id="t1",
    )
    generated = client.post("/api/v1/learning-plans/generate", json=_request(), headers=headers).json()
    plan_id = generated["plan_id"]
    assert client.get(f"/api/v1/learning-plans/{plan_id}", headers=other_headers).status_code == 404
    container.user_repository.create_user(
        username="phase4_admin", password_hash=hash_password("Demo123456"), role="admin"
    )
    admin_login = client.post(
        "/api/v1/auth/login", json={"username": "phase4_admin", "password": "Demo123456"}
    )
    assert admin_login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    assert client.get(f"/api/v1/learning-plans/{plan_id}", headers=admin_headers).status_code == 403


def test_legacy_teacher_role_cannot_read_student_plans() -> None:
    client, container, _, _ = _setup()
    container.user_repository.create_user(
        username="phase4_teacher", password_hash=hash_password("Demo123456"), role="teacher"
    )
    login = client.post(
        "/api/v1/auth/login", json={"username": "phase4_teacher", "password": "Demo123456"}
    )
    assert login.status_code == 200
    teacher_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.post("/api/v1/learning-plans/generate", json=_request(), headers=teacher_headers).status_code == 403


def test_security_allowlist_exposes_only_read_propose_write_operations() -> None:
    from app.services.learning_agent_tools import ALLOWED_TOOL_SPECS

    assert set(ALLOWED_TOOL_SPECS) >= {
        "read_core_state", "read_knowledge_state", "read_personal_tasks",
        "search_course_materials", "propose_learning_plan", "create_personal_task",
        "update_plan_created_task", "undo_plan_action",
    }
    assert not any("submit" in name or "message" in name or "credential" in name for name in ALLOWED_TOOL_SPECS)


def test_accept_execute_and_undo_only_removes_plan_created_tasks() -> None:
    client, container, headers, _ = _setup()
    user_id = container.user_repository.get_user_by_username("phase4_student").id
    course = container.course_repository.create_course(name="C", owner_user_id=user_id)
    original = container.personal_task_repository.create_task(user_id=user_id, title="已有任务")
    generated = client.post(
        "/api/v1/learning-plans/generate", json=_request(60, course_id=course.id), headers=headers
    )
    assert generated.status_code == 200, generated.text
    assert generated.json()["items"]
    plan_id = generated.json()["plan_id"]
    assert client.post(f"/api/v1/learning-plans/{plan_id}/decision", json={"decision": "ACCEPT"}, headers=headers).status_code == 200
    executed = client.post(f"/api/v1/learning-plans/{plan_id}/execute", headers=headers)
    assert executed.status_code == 200
    assert container.personal_task_repository.get_task(original.id, user_id=user_id).status == "pending"
    assert client.post(f"/api/v1/learning-plans/{plan_id}/undo", headers=headers).status_code == 200
    assert container.personal_task_repository.get_task(original.id, user_id=user_id).status == "pending"


def test_llm_failure_returns_complete_deterministic_plan() -> None:
    client, container, headers, _ = _setup()
    container.personal_task_repository.create_task(
        user_id=container.user_repository.get_user_by_username("phase4_student").id,
        title="测试任务", source="test", external_id="t1",
    )
    class FailingLLM:
        available = True
        async def chat(self, *args, **kwargs):
            raise TimeoutError("provider timeout")
    container.learning_planner_service.llm = FailingLLM()
    response = client.post(
        "/api/v1/learning-plans/generate", json=_request(60, enhance_with_llm=True), headers=headers
    )
    assert response.status_code == 200
    assert response.json()["items"] is not None
    assert response.json()["llm_summary"] is None
