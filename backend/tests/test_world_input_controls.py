from datetime import datetime, timedelta, timezone

import pytest
from test_learner_preferences import context as shared_context


@pytest.fixture
def context():
    return shared_context.__wrapped__()


def test_source_pause_excludes_new_and_changed_facts_without_deleting_business_data(
    context,
):
    container, _, users = context
    uid = users[0][0]
    repository = container.personal_task_repository
    old = repository.create_task(
        user_id=uid,
        title="before pause",
        deadline=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    )
    cut = datetime.now(timezone.utc) + timedelta(seconds=1)
    container.learner_control_repository.upsert_source_control(
        user_id=uid, source_key="PERSONAL_TASK", status="PAUSED"
    )
    new = repository.create_task(
        user_id=uid, title="after pause", deadline=(cut + timedelta(days=1)).isoformat()
    )
    with container.db.transaction() as conn:
        conn.execute(
            "UPDATE learner_data_source_controls SET updated_at=? WHERE user_id=? AND source_key='PERSONAL_TASK'",
            (cut.isoformat(), uid),
        )
        conn.execute(
            "UPDATE personal_tasks SET created_at=?,updated_at=? WHERE id=?",
            (
                (cut + timedelta(seconds=1)).isoformat(),
                (cut + timedelta(seconds=1)).isoformat(),
                new.id,
            ),
        )
    inputs = container.forecast_service.collect_inputs(
        user_id=uid, as_of=cut + timedelta(seconds=2)
    )
    assert old.id in {row["id"] for row in inputs.tasks}
    assert new.id not in {row["id"] for row in inputs.tasks}
    with container.db.transaction() as conn:
        conn.execute(
            "UPDATE personal_tasks SET updated_at=? WHERE id=?",
            ((cut + timedelta(seconds=1)).isoformat(), old.id),
        )
    assert (
        container.forecast_service.collect_inputs(
            user_id=uid, as_of=cut + timedelta(seconds=2)
        ).tasks
        == []
    )
    assert repository.get_task(new.id, user_id=uid) is not None
    projection = container.learner_state_service.project_world(
        uid, as_of=cut + timedelta(seconds=2)
    )
    workload = next(
        snap for snap in projection.snapshots if snap.state_type == "workload_pressure"
    )
    assert workload.value["task_count"] == 0
    assert "learner_data_source_paused" in projection.warnings


def test_workload_evidence_uses_only_records_that_support_the_estimate(context):
    container, _, users = context
    uid = users[0][0]
    now = datetime.now(timezone.utc)
    inputs = {
        "tasks": [
            {
                "id": "included",
                "status": "pending",
                "deadline": (now + timedelta(days=1)).isoformat(),
            },
            {
                "id": "completed",
                "status": "completed",
                "deadline": (now + timedelta(days=1)).isoformat(),
            },
            {"id": "no-deadline", "status": "pending"},
            {
                "id": "outside",
                "status": "pending",
                "deadline": (now + timedelta(days=20)).isoformat(),
            },
        ],
        "sessions": [],
        "goals": [],
        "schedule_items": [],
        "exam_items": [],
        "grade_items": [],
        "events": [],
    }
    _, snapshots, evidence = container.learner_state_service._compute_world(
        user_id=uid, inputs=inputs, as_of=now, input_digest="evidence", trigger="test"
    )
    snapshot = next(
        snap for snap in snapshots if snap.state_type == "workload_pressure"
    )
    assert snapshot.value["task_count"] == 1
    assert {
        row["source_id"]
        for row in evidence
        if row["snapshot_id"] == snapshot.snapshot_id and row["role"] == "SUPPORTS"
    } == {"included"}
