from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.c_knowledge import PracticeAttemptCreate
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
        )
    )
    seed_demo_data(container, force=True)
    return container, TestClient(create_app())


def _login(client, username):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_learner_state_api_requires_student_auth_and_never_returns_raw_payload():
    container, client = _client()
    assert client.get("/api/v1/learner-state/snapshots").status_code == 401
    headers = _login(client, "student_demo")
    response = client.get("/api/v1/learner-state/snapshots", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert all("payload" not in item for item in body["items"])
    assert all("mastered" not in str(item).lower() for item in body["items"])
    workload = next(item for item in body["items"] if item["state_type"] == "task_workload")
    evidence = client.get(
        f"/api/v1/learner-state/snapshots/{workload['snapshot_id']}/evidence",
        headers=headers,
    )
    assert evidence.status_code == 200
    assert evidence.json()["items"]
    assert all({"evidence_kind", "source_category", "role", "explanation_code"} <= set(item) for item in evidence.json()["items"])
    assert all("source_id" not in item and "row_id" not in item for item in evidence.json()["items"])


def test_learner_state_api_rejects_admin_and_cross_user_snapshot_is_404():
    container, client = _client()
    admin_headers = _login(client, "admin_demo")
    assert client.get("/api/v1/learner-state/snapshots", headers=admin_headers).status_code == 403
    student_headers = _login(client, "student_demo")
    response = client.get("/api/v1/learner-state/snapshots", headers=student_headers)
    snapshot_id = response.json()["items"][0]["snapshot_id"]
    other_headers = _login(client, "student_demo_01")
    assert client.get(
        f"/api/v1/learner-state/snapshots/{snapshot_id}/evidence",
        headers=other_headers,
    ).status_code == 404


def test_knowledge_snapshot_evidence_uses_its_projection_family():
    container, client = _client()
    student = container.user_repository.get_user_by_username("student_demo")
    headers = _login(client, "student_demo")
    course = container.course_repository.create_course(
        name="C evidence course", owner_user_id=student.id, status="active"
    )
    service = container.knowledge_service
    service.seed_c_taxonomy()
    service.map_exercise(
        course_id=course.id,
        exercise_id="evidence-exercise",
        knowledge_component_code="c.pointer.indirection",
    )
    service.record_practice_attempt(
        user_id=student.id,
        attempt=PracticeAttemptCreate(
            client_attempt_id="evidence-attempt",
            course_id=course.id,
            exercise_id="evidence-exercise",
            occurred_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            result_type="failed",
            score=20,
            max_score=100,
            total_test_count=2,
            passed_test_count=0,
            compiler_outcome="compile_error",
            error_codes=["pointer_indirection"],
        ),
    )
    projection = service.project_knowledge(
        user_id=student.id,
        course_id=course.id,
        as_of=datetime.now(timezone.utc),
    )
    snapshot = next(
        item for item in projection.snapshots
        if item.scope_id == "c.pointer.indirection"
    )

    response = client.get(
        f"/api/v1/learner-state/snapshots/{snapshot.snapshot_id}/evidence",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert all("source_id" not in item and "row_id" not in item for item in body["items"])
    assert all(
        {"evidence_kind", "source_category", "role", "explanation_code"} <= set(item)
        for item in body["items"]
    )
