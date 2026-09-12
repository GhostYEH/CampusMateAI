from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.database.sqlite_db import Database
from app.repositories.learner_state_repository import LearnerStateRepository
from app.repositories.learner_event_repository import LearnerEventRepository
from app.services.learner_state_service import LearnerStateProjectionService, ACADEMIC_ESTIMATOR_VERSION


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


def _make_service(db: Database, edu_data_repository=None, source_policy=None) -> LearnerStateProjectionService:
    repo = LearnerStateRepository(db)
    event_repo = LearnerEventRepository(db)
    return LearnerStateProjectionService(
        repo, edu_data_repository=edu_data_repository,
        learner_event_repository=event_repo, source_policy=source_policy,
    )


def _insert_edu_schedule_item(db, user_id, item_id, semester="2024-2025-1", course_code="CS101", credit=3.0, weekday=1):
    now = _now().isoformat()
    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO edu_schedule_items (
                id, user_id, university_id, semester, course_code, course_name,
                credit, weekday, source, source_hash, last_seen_at, sync_batch_id,
                is_stale, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (item_id, user_id, "uni1", semester, course_code, "Course",
             credit, weekday, "edu", "hash", now, "batch1", 0, now, now),
        )


def _insert_edu_grade_item(db, user_id, item_id, semester="2024-2025-1", course_code="CS101", credit=3.0, score="85"):
    now = _now().isoformat()
    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO edu_grades (
                id, user_id, university_id, semester, course_code, course_name,
                credit, score, category, status, is_stale, last_seen_at, sync_batch_id,
                source_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (item_id, user_id, "uni1", semester, course_code, "Course",
             credit, score, "exam", "active", 0, now, "batch1", "hash", now, now),
        )


def _insert_edu_exam_item(db, user_id, item_id, semester="2024-2025-1", course_code="CS101", starts_at=None):
    now = _now().isoformat()
    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO edu_exam_items (
                id, user_id, university_id, semester, course_code, course_name,
                exam_type, starts_at, is_stale, last_seen_at, sync_batch_id,
                source_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (item_id, user_id, "uni1", semester, course_code, "Course",
             "final", starts_at, 0, now, "batch1", "hash", now, now),
        )


def test_academic_projection_creates_six_snapshots():
    db = _make_db()
    _add_user(db, "user1")
    _insert_edu_schedule_item(db, "user1", "sch1")
    _insert_edu_schedule_item(db, "user1", "sch2", course_code="CS102")
    _insert_edu_grade_item(db, "user1", "g1", score="85")
    _insert_edu_grade_item(db, "user1", "g2", course_code="CS102", score="92")
    future = (_now() + timedelta(days=5)).isoformat()
    _insert_edu_exam_item(db, "user1", "ex1", starts_at=future)
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo)
    result = service.project_academic("user1", as_of=_now())
    state_types = {s.state_type for s in result.snapshots}
    assert "academic_course_load" in state_types
    assert "grade_observation" in state_types
    assert "credit_progress" in state_types
    assert "exam_exposure" in state_types
    assert "schedule_load" in state_types
    assert "goal_state" in state_types
    assert len(result.snapshots) == 6


def test_academic_projection_unavailable_when_no_edu_data():
    db = _make_db()
    _add_user(db, "user1")
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo)
    result = service.project_academic("user1", as_of=_now())
    for snap in result.snapshots:
        assert snap.data_quality == "unavailable"
        assert snap.confidence == 0.0


def test_academic_projection_idempotent():
    db = _make_db()
    _add_user(db, "user1")
    _insert_edu_schedule_item(db, "user1", "sch1")
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo)
    now = _now()
    r1 = service.project_academic("user1", as_of=now)
    r2 = service.project_academic("user1", as_of=now)
    assert r1.run_id == r2.run_id


def test_academic_projection_cross_user_isolation():
    db = _make_db()
    _add_user(db, "user1")
    _add_user(db, "user2")
    _insert_edu_schedule_item(db, "user1", "sch1")
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo)
    r1 = service.project_academic("user1", as_of=_now())
    r2 = service.project_academic("user2", as_of=_now())
    assert r1.run_id != r2.run_id
    for snap in r2.snapshots:
        assert snap.data_quality == "unavailable"


def test_academic_projection_estimator_version():
    db = _make_db()
    _add_user(db, "user1")
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo)
    result = service.project_academic("user1", as_of=_now())
    assert result.estimator_version == ACADEMIC_ESTIMATOR_VERSION


def test_academic_course_load_value_correctness():
    db = _make_db()
    _add_user(db, "user1")
    _insert_edu_schedule_item(db, "user1", "sch1", credit=3.0)
    _insert_edu_schedule_item(db, "user1", "sch2", course_code="CS102", credit=2.0)
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo)
    result = service.project_academic("user1", as_of=_now())
    course_load = next(s for s in result.snapshots if s.state_type == "academic_course_load")
    assert course_load.value["current_semester_course_count"] == 2
    assert course_load.value["effective_credit_load"] == 5.0
    assert course_load.value["data_completeness"] == "verified"


def test_grade_observation_value_correctness():
    db = _make_db()
    _add_user(db, "user1")
    _insert_edu_grade_item(db, "user1", "g1", score="85")
    _insert_edu_grade_item(db, "user1", "g2", course_code="CS102", score="92")
    _insert_edu_grade_item(db, "user1", "g3", course_code="CS103", score="55")
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo)
    result = service.project_academic("user1", as_of=_now())
    grade_obs = next(s for s in result.snapshots if s.state_type == "grade_observation")
    assert grade_obs.value["observed_grade_count"] == 3
    assert grade_obs.value["has_observed_grades"] is True
    assert grade_obs.value["score_band_distribution"]["80_89"] == 1
    assert grade_obs.value["score_band_distribution"]["90_100"] == 1
    assert grade_obs.value["score_band_distribution"]["0_59"] == 1


def test_credit_progress_does_not_fabricate_total():
    db = _make_db()
    _add_user(db, "user1")
    _insert_edu_grade_item(db, "user1", "g1", credit=3.0)
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo)
    result = service.project_academic("user1", as_of=_now())
    credit = next(s for s in result.snapshots if s.state_type == "credit_progress")
    assert credit.value["total_required_credits"] is None
    assert "total_required_credits_unknown" in credit.value["warning_codes"]


def test_exam_exposure_time_buckets():
    db = _make_db()
    _add_user(db, "user1")
    now = _now()
    _insert_edu_exam_item(db, "user1", "ex1", starts_at=(now + timedelta(days=3)).isoformat())
    _insert_edu_exam_item(db, "user1", "ex2", course_code="CS102", starts_at=(now + timedelta(days=20)).isoformat())
    _insert_edu_exam_item(db, "user1", "ex3", course_code="CS103", starts_at=None)
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo)
    result = service.project_academic("user1", as_of=now)
    exam = next(s for s in result.snapshots if s.state_type == "exam_exposure")
    assert exam.value["upcoming_exam_count"] == 2
    assert exam.value["unknown_time_exam_count"] == 1
    assert exam.value["time_bucket_distribution"]["within_7d"] == 1
    assert exam.value["time_bucket_distribution"]["within_30d"] == 1


def test_schedule_load_value_correctness():
    db = _make_db()
    _add_user(db, "user1")
    _insert_edu_schedule_item(db, "user1", "sch1")
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo)
    result = service.project_academic("user1", as_of=_now())
    load = next(s for s in result.snapshots if s.state_type == "schedule_load")
    assert load.value["future_7d_course_density"] > 0
    assert load.value["density_description"] == "observed"


def test_goal_state_unavailable_without_self_reports():
    db = _make_db()
    _add_user(db, "user1")
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo)
    result = service.project_academic("user1", as_of=_now())
    goal = next(s for s in result.snapshots if s.state_type == "goal_state")
    assert goal.data_quality == "unavailable"
    assert goal.value["active_daily_goals"] == 0


def test_academic_projection_no_value_judgments():
    db = _make_db()
    _add_user(db, "user1")
    _insert_edu_grade_item(db, "user1", "g1", score="55")
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo)
    result = service.project_academic("user1", as_of=_now())
    grade_obs = next(s for s in result.snapshots if s.state_type == "grade_observation")
    value_str = str(grade_obs.value)
    assert "优秀" not in value_str
    assert "差" not in value_str
    assert "能力" not in value_str
    assert "挂科" not in value_str


def test_academic_projection_evidence_safe_structure():
    db = _make_db()
    _add_user(db, "user1")
    _insert_edu_schedule_item(db, "user1", "sch1")
    _insert_edu_grade_item(db, "user1", "g1")
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo)
    result = service.project_academic("user1", as_of=_now())
    repo = service.repository
    for snap in result.snapshots:
        evidence_rows, _ = repo.list_evidence(
            user_id="user1", snapshot_id=snap.snapshot_id,
            page=1, page_size=10, projection_kind="ACADEMIC", projection_scope="__user__",
        )
        for ev in evidence_rows:
            assert ev.source_category in (
                "edu_schedule", "edu_grade", "edu_exam", "unknown",
            )
            assert ev.explanation_code in (
                "edu_schedule_observed", "edu_grade_observed", "edu_exam_observed",
                "state_observed", "academic_data_unavailable",
            )


def test_academic_projection_with_paused_source():
    class MockPolicy:
        def get_paused_sources(self, *, user_id):
            return {"EDU"}
        def get_projection_warning(self, *, user_id):
            return "learner_data_source_paused"
    db = _make_db()
    _add_user(db, "user1")
    _insert_edu_schedule_item(db, "user1", "sch1")
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo, source_policy=MockPolicy())
    result = service.project_academic("user1", as_of=_now())
    assert "learner_data_source_paused" in result.warnings


def test_academic_projection_new_data_triggers_recompute():
    db = _make_db()
    _add_user(db, "user1")
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo)
    now = _now()
    r1 = service.project_academic("user1", as_of=now)
    _insert_edu_schedule_item(db, "user1", "sch1")
    r2 = service.project_academic("user1", as_of=now + timedelta(seconds=1))
    assert r1.run_id != r2.run_id


def test_academic_projection_saves_to_repository():
    db = _make_db()
    _add_user(db, "user1")
    _insert_edu_schedule_item(db, "user1", "sch1")
    from app.repositories.edu_data_repository import EduDataRepository
    edu_repo = EduDataRepository(db)
    service = _make_service(db, edu_data_repository=edu_repo)
    result = service.project_academic("user1", as_of=_now())
    current = service.repository.get_current_run(
        user_id="user1", projection_kind="ACADEMIC", projection_scope="__user__"
    )
    assert current is not None
    assert current.run_id == result.run_id
    assert current.projection_kind == "ACADEMIC"