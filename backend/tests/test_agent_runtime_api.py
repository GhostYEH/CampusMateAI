from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests


def _setup():
    container = reset_container_for_tests(Settings(
        app_env="test", database_url="sqlite:///:memory:", llm_provider="none",
        agent_artifact_path="./data/test-agent-artifacts",
    ))
    users = []
    for name in ("agent_student", "other_student"):
        users.append(container.user_repository.create_user(
            username=name, password_hash=hash_password("Demo123456"), role="student", display_name=name
        ))
    client = TestClient(create_app())
    headers = []
    for user in users:
        response = client.post("/api/v1/auth/login", json={"username": user.username, "password": "Demo123456"})
        headers.append({"Authorization": f"Bearer {response.json()['access_token']}"})
    return container, client, headers


def test_runtime_job_run_events_cancel_and_ownership():
    _container, client, headers = _setup()
    created = client.post(
        "/api/v1/agent-jobs", headers={**headers[0], "Idempotency-Key": "create-job-1"},
        json={"domain": "final_review", "objective_summary": "准备期末复习", "total_steps": 4},
    )
    assert created.status_code == 200
    body = created.json()
    run_id = body["run"]["run_id"]
    assert body["run"]["status"] == "QUEUED"
    repeated = client.post(
        "/api/v1/agent-jobs", headers={**headers[0], "Idempotency-Key": "create-job-1"},
        json={"domain": "final_review", "objective_summary": "准备期末复习", "total_steps": 4},
    )
    assert repeated.status_code == 200
    assert repeated.json()["job_id"] == body["job_id"]
    conflict = client.post(
        "/api/v1/agent-jobs", headers={**headers[0], "Idempotency-Key": "create-job-1"},
        json={"domain": "final_review", "objective_summary": "不同输入", "total_steps": 4},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "AGENT_IDEMPOTENCY_CONFLICT"
    assert client.get(f"/api/v1/agent-runs/{run_id}", headers=headers[1]).status_code == 404
    events = client.get(f"/api/v1/agent-runs/{run_id}/events", headers=headers[0]).json()
    assert [event["type"] for event in events["items"]] == ["RUN_QUEUED"]
    cancelled = client.post(f"/api/v1/agent-runs/{run_id}/cancel", headers=headers[0])
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"


def test_create_requires_idempotency_header_and_stream_requires_bearer():
    _container, client, headers = _setup()
    missing_key = client.post(
        "/api/v1/agent-jobs", headers=headers[0],
        json={"domain": "course_research", "objective_summary": "研究课程", "total_steps": 2},
    )
    assert missing_key.status_code == 422
    response = client.get("/api/v1/agent-runs/missing/events/stream?access_token=forbidden")
    assert response.status_code == 401


def test_capability_response_is_safe_and_student_only():
    _container, client, headers = _setup()
    response = client.get("/api/v1/agent-runtime/capabilities", headers=headers[0])
    assert response.status_code == 200
    encoded = response.text.lower()
    assert "api_key" not in encoded and "base_url" not in encoded and "prompt" not in encoded
