from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.database.sqlite_db import Database, LEARNER_CONTROL_SCHEMA_SQL


@pytest.fixture
def context():
    container = reset_container_for_tests(
        Settings(app_env="test", database_url="sqlite:///:memory:")
    )
    client = TestClient(create_app())
    users = []
    for name in ("preferences_one", "preferences_two"):
        user = container.user_repository.create_user(
            username=name, password_hash=hash_password("Demo123456"), role="student"
        )
        response = client.post(
            "/api/v1/auth/login", json={"username": name, "password": "Demo123456"}
        )
        users.append(
            (user.id, {"Authorization": f"Bearer {response.json()['access_token']}"})
        )
    return container, client, users


def test_preferences_optimistic_version_idempotency_and_owner_isolation(context):
    container, client, users = context
    uid, auth = users[0]
    path = "/api/v1/learner-state/preferences"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=auth).json()["configured"] is False
    body = {
        "expected_version": 0,
        "idempotency_key": "pref-first",
        "daily_capacity_minutes": 60,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "07:00",
        "semester_start_dates": {"2026-autumn": "2026-09-07"},
    }
    first = client.put(path, json=body, headers=auth)
    assert first.status_code == 200, first.text
    assert first.json()["version"] == 1
    assert client.put(path, json=body, headers=auth).json() == first.json()
    changed = client.put(
        path, json={**body, "daily_capacity_minutes": 90}, headers=auth
    )
    assert changed.status_code == 409
    assert changed.json()["code"] == "LEARNER_PREFERENCE_IDEMPOTENCY_CONFLICT"
    stale = client.put(path, json={**body, "idempotency_key": "new"}, headers=auth)
    assert stale.status_code == 409
    assert stale.json()["code"] == "LEARNER_PREFERENCE_VERSION_CONFLICT"
    assert client.get(path, headers=users[1][1]).json()["version"] == 0
    assert (
        container.learner_control_repository.get_preferences(user_id=uid)[
            "daily_capacity_minutes"
        ]
        == 60
    )


@pytest.mark.parametrize(
    "fields",
    [
        {"timezone": "Not/AZone"},
        {"daily_capacity_minutes": 0},
        {"quiet_hours_start": "22:00"},
        {"quiet_hours_start": "25:00", "quiet_hours_end": "07:00"},
        {"semester_start_dates": {"2026": "2026-09-08"}},
        {"user_id": "other"},
    ],
)
def test_preferences_reject_invalid_and_injected_fields(context, fields):
    _, client, users = context
    response = client.put(
        "/api/v1/learner-state/preferences",
        headers=users[0][1],
        json={"expected_version": 0, "idempotency_key": "invalid", **fields},
    )
    assert response.status_code == 422


def test_preferences_bound_plan_budget_and_stale_plan(context):
    container, client, users = context
    uid, auth = users[0]
    for index in range(6):
        container.personal_task_repository.create_task(
            user_id=uid,
            title=f"task {index}",
            deadline=(datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(),
        )
    preference = {
        "expected_version": 0,
        "idempotency_key": "budget",
        "daily_capacity_minutes": 30,
    }
    assert (
        client.put(
            "/api/v1/learner-state/preferences", headers=auth, json=preference
        ).status_code
        == 200
    )
    generated = client.post(
        "/api/v1/learning-plans/generate", headers=auth, json={"available_minutes": 120}
    )
    assert generated.status_code == 200, generated.text
    plan = generated.json()
    assert plan["allocated_minutes"] <= 30
    assert "preference_capacity_applied" in plan["warning_codes"]
    assert (
        client.post(
            f"/api/v1/learning-plans/{plan['plan_id']}/decision",
            headers=auth,
            json={"decision": "ACCEPT"},
        ).status_code
        == 200
    )
    preference.update(
        expected_version=1, idempotency_key="budget-2", daily_capacity_minutes=60
    )
    assert (
        client.put(
            "/api/v1/learner-state/preferences", headers=auth, json=preference
        ).status_code
        == 200
    )
    response = client.post(
        f"/api/v1/learning-plans/{plan['plan_id']}/execute", headers=auth
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "LEARNING_PLAN_STALE"


def test_all_model_deletion_removes_explicit_preferences(context):
    container, _, users = context
    uid = users[0][0]
    container.learner_control_repository.update_preferences(
        user_id=uid,
        preferences={"timezone": "UTC", "daily_capacity_minutes": 60},
        expected_version=0,
        idempotency_key="erase",
    )
    container.learner_control_service.request_deletion(
        user_id=uid, scope="ALL_LEARNER_MODEL_DATA", idempotency_key="delete"
    )
    assert container.learner_control_repository.get_preferences(user_id=uid) is None
    with container.db.query() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM learner_preference_receipts WHERE user_id=?",
                (uid,),
            ).fetchone()[0]
            == 0
        )


@pytest.mark.parametrize("projection", ["WORLD", "ACADEMIC"])
def test_extended_corrections_affect_only_matching_projection_and_keep_history(
    context, projection
):
    container, client, users = context
    uid, auth = users[0]
    container.personal_task_repository.create_task(
        user_id=uid,
        title="fact",
        deadline=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
    )
    snapshots = client.get(
        f"/api/v1/learner-state/snapshots?projection_kind={projection}", headers=auth
    )
    assert snapshots.status_code == 200, snapshots.text
    target = snapshots.json()["items"][0]
    body = {
        "projection_kind": projection,
        "projection_scope": target["projection_scope"],
        "scope_type": target["scope_type"],
        "scope_id": target["scope_id"],
        "state_type": target["state_type"],
        "target_snapshot_id": target["snapshot_id"],
        "correction_type": "SOURCE_OUTDATED",
        "reason_code": "SOURCE_DATA_STALE",
        "idempotency_key": "extend",
    }
    assert (
        client.post(
            "/api/v1/learner-state/corrections", headers=users[1][1], json=body
        ).status_code
        == 404
    )
    correction = client.post(
        "/api/v1/learner-state/corrections", headers=auth, json=body
    )
    assert correction.status_code == 201, correction.text
    after = client.get(
        f"/api/v1/learner-state/snapshots?projection_kind={projection}", headers=auth
    ).json()["items"]
    same = next(
        item
        for item in after
        if item["state_type"] == target["state_type"]
        and item["scope_id"] == target["scope_id"]
    )
    assert same["data_quality"] == "stale"
    assert "learner_correction_source_outdated" in same["warning_codes"]
    historical = container.learner_state_repository.get_snapshot(
        user_id=uid,
        snapshot_id=target["snapshot_id"],
        projection_kind=projection,
        projection_scope=target["projection_scope"],
    )
    assert historical.data_quality == target["data_quality"]
    assert (
        client.post(
            f"/api/v1/learner-state/corrections/{correction.json()['correction_id']}/revoke",
            headers=auth,
            json={"idempotency_key": "revoke"},
        ).status_code
        == 200
    )
    restored = client.get(
        f"/api/v1/learner-state/snapshots?projection_kind={projection}", headers=auth
    ).json()["items"]
    same = next(
        item
        for item in restored
        if item["state_type"] == target["state_type"]
        and item["scope_id"] == target["scope_id"]
    )
    assert same["data_quality"] == target["data_quality"]


def test_legacy_correction_constraints_upgrade_without_losing_rows(context):
    container, _, users = context
    uid = users[0][0]
    with container.db.transaction() as conn:
        conn.execute("DROP TABLE learner_state_corrections")
        legacy = LEARNER_CONTROL_SCHEMA_SQL.replace(
            "'CORE','KNOWLEDGE','ACADEMIC','WORLD'", "'CORE','KNOWLEDGE'"
        )
        legacy = legacy.replace(
            "'KNOWLEDGE_COMPONENT','SEMESTER'", "'KNOWLEDGE_COMPONENT'"
        )
        Database._execute_schema_script(conn, legacy)
        conn.execute(
            "INSERT INTO learner_state_corrections(correction_id,user_id,projection_kind,projection_scope,scope_type,scope_id,state_type,target_snapshot_id,correction_type,reason_code,status,created_at,correction_version,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy",
                uid,
                "CORE",
                "__user__",
                "USER",
                uid,
                "task_workload",
                "old-snap",
                "MARK_INACCURATE",
                "OTHER_CONTROLLED_REASON",
                "ACTIVE",
                datetime.now(timezone.utc).isoformat(),
                1,
                "legacy-key",
            ),
        )
        container.db._migrate_learner_corrections(conn)
        assert (
            conn.execute(
                "SELECT correction_id FROM learner_state_corrections"
            ).fetchone()[0]
            == "legacy"
        )
        conn.execute(
            "UPDATE learner_state_corrections SET projection_kind='WORLD',scope_type='SEMESTER' WHERE correction_id='legacy'"
        )
        container.db._migrate_learner_corrections(conn)
        assert (
            conn.execute("SELECT COUNT(*) FROM learner_state_corrections").fetchone()[0]
            == 1
        )


def test_repeated_pause_keeps_original_input_cutoff(context):
    container, _, users = context
    uid = users[0][0]
    repository = container.learner_control_repository
    repository.upsert_source_control(
        user_id=uid, source_key="PERSONAL_TASK", status="PAUSED"
    )
    old = "2026-09-07T08:00:00+00:00"
    with container.db.transaction() as conn:
        conn.execute(
            "UPDATE learner_data_source_controls SET updated_at=? WHERE user_id=? AND source_key='PERSONAL_TASK'",
            (old, uid),
        )
    replay = repository.upsert_source_control(
        user_id=uid, source_key="PERSONAL_TASK", status="PAUSED"
    )
    assert replay.updated_at.isoformat() == old


def test_world_correction_invalidates_an_unexecuted_accepted_plan(context):
    container, client, users = context
    uid, auth = users[0]
    container.personal_task_repository.create_task(
        user_id=uid,
        title="task",
        deadline=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    )
    generated = client.post(
        "/api/v1/learning-plans/generate", headers=auth, json={"available_minutes": 60}
    )
    assert generated.status_code == 200, generated.text
    plan_id = generated.json()["plan_id"]
    assert (
        client.post(
            f"/api/v1/learning-plans/{plan_id}/decision",
            headers=auth,
            json={"decision": "ACCEPT"},
        ).status_code
        == 200
    )
    snapshot = next(
        row
        for row in client.get(
            "/api/v1/learner-state/snapshots?projection_kind=WORLD", headers=auth
        ).json()["items"]
        if row["state_type"] == "workload_pressure"
    )
    body = {
        key: snapshot[key]
        for key in (
            "projection_kind",
            "projection_scope",
            "scope_type",
            "scope_id",
            "state_type",
        )
    }
    body.update(
        target_snapshot_id=snapshot["snapshot_id"],
        correction_type="MARK_INACCURATE",
        reason_code="EVIDENCE_NOT_RELEVANT",
        idempotency_key="question-world",
    )
    assert (
        client.post(
            "/api/v1/learner-state/corrections", headers=auth, json=body
        ).status_code
        == 201
    )
    stale = client.post(f"/api/v1/learning-plans/{plan_id}/execute", headers=auth)
    assert stale.status_code == 409
    assert stale.json()["code"] == "LEARNING_PLAN_STALE"
