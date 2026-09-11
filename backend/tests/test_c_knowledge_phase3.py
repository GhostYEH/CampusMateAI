from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.schemas.c_knowledge import PracticeAttemptCreate
from app.services.container import reset_container_for_tests
from app.core.config import Settings
from app.services.demo_seeder import seed_demo_data
from app.main import create_app


UTC = timezone.utc


def _container():
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
    return container


def _login(client, username: str):
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "Demo123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_c_taxonomy_is_versioned_and_has_30_to_50_components():
    container = _container()

    rows = container.knowledge_service.seed_c_taxonomy()

    assert 30 <= len(rows) <= 50
    assert len({row.code for row in rows}) == len(rows)
    assert {row.taxonomy_version for row in rows} == {"c-language-v1"}
    assert container.knowledge_service.seed_c_taxonomy() == rows


def test_practice_attempt_rejects_raw_code_and_invalid_client_evidence():
    with pytest.raises(ValidationError):
        PracticeAttemptCreate(
            client_attempt_id="attempt-1",
            course_id="course-1",
            exercise_id="exercise-1",
            occurred_at=datetime.now(UTC),
            result_type="failed",
            score=0,
            max_score=100,
            test_count=1,
            passed_test_count=0,
            compiler_outcome="compile_error",
            error_codes=["pointer_indirection"],
            source_code="int main(){return 0;}",
        )

    with pytest.raises(ValidationError):
        PracticeAttemptCreate(
            client_attempt_id="attempt-1",
            course_id="course-1",
            exercise_id="exercise-1",
            occurred_at=datetime.now(UTC),
            result_type="passed",
            score=100,
            max_score=100,
            test_count=1,
            passed_test_count=1,
            compiler_outcome="success",
            evidence_quality="verified",
        )


def test_practice_attempt_is_idempotent_and_event_failure_is_repairable(monkeypatch):
    container = _container()
    service = container.knowledge_service
    student = container.user_repository.get_user_by_username("student_demo")
    course = container.course_repository.create_course(
        name="C language", owner_user_id=student.id, status="active"
    )
    service.seed_c_taxonomy()
    service.map_exercise(
        course_id=course.id,
        exercise_id="ex-1",
        knowledge_component_code="c.pointer.indirection",
    )
    attempt = PracticeAttemptCreate(
        client_attempt_id="attempt-1",
        course_id=course.id,
        exercise_id="ex-1",
        occurred_at=datetime.now(UTC) - timedelta(minutes=1),
        result_type="failed",
        score=20,
        max_score=100,
        test_count=5,
        passed_test_count=1,
        compiler_outcome="compile_error",
        error_codes=["pointer_indirection"],
    )

    original_append = container.learner_event_repository.append_idempotent
    monkeypatch.setattr(
        container.learner_event_repository, "append_idempotent",
        lambda **_: (_ for _ in ()).throw(RuntimeError("temporary event store failure")),
    )
    first = service.record_practice_attempt(user_id=student.id, attempt=attempt)
    assert first.event_id is None
    monkeypatch.setattr(container.learner_event_repository, "append_idempotent", original_append)
    second = service.record_practice_attempt(user_id=student.id, attempt=attempt)

    assert first.attempt_id == second.attempt_id
    assert second.event_created is True
    assert container.learner_event_repository.list_for_user(
        user_id=student.id, event_type="practice_answered"
    )[1] == 1
    event = container.learner_event_repository.get_event(user_id=student.id, event_id=second.event_id)
    assert "source_code" not in (event.payload or {})


def test_knowledge_projection_is_conservative_and_requires_repeated_evidence():
    container = _container()
    service = container.knowledge_service
    student = container.user_repository.get_user_by_username("student_demo")
    course = container.course_repository.create_course(
        name="C language", owner_user_id=student.id, status="active"
    )
    service.seed_c_taxonomy()
    service.map_exercise(
        course_id=course.id, exercise_id="ex-1", knowledge_component_code="c.pointer.indirection"
    )
    for index, result_type in enumerate(("failed", "failed"), start=1):
        service.record_practice_attempt(
            user_id=student.id,
            attempt=PracticeAttemptCreate(
                client_attempt_id=f"attempt-{index}", course_id=course.id, exercise_id="ex-1",
                occurred_at=datetime.now(UTC) - timedelta(days=index), result_type=result_type,
                score=20, max_score=100, test_count=5, passed_test_count=1,
                compiler_outcome="compile_error", error_codes=["pointer_indirection"],
            ),
        )

    projection = service.project_knowledge(user_id=student.id, course_id=course.id, as_of=datetime.now(UTC))
    state = next(item for item in projection.snapshots if item.scope_id == "c.pointer.indirection")
    assert state.state_type == "knowledge_mastery_estimate"
    assert state.value["evidence_count"] == 2
    assert state.value["evidence_sufficiency"] == "SUFFICIENT"
    assert state.value["estimate"] < 0.5
    assert state.valid_until is not None
    hypotheses = service.list_hypotheses(user_id=student.id, course_id=course.id)
    assert len(hypotheses) == 1
    assert hypotheses[0].status == "OPEN"


def test_hypothesis_can_be_rejected_without_deleting_history():
    container = _container()
    service = container.knowledge_service
    student = container.user_repository.get_user_by_username("student_demo")
    course = container.course_repository.create_course(
        name="C language", owner_user_id=student.id, status="active"
    )
    service.seed_c_taxonomy()
    service.map_exercise(course_id=course.id, exercise_id="ex-1", knowledge_component_code="c.pointer.indirection")
    for index in range(2):
        service.record_practice_attempt(
            user_id=student.id,
            attempt=PracticeAttemptCreate(
                client_attempt_id=f"attempt-{index}", course_id=course.id, exercise_id="ex-1",
                occurred_at=datetime.now(UTC) - timedelta(days=index), result_type="failed",
                score=20, max_score=100, test_count=5, passed_test_count=1,
                compiler_outcome="compile_error", error_codes=["pointer_indirection"],
            ),
        )
    service.project_knowledge(user_id=student.id, course_id=course.id, as_of=datetime.now(UTC))
    hypothesis = service.list_hypotheses(user_id=student.id, course_id=course.id)[0]
    decided = service.decide_hypothesis(user_id=student.id, hypothesis_id=hypothesis.hypothesis_id, decision="REJECTED")
    assert decided.status == "REJECTED"
    assert service.repository.count_hypothesis_history(hypothesis.hypothesis_id) == 2


def test_knowledge_http_contract_is_student_only_and_does_not_echo_raw_code():
    container = _container()
    client = TestClient(create_app())
    assert client.get("/api/v1/learner-state/taxonomy").status_code == 401
    student = container.user_repository.get_user_by_username("student_demo")
    course = container.course_repository.create_course(
        name="C language", owner_user_id=student.id, status="active"
    )
    container.knowledge_service.map_exercise(
        course_id=course.id, exercise_id="ex-http", knowledge_component_code="c.variables"
    )
    headers = _login(client, "student_demo")
    taxonomy = client.get("/api/v1/learner-state/taxonomy", headers=headers)
    assert taxonomy.status_code == 200 and len(taxonomy.json()) == 39
    payload = {
        "client_attempt_id": "http-1", "course_id": course.id, "exercise_id": "ex-http",
        "occurred_at": datetime.now(UTC).isoformat(), "result_type": "failed", "score": 0,
        "max_score": 100, "test_count": 1, "passed_test_count": 0,
        "compiler_outcome": "compile_error", "error_codes": ["compile_syntax"],
        "source_code": "RAW_MUST_NOT_BE_ECHOED",
    }
    rejected = client.post("/api/v1/practice/attempts", json=payload, headers=headers)
    assert rejected.status_code == 422
    assert "RAW_MUST_NOT_BE_ECHOED" not in rejected.text
    payload.pop("source_code")
    created = client.post("/api/v1/practice/attempts", json=payload, headers=headers)
    assert created.status_code == 200
    states = client.get(
        f"/api/v1/learner-state/knowledge?course_id={course.id}", headers=headers
    )
    assert states.status_code == 200
    assert all("source_code" not in item and "payload" not in item for item in states.json())
    assert all(item["value"]["evidence_sufficiency"] == "INSUFFICIENT_EVIDENCE" for item in states.json())
    assert client.get("/api/v1/learner-state/taxonomy", headers=_login(client, "admin_demo")).status_code == 403
