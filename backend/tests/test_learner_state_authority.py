from datetime import datetime, timezone

from app.core.config import Settings
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


AS_OF = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


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


def _event(container, *, user_id, event_id, event_type, subject_id, course_id):
    with container.db.transaction() as conn:
        conn.execute(
            """INSERT INTO learner_events
               (event_id,user_id,occurred_at,received_at,source,event_type,course_id,
                subject_type,subject_id,outcome,evidence_reference_json,data_quality,
                consent_scope,dedupe_key,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event_id, user_id, AS_OF.isoformat(), AS_OF.isoformat(), "chaoxing",
                event_type, course_id, "personal_task", subject_id, "completed",
                "{}", "verified", "core_learning_record", event_id, AS_OF.isoformat(),
            ),
        )


def test_course_assignment_completion_requires_current_completed_task():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    task = container.personal_task_repository.create_task(
        user_id=user_id, title="platform assignment", source="chaoxing",
        external_id="remote-1", course_id="course-authority",
    )
    container.personal_task_repository.complete(task.id, user_id=user_id)
    _event(
        container, user_id=user_id, event_id="submitted-1", event_type="assignment_submitted",
        subject_id=task.id, course_id="course-authority",
    )
    completed = container.learner_state_service.project_user(user_id, as_of=AS_OF, trigger="test")
    state = next(item for item in completed.snapshots if item.scope_id == "course-authority")
    assert state.value["observed_assignments_completed"] == 1

    container.personal_task_repository.restore(task.id, user_id=user_id)
    restored = container.learner_state_service.project_user(
        user_id, as_of=AS_OF.replace(second=1), trigger="test"
    )
    state = next(item for item in restored.snapshots if item.scope_id == "course-authority")
    assert state.value["observed_assignments_completed"] == 0
    assert "authoritative_task_changed" in state.value["warning_codes"]
    evidence = container.learner_state_repository.list_evidence(
        user_id=user_id, snapshot_id=state.snapshot_id
    )[0]
    assert any(item.role == "INVALIDATES" for item in evidence)


def test_orphan_assignment_submission_is_partial_and_does_not_count_as_current_completion():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    _event(
        container, user_id=user_id, event_id="orphan-submitted", event_type="assignment_submitted",
        subject_id="missing-task", course_id="course-orphan",
    )
    result = container.learner_state_service.project_user(user_id, as_of=AS_OF, trigger="test")
    state = next(item for item in result.snapshots if item.scope_id == "course-orphan")
    assert state.value["observed_assignments_completed"] == 0
    assert state.data_quality == "partial"
    assert "orphan_assignment_submitted" in state.value["warning_codes"]


def test_chapter_participation_never_claims_verified_knowledge():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    with container.db.query() as conn:
        course_id = conn.execute("SELECT id FROM courses ORDER BY id LIMIT 1").fetchone()["id"]
    with container.db.transaction() as conn:
        conn.execute(
            """INSERT INTO course_content_items
               (id,user_id,course_id,provider,external_id,kind,title,status,is_stale,
                last_synced_at,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("chapter-1", user_id, course_id, "chaoxing", "chapter-1", "chapter",
             "redacted", "completed", 0, AS_OF.isoformat(), AS_OF.isoformat(), AS_OF.isoformat()),
        )
        conn.execute(
            """INSERT INTO course_sync_sections
               (user_id,course_id,section,status,item_count,last_synced_at,error_code)
               VALUES (?,?,?,?,?,?,?)""",
            (user_id, course_id, "chapters", "complete", 1, AS_OF.isoformat(), None),
        )
    result = container.learner_state_service.project_user(user_id, as_of=AS_OF, trigger="test")
    state = next(item for item in result.snapshots if item.scope_id == course_id)
    assert state.data_quality == "partial"
    assert state.value["evidence_quality"] == "partial"
    assert not any(
        forbidden in str(state.value).lower()
        for forbidden in ("mastered", "understood", "weak", "knowledge_level")
    )


def test_chaoxing_rows_do_not_create_a_core_event_gap_and_notice_completion_is_core():
    container = _container()
    service = container.learner_state_service
    inputs = {
        "events": [
            {"event_id": "event-session", "source": "study", "event_type": "study_session_finished", "subject_id": "session-1", "occurred_at": AS_OF.isoformat(), "data_quality": "verified"},
            {"event_id": "event-notice", "source": "personal_task", "event_type": "task_completed", "subject_id": "notice-1", "occurred_at": AS_OF.isoformat(), "data_quality": "verified"},
        ],
        "sessions": [{"id": "session-1", "status": "completed", "ended_at": AS_OF.isoformat()}],
        "tasks": [
            {"id": "notice-1", "source": "chaoxing_notice", "status": "completed", "completed_at": AS_OF.isoformat(), "deleted_at": None},
            {"id": "platform-1", "source": "chaoxing", "status": "completed", "completed_at": AS_OF.isoformat(), "deleted_at": None},
        ],
    }
    value, quality, _, _, _ = service._source_health("core_learning_record", inputs, AS_OF)
    assert value["status"] == "FRESH"
    assert quality == "verified"


def test_failed_or_stale_chapter_section_limits_platform_participation():
    container = _container()
    state = container.learner_state_service._course_participation(
        "course-failed",
        [],
        [{"id": "chapter-1", "course_id": "course-failed", "kind": "chapter", "status": "completed", "is_stale": False}],
        [{"course_id": "course-failed", "section": "chapters", "status": "failed", "last_synced_at": AS_OF.isoformat()}],
        [],
        AS_OF,
    )
    value, quality, _, _ = state
    assert value["observed_chapters_completed"] == 0
    assert value["evidence_quality"] == "partial"
    assert quality == "partial"
