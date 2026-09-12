from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.database.sqlite_db import Database
from app.repositories.c_knowledge_repository import KnowledgeRepository
from app.repositories.learner_event_repository import LearnerEventRepository
from app.repositories.learner_state_repository import LearnerStateRepository
from app.schemas.c_knowledge import PracticeAttemptCreate
from app.services.c_knowledge_service import KnowledgeService
from app.services.learner_state_service import (
    LearnerStateProjectionService,
    PREDICTION_ESTIMATOR_VERSION,
)


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


def _make_state_service(db: Database) -> LearnerStateProjectionService:
    state_repo = LearnerStateRepository(db)
    knowledge_repo = KnowledgeRepository(db)
    event_repo = LearnerEventRepository(db)
    service = LearnerStateProjectionService(
        state_repo, knowledge_repository=knowledge_repo,
    )
    return service


def _make_knowledge_service(db: Database) -> KnowledgeService:
    repo = KnowledgeRepository(db)
    event_repo = LearnerEventRepository(db)
    state_repo = LearnerStateRepository(db)
    service = KnowledgeService(repo, event_repo, state_repo)
    service.seed_c_taxonomy()
    return service


def _setup_course(db: Database, ks: KnowledgeService, user_id: str = "user1"):
    _add_course(db, "course_c", user_id)
    ks.map_exercise(
        course_id="course_c", exercise_id="ex_1",
        knowledge_component_code="c.pointer.basics", mapping_confidence=1.0,
    )


def _valid_attempt(**overrides) -> dict:
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


def test_prediction_estimator_version():
    assert PREDICTION_ESTIMATOR_VERSION == "prediction-linear-v1"


def test_prediction_returns_empty_when_no_evidence():
    db = _make_db()
    _add_user(db, "user1")

    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    svc = _make_state_service(db)
    result = svc.project_prediction(
        "user1", course_id="course_c", as_of=_now(), trigger="test",
    )
    assert result.estimator_version == PREDICTION_ESTIMATOR_VERSION
    assert len(result.snapshots) == 0
    assert "no_prediction_evidence" in result.warnings


def test_prediction_generates_three_snapshots_per_kc():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    for i in range(4):
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=30 + i * 15,
            passed_test_count=1 + i,
            occurred_at=now - timedelta(days=4 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    svc = _make_state_service(db)
    result = svc.project_prediction(
        "user1", course_id="course_c", as_of=now, trigger="test",
    )
    state_types = {s.state_type for s in result.snapshots}
    assert "knowledge_mastery_forecast" in state_types
    assert "performance_prediction" in state_types
    assert "learning_velocity" in state_types


def test_prediction_is_idempotent():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    for i in range(3):
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=40 + i * 20,
            passed_test_count=2 + i,
            occurred_at=now - timedelta(days=3 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    svc = _make_state_service(db)
    r1 = svc.project_prediction("user1", course_id="course_c", as_of=now, trigger="test")
    r2 = svc.project_prediction("user1", course_id="course_c", as_of=now, trigger="test")
    assert r1.run_id == r2.run_id
    assert len(r1.snapshots) == len(r2.snapshots)


def test_prediction_forecast_values_within_bounds():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    for i in range(4):
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=20 + i * 20,
            passed_test_count=1 + i,
            occurred_at=now - timedelta(days=4 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    svc = _make_state_service(db)
    result = svc.project_prediction("user1", course_id="course_c", as_of=now, trigger="test")
    for snap in result.snapshots:
        if snap.state_type == "knowledge_mastery_forecast":
            assert 0.0 <= snap.value["forecast_7d"] <= 1.0
            assert 0.0 <= snap.value["forecast_30d"] <= 1.0
            assert 0.0 <= snap.value["current_estimate"] <= 1.0


def test_prediction_performance_band_is_valid():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    for i in range(4):
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=50 + i * 10,
            passed_test_count=2 + i,
            result_type="partial",
            compiler_outcome="runtime_error",
            error_codes=[],
            occurred_at=now - timedelta(days=4 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    svc = _make_state_service(db)
    result = svc.project_prediction("user1", course_id="course_c", as_of=now, trigger="test")
    for snap in result.snapshots:
        if snap.state_type == "performance_prediction":
            assert snap.value["predicted_score_band"] in {
                "likely_fail", "likely_partial", "likely_pass", "insufficient_evidence",
            }
            assert 0.0 <= snap.value["predicted_pass_probability"] <= 1.0


def test_prediction_velocity_trend_is_valid():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    for i in range(4):
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=20 + i * 20,
            passed_test_count=1 + i,
            occurred_at=now - timedelta(days=4 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    svc = _make_state_service(db)
    result = svc.project_prediction("user1", course_id="course_c", as_of=now, trigger="test")
    for snap in result.snapshots:
        if snap.state_type == "learning_velocity":
            assert snap.value["trend"] in {
                "accelerating", "steady", "decelerating", "insufficient_evidence",
            }
            assert 0.0 <= snap.value["consistency"] <= 1.0


def test_prediction_forecast_trend_is_valid():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    for i in range(4):
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=30 + i * 15,
            passed_test_count=1 + i,
            occurred_at=now - timedelta(days=4 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    svc = _make_state_service(db)
    result = svc.project_prediction("user1", course_id="course_c", as_of=now, trigger="test")
    for snap in result.snapshots:
        if snap.state_type == "knowledge_mastery_forecast":
            assert snap.value["trend"] in {
                "improving", "steady", "declining", "insufficient_evidence",
            }


def test_prediction_data_quality_unavailable_when_no_knowledge():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    attempt = PracticeAttemptCreate(**_valid_attempt(
        client_attempt_id="att_1", score=0, occurred_at=now,
    ))
    ks.record_practice_attempt(user_id="user1", attempt=attempt)
    svc = _make_state_service(db)
    result = svc.project_prediction("user1", course_id="course_c", as_of=now, trigger="test")
    for snap in result.snapshots:
        assert snap.data_quality in {"partial", "unavailable"}


def test_prediction_confidence_capped_at_0_6():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    for i in range(10):
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=50 + i * 5,
            passed_test_count=min(2 + i // 2, 5),
            occurred_at=now - timedelta(days=10 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    svc = _make_state_service(db)
    result = svc.project_prediction("user1", course_id="course_c", as_of=now, trigger="test")
    for snap in result.snapshots:
        assert snap.confidence <= 0.6 + 1e-9


def test_prediction_scope_is_knowledge_component():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    for i in range(3):
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=40 + i * 20,
            passed_test_count=2 + i,
            occurred_at=now - timedelta(days=3 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    svc = _make_state_service(db)
    result = svc.project_prediction("user1", course_id="course_c", as_of=now, trigger="test")
    for snap in result.snapshots:
        assert snap.scope_type == "KNOWLEDGE_COMPONENT"
    pointer_snaps = [s for s in result.snapshots if s.scope_id == "c.pointer.basics"]
    assert len(pointer_snaps) >= 3


def test_prediction_persisted_to_repository():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    for i in range(4):
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=30 + i * 15,
            passed_test_count=1 + i,
            occurred_at=now - timedelta(days=4 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    svc = _make_state_service(db)
    svc.project_prediction("user1", course_id="course_c", as_of=now, trigger="test")
    state_repo = LearnerStateRepository(db)
    snapshots, total = state_repo.list_snapshots(
        user_id="user1", page=1, page_size=50,
        scope_type=None, state_type=None, course_id=None,
        projection_kind="PREDICTION", projection_scope="course_c",
    )
    prediction_snaps = [s for s in snapshots if s.state_type in {
        "knowledge_mastery_forecast", "performance_prediction", "learning_velocity",
    }]
    assert len(prediction_snaps) >= 3


def test_prediction_cross_user_isolation():
    db = _make_db()
    _add_user(db, "user1")
    _add_user(db, "user2")
    _add_course(db, "course_c", "user1")
    _add_course(db, "course_c2", "user2")
    ks = _make_knowledge_service(db)
    ks.map_exercise(course_id="course_c", exercise_id="ex_1",
                    knowledge_component_code="c.pointer.basics", mapping_confidence=1.0)
    ks.map_exercise(course_id="course_c2", exercise_id="ex_1",
                    knowledge_component_code="c.pointer.basics", mapping_confidence=1.0)
    now = _now()
    for i in range(3):
        a1 = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"u1_att_{i}",
            score=40 + i * 20, passed_test_count=2 + i,
            occurred_at=now - timedelta(days=3 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=a1)
        a2 = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"u2_att_{i}",
            course_id="course_c2",
            score=20 + i * 10, passed_test_count=1 + i,
            occurred_at=now - timedelta(days=3 - i),
        ))
        ks.record_practice_attempt(user_id="user2", attempt=a2)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    ks.project_knowledge(user_id="user2", course_id="course_c2", as_of=now, trigger="test")
    svc = _make_state_service(db)
    r1 = svc.project_prediction("user1", course_id="course_c", as_of=now, trigger="test")
    r2 = svc.project_prediction("user2", course_id="course_c2", as_of=now, trigger="test")
    assert r1.run_id != r2.run_id
    r1_pointer = [s for s in r1.snapshots if s.scope_id == "c.pointer.basics"]
    r2_pointer = [s for s in r2.snapshots if s.scope_id == "c.pointer.basics"]
    assert len(r1_pointer) >= 3
    assert len(r2_pointer) >= 3


def test_prediction_improving_trend_when_scores_rise():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    for i in range(6):
        is_pass = i >= 4
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=100 if is_pass else 10 + i * 15,
            passed_test_count=5 if is_pass else i,
            result_type="passed" if is_pass else "failed",
            compiler_outcome="success" if is_pass else "compile_error",
            error_codes=[] if is_pass else ["pointer_indirection"],
            occurred_at=now - timedelta(days=6 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    svc = _make_state_service(db)
    result = svc.project_prediction("user1", course_id="course_c", as_of=now, trigger="test")
    forecasts = [s for s in result.snapshots if s.state_type == "knowledge_mastery_forecast" and s.scope_id == "c.pointer.basics"]
    assert len(forecasts) >= 1
    assert forecasts[0].value["trend"] in {"improving", "steady"}


def test_prediction_explanation_codes_present():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    for i in range(4):
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=30 + i * 15,
            passed_test_count=1 + i,
            occurred_at=now - timedelta(days=4 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    svc = _make_state_service(db)
    result = svc.project_prediction("user1", course_id="course_c", as_of=now, trigger="test")
    for snap in result.snapshots:
        assert len(snap.value["explanation_codes"]) >= 1


def test_prediction_valid_until_in_future():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    for i in range(3):
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=40 + i * 20,
            passed_test_count=2 + i,
            occurred_at=now - timedelta(days=3 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    svc = _make_state_service(db)
    result = svc.project_prediction("user1", course_id="course_c", as_of=now, trigger="test")
    for snap in result.snapshots:
        assert snap.valid_until is not None
        assert snap.valid_until > snap.computed_at


def test_prediction_does_not_accept_source_code():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        PracticeAttemptCreate(**_valid_attempt(source_code="int main() { return 0; }"))


def test_prediction_no_psychological_terms_in_output():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    for i in range(4):
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=30 + i * 15,
            passed_test_count=1 + i,
            occurred_at=now - timedelta(days=4 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    svc = _make_state_service(db)
    result = svc.project_prediction("user1", course_id="course_c", as_of=now, trigger="test")
    for snap in result.snapshots:
        payload_str = str(snap.value)
        for term in ["焦虑", "抑郁", "厌学", "人格", "lazy", "stupid"]:
            assert term not in payload_str.lower()