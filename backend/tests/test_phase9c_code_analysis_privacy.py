from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.database.sqlite_db import Database
from app.repositories.c_knowledge_repository import KnowledgeRepository
from app.repositories.learner_event_repository import LearnerEventRepository
from app.repositories.learner_state_repository import LearnerStateRepository
from app.schemas.c_knowledge import PracticeAttemptCreate
from app.services.c_knowledge_service import KnowledgeService, ERROR_TO_HYPOTHESIS, MIN_EVIDENCE_COUNT


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _make_db() -> Database:
    return Database(None)


def _add_user(db: Database, user_id: str = "user1") -> None:
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, user_id, "hash", "now", "now"),
        )


def _add_course(db: Database, course_id: str = "course_c", user_id: str = "user1") -> None:
    now = _now().isoformat()
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO courses (id, name, owner_user_id, provider, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (course_id, "C Course", user_id, "manual", "active", now, now),
        )


def _make_service(db: Database) -> KnowledgeService:
    repo = KnowledgeRepository(db)
    event_repo = LearnerEventRepository(db)
    state_repo = LearnerStateRepository(db)
    service = KnowledgeService(repo, event_repo, state_repo)
    service.seed_c_taxonomy()
    return service


def _valid_attempt_dict(**overrides) -> dict:
    data = {
        "client_attempt_id": "att_1",
        "course_id": "course_c",
        "exercise_id": "ex_1",
        "occurred_at": _now(),
        "attempt_no": 1,
        "result_type": "failed",
        "score": 0,
        "max_score": 100,
        "total_test_count": 5,
        "passed_test_count": 2,
        "compiler_outcome": "compile_error",
        "error_codes": ["pointer_indirection"],
        "evidence_quality": "partial",
    }
    data.update(overrides)
    return data


def _setup_course_with_mapping(db: Database, service: KnowledgeService, user_id: str = "user1"):
    _add_course(db, "course_c", user_id)
    service.map_exercise(
        course_id="course_c", exercise_id="ex_1",
        knowledge_component_code="c.pointer.basics", mapping_confidence=1.0,
    )


def test_source_code_field_rejected():
    with pytest.raises(ValidationError):
        PracticeAttemptCreate(**_valid_attempt_dict(source_code="int main() { return 0; }"))


def test_prompt_field_rejected():
    with pytest.raises(ValidationError):
        PracticeAttemptCreate(**_valid_attempt_dict(prompt="Help me fix this code"))


def test_answer_field_rejected():
    with pytest.raises(ValidationError):
        PracticeAttemptCreate(**_valid_attempt_dict(answer="The correct answer is 42"))


def test_stdout_field_rejected():
    with pytest.raises(ValidationError):
        PracticeAttemptCreate(**_valid_attempt_dict(stdout="Program output here"))


def test_stderr_field_rejected():
    with pytest.raises(ValidationError):
        PracticeAttemptCreate(**_valid_attempt_dict(stderr="Segmentation fault"))


def test_compiler_output_field_rejected():
    with pytest.raises(ValidationError):
        PracticeAttemptCreate(**_valid_attempt_dict(compiler_output="error: expected ';'"))


def test_unknown_error_code_rejected():
    with pytest.raises(ValidationError) as exc_info:
        PracticeAttemptCreate(**_valid_attempt_dict(error_codes=["unknown_error_code"]))
    assert "unsupported" in str(exc_info.value).lower()


def test_canary_secret_not_in_database():
    CANARY = "SECRET_CANARY_TOKEN_12345"
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    _setup_course_with_mapping(db, service)
    with pytest.raises(ValidationError):
        PracticeAttemptCreate(**_valid_attempt_dict(source_code=CANARY))
    with db.query() as conn:
        for table in ["practice_attempts", "learner_events"]:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            for row in rows:
                assert CANARY not in str(dict(row))


def test_code_attempt_analyzed_event_has_no_source_code():
    SOURCE_SNIPPET = "int *p = NULL; *p = 42;"
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    _setup_course_with_mapping(db, service)
    attempt = PracticeAttemptCreate(**_valid_attempt_dict())
    result = service.record_practice_attempt(user_id="user1", attempt=attempt)
    event_repo = LearnerEventRepository(db)
    events, total = event_repo.list_for_user(
        user_id="user1", source="code_analysis", page=1, page_size=10
    )
    assert total == 1
    event = events[0]
    assert event.event_type == "code_attempt_analyzed"
    assert SOURCE_SNIPPET not in str(event.payload)
    assert SOURCE_SNIPPET not in str(event.evidence_reference)
    assert "source_code" not in str(event.payload)
    assert "code" not in event.payload
    assert "prompt" not in event.payload
    assert "answer" not in event.payload


def test_validation_error_does_not_leak_input():
    with pytest.raises(ValidationError) as exc_info:
        PracticeAttemptCreate(**_valid_attempt_dict(
            source_code="secret_source_code_here",
            prompt="secret_prompt_here",
        ))
    error_str = str(exc_info.value)
    assert "secret_source_code_here" not in error_str
    assert "secret_prompt_here" not in error_str


def test_error_code_white_list_enforced():
    allowed = {
        "pointer_indirection", "array_boundary", "loop_termination",
        "function_parameter", "dynamic_memory", "struct_member",
        "file_io", "type_conversion", "compile_syntax", "uninitialized_value",
    }
    for code in allowed:
        attempt = PracticeAttemptCreate(**_valid_attempt_dict(
            error_codes=[code],
            result_type="failed",
            compiler_outcome="compile_error",
        ))
        assert code in attempt.error_codes
    with pytest.raises(ValidationError):
        PracticeAttemptCreate(**_valid_attempt_dict(error_codes=["not_a_real_error_code"]))


def test_error_codes_must_be_unique():
    with pytest.raises(ValidationError):
        PracticeAttemptCreate(**_valid_attempt_dict(
            error_codes=["pointer_indirection", "pointer_indirection"],
        ))


def test_cross_user_isolation():
    db = _make_db()
    _add_user(db, "user1")
    _add_user(db, "user2")
    _add_course(db, "course_c", "user1")
    _add_course(db, "course_c2", "user2")
    service = _make_service(db)
    service.map_exercise(
        course_id="course_c", exercise_id="ex_1",
        knowledge_component_code="c.pointer.basics", mapping_confidence=1.0,
    )
    service.map_exercise(
        course_id="course_c2", exercise_id="ex_1",
        knowledge_component_code="c.pointer.basics", mapping_confidence=1.0,
    )
    attempt1 = PracticeAttemptCreate(**_valid_attempt_dict())
    service.record_practice_attempt(user_id="user1", attempt=attempt1)
    attempt2 = PracticeAttemptCreate(**_valid_attempt_dict(
        client_attempt_id="att_2", course_id="course_c2",
    ))
    service.record_practice_attempt(user_id="user2", attempt=attempt2)
    event_repo = LearnerEventRepository(db)
    _, total_u1 = event_repo.list_for_user(user_id="user1", source="code_analysis", page=1, page_size=10)
    _, total_u2 = event_repo.list_for_user(user_id="user2", source="code_analysis", page=1, page_size=10)
    assert total_u1 == 1
    assert total_u2 == 1


def test_retry_idempotency():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    _setup_course_with_mapping(db, service)
    attempt = PracticeAttemptCreate(**_valid_attempt_dict())
    result1 = service.record_practice_attempt(user_id="user1", attempt=attempt)
    attempt2 = PracticeAttemptCreate(**_valid_attempt_dict())
    result2 = service.record_practice_attempt(user_id="user1", attempt=attempt2)
    assert result1.attempt_id == result2.attempt_id
    event_repo = LearnerEventRepository(db)
    _, total = event_repo.list_for_user(user_id="user1", source="code_analysis", page=1, page_size=10)
    assert total == 1


def test_single_error_does_not_form_hypothesis():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    _setup_course_with_mapping(db, service)
    attempt = PracticeAttemptCreate(**_valid_attempt_dict(
        error_codes=["pointer_indirection"],
        result_type="failed",
        compiler_outcome="compile_error",
    ))
    service.record_practice_attempt(user_id="user1", attempt=attempt)
    hypotheses = service.repository.list_hypotheses(user_id="user1", course_id="course_c")
    open_hypotheses = [h for h in hypotheses if h.status == "OPEN"]
    assert len(open_hypotheses) == 0


def test_two_errors_at_different_times_form_open_hypothesis():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    _setup_course_with_mapping(db, service)
    now = _now()
    attempt1 = PracticeAttemptCreate(**_valid_attempt_dict(
        client_attempt_id="att_1",
        error_codes=["pointer_indirection"],
        result_type="failed",
        compiler_outcome="compile_error",
        occurred_at=now - timedelta(hours=2),
    ))
    service.record_practice_attempt(user_id="user1", attempt=attempt1)
    attempt2 = PracticeAttemptCreate(**_valid_attempt_dict(
        client_attempt_id="att_2",
        error_codes=["pointer_indirection"],
        result_type="failed",
        compiler_outcome="compile_error",
        occurred_at=now,
    ))
    service.record_practice_attempt(user_id="user1", attempt=attempt2)
    service.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    hypotheses = service.repository.list_hypotheses(user_id="user1", course_id="course_c")
    open_hypotheses = [h for h in hypotheses if h.status == "OPEN"]
    assert len(open_hypotheses) >= 1
    assert open_hypotheses[0].misconception_code == "pointer_value_address_confusion"


def test_correct_performance_resolves_hypothesis():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    _setup_course_with_mapping(db, service)
    now = _now()
    for i in range(2):
        attempt = PracticeAttemptCreate(**_valid_attempt_dict(
            client_attempt_id=f"att_fail_{i}",
            error_codes=["pointer_indirection"],
            result_type="failed",
            compiler_outcome="compile_error",
            occurred_at=now - timedelta(hours=3 - i),
        ))
        service.record_practice_attempt(user_id="user1", attempt=attempt)
    service.project_knowledge(user_id="user1", course_id="course_c", as_of=now - timedelta(hours=1), trigger="test")
    hypotheses = service.repository.list_hypotheses(user_id="user1", course_id="course_c")
    open_hypotheses = [h for h in hypotheses if h.status == "OPEN"]
    assert len(open_hypotheses) >= 1
    correct_attempt = PracticeAttemptCreate(**_valid_attempt_dict(
        client_attempt_id="att_correct",
        error_codes=[],
        result_type="passed",
        score=100,
        max_score=100,
        passed_test_count=5,
        total_test_count=5,
        compiler_outcome="success",
        occurred_at=now,
    ))
    service.record_practice_attempt(user_id="user1", attempt=correct_attempt)
    service.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    hypotheses = service.repository.list_hypotheses(user_id="user1", course_id="course_c")
    resolved = [h for h in hypotheses if h.status == "RESOLVED"]
    assert len(resolved) >= 1


def test_evidence_api_does_not_return_source_id():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    _setup_course_with_mapping(db, service)
    attempt = PracticeAttemptCreate(**_valid_attempt_dict())
    result = service.record_practice_attempt(user_id="user1", attempt=attempt)
    assert not hasattr(result, "source_code")
    assert not hasattr(result, "source_id")
    assert not hasattr(result, "prompt")
    assert not hasattr(result, "answer")
    assert not hasattr(result, "stdout")
    assert not hasattr(result, "stderr")


def test_payload_only_contains_controlled_fields():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    _setup_course_with_mapping(db, service)
    attempt = PracticeAttemptCreate(**_valid_attempt_dict(
        error_codes=["pointer_indirection", "array_boundary"],
    ))
    service.record_practice_attempt(user_id="user1", attempt=attempt)
    event_repo = LearnerEventRepository(db)
    events, _ = event_repo.list_for_user(user_id="user1", source="code_analysis", page=1, page_size=10)
    payload = events[0].payload
    allowed_keys = {
        "exercise_id", "correctness", "test_pass_band",
        "compiler_error_categories", "runtime_error_categories", "data_quality",
    }
    for key in payload:
        assert key in allowed_keys, f"unexpected payload key: {key}"


def test_delete_cascade_removes_events():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    _setup_course_with_mapping(db, service)
    attempt = PracticeAttemptCreate(**_valid_attempt_dict())
    service.record_practice_attempt(user_id="user1", attempt=attempt)
    event_repo = LearnerEventRepository(db)
    _, total_before = event_repo.list_for_user(user_id="user1", page=1, page_size=10)
    assert total_before >= 2
    deleted = event_repo.delete_for_user(user_id="user1")
    assert deleted >= 2
    _, total_after = event_repo.list_for_user(user_id="user1", page=1, page_size=10)
    assert total_after == 0


def test_min_evidence_count_is_two():
    assert MIN_EVIDENCE_COUNT == 2


def test_error_to_hypothesis_mapping_covers_key_codes():
    assert "pointer_indirection" in ERROR_TO_HYPOTHESIS
    assert "array_boundary" in ERROR_TO_HYPOTHESIS
    assert "loop_termination" in ERROR_TO_HYPOTHESIS
    assert "function_parameter" in ERROR_TO_HYPOTHESIS
    assert "dynamic_memory" in ERROR_TO_HYPOTHESIS
    assert "struct_member" in ERROR_TO_HYPOTHESIS
    assert "file_io" in ERROR_TO_HYPOTHESIS
    assert "type_conversion" in ERROR_TO_HYPOTHESIS


def test_code_attempt_analyzed_event_idempotent():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    _setup_course_with_mapping(db, service)
    attempt = PracticeAttemptCreate(**_valid_attempt_dict())
    service.record_practice_attempt(user_id="user1", attempt=attempt)
    attempt2 = PracticeAttemptCreate(**_valid_attempt_dict())
    service.record_practice_attempt(user_id="user1", attempt=attempt2)
    event_repo = LearnerEventRepository(db)
    events, total = event_repo.list_for_user(
        user_id="user1", source="code_analysis", page=1, page_size=10
    )
    assert total == 1


def test_no_psychological_diagnosis_in_payload():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    _setup_course_with_mapping(db, service)
    attempt = PracticeAttemptCreate(**_valid_attempt_dict())
    service.record_practice_attempt(user_id="user1", attempt=attempt)
    event_repo = LearnerEventRepository(db)
    events, _ = event_repo.list_for_user(user_id="user1", source="code_analysis", page=1, page_size=10)
    payload_str = str(events[0].payload)
    for term in ["焦虑", "抑郁", "厌学", "人格", "动机", "lazy", "stupid", "incapable"]:
        assert term not in payload_str.lower()