from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.database.sqlite_db import Database
from app.models.learner_event import LearnerEventRow
from app.models.personal_task import PersonalTaskRow
from app.models.study import StudySessionRow
from app.schemas.learner_event import LearnerEventCreate


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


def _valid_event_dict(**overrides) -> dict:
    data = {
        "source": "study",
        "event_type": "study_session_finished",
        "occurred_at": _now(),
        "subject_type": "study_session",
        "subject_id": "stdy_abc123",
        "outcome": "completed",
        "duration_seconds": 1500,
        "evidence_reference": {
            "kind": "row",
            "table": "study_sessions",
            "row_id": "stdy_abc123",
        },
        "data_quality": "verified",
        "consent_scope": "core_learning_record",
        "dedupe_key": "study:study_session_finished:stdy_abc123",
        "payload": {"mode": "focus"},
    }
    data.update(overrides)
    return data


def _valid_event(**overrides) -> LearnerEventCreate:
    return LearnerEventCreate(**_valid_event_dict(**overrides))


def _completed_session(session_id: str = "stdy_1", user_id: str = "user1") -> StudySessionRow:
    now = _now().isoformat()
    return StudySessionRow(
        id=session_id,
        user_id=user_id,
        mode="focus",
        experience_mode="QUIET",
        goal=None,
        related_task_id=None,
        started_at=(_now() - timedelta(minutes=30)).isoformat(),
        paused_at=None,
        ended_at=now,
        planned_duration_seconds=1500,
        duration_seconds=1500,
        pause_seconds=60,
        status="completed",
        self_report="session self report text",
        self_report_tags=["calm"],
        expression_signal={"label": "NEUTRAL"},
        behavior_summary={"observed_seconds": 600},
        created_at=now,
        updated_at=now,
    )


def _completed_task(task_id: str = "ptask_1", user_id: str = "user1") -> PersonalTaskRow:
    now = _now().isoformat()
    return PersonalTaskRow(
        id=task_id,
        user_id=user_id,
        title="secret title must not leak",
        description="secret description",
        target_students=None,
        deadline=now,
        materials='["secret material"]',
        submission_method="secret method",
        location=None,
        source_name="chaoxing",
        source_text="secret source text",
        source_notice_id=None,
        priority="high",
        importance="important",
        status="completed",
        reminder_minutes=None,
        source="chaoxing",
        external_id="ext-1",
        course_id="course-1",
        source_url=None,
        last_synced_at=None,
        created_at=now,
        updated_at=now,
        completed_at=now,
        deleted_at=None,
    )


def test_learner_events_table_and_constraints_are_created():
    db = _make_db()
    try:
        with db.query() as conn:
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "learner_events" in tables
            indexes = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='learner_events'"
                ).fetchall()
            }
            assert "idx_learner_events_user_time" in indexes
            assert "idx_learner_events_user_source_type" in indexes
            assert "idx_learner_events_user_course" in indexes
            assert "idx_learner_events_user_subject" in indexes
            unique_found = False
            for row in conn.execute("PRAGMA index_list(learner_events)").fetchall():
                if row["unique"] == 1:
                    cols = {
                        c["name"]
                        for c in conn.execute(
                            f"PRAGMA index_info({row['name']})"
                        ).fetchall()
                    }
                    if cols == {"user_id", "dedupe_key"}:
                        unique_found = True
            assert unique_found
    finally:
        db.dispose()


def test_valid_event_passes_schema():
    event = _valid_event()
    assert event.source == "study"
    assert event.occurred_at.tzinfo is not None


@pytest.mark.parametrize("source", ["forum", "admin", "unknown", ""])
def test_illegal_source_rejected(source):
    with pytest.raises(ValidationError):
        _valid_event(source=source)


@pytest.mark.parametrize("event_type", ["chapter_completed", "chat_message", "unknown", ""])
def test_illegal_event_type_rejected(event_type):
    with pytest.raises(ValidationError):
        _valid_event(event_type=event_type)


def test_illegal_source_event_combination_rejected():
    with pytest.raises(ValidationError):
        _valid_event(source="study", event_type="task_completed")
    with pytest.raises(ValidationError):
        _valid_event(
            source="personal_task",
            event_type="study_session_finished",
            subject_type="personal_task",
            subject_id="ptask_1",
            dedupe_key="personal_task:task_completed:ptask_1:x",
        )


def test_illegal_data_quality_rejected():
    with pytest.raises(ValidationError):
        _valid_event(data_quality="guess")


def test_negative_duration_rejected():
    with pytest.raises(ValidationError):
        _valid_event(duration_seconds=-1)


def test_naive_datetime_rejected():
    with pytest.raises(ValidationError):
        _valid_event(occurred_at=datetime.now().replace(tzinfo=None))


def test_oversized_payload_rejected():
    with pytest.raises(ValidationError):
        _valid_event(payload={"blob": "x" * 8192})


def test_top_level_sensitive_key_rejected():
    sentinel = "S3CR3T-SENTINEL-TOP-9f8a"
    with pytest.raises(ValidationError) as excinfo:
        _valid_event(payload={"mode": "focus", "password": sentinel})
    assert sentinel not in str(excinfo.value)


def test_nested_sensitive_key_rejected():
    sentinel = "S3CR3T-SENTINEL-NESTED-9f8a"
    with pytest.raises(ValidationError) as excinfo:
        _valid_event(payload={"outer": [{"token": sentinel}]})
    assert sentinel not in str(excinfo.value)


@pytest.mark.parametrize("key", ["Access-Token", "accessToken", "API_KEY", "Authorization"])
def test_sensitive_key_variants_rejected(key):
    sentinel = "S3CR3T-SENTINEL-VARIANT-9f8a"
    with pytest.raises(ValidationError) as excinfo:
        _valid_event(payload={key: sentinel})
    assert sentinel not in str(excinfo.value)
    assert sentinel not in repr(excinfo.value.errors())


def test_repository_append_is_idempotent_per_user():
    from app.repositories.learner_event_repository import LearnerEventRepository

    db = _make_db()
    try:
        _add_user(db, "user1")
        repo = LearnerEventRepository(db)
        first = repo.append_idempotent(user_id="user1", event=_valid_event())
        assert first.created is True
        second = repo.append_idempotent(user_id="user1", event=_valid_event())
        assert second.created is False
        assert second.event_id == first.event_id
        rows, total = repo.list_for_user(user_id="user1")
        assert total == 1
        assert len(rows) == 1
    finally:
        db.dispose()


def test_same_dedupe_key_allowed_across_users():
    from app.repositories.learner_event_repository import LearnerEventRepository

    db = _make_db()
    try:
        _add_user(db, "user1")
        _add_user(db, "user2")
        repo = LearnerEventRepository(db)
        first = repo.append_idempotent(user_id="user1", event=_valid_event())
        second = repo.append_idempotent(user_id="user2", event=_valid_event())
        assert first.event_id != second.event_id
    finally:
        db.dispose()


def test_conflicting_identity_on_same_dedupe_raises():
    from app.repositories.learner_event_repository import (
        LearnerEventConflict,
        LearnerEventRepository,
    )

    db = _make_db()
    try:
        _add_user(db, "user1")
        repo = LearnerEventRepository(db)
        repo.append_idempotent(user_id="user1", event=_valid_event())
        with pytest.raises(LearnerEventConflict):
            repo.append_idempotent(
                user_id="user1",
                event=_valid_event(subject_id="stdy_other"),
            )
    finally:
        db.dispose()


def test_get_event_is_scoped_to_user():
    from app.repositories.learner_event_repository import LearnerEventRepository

    db = _make_db()
    try:
        _add_user(db, "user1")
        _add_user(db, "user2")
        repo = LearnerEventRepository(db)
        result = repo.append_idempotent(user_id="user1", event=_valid_event())
        assert repo.get_event(user_id="user1", event_id=result.event_id) is not None
        assert repo.get_event(user_id="user2", event_id=result.event_id) is None
        assert repo.get_by_dedupe(
            user_id="user2", dedupe_key="study:study_session_finished:stdy_abc123"
        ) is None
    finally:
        db.dispose()


def test_list_filters_and_ordering_and_pagination():
    from app.repositories.learner_event_repository import LearnerEventRepository

    db = _make_db()
    try:
        _add_user(db, "user1")
        repo = LearnerEventRepository(db)
        base = _now()
        for index in range(3):
            repo.append_idempotent(
                user_id="user1",
                event=_valid_event(
                    occurred_at=base - timedelta(minutes=index),
                    subject_id=f"stdy_{index}",
                    dedupe_key=f"study:study_session_finished:stdy_{index}",
                    evidence_reference={
                        "kind": "row",
                        "table": "study_sessions",
                        "row_id": f"stdy_{index}",
                    },
                ),
            )
        rows, total = repo.list_for_user(user_id="user1", page=1, page_size=2)
        assert total == 3
        assert len(rows) == 2
        assert rows[0].occurred_at >= rows[1].occurred_at
        rows, _ = repo.list_for_user(user_id="user1", source="study")
        assert len(rows) == 3
        rows, _ = repo.list_for_user(user_id="user1", source="personal_task")
        assert rows == []
        rows, _ = repo.list_for_user(
            user_id="user1", since=base - timedelta(minutes=1), until=base + timedelta(minutes=1)
        )
        assert len(rows) == 2
    finally:
        db.dispose()


def test_list_rejects_bad_pagination_and_range():
    from app.repositories.learner_event_repository import LearnerEventRepository

    db = _make_db()
    try:
        _add_user(db, "user1")
        repo = LearnerEventRepository(db)
        with pytest.raises(ValueError):
            repo.list_for_user(user_id="user1", page_size=101)
        with pytest.raises(ValueError):
            repo.list_for_user(
                user_id="user1",
                since=_now(),
                until=_now() - timedelta(seconds=1),
            )
    finally:
        db.dispose()


def test_corrupt_json_does_not_break_list():
    from app.repositories.learner_event_repository import LearnerEventRepository

    db = _make_db()
    try:
        _add_user(db, "user1")
        repo = LearnerEventRepository(db)
        result = repo.append_idempotent(user_id="user1", event=_valid_event())
        with db.transaction() as conn:
            conn.execute(
                "UPDATE learner_events SET evidence_reference_json='not-json', "
                "payload_json='{broken' WHERE event_id=?",
                (result.event_id,),
            )
        rows, total = repo.list_for_user(user_id="user1")
        assert total == 1
        assert isinstance(rows[0], LearnerEventRow)
        assert rows[0].event_id == result.event_id
        assert rows[0].user_id == "user1"
        assert rows[0].source == "study"
    finally:
        db.dispose()


def test_delete_for_user_only_removes_target_user():
    from app.repositories.learner_event_repository import LearnerEventRepository

    db = _make_db()
    try:
        _add_user(db, "user1")
        _add_user(db, "user2")
        repo = LearnerEventRepository(db)
        repo.append_idempotent(user_id="user1", event=_valid_event())
        repo.append_idempotent(user_id="user2", event=_valid_event())
        removed = repo.delete_for_user(user_id="user1")
        assert removed == 1
        rows, total = repo.list_for_user(user_id="user2")
        assert total == 1
        assert len(rows) == 1
    finally:
        db.dispose()


def test_delete_user_cascades_events_when_fk_enabled():
    from app.repositories.learner_event_repository import LearnerEventRepository

    db = _make_db()
    try:
        _add_user(db, "user1")
        repo = LearnerEventRepository(db)
        repo.append_idempotent(user_id="user1", event=_valid_event())
        with db.transaction() as conn:
            conn.execute("DELETE FROM users WHERE id='user1'")
        rows, total = repo.list_for_user(user_id="user1")
        assert total == 0
        assert rows == []
    finally:
        db.dispose()


def test_delete_for_user_keeps_business_tables():
    from app.repositories.learner_event_repository import LearnerEventRepository

    db = _make_db()
    try:
        _add_user(db, "user1")
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO personal_tasks (id, user_id, title, status, created_at, updated_at) "
                "VALUES ('ptask_1', 'user1', 't', 'completed', 'now', 'now')"
            )
            conn.execute(
                "INSERT INTO study_sessions (id, user_id, started_at, status, created_at, updated_at) "
                "VALUES ('stdy_1', 'user1', 'now', 'completed', 'now', 'now')"
            )
        repo = LearnerEventRepository(db)
        repo.append_idempotent(user_id="user1", event=_valid_event())
        repo.delete_for_user(user_id="user1")
        with db.query() as conn:
            assert conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 1
            assert (
                conn.execute("SELECT COUNT(*) AS n FROM personal_tasks").fetchone()["n"] == 1
            )
            assert (
                conn.execute("SELECT COUNT(*) AS n FROM study_sessions").fetchone()["n"] == 1
            )
            assert (
                conn.execute("SELECT COUNT(*) AS n FROM learner_events").fetchone()["n"] == 0
            )
    finally:
        db.dispose()


def test_service_records_completed_session():
    from app.services.container import reset_container_for_tests
    from app.core.config import Settings

    container = reset_container_for_tests(
        Settings(app_env="test", database_url="sqlite:///:memory:")
    )
    try:
        with container.db.transaction() as conn:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
                "VALUES ('user1', 'user1', 'hash', 'now', 'now')"
            )
        result = container.learner_event_service.record_study_session_finished(
            _completed_session()
        )
        assert result is not None
        assert result.created is True
        stored = container.learner_event_repository.get_event(
            user_id="user1", event_id=result.event_id
        )
        assert stored is not None
        assert stored.source == "study"
        assert stored.event_type == "study_session_finished"
        assert stored.subject_type == "study_session"
        assert stored.subject_id == "stdy_1"
        assert stored.outcome == "completed"
        dumped = stored.to_safe_dict()
        assert "session self report text" not in str(dumped)
        assert "NEUTRAL" not in str(dumped)
    finally:
        container.db.dispose()


def test_service_skips_incomplete_or_broken_sessions():
    from app.services.container import reset_container_for_tests
    from app.core.config import Settings

    container = reset_container_for_tests(
        Settings(app_env="test", database_url="sqlite:///:memory:")
    )
    try:
        with container.db.transaction() as conn:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
                "VALUES ('user1', 'user1', 'hash', 'now', 'now')"
            )
        service = container.learner_event_service
        active = _completed_session("stdy_active")
        active.status = "active"
        assert service.record_study_session_finished(active) is None
        paused = _completed_session("stdy_paused")
        paused.status = "paused"
        assert service.record_study_session_finished(paused) is None
        broken = _completed_session("stdy_broken")
        broken.ended_at = None
        assert service.record_study_session_finished(broken) is None
        rows, total = container.learner_event_repository.list_for_user(user_id="user1")
        assert total == 0
        assert rows == []
    finally:
        container.db.dispose()


def test_service_records_completed_task_without_sensitive_text():
    from app.services.container import reset_container_for_tests
    from app.core.config import Settings

    container = reset_container_for_tests(
        Settings(app_env="test", database_url="sqlite:///:memory:")
    )
    try:
        with container.db.transaction() as conn:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
                "VALUES ('user1', 'user1', 'hash', 'now', 'now')"
            )
        task = _completed_task()
        result = container.learner_event_service.record_personal_task_completed(task)
        assert result is not None
        assert result.created is True
        stored = container.learner_event_repository.get_event(
            user_id="user1", event_id=result.event_id
        )
        assert stored is not None
        assert stored.source == "personal_task"
        assert stored.event_type == "task_completed"
        assert stored.course_id == "course-1"
        dumped = stored.to_safe_dict()
        assert "secret title must not leak" not in str(dumped)
        assert "secret source text" not in str(dumped)
        assert "secret material" not in str(dumped)
        again = container.learner_event_service.record_personal_task_completed(task)
        assert again is not None
        assert again.created is False
        assert again.event_id == result.event_id
    finally:
        container.db.dispose()


def test_service_skips_pending_or_deleted_tasks():
    from app.services.container import reset_container_for_tests
    from app.core.config import Settings

    container = reset_container_for_tests(
        Settings(app_env="test", database_url="sqlite:///:memory:")
    )
    try:
        with container.db.transaction() as conn:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
                "VALUES ('user1', 'user1', 'hash', 'now', 'now')"
            )
        service = container.learner_event_service
        pending = _completed_task("ptask_pending")
        pending.status = "pending"
        assert service.record_personal_task_completed(pending) is None
        deleted = _completed_task("ptask_deleted")
        deleted.deleted_at = _now().isoformat()
        assert service.record_personal_task_completed(deleted) is None
    finally:
        container.db.dispose()


def test_unique_constraint_rejects_duplicate_insert():
    db = _make_db()
    try:
        _add_user(db, "user1")
        event = _valid_event()
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO learner_events (event_id, user_id, occurred_at, received_at, "
                "source, event_type, subject_type, subject_id, outcome, evidence_reference_json, "
                "data_quality, consent_scope, dedupe_key, created_at) "
                "VALUES ('a', 'user1', 't', 't', 'study', 'study_session_finished', "
                "'study_session', 's', 'completed', '{}', 'verified', 'core_learning_record', 'k', 't')"
            )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO learner_events (event_id, user_id, occurred_at, received_at, "
                    "source, event_type, subject_type, subject_id, outcome, evidence_reference_json, "
                    "data_quality, consent_scope, dedupe_key, created_at) "
                    "VALUES ('b', 'user1', 't', 't', 'study', 'study_session_finished', "
                    "'study_session', 's', 'completed', '{}', 'verified', 'core_learning_record', 'k', 't')"
                )
    finally:
        db.dispose()
