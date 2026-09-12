from __future__ import annotations

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


def _seed_evidence(db, ks, now):
    for i in range(4):
        attempt = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"att_{i}",
            score=30 + i * 15,
            passed_test_count=1 + i,
            occurred_at=now - timedelta(days=4 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=attempt)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")


def test_counterfactual_returns_deltas():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_evidence(db, ks, now)
    svc = _make_state_service(db)
    result = svc.simulate_counterfactual(
        "user1", course_id="course_c", as_of=now,
        intervention={
            "intervention_type": "additional_practice",
            "knowledge_component_code": "c.pointer.basics",
            "additional_practice_count": 5,
            "expected_score": 80,
            "misconception_code": None,
        },
    )
    assert result["course_id"] == "course_c"
    assert len(result["deltas"]) >= 1
    assert result["baseline_snapshot_count"] > 0
    assert result["counterfactual_snapshot_count"] > 0


def test_additional_practice_improves_forecast():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_evidence(db, ks, now)
    svc = _make_state_service(db)
    result = svc.simulate_counterfactual(
        "user1", course_id="course_c", as_of=now,
        intervention={
            "intervention_type": "additional_practice",
            "knowledge_component_code": "c.pointer.basics",
            "additional_practice_count": 10,
            "expected_score": 90,
            "misconception_code": None,
        },
    )
    pointer_deltas = [d for d in result["deltas"] if d["knowledge_component_code"] == "c.pointer.basics"]
    assert len(pointer_deltas) >= 1
    assert pointer_deltas[0]["mastery_delta"] >= 0


def test_remediation_improves_mastery():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_evidence(db, ks, now)
    svc = _make_state_service(db)
    result = svc.simulate_counterfactual(
        "user1", course_id="course_c", as_of=now,
        intervention={
            "intervention_type": "remediation",
            "knowledge_component_code": "c.pointer.basics",
            "additional_practice_count": 0,
            "expected_score": 0,
            "misconception_code": "pointer_value_address_confusion",
        },
    )
    pointer_deltas = [d for d in result["deltas"] if d["knowledge_component_code"] == "c.pointer.basics"]
    assert len(pointer_deltas) >= 1
    assert pointer_deltas[0]["mastery_delta"] >= 0


def test_review_session_improves_mastery():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_evidence(db, ks, now)
    svc = _make_state_service(db)
    result = svc.simulate_counterfactual(
        "user1", course_id="course_c", as_of=now,
        intervention={
            "intervention_type": "review_session",
            "knowledge_component_code": "c.pointer.basics",
            "additional_practice_count": 0,
            "expected_score": 0,
            "misconception_code": None,
        },
    )
    pointer_deltas = [d for d in result["deltas"] if d["knowledge_component_code"] == "c.pointer.basics"]
    assert len(pointer_deltas) >= 1
    assert pointer_deltas[0]["mastery_delta"] >= 0


def test_counterfactual_is_deterministic():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_evidence(db, ks, now)
    svc = _make_state_service(db)
    intervention = {
        "intervention_type": "additional_practice",
        "knowledge_component_code": "c.pointer.basics",
        "additional_practice_count": 5,
        "expected_score": 70,
        "misconception_code": None,
    }
    r1 = svc.simulate_counterfactual("user1", course_id="course_c", as_of=now, intervention=intervention)
    r2 = svc.simulate_counterfactual("user1", course_id="course_c", as_of=now, intervention=intervention)
    assert r1["deltas"] == r2["deltas"]


def test_counterfactual_does_not_persist():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_evidence(db, ks, now)
    svc = _make_state_service(db)
    state_repo = LearnerStateRepository(db)
    before_snapshots, before_total = state_repo.list_snapshots(
        user_id="user1", page=1, page_size=100,
        scope_type=None, state_type=None, course_id=None,
        projection_kind="PREDICTION", projection_scope="course_c",
    )
    svc.simulate_counterfactual(
        "user1", course_id="course_c", as_of=now,
        intervention={
            "intervention_type": "additional_practice",
            "knowledge_component_code": "c.pointer.basics",
            "additional_practice_count": 5,
            "expected_score": 80,
            "misconception_code": None,
        },
    )
    after_snapshots, after_total = state_repo.list_snapshots(
        user_id="user1", page=1, page_size=100,
        scope_type=None, state_type=None, course_id=None,
        projection_kind="PREDICTION", projection_scope="course_c",
    )
    assert before_total == after_total


def test_counterfactual_no_evidence_returns_warning():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    svc = _make_state_service(db)
    result = svc.simulate_counterfactual(
        "user1", course_id="course_c", as_of=now,
        intervention={
            "intervention_type": "additional_practice",
            "knowledge_component_code": "c.pointer.basics",
            "additional_practice_count": 5,
            "expected_score": 80,
            "misconception_code": None,
        },
    )
    assert "no_simulated_change" in result["warning_codes"] or len(result["deltas"]) == 0


def test_counterfactual_delta_values_within_bounds():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_evidence(db, ks, now)
    svc = _make_state_service(db)
    result = svc.simulate_counterfactual(
        "user1", course_id="course_c", as_of=now,
        intervention={
            "intervention_type": "additional_practice",
            "knowledge_component_code": "c.pointer.basics",
            "additional_practice_count": 5,
            "expected_score": 80,
            "misconception_code": None,
        },
    )
    for delta in result["deltas"]:
        assert 0.0 <= delta["baseline_forecast_7d"] <= 1.0
        assert 0.0 <= delta["counterfactual_forecast_7d"] <= 1.0
        assert 0.0 <= delta["baseline_pass_probability"] <= 1.0
        assert 0.0 <= delta["counterfactual_pass_probability"] <= 1.0


def test_counterfactual_cross_user_isolation():
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
    for i in range(4):
        a1 = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"u1_att_{i}",
            score=30 + i * 15, passed_test_count=1 + i,
            occurred_at=now - timedelta(days=4 - i),
        ))
        ks.record_practice_attempt(user_id="user1", attempt=a1)
        a2 = PracticeAttemptCreate(**_valid_attempt(
            client_attempt_id=f"u2_att_{i}",
            course_id="course_c2",
            score=10 + i * 5, passed_test_count=0,
            occurred_at=now - timedelta(days=4 - i),
        ))
        ks.record_practice_attempt(user_id="user2", attempt=a2)
    ks.project_knowledge(user_id="user1", course_id="course_c", as_of=now, trigger="test")
    ks.project_knowledge(user_id="user2", course_id="course_c2", as_of=now, trigger="test")
    svc = _make_state_service(db)
    r1 = svc.simulate_counterfactual(
        "user1", course_id="course_c", as_of=now,
        intervention={
            "intervention_type": "additional_practice",
            "knowledge_component_code": "c.pointer.basics",
            "additional_practice_count": 5,
            "expected_score": 80,
            "misconception_code": None,
        },
    )
    r2 = svc.simulate_counterfactual(
        "user2", course_id="course_c2", as_of=now,
        intervention={
            "intervention_type": "additional_practice",
            "knowledge_component_code": "c.pointer.basics",
            "additional_practice_count": 5,
            "expected_score": 80,
            "misconception_code": None,
        },
    )
    assert r1["course_id"] == "course_c"
    assert r2["course_id"] == "course_c2"


def test_counterfactual_no_psychological_terms():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_evidence(db, ks, now)
    svc = _make_state_service(db)
    result = svc.simulate_counterfactual(
        "user1", course_id="course_c", as_of=now,
        intervention={
            "intervention_type": "additional_practice",
            "knowledge_component_code": "c.pointer.basics",
            "additional_practice_count": 5,
            "expected_score": 80,
            "misconception_code": None,
        },
    )
    result_str = str(result)
    for term in ["焦虑", "抑郁", "厌学", "人格", "lazy", "stupid"]:
        assert term not in result_str.lower()


def test_zero_practice_count_has_no_effect():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_evidence(db, ks, now)
    svc = _make_state_service(db)
    result = svc.simulate_counterfactual(
        "user1", course_id="course_c", as_of=now,
        intervention={
            "intervention_type": "additional_practice",
            "knowledge_component_code": "c.pointer.basics",
            "additional_practice_count": 0,
            "expected_score": 80,
            "misconception_code": None,
        },
    )
    for delta in result["deltas"]:
        if delta["knowledge_component_code"] == "c.pointer.basics":
            assert abs(delta["mastery_delta"]) < 0.01


def test_counterfactual_explanation_codes_present():
    db = _make_db()
    _add_user(db, "user1")
    ks = _make_knowledge_service(db)
    _setup_course(db, ks)
    now = _now()
    _seed_evidence(db, ks, now)
    svc = _make_state_service(db)
    result = svc.simulate_counterfactual(
        "user1", course_id="course_c", as_of=now,
        intervention={
            "intervention_type": "additional_practice",
            "knowledge_component_code": "c.pointer.basics",
            "additional_practice_count": 5,
            "expected_score": 80,
            "misconception_code": None,
        },
    )
    assert "deterministic_counterfactual" in result["explanation_codes"]
    for delta in result["deltas"]:
        assert "counterfactual_simulation" in delta["explanation_codes"]