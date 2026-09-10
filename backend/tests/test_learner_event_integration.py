from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _setup() -> tuple[TestClient, object, dict[str, str]]:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
        llm_provider="none",
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert login.status_code == 200
    return client, container, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _events(container, user_id: str):
    return container.learner_event_repository.list_for_user(user_id=user_id)


def test_finish_route_projects_completed_session_without_changing_response():
    client, container, headers = _setup()
    created = client.post(
        "/api/v1/study/sessions",
        headers=headers,
        json={"mode": "focus", "planned_duration_seconds": 1500},
    )
    assert created.status_code == 201

    finished = client.post(
        f"/api/v1/study/sessions/{created.json()['id']}/finish",
        headers=headers,
        json={
            "self_report": "private report must not enter event",
            "self_report_tags": ["calm"],
            "behavior_summary": {
                "observed_seconds": 10,
                "study_seconds": 8,
                "paused_seconds": 0,
                "longest_continuous_study_seconds": 8,
                "meaningful_switch_count": 0,
                "phone_interaction_count": 0,
                "possible_distraction_count": 0,
                "absent_count": 0,
                "reminder_count": 0,
                "model_version": "test",
            },
        },
    )

    assert finished.status_code == 200
    assert set(finished.json()) == set(created.json())
    rows, total = _events(container, finished.json()["user_id"])
    assert total == 1
    assert rows[0].event_type == "study_session_finished"
    assert rows[0].occurred_at == finished.json()["ended_at"]
    assert rows[0].duration_seconds == finished.json()["duration_seconds"]
    safe_event = str(rows[0].to_safe_dict())
    assert "private report" not in safe_event
    assert "behavior_summary" not in safe_event
    assert "calm" not in safe_event


def test_pause_resume_and_completed_session_update_do_not_project_extra_events():
    client, container, headers = _setup()
    created = client.post("/api/v1/study/sessions", headers=headers, json={})
    session_id = created.json()["id"]
    assert client.post(f"/api/v1/study/sessions/{session_id}/pause", headers=headers).status_code == 200
    assert client.post(f"/api/v1/study/sessions/{session_id}/resume", headers=headers).status_code == 200
    rows, total = _events(container, created.json()["user_id"])
    assert rows == []
    assert total == 0

    finished = client.post(f"/api/v1/study/sessions/{session_id}/finish", headers=headers, json={})
    assert finished.status_code == 200
    updated = client.patch(
        f"/api/v1/study/sessions/{session_id}",
        headers=headers,
        json={"expression_signal": {"label": "NEUTRAL"}},
    )
    assert updated.status_code == 200
    rows, total = _events(container, created.json()["user_id"])
    assert total == 1
    assert len(rows) == 1


def test_repeated_finish_keeps_existing_api_error_and_event_count():
    client, container, headers = _setup()
    created = client.post("/api/v1/study/sessions", headers=headers, json={})
    session_id = created.json()["id"]
    first = client.post(f"/api/v1/study/sessions/{session_id}/finish", headers=headers, json={})
    second = client.post(f"/api/v1/study/sessions/{session_id}/finish", headers=headers, json={})
    assert first.status_code == 200
    assert second.status_code == 409
    assert _events(container, created.json()["user_id"])[1] == 1


def test_session_event_failure_does_not_rollback_completion():
    client, container, headers = _setup()
    created = client.post("/api/v1/study/sessions", headers=headers, json={})
    session_id = created.json()["id"]

    def fail(_session):
        raise RuntimeError("event store unavailable")

    original = container.learner_event_service.record_study_session_finished
    container.learner_event_service.record_study_session_finished = fail
    try:
        finished = client.post(
            f"/api/v1/study/sessions/{session_id}/finish",
            headers=headers,
            json={"self_report": "must not be logged"},
        )
    finally:
        container.learner_event_service.record_study_session_finished = original

    assert finished.status_code == 200
    assert finished.json()["status"] == "completed"
    assert _events(container, created.json()["user_id"])[1] == 0


def test_complete_route_projects_task_and_repeat_is_idempotent():
    client, container, headers = _setup()
    created = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "title": "private title must not enter event",
            "description": "private description",
            "materials": ["private material"],
            "source_text": "private notice text",
        },
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    first = client.post(f"/api/v1/tasks/{task_id}/complete", headers=headers)
    second = client.post(f"/api/v1/tasks/{task_id}/complete", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "completed"

    rows, total = _events(container, created.json()["user_id"])
    assert total == 1
    assert rows[0].event_type == "task_completed"
    safe_event = str(rows[0].to_safe_dict())
    for private_text in ("private title", "private description", "private material", "private notice text"):
        assert private_text not in safe_event


def test_restore_then_complete_creates_new_task_event_for_new_completion_time():
    client, container, headers = _setup()
    created = client.post("/api/v1/tasks", headers=headers, json={"title": "repeatable task"})
    task_id = created.json()["id"]
    first = client.post(f"/api/v1/tasks/{task_id}/complete", headers=headers)
    assert first.status_code == 200
    assert client.post(f"/api/v1/tasks/{task_id}/restore", headers=headers).status_code == 200
    second = client.post(f"/api/v1/tasks/{task_id}/complete", headers=headers)
    assert second.status_code == 200
    rows, total = _events(container, created.json()["user_id"])
    assert total == 2
    assert len({row.dedupe_key for row in rows}) == 2


def test_deleted_task_and_task_event_failure_do_not_create_bad_events():
    client, container, headers = _setup()
    deleted = client.post("/api/v1/tasks", headers=headers, json={"title": "deleted task"})
    assert client.delete(f"/api/v1/tasks/{deleted.json()['id']}", headers=headers).status_code == 200
    assert client.post(f"/api/v1/tasks/{deleted.json()['id']}/complete", headers=headers).status_code == 409
    assert _events(container, deleted.json()["user_id"])[1] == 0

    task = client.post("/api/v1/tasks", headers=headers, json={"title": "event failure task"})
    task_id = task.json()["id"]

    def fail(_task):
        raise RuntimeError("event store unavailable")

    original = container.learner_event_service.record_personal_task_completed
    container.learner_event_service.record_personal_task_completed = fail
    try:
        completed = client.post(f"/api/v1/tasks/{task_id}/complete", headers=headers)
    finally:
        container.learner_event_service.record_personal_task_completed = original

    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert _events(container, task.json()["user_id"])[1] == 0
