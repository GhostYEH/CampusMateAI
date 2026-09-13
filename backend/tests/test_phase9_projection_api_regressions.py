from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.schemas.c_knowledge import PracticeAttemptCreate
from app.services.container import reset_container_for_tests


def _setup():
    container = reset_container_for_tests(
        Settings(app_env="test", database_url="sqlite:///:memory:", llm_provider="none")
    )
    user = container.user_repository.create_user(
        username="phase9_api_student",
        password_hash=hash_password("Demo123456"),
        role="student",
        display_name="Phase 9 API Student",
    )
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "Demo123456"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return container, client, headers, user


def _seed_prediction_evidence(container, user_id: str) -> str:
    course = container.course_repository.create_course(
        name="Prediction contract course", owner_user_id=user_id, status="active"
    )
    container.knowledge_service.seed_c_taxonomy()
    container.knowledge_service.map_exercise(
        course_id=course.id,
        exercise_id="prediction-contract-exercise",
        knowledge_component_code="c.pointer.basics",
    )
    now = datetime.now(timezone.utc).replace(microsecond=0)
    for index in range(4):
        passed = index >= 2
        container.knowledge_service.record_practice_attempt(
            user_id=user_id,
            attempt=PracticeAttemptCreate(
                client_attempt_id=f"prediction-contract-{index}",
                course_id=course.id,
                exercise_id="prediction-contract-exercise",
                occurred_at=now - timedelta(days=4 - index),
                result_type="passed" if passed else "failed",
                score=100 if passed else 30 + index * 10,
                max_score=100,
                total_test_count=4,
                passed_test_count=4 if passed else index,
                compiler_outcome="success" if passed else "compile_error",
                error_codes=[] if passed else ["pointer_indirection"],
            ),
        )
    container.knowledge_service.project_knowledge(
        user_id=user_id, course_id=course.id, as_of=now, trigger="api_regression"
    )
    return course.id


def test_academic_api_reads_the_academic_projection_family():
    _container, client, headers, _user = _setup()

    response = client.get("/api/v1/learner-state/academic", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 6
    assert {item["projection_kind"] for item in body["items"]} == {"ACADEMIC"}
    assert {item["state_type"] for item in body["items"]} == {
        "academic_course_load",
        "grade_observation",
        "credit_progress",
        "exam_exposure",
        "schedule_load",
        "goal_state",
    }


def test_prediction_api_reads_its_course_family_and_exposes_evidence():
    container, client, headers, user = _setup()
    course_id = _seed_prediction_evidence(container, user.id)

    response = client.get(
        f"/api/v1/learner-state/predictions/{course_id}", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 0
    assert {item["projection_kind"] for item in body["items"]} == {"PREDICTION"}
    assert {item["projection_scope"] for item in body["items"]} == {course_id}
    evidence = client.get(
        f"/api/v1/learner-state/snapshots/{body['items'][0]['snapshot_id']}/evidence",
        headers=headers,
    )
    assert evidence.status_code == 200
    evidence_body = evidence.json()
    assert evidence_body["total"] > 0
    assert evidence_body["items"]
    assert all("source_id" not in item for item in evidence_body["items"])


def test_counterfactual_api_returns_typed_response_without_mutating_projection():
    container, client, headers, user = _setup()
    course_id = _seed_prediction_evidence(container, user.id)
    before = client.get(
        f"/api/v1/learner-state/predictions/{course_id}", headers=headers
    ).json()

    response = client.post(
        "/api/v1/learner-state/simulate",
        headers=headers,
        json={
            "course_id": course_id,
            "intervention": {
                "intervention_type": "additional_practice",
                "knowledge_component_code": "c.pointer.basics",
                "additional_practice_count": 5,
                "expected_score": 80,
                "misconception_code": None,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["course_id"] == course_id
    assert body["intervention"]["intervention_type"] == "additional_practice"
    assert body["deltas"]
    after = client.get(
        f"/api/v1/learner-state/predictions/{course_id}", headers=headers
    ).json()
    assert [item["snapshot_id"] for item in after["items"]] == [
        item["snapshot_id"] for item in before["items"]
    ]


def test_paused_practice_source_removes_practice_from_prediction_inputs():
    container, client, headers, user = _setup()
    course_id = _seed_prediction_evidence(container, user.id)
    initial = client.get(
        f"/api/v1/learner-state/predictions/{course_id}", headers=headers
    )
    assert initial.status_code == 200
    assert initial.json()["total"] > 0

    paused = client.put(
        "/api/v1/learner-state/data-controls/PRACTICE",
        json={"status": "PAUSED", "idempotency_key": "pause-practice-for-prediction"},
        headers=headers,
    )
    assert paused.status_code == 200

    after_pause = client.get(
        f"/api/v1/learner-state/predictions/{course_id}", headers=headers
    )
    assert after_pause.status_code == 200
    assert after_pause.json()["total"] == 0
