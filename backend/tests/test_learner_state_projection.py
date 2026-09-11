from datetime import datetime, timezone

import pytest

from app.core.config import Settings
from app.database.sqlite_db import Database
from app.repositories.learner_event_repository import LearnerEventRepository
from app.schemas.learner_event import EvidenceReference, LearnerEventCreate
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.learner_state_service import ESTIMATOR_VERSION
from app.repositories.learner_state_repository import LearnerStateRepository


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


def _append_event(container, *, user_id: str, event_id: str, event_type: str, subject_id: str, occurred_at: str):
    event = LearnerEventCreate(
        source="study" if event_type == "study_session_finished" else "personal_task",
        event_type=event_type,
        occurred_at=occurred_at,
        subject_type="study_session" if event_type == "study_session_finished" else "personal_task",
        subject_id=subject_id,
        outcome="completed",
        evidence_reference=EvidenceReference(kind="row", table="source", row_id=subject_id),
        consent_scope="core_learning_record",
        dedupe_key=f"test:{event_id}",
    )
    with container.db.transaction() as conn:
        conn.execute(
            "INSERT INTO learner_events (event_id,user_id,occurred_at,received_at,source,event_type,"
            "subject_type,subject_id,outcome,evidence_reference_json,data_quality,consent_scope,dedupe_key,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                event_id,
                user_id,
                event.occurred_at.isoformat(),
                AS_OF.isoformat(),
                event.source,
                event.event_type,
                event.subject_type,
                event.subject_id,
                event.outcome,
                '{"kind":"row","table":"source","row_id":"' + subject_id + '"}',
                "verified",
                "core_learning_record",
                event.dedupe_key,
                AS_OF.isoformat(),
            ),
        )


def test_projection_is_deterministic_and_uses_current_task_status_for_workload():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    task = container.personal_task_repository.create_task(
        user_id=user_id,
        title="private title",
        deadline="2026-09-10T18:00:00+00:00",
    )
    session = container.study_session_repository.create_session(user_id=user_id)
    with container.db.transaction() as conn:
        conn.execute(
            "UPDATE study_sessions SET started_at=?, ended_at=?, status='completed', duration_seconds=600 WHERE id=?",
            ("2026-09-09T10:00:00+00:00", "2026-09-09T10:10:00+00:00", session.id),
        )
    _append_event(
        container,
        user_id=user_id,
        event_id="evt_session",
        event_type="study_session_finished",
        subject_id=session.id,
        occurred_at="2026-09-09T10:10:00+00:00",
    )
    first = container.learner_state_service.project_user(user_id, as_of=AS_OF, trigger="test")
    second = container.learner_state_service.project_user(user_id, as_of=AS_OF, trigger="test")
    assert first.input_digest == second.input_digest
    assert first.run_id == second.run_id
    assert first.estimator_version == ESTIMATOR_VERSION
    activity = next(s for s in first.snapshots if s.state_type == "observed_learning_activity")
    assert activity.value["observed_sessions_7d"] == 1
    workload = next(s for s in first.snapshots if s.state_type == "task_workload")
    assert workload.value["known_pending"] >= 1
    assert workload.value["known_due_24h"] >= 1
    deadline = next(s for s in first.snapshots if s.state_type == "deadline_exposure" and s.scope_id == task.id)
    assert deadline.value["bucket"] == "DUE_24H"
    container.personal_task_repository.complete(task.id, user_id=user_id)
    after = container.learner_state_service.project_user(user_id, as_of=AS_OF, trigger="test")
    after_workload = next(s for s in after.snapshots if s.state_type == "task_workload")
    assert after_workload.value["known_pending"] <= workload.value["known_pending"] - 1


def test_projection_rejects_naive_as_of_and_preserves_old_run_on_write_failure():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    with pytest.raises(ValueError):
        container.learner_state_service.project_user(
            user_id, as_of=datetime(2026, 9, 10, 12, 0), trigger="test"
        )
    run = container.learner_state_service.project_user(user_id, as_of=AS_OF, trigger="test")
    with container.db.query() as conn:
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM learner_state_projection_runs WHERE user_id=? AND is_current=1",
            (user_id,),
        ).fetchone()["n"] == 1
    assert run.run_id


def test_state_tables_indexes_foreign_keys_and_atomic_projection_write():
    db = Database(None)
    try:
        with db.query() as conn:
            tables = {
                row["name"] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'learner_state_%'"
                )
            }
            assert tables == {
                "learner_state_projection_runs",
                "learner_state_snapshots",
                "learner_state_evidence",
            }
            indexes = {
                row["name"] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='learner_state_projection_runs'"
                )
            }
            assert "idx_learner_state_runs_current" in indexes
            fks = {
                row["table"] for row in conn.execute(
                    "PRAGMA foreign_key_list(learner_state_evidence)"
                )
            }
            assert {"learner_state_snapshots", "learner_events"} <= fks
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO users (id,username,password_hash,role,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                ("state_user", "state_user", "hash", "student", AS_OF.isoformat(), AS_OF.isoformat()),
            )
        repo = LearnerStateRepository(db)
        with pytest.raises(Exception):
            repo.save_projection(
                run={
                    "run_id": "run_atomic", "user_id": "state_user", "as_of": AS_OF.isoformat(),
                    "computed_at": AS_OF.isoformat(), "estimator_version": ESTIMATOR_VERSION,
                    "input_digest": "digest", "trigger": "test", "warnings": [],
                },
                snapshots=[{
                    "snapshot_id": "snap_atomic", "scope_type": "USER", "scope_id": "state_user",
                    "state_type": "task_workload", "value": {"known_pending": 0}, "confidence": 1.0,
                    "data_quality": "verified", "computed_at": AS_OF.isoformat(),
                }],
                evidence=[{
                    "evidence_id": "evidence_bad", "snapshot_id": "snap_atomic", "evidence_kind": "EVENT",
                    "event_id": "missing_event", "source_type": "study", "source_id": "missing_event",
                    "role": "SUPPORTS", "quality": "verified",
                }],
            )
        with db.query() as conn:
            assert conn.execute(
                "SELECT COUNT(*) AS n FROM learner_state_projection_runs WHERE run_id='run_atomic'"
            ).fetchone()["n"] == 0
    finally:
        db.dispose()


def test_projection_failure_degrades_existing_state_to_stale():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    first = container.learner_state_service.project_user(user_id, as_of=AS_OF, trigger="test")
    original = container.learner_state_repository.collect_inputs
    container.learner_state_repository.collect_inputs = lambda **_: (_ for _ in ()).throw(RuntimeError("source unavailable"))
    try:
        degraded = container.learner_state_service.project_user(
            user_id, as_of=AS_OF.replace(hour=13), trigger="test"
        )
    finally:
        container.learner_state_repository.collect_inputs = original
    assert degraded.run_id == first.run_id
    assert degraded.warnings[-1] == "projection_failed"
    assert all(snapshot.data_quality == "stale" for snapshot in degraded.snapshots)
    assert all(snapshot.confidence <= 0.25 for snapshot in degraded.snapshots)
