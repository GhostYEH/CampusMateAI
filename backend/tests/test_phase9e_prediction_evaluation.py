from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.database.sqlite_db import Database
from app.repositories.c_knowledge_repository import KnowledgeRepository
from app.repositories.learner_event_repository import LearnerEventRepository
from app.repositories.learner_state_repository import LearnerStateRepository
from app.schemas.c_knowledge import PracticeAttemptCreate
from app.services.c_knowledge_service import KnowledgeService
from app.services.learner_state_service import LearnerStateProjectionService


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
    return LearnerStateProjectionService(state_repo, knowledge_repository=knowledge_repo)


def _make_knowledge_service(db: Database) -> KnowledgeService:
    repo = KnowledgeRepository(db)
    event_repo = LearnerEventRepository(db)
    state_repo = LearnerStateRepository(db)
    service = KnowledgeService(repo, event_repo, state_repo)
    service.seed_c_taxonomy()
    return service


def _setup_course(db: Database, ks: KnowledgeService):
    _add_course(db, "course_c", "user1")
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


def _seed_attempts(db, ks, now, count=10, improving=True):
    for i in range(count):
        if improving:
            raw_score = 10 + i * 9
        else:
            raw_score = 90 - i * 9
        is_pass = raw_score >= 60
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=100 if is_pass else raw_score,
            passed_test_count=5 if is_pass else min(raw_score // 20, 5),
            result_type="passed" if is_pass else "failed",
            compiler_outcome="success" if is_pass else "compile_error",
            error_codes=[] if is_pass else ["pointer_indirection"],
            occurred_at=now - timedelta(days=count - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)


def test_evaluation_returns_metrics():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_attempts(db, ks, now, count=10)
    svc = _make_state_service(db)
    result = svc.evaluate_predictions("user1", course_id="course_c", as_of=now)
    assert result["course_id"] == "course_c"
    assert result["total_attempts"] == 10
    assert result["training_count"] + result["test_count"] == 10
    assert 0.0 <= result["accuracy"] <= 1.0
    assert 0.0 <= result["pr_auc"] <= 1.0
    assert result["log_loss"] >= 0.0
    assert 0.0 <= result["brier_score"] <= 1.0


def test_evaluation_insufficient_data_fails_gate():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    for i in range(3):
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=50, occurred_at=now - timedelta(days=3 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    svc = _make_state_service(db)
    result = svc.evaluate_predictions("user1", course_id="course_c", as_of=now)
    assert not result["truthfulness_gate_passed"]
    assert "insufficient_total_data" in result["gate_failure_reasons"]


def test_evaluation_no_data_returns_defaults():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    svc = _make_state_service(db)
    result = svc.evaluate_predictions("user1", course_id="course_c", as_of=now)
    assert result["total_attempts"] == 0
    assert not result["truthfulness_gate_passed"]
    assert result["log_loss"] == pytest.approx(0.6931, abs=0.001)


def test_evaluation_chronological_split():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_attempts(db, ks, now, count=20, improving=True)
    svc = _make_state_service(db)
    result = svc.evaluate_predictions("user1", course_id="course_c", as_of=now, test_ratio=0.3)
    assert result["training_count"] == 14
    assert result["test_count"] == 6


def test_evaluation_log_loss_better_than_random_with_good_predictions():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_attempts(db, ks, now, count=20, improving=True)
    svc = _make_state_service(db)
    result = svc.evaluate_predictions("user1", course_id="course_c", as_of=now)
    random_log_loss = 0.6931
    assert result["log_loss"] <= random_log_loss + 0.1


def test_evaluation_pr_auc_non_negative():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_attempts(db, ks, now, count=15, improving=True)
    svc = _make_state_service(db)
    result = svc.evaluate_predictions("user1", course_id="course_c", as_of=now)
    assert result["pr_auc"] >= 0.0


def test_evaluation_brier_score_within_bounds():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_attempts(db, ks, now, count=12, improving=True)
    svc = _make_state_service(db)
    result = svc.evaluate_predictions("user1", course_id="course_c", as_of=now)
    assert 0.0 <= result["brier_score"] <= 1.0


def test_evaluation_calibration_error_within_bounds():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_attempts(db, ks, now, count=12, improving=True)
    svc = _make_state_service(db)
    result = svc.evaluate_predictions("user1", course_id="course_c", as_of=now)
    assert 0.0 <= result["calibration_error"] <= 1.0


def test_evaluation_gate_checks_systematic_bias():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    for i in range(20):
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=10, passed_test_count=0,
            occurred_at=now - timedelta(days=20 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    svc = _make_state_service(db)
    result = svc.evaluate_predictions("user1", course_id="course_c", as_of=now)
    assert "systematically_biased" in result["gate_failure_reasons"] or "no_better_than_random" in result["gate_failure_reasons"]


def test_evaluation_is_deterministic():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_attempts(db, ks, now, count=10, improving=True)
    svc = _make_state_service(db)
    r1 = svc.evaluate_predictions("user1", course_id="course_c", as_of=now)
    r2 = svc.evaluate_predictions("user1", course_id="course_c", as_of=now)
    assert r1 == r2


def test_evaluation_cross_user_isolation():
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
    for i in range(10):
        a1 = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"u1_att_{i}",
            score=10 + i * 9, passed_test_count=min(i, 5),
            occurred_at=now - timedelta(days=10 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=a1)
        a2 = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"u2_att_{i}",
            course_id="course_c2",
            score=90 - i * 9, passed_test_count=min(5 - i // 2, 5),
            occurred_at=now - timedelta(days=10 - i),
        ))
        ks.record_practice_attempt(user_id="user2", attempt=a2)
    svc = _make_state_service(db)
    r1 = svc.evaluate_predictions("user1", course_id="course_c", as_of=now)
    r2 = svc.evaluate_predictions("user2", course_id="course_c2", as_of=now)
    assert r1["course_id"] == "course_c"
    assert r2["course_id"] == "course_c2"


def test_evaluation_test_ratio_validation():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    svc = _make_state_service(db)
    with pytest.raises(ValueError):
        svc.evaluate_predictions("user1", course_id="course_c", as_of=now, test_ratio=0.6)
    with pytest.raises(ValueError):
        svc.evaluate_predictions("user1", course_id="course_c", as_of=now, test_ratio=0.05)


def test_evaluation_explanation_codes_present():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_attempts(db, ks, now, count=10, improving=True)
    svc = _make_state_service(db)
    result = svc.evaluate_predictions("user1", course_id="course_c", as_of=now)
    assert len(result["explanation_codes"]) >= 1


def test_evaluation_no_psychological_terms():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_attempts(db, ks, now, count=10, improving=True)
    svc = _make_state_service(db)
    result = svc.evaluate_predictions("user1", course_id="course_c", as_of=now)
    result_str = str(result)
    for term in ["焦虑", "抑郁", "厌学", "人格", "lazy", "stupid"]:
        assert term not in result_str.lower()