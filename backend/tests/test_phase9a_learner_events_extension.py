from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.database.sqlite_db import Database
from app.repositories.learner_event_repository import LearnerEventRepository, LearnerEventConflict
from app.schemas.learner_event import LearnerEventCreate, SOURCE_EVENT_TYPES
from app.services.learner_event_service import LearnerEventService


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_db() -> Database:
    return Database(None)


def _add_user(db: Database, user_id: str = "user1") -> None:
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, user_id, "hash", "now", "now"),
        )


def _make_service(db: Database, source_policy=None) -> LearnerEventService:
    repo = LearnerEventRepository(db)
    return LearnerEventService(repo, source_policy=source_policy)


def test_new_sources_and_event_types_are_writable():
    assert "edu" in SOURCE_EVENT_TYPES
    assert "self_report" in SOURCE_EVENT_TYPES
    assert "ai_learning_feedback" in SOURCE_EVENT_TYPES
    assert "code_analysis" in SOURCE_EVENT_TYPES
    assert "edu_schedule_synced" in SOURCE_EVENT_TYPES["edu"]
    assert "edu_grade_observed" in SOURCE_EVENT_TYPES["edu"]
    assert "edu_exam_discovered" in SOURCE_EVENT_TYPES["edu"]
    assert "self_report_submitted" in SOURCE_EVENT_TYPES["self_report"]
    assert "ai_learning_feedback_recorded" in SOURCE_EVENT_TYPES["ai_learning_feedback"]
    assert "code_attempt_analyzed" in SOURCE_EVENT_TYPES["code_analysis"]
    assert "assignment_graded" in SOURCE_EVENT_TYPES["chaoxing"]
    assert "discussion_participated" in SOURCE_EVENT_TYPES["chaoxing"]
    assert "exam_discovered" in SOURCE_EVENT_TYPES["chaoxing"]


def test_edu_schedule_synced_event_success():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    result = service.record_edu_schedule_synced(
        user_id="user1",
        binding_id="binding_1",
        semester="2024-2025-1",
        scheduled_item_count=5,
        observed_at=now,
        sync_batch_id="batch_1",
    )
    assert result is not None
    assert result.created is True
    events, total = service.list_events(user_id="user1", page=1, page_size=10)
    assert total == 1
    assert events[0].source == "edu"
    assert events[0].event_type == "edu_schedule_synced"
    assert events[0].outcome == "synced"
    assert events[0].consent_scope == "connected_learning_platform"


def test_edu_schedule_synced_idempotent():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    r1 = service.record_edu_schedule_synced(
        user_id="user1",
        binding_id="binding_1",
        semester="2024-2025-1",
        scheduled_item_count=5,
        observed_at=now,
        sync_batch_id="batch_1",
    )
    r2 = service.record_edu_schedule_synced(
        user_id="user1",
        binding_id="binding_1",
        semester="2024-2025-1",
        scheduled_item_count=5,
        observed_at=now,
        sync_batch_id="batch_1",
    )
    assert r1 is not None and r2 is not None
    assert r1.event_id == r2.event_id
    assert r1.created is True and r2.created is False


def test_edu_grade_observed_event_success():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    result = service.record_edu_grade_observed(
        user_id="user1",
        binding_id="binding_1",
        semester="2024-2025-1",
        course_code="CS101",
        credit_value=3.0,
        score="85",
        assessment_category="exam",
        grade_id="grade_1",
        observed_at=now,
    )
    assert result is not None
    assert result.created is True
    events, total = service.list_events(user_id="user1", page=1, page_size=10)
    assert total == 1
    assert events[0].source == "edu"
    assert events[0].event_type == "edu_grade_observed"
    assert events[0].payload["normalized_score_band"] == "80_89"
    assert events[0].payload["credit_value"] == 3.0


def test_edu_exam_discovered_event_success():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    future = (now + timedelta(days=5)).isoformat()
    result = service.record_edu_exam_discovered(
        user_id="user1",
        binding_id="binding_1",
        semester="2024-2025-1",
        course_code="CS101",
        exam_id="exam_1",
        starts_at=future,
        observed_at=now,
    )
    assert result is not None
    assert result.created is True
    events, _ = service.list_events(user_id="user1", page=1, page_size=10)
    assert events[0].event_type == "edu_exam_discovered"
    assert events[0].payload["exam_time_bucket"] == "within_7d"


def test_self_report_submitted_event_success():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    result = service.record_self_report_submitted(
        user_id="user1",
        report_id="sr_1",
        report_kind="study_reflection",
        occurred_at=now,
        duration_minutes=30,
    )
    assert result is not None
    assert result.created is True
    events, _ = service.list_events(user_id="user1", page=1, page_size=10)
    assert events[0].source == "self_report"
    assert events[0].event_type == "self_report_submitted"
    assert events[0].consent_scope == "core_learning_record"


def test_ai_learning_feedback_recorded_event_success():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    result = service.record_ai_learning_feedback_recorded(
        user_id="user1",
        feedback_id="aifb_1",
        feedback_kind="concept_explanation",
        course_id="course_1",
        occurred_at=now,
    )
    assert result is not None
    assert result.created is True
    events, _ = service.list_events(user_id="user1", page=1, page_size=10)
    assert events[0].source == "ai_learning_feedback"
    assert events[0].event_type == "ai_learning_feedback_recorded"



def test_chaoxing_assignment_graded_event_success():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    result = service.record_chaoxing_assignment_graded(
        user_id="user1",
        task_id="task_1",
        course_id="course_1",
        score_band="80_89",
        observed_at=now,
    )
    assert result is not None
    assert result.created is True
    events, _ = service.list_events(user_id="user1", page=1, page_size=10)
    assert events[0].source == "chaoxing"
    assert events[0].event_type == "assignment_graded"


def test_chaoxing_discussion_participated_event_success():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    result = service.record_chaoxing_discussion_participated(
        user_id="user1",
        discussion_id="disc_1",
        course_id="course_1",
        observed_at=now,
    )
    assert result is not None
    assert result.created is True


def test_chaoxing_exam_discovered_event_success():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    result = service.record_chaoxing_exam_discovered(
        user_id="user1",
        exam_id="exam_cx_1",
        course_id="course_1",
        exam_time_bucket="within_7d",
        observed_at=now,
    )
    assert result is not None
    assert result.created is True


def test_different_users_can_reuse_same_external_ids():
    db = _make_db()
    _add_user(db, "user1")
    _add_user(db, "user2")
    service = _make_service(db)
    now = _now()
    r1 = service.record_edu_grade_observed(
        user_id="user1",
        binding_id="b1",
        semester="2024-2025-1",
        course_code="CS101",
        credit_value=3.0,
        score="85",
        assessment_category="exam",
        grade_id="grade_shared",
        observed_at=now,
    )
    r2 = service.record_edu_grade_observed(
        user_id="user2",
        binding_id="b2",
        semester="2024-2025-1",
        course_code="CS101",
        credit_value=3.0,
        score="85",
        assessment_category="exam",
        grade_id="grade_shared",
        observed_at=now,
    )
    assert r1 is not None and r2 is not None
    assert r1.event_id != r2.event_id
    assert r1.created is True and r2.created is True


def test_cross_user_isolation():
    db = _make_db()
    _add_user(db, "user1")
    _add_user(db, "user2")
    service = _make_service(db)
    now = _now()
    service.record_self_report_submitted(
        user_id="user1",
        report_id="sr_1",
        report_kind="reflection",
        occurred_at=now,
    )
    events_u2, total_u2 = service.list_events(user_id="user2", page=1, page_size=10)
    assert total_u2 == 0
    assert len(events_u2) == 0


def test_cross_user_delete_isolation():
    db = _make_db()
    _add_user(db, "user1")
    _add_user(db, "user2")
    service = _make_service(db)
    now = _now()
    service.record_self_report_submitted(
        user_id="user1",
        report_id="sr_1",
        report_kind="reflection",
        occurred_at=now,
    )
    service.record_self_report_submitted(
        user_id="user2",
        report_id="sr_2",
        report_kind="reflection",
        occurred_at=now,
    )
    deleted = service.delete_user_events(user_id="user1")
    assert deleted == 1
    _, total_u2 = service.list_events(user_id="user2", page=1, page_size=10)
    assert total_u2 == 1


def test_payload_does_not_contain_sensitive_fields():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    service.record_self_report_submitted(
        user_id="user1",
        report_id="sr_1",
        report_kind="reflection",
        occurred_at=now,
    )
    events, _ = service.list_events(user_id="user1", page=1, page_size=10)
    payload = events[0].payload
    sensitive_keys = {"code", "sourcecode", "answer", "stdout", "stderr", "prompt", "title", "body", "url"}
    for key in payload:
        assert key not in sensitive_keys, f"payload contains sensitive key: {key}"


def test_edu_event_payload_has_controlled_semester_key():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    service.record_edu_schedule_synced(
        user_id="user1",
        binding_id="b1",
        semester="2024-2025-1",
        scheduled_item_count=3,
        observed_at=now,
        sync_batch_id="batch_1",
    )
    events, _ = service.list_events(user_id="user1", page=1, page_size=10)
    payload = events[0].payload
    assert "semester_key" in payload
    assert payload["semester_key"] != "2024-2025-1"
    assert len(payload["semester_key"]) == 16


def test_score_band_correctness():
    assert LearnerEventService._score_band("95") == "90_100"
    assert LearnerEventService._score_band("85") == "80_89"
    assert LearnerEventService._score_band("75") == "70_79"
    assert LearnerEventService._score_band("65") == "60_69"
    assert LearnerEventService._score_band("55") == "0_59"
    assert LearnerEventService._score_band(None) is None
    assert LearnerEventService._score_band("优秀") == "non_numeric"


def test_exam_time_bucket_correctness():
    now = datetime.now(timezone.utc)
    past = (now - timedelta(days=1)).isoformat()
    near = (now + timedelta(days=3)).isoformat()
    mid = (now + timedelta(days=20)).isoformat()
    far = (now + timedelta(days=60)).isoformat()
    assert LearnerEventService._exam_time_bucket(past) == "past"
    assert LearnerEventService._exam_time_bucket(near) == "within_7d"
    assert LearnerEventService._exam_time_bucket(mid) == "within_30d"
    assert LearnerEventService._exam_time_bucket(far) == "beyond_30d"
    assert LearnerEventService._exam_time_bucket(None) == "unknown"
    assert LearnerEventService._exam_time_bucket("not-a-date") == "unknown"



def test_paused_edu_source_skips_event():
    class MockPolicy:
        def should_skip_learner_event(self, *, user_id, source):
            return source == "edu"
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db, source_policy=MockPolicy())
    now = _now()
    result = service.record_edu_schedule_synced(
        user_id="user1",
        binding_id="b1",
        semester="2024-2025-1",
        scheduled_item_count=3,
        observed_at=now,
        sync_batch_id="batch_1",
    )
    assert result is None
    _, total = service.list_events(user_id="user1", page=1, page_size=10)
    assert total == 0



def test_paused_self_report_source_skips_event():
    class MockPolicy:
        def should_skip_learner_event(self, *, user_id, source):
            return source == "self_report"
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db, source_policy=MockPolicy())
    now = _now()
    result = service.record_self_report_submitted(
        user_id="user1",
        report_id="sr_1",
        report_kind="reflection",
        occurred_at=now,
    )
    assert result is None


def test_project_safely_does_not_raise_on_event_failure():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)

    def failing_callback():
        raise RuntimeError("simulated failure")
    result = service.project_safely(
        action="test_action",
        subject_type="test",
        subject_id="t1",
        callback=failing_callback,
    )
    assert result is None


def test_edu_schedule_dedupe_conflict_on_different_semantics():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    r1 = service.record_edu_schedule_synced(
        user_id="user1",
        binding_id="b1",
        semester="2024-2025-1",
        scheduled_item_count=5,
        observed_at=now,
        sync_batch_id="batch_1",
    )
    assert r1 is not None and r1.created is True
    r2 = service.record_edu_schedule_synced(
        user_id="user1",
        binding_id="b1",
        semester="2024-2025-1",
        scheduled_item_count=5,
        observed_at=now,
        sync_batch_id="batch_1",
    )
    assert r2 is not None and r2.created is False
    assert r1.event_id == r2.event_id



def test_self_report_idempotent():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    r1 = service.record_self_report_submitted(
        user_id="user1",
        report_id="sr_1",
        report_kind="reflection",
        occurred_at=now,
    )
    r2 = service.record_self_report_submitted(
        user_id="user1",
        report_id="sr_1",
        report_kind="reflection",
        occurred_at=now,
    )
    assert r1 is not None and r2 is not None
    assert r1.event_id == r2.event_id
    assert r2.created is False


def test_ai_learning_feedback_idempotent():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    r1 = service.record_ai_learning_feedback_recorded(
        user_id="user1",
        feedback_id="fb_1",
        feedback_kind="hint",
        occurred_at=now,
    )
    r2 = service.record_ai_learning_feedback_recorded(
        user_id="user1",
        feedback_id="fb_1",
        feedback_kind="hint",
        occurred_at=now,
    )
    assert r1 is not None and r2 is not None
    assert r1.event_id == r2.event_id
    assert r2.created is False


def test_edu_backfill_requires_repositories():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    with pytest.raises(RuntimeError, match="edu learning event backfill"):
        service.backfill_edu_learning_events(user_id="user1")


def test_edu_backfill_batch_size_validation():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    with pytest.raises(ValueError, match="batch_size"):
        service.backfill_edu_learning_events(user_id="user1", batch_size=0)
    with pytest.raises(ValueError, match="batch_size"):
        service.backfill_edu_learning_events(user_id="user1", batch_size=101)


def test_edu_consent_scope_is_connected_platform():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    service.record_edu_schedule_synced(
        user_id="user1",
        binding_id="b1",
        semester="s1",
        scheduled_item_count=1,
        observed_at=now,
        sync_batch_id="b1",
    )
    events, _ = service.list_events(user_id="user1", page=1, page_size=10)
    assert events[0].consent_scope == "connected_learning_platform"


def test_self_report_consent_scope_is_core_learning():
    db = _make_db()
    _add_user(db, "user1")
    service = _make_service(db)
    now = _now()
    service.record_self_report_submitted(
        user_id="user1",
        report_id="sr_1",
        report_kind="reflection",
        occurred_at=now,
    )
    events, _ = service.list_events(user_id="user1", page=1, page_size=10)
    assert events[0].consent_scope == "core_learning_record"