from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from fastapi.testclient import TestClient


def _client():
    container = reset_container_for_tests(
        Settings(
            app_env="test", database_url="sqlite:///:memory:",
            auto_seed_demo_users=True, auto_import_demo=False, llm_provider="none",
        )
    )
    seed_demo_data(container, force=True)
    return container, TestClient(create_app())


def _login(client, username):
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "Demo123456"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_runs_api_is_paginated_and_returns_safe_run_summary():
    _, client = _client()
    headers = _login(client, "student_demo")
    response = client.get("/api/v1/learner-state/runs?page=1&page_size=1", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert {"run_id", "as_of", "computed_at", "estimator_version", "trigger", "is_current", "warning_codes", "snapshot_count"} <= set(body["items"][0])
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert "user_id" not in str(body)


def test_changes_api_reports_added_updated_removed_and_filters_without_internal_json():
    container, client = _client()
    headers = _login(client, "student_demo")
    first = client.get("/api/v1/learner-state/snapshots", headers=headers).json()
    first_run_id = first["items"][0]["run_id"]
    user_id = container.user_repository.get_user_by_username("student_demo").id
    task = container.personal_task_repository.create_task(
        user_id=user_id, title="evolution", deadline="2026-09-30T00:00:00+00:00"
    )
    second = client.get("/api/v1/learner-state/snapshots", headers=headers).json()
    second_run_id = second["items"][0]["run_id"]
    changes = client.get(
        f"/api/v1/learner-state/changes?from_run_id={first_run_id}&to_run_id={second_run_id}&scope_type=TASK",
        headers=headers,
    )
    assert changes.status_code == 200
    body = changes.json()
    assert body["from_run_id"] == first_run_id
    assert body["to_run_id"] == second_run_id
    assert any(item["change_type"] == "ADDED" for item in body["changes"])
    assert all("payload" not in str(item).lower() for item in body["changes"])

    container.personal_task_repository.soft_delete(task.id, user_id=user_id)
    third = client.get("/api/v1/learner-state/snapshots", headers=headers).json()
    removed = client.get(
        f"/api/v1/learner-state/changes?from_run_id={second_run_id}&to_run_id={third['items'][0]['run_id']}&scope_type=TASK",
        headers=headers,
    )
    assert removed.status_code == 200
    assert any(item["change_type"] == "REMOVED" for item in removed.json()["changes"])


def test_changes_api_same_run_is_empty_and_rejects_admin_or_cross_user_runs():
    _, client = _client()
    student_headers = _login(client, "student_demo")
    run_id = client.get("/api/v1/learner-state/runs", headers=student_headers).json()["items"][0]["run_id"]
    same = client.get(
        f"/api/v1/learner-state/changes?from_run_id={run_id}&to_run_id={run_id}",
        headers=student_headers,
    )
    assert same.status_code == 200
    assert same.json()["changes"] == []
    assert client.get(
        "/api/v1/learner-state/runs", headers=_login(client, "admin_demo")
    ).status_code == 403

    other_headers = _login(client, "student_demo_01")
    cross_user = client.get(
        f"/api/v1/learner-state/changes?to_run_id={run_id}", headers=other_headers
    )
    assert cross_user.status_code == 404


def test_changes_api_marks_estimator_version_changes_without_comparing_numbers(monkeypatch):
    _, client = _client()
    headers = _login(client, "student_demo")
    first = client.get("/api/v1/learner-state/snapshots", headers=headers).json()
    first_run_id = first["items"][0]["run_id"]
    monkeypatch.setattr(
        "app.services.learner_state_service.ESTIMATOR_VERSION",
        "deterministic-observed-v2",
    )
    second = client.get("/api/v1/learner-state/snapshots", headers=headers).json()
    second_run_id = second["items"][0]["run_id"]
    response = client.get(
        f"/api/v1/learner-state/changes?from_run_id={first_run_id}&to_run_id={second_run_id}",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["estimator_changed"] is True
    assert response.json()["changes"] == []


def test_changes_api_can_explicitly_include_unchanged_snapshots():
    _, client = _client()
    headers = _login(client, "student_demo")
    run_id = client.get("/api/v1/learner-state/runs", headers=headers).json()["items"][0]["run_id"]
    response = client.get(
        f"/api/v1/learner-state/changes?from_run_id={run_id}&to_run_id={run_id}&include_unchanged=true&page_size=2",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["changes"]
    assert all(item["change_type"] == "UNCHANGED" for item in response.json()["changes"])
