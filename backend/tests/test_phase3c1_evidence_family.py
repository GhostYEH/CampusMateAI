from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.c_knowledge import PracticeAttemptCreate
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


UTC = timezone.utc
SAFE_EVIDENCE_FIELDS = {
    "evidence_kind", "source_category", "event_id", "event_type", "occurred_at",
    "data_quality", "role", "explanation_code",
}


def _setup():
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


def _knowledge_snapshot(container):
    student = container.user_repository.get_user_by_username("student_demo")
    course = container.course_repository.create_course(
        name="C language", owner_user_id=student.id, status="active"
    )
    container.knowledge_service.seed_c_taxonomy()
    container.knowledge_service.map_exercise(
        course_id=course.id, exercise_id="ex-1", knowledge_component_code="c.variables"
    )
    container.knowledge_service.record_practice_attempt(
        user_id=student.id,
        attempt=PracticeAttemptCreate(
            client_attempt_id="evidence-1", course_id=course.id, exercise_id="ex-1",
            occurred_at=datetime.now(UTC) - timedelta(minutes=1), result_type="failed",
            score=20, max_score=100, test_count=5, passed_test_count=1,
            compiler_outcome="compile_error", error_codes=["compile_syntax"],
        ),
    )
    projection = container.knowledge_service.project_knowledge(
        user_id=student.id, course_id=course.id, as_of=datetime.now(UTC)
    )
    snapshot = next(item for item in projection.snapshots if item.scope_id == "c.variables")
    return student, snapshot


def test_core_snapshot_evidence_query_remains_successful():
    container, client = _setup()
    headers = _login(client, "student_demo")
    snapshot = client.get("/api/v1/learner-state/snapshots", headers=headers).json()["items"][0]

    response = client.get(
        f"/api/v1/learner-state/snapshots/{snapshot['snapshot_id']}/evidence",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["page"] == 1
    assert response.json()["page_size"] == 50


def test_knowledge_snapshot_evidence_query_uses_knowledge_family():
    container, client = _setup()
    student, snapshot = _knowledge_snapshot(container)
    headers = _login(client, "student_demo")

    response = client.get(
        f"/api/v1/learner-state/snapshots/{snapshot.snapshot_id}/evidence",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert set(body["items"][0]) == SAFE_EVIDENCE_FIELDS


def test_snapshot_evidence_cross_user_and_unknown_id_are_404():
    container, client = _setup()
    student, snapshot = _knowledge_snapshot(container)

    other_headers = _login(client, "student_demo_01")
    cross_user = client.get(
        f"/api/v1/learner-state/snapshots/{snapshot.snapshot_id}/evidence",
        headers=other_headers,
    )
    unknown = client.get(
        "/api/v1/learner-state/snapshots/not-a-real-snapshot/evidence",
        headers=_login(client, "student_demo"),
    )

    assert cross_user.status_code == 404
    assert unknown.status_code == 404
