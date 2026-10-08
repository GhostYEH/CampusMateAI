from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.main import create_app
from app.services.container import get_container, reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client() -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app())


def _user_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _bind(client: TestClient, user_headers: dict[str, str]) -> tuple[str, str, str]:
    created = client.post(
        "/api/v1/devices/bindings",
        json={
            "device_name": "Desk prototype",
            "platform": "android",
            "hardware_model": "RK3588S",
            "app_version": "0.1.0",
        },
    )
    assert created.status_code == 201, created.text
    binding = created.json()
    parsed = parse_qs(urlparse(binding["qr_payload"]).query)
    assert "poll_token" not in binding["qr_payload"]
    assert binding["poll_token"] not in binding["qr_payload"]
    bind_token = parsed["token"][0]
    rejected = client.post(
        f"/api/v1/devices/bindings/{binding['binding_id']}/confirm",
        headers=user_headers,
        json={"bind_token": "x" * 48},
    )
    assert rejected.status_code == 401
    confirmed = client.post(
        f"/api/v1/devices/bindings/{binding['binding_id']}/confirm",
        headers=user_headers,
        json={"bind_token": bind_token},
    )
    assert confirmed.status_code == 204, confirmed.text
    result = client.get(
        f"/api/v1/devices/bindings/{binding['binding_id']}/result",
        headers={"X-Device-Poll-Token": binding["poll_token"]},
    )
    assert result.status_code == 200, result.text
    return (
        binding["binding_id"],
        binding["poll_token"],
        result.json()["device_credential"],
    )


def test_binding_poll_is_recoverable_and_credential_is_hashed_and_revocable() -> None:
    client = _client()
    user = _user_headers(client)
    binding_id, poll_token, credential = _bind(client, user)
    first = client.get(
        f"/api/v1/devices/bindings/{binding_id}/result",
        headers={"X-Device-Poll-Token": poll_token},
    )
    assert first.json()["device_credential"] == credential
    container = get_container()
    with container.db.query() as conn:
        stored = conn.execute(
            "SELECT credential_hash FROM desktop_devices WHERE id=?",
            (first.json()["device_id"],),
        ).fetchone()[0]
    assert stored != credential
    assert stored
    assert (
        client.get("/api/v1/devices", headers=user).json()["items"][0]["status"]
        == "ACTIVE"
    )
    assert (
        client.delete(
            f"/api/v1/devices/{first.json()['device_id']}", headers=user
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/v1/devices/me/heartbeat",
            headers={"Authorization": f"Bearer {credential}"},
            json={
                "app_version": "0.1.0",
                "network_state": "online",
            },
        ).status_code
        == 401
    )


def test_device_credential_controls_owner_focus_session_and_aggregated_events() -> None:
    client = _client()
    user = _user_headers(client)
    binding_id, poll_token, credential = _bind(client, user)
    device = {"Authorization": f"Bearer {credential}"}
    default_config = client.get("/api/v1/devices/me/config", headers=device)
    assert default_config.status_code == 200
    assert default_config.json()["preferences_configured"] is False
    assert default_config.json()["supports_ota"] is False
    assert default_config.json()["local_behavior_inference"] is False
    assert default_config.json()["hardware_acceleration_status"] == "unverified"
    heartbeat = client.post(
        "/api/v1/devices/me/heartbeat",
        headers=device,
        json={
            "app_version": "0.1.0",
            "network_state": "online",
            "capabilities": {
                "camera": True,
                "behavior_model": True,
                "expression_model": True,
            },
            "model_versions": {
                "behavior": "behavior-v34",
                "expression": "expression-v1",
            },
        },
    )
    assert heartbeat.status_code == 200
    assert (
        client.get("/api/v1/devices/me/config", headers=device).json()[
            "local_behavior_inference"
        ]
        is True
    )
    container = get_container()
    with container.db.query() as conn:
        user_id = conn.execute(
            "SELECT id FROM users WHERE username='student_demo'"
        ).fetchone()[0]
    container.learner_control_repository.update_preferences(
        user_id=user_id,
        preferences={
            "timezone": "Asia/Shanghai",
            "daily_capacity_minutes": 180,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
            "semester_start_dates": {},
        },
        expected_version=0,
        idempotency_key="device-config-test",
    )
    configured = client.get("/api/v1/devices/me/config", headers=device).json()
    assert configured["preferences_configured"] is True
    assert configured["preferences_version"] == 1
    assert configured["timezone"] == "Asia/Shanghai"
    assert configured["daily_capacity_minutes"] == 180
    assert configured["quiet_hours_start"] == "22:00"
    create_headers = {**device, "Idempotency-Key": "create-focus-1"}
    create_body = {"planned_duration_seconds": 1500}
    created = client.post(
        "/api/v1/devices/me/focus-sessions", headers=create_headers, json=create_body
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["id"]
    assert created.json()["status"] == "active"
    replay_create = client.post(
        "/api/v1/devices/me/focus-sessions", headers=create_headers, json=create_body
    )
    assert replay_create.status_code == 201
    assert replay_create.json()["id"] == session_id
    conflict_create = client.post(
        "/api/v1/devices/me/focus-sessions",
        headers=create_headers,
        json={"planned_duration_seconds": 1800},
    )
    assert conflict_create.status_code == 409
    pause_headers = {**device, "Idempotency-Key": "pause-1"}
    paused = client.post(
        f"/api/v1/devices/me/focus-sessions/{session_id}/pause", headers=pause_headers
    )
    assert paused.json()["status"] == "paused"
    assert (
        client.post(
            f"/api/v1/devices/me/focus-sessions/{session_id}/pause",
            headers=pause_headers,
        ).json()
        == paused.json()
    )
    assert (
        client.post(
            f"/api/v1/devices/me/focus-sessions/{session_id}/resume",
            headers={**device, "Idempotency-Key": "resume-1"},
        ).json()["status"]
        == "active"
    )
    finish_headers = {**device, "Idempotency-Key": "finish-1"}
    finished = client.post(
        f"/api/v1/devices/me/focus-sessions/{session_id}/finish",
        headers=finish_headers,
        json={},
    )
    assert finished.status_code == 200, finished.text
    assert finished.json()["status"] == "completed"
    assert finished.json()["duration_seconds"] >= 0
    assert (
        client.post(
            f"/api/v1/devices/me/focus-sessions/{session_id}/finish",
            headers=finish_headers,
            json={},
        ).json()
        == finished.json()
    )
    with get_container().db.query() as conn:
        learning_event = conn.execute(
            "SELECT event_type FROM learner_events WHERE subject_id=?", (session_id,)
        ).fetchone()
    assert learning_event["event_type"] == "study_session_finished"

    occurred = datetime.now(timezone.utc).isoformat()
    event = {
        "event_id": "event-0001",
        "session_id": session_id,
        "event_type": "behavior_stable",
        "occurred_at": occurred,
        "model_version": "behavior-v34",
        "payload": {
            "label": "READ",
            "confidence": 0.88,
            "duration_seconds": 20,
        },
    }
    first = client.post(
        "/api/v1/devices/me/events:batch", headers=device, json={"events": [event]}
    )
    assert first.status_code == 200, first.text
    assert first.json() == {
        "accepted_event_ids": ["event-0001"],
        "duplicate_event_ids": [],
    }
    replay = client.post(
        "/api/v1/devices/me/events:batch", headers=device, json={"events": [event]}
    )
    assert replay.json() == {
        "accepted_event_ids": [],
        "duplicate_event_ids": ["event-0001"],
    }

    changed = {
        **event,
        "payload": {"label": "WRITE", "confidence": 0.88, "duration_seconds": 20},
    }
    conflict = client.post(
        "/api/v1/devices/me/events:batch", headers=device, json={"events": [changed]}
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "DEVICE_EVENT_ID_CONFLICT"

    future = {
        **event,
        "event_id": "event-future",
        "occurred_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }
    assert (
        client.post(
            "/api/v1/devices/me/events:batch", headers=device, json={"events": [future]}
        ).status_code
        == 422
    )


def test_event_batch_rejects_image_fields_and_rolls_back_on_conflict() -> None:
    client = _client()
    user = _user_headers(client)
    _, _, credential = _bind(client, user)
    device = {"Authorization": f"Bearer {credential}"}
    session = client.post(
        "/api/v1/devices/me/focus-sessions",
        headers={**device, "Idempotency-Key": "create-events-test"},
        json={},
    )
    assert session.status_code == 201, session.text
    session_id = session.json()["id"]
    occurred = datetime.now(timezone.utc).isoformat()
    existing = {
        "event_id": "stable-id",
        "session_id": session_id,
        "event_type": "presence_changed",
        "occurred_at": occurred,
        "model_version": "presence-v1",
        "payload": {"state": "PRESENT", "confidence": 0.9},
    }
    assert (
        client.post(
            "/api/v1/devices/me/events:batch",
            headers=device,
            json={"events": [existing]},
        ).status_code
        == 200
    )
    new_event = {**existing, "event_id": "should-rollback"}
    conflicting = {**existing, "payload": {"state": "ABSENT", "confidence": 0.9}}
    response = client.post(
        "/api/v1/devices/me/events:batch",
        headers=device,
        json={"events": [new_event, conflicting]},
    )
    assert response.status_code == 409
    retry = client.post(
        "/api/v1/devices/me/events:batch", headers=device, json={"events": [new_event]}
    )
    assert retry.status_code == 200
    assert retry.json()["accepted_event_ids"] == ["should-rollback"]
    image = {
        **existing,
        "event_id": "with-image",
        "payload": {"state": "PRESENT", "confidence": 0.9, "image": "base64"},
    }
    assert (
        client.post(
            "/api/v1/devices/me/events:batch", headers=device, json={"events": [image]}
        ).status_code
        == 422
    )


def test_device_session_and_event_access_are_owner_scoped() -> None:
    client = _client()
    owner = _user_headers(client)
    _, _, credential = _bind(client, owner)
    device = {"Authorization": f"Bearer {credential}"}
    assert client.get("/api/v1/devices", headers=owner).status_code == 200
    # The device credential is a distinct auth scheme and is rejected by user-only management routes.
    assert client.get("/api/v1/devices", headers=device).status_code == 401
    other_login = client.post(
        "/api/v1/auth/login",
        json={"username": "course_demo_owner1", "password": "Demo123456"},
    )
    assert other_login.status_code == 200
    other_user = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
    other_session = client.post(
        "/api/v1/study/sessions", headers=other_user, json={"mode": "focus"}
    )
    assert other_session.status_code == 201
    event = {
        "event_id": "other-owner-event",
        "session_id": other_session.json()["id"],
        "event_type": "presence_changed",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "model_version": "presence-v1",
        "payload": {"state": "PRESENT", "confidence": 0.9},
    }
    denied = client.post(
        "/api/v1/devices/me/events:batch", headers=device, json={"events": [event]}
    )
    assert denied.status_code == 404


@pytest.mark.parametrize("invalid_owner", ["legacy_teacher", "inactive"])
def test_device_auth_and_user_management_reject_invalid_owner(
    invalid_owner: str,
) -> None:
    client = _client()
    user = _user_headers(client)
    binding_id, poll_token, credential = _bind(client, user)
    container = get_container()
    with container.db.query() as conn:
        user_id = conn.execute(
            "SELECT id FROM users WHERE username='student_demo'"
        ).fetchone()[0]
    if invalid_owner == "legacy_teacher":
        with container.db.transaction() as conn:
            conn.execute("UPDATE users SET role='teacher' WHERE id=?", (user_id,))
        assert client.get("/api/v1/devices", headers=user).status_code == 403
    else:
        with container.db.transaction() as conn:
            conn.execute("UPDATE users SET is_active=0 WHERE id=?", (user_id,))
    denied = client.post(
        "/api/v1/devices/me/heartbeat",
        headers={"Authorization": f"Bearer {credential}"},
        json={
            "app_version": "0.1.0",
            "network_state": "online",
        },
    )
    assert denied.status_code == 401
    poll = client.get(
        f"/api/v1/devices/bindings/{binding_id}/result",
        headers={"X-Device-Poll-Token": poll_token},
    )
    assert poll.status_code == 200
    assert poll.json()["status"] == "REVOKED"
    assert poll.json().get("device_credential") is None


def test_revocation_after_authentication_blocks_session_command_write() -> None:
    client = _client()
    user = _user_headers(client)
    _, _, credential = _bind(client, user)
    container = get_container()
    stale_device = container.desktop_device_service.authenticate(credential)
    with container.db.query() as conn:
        user_id = conn.execute(
            "SELECT id FROM users WHERE username='student_demo'"
        ).fetchone()[0]
    with container.db.query() as conn:
        count_before = conn.execute(
            "SELECT COUNT(*) FROM study_sessions WHERE user_id=?", (user_id,)
        ).fetchone()[0]
    container.desktop_device_service.revoke_device(
        device_id=stale_device.id,
        owner_user_id=user_id,
        now=datetime.now(timezone.utc),
    )
    with pytest.raises(Exception, match="设备已撤销"):
        container.desktop_device_service.create_focus_session(
            device=stale_device,
            planned_duration_seconds=1500,
            goal=None,
            idempotency_key="revoked-command",
        )
    with container.db.query() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM study_sessions WHERE user_id=?", (user_id,)
        ).fetchone()[0]
        receipt_count = conn.execute(
            "SELECT COUNT(*) FROM desktop_device_session_commands WHERE device_id=?",
            (stale_device.id,),
        ).fetchone()[0]
    assert count == count_before
    assert receipt_count == 0


def test_finish_event_and_command_receipt_roll_back_together(monkeypatch) -> None:
    client = _client()
    user = _user_headers(client)
    _, _, credential = _bind(client, user)
    device_headers = {"Authorization": f"Bearer {credential}"}
    session = client.post(
        "/api/v1/devices/me/focus-sessions",
        headers={
            **device_headers,
            "Idempotency-Key": "atomic-create",
        },
        json={},
    )
    assert session.status_code == 201
    session_id = session.json()["id"]
    container = get_container()
    service = container.desktop_device_service._learner_event_service
    original = service.record_study_session_finished

    def fail(_session):
        raise RuntimeError("event sink unavailable")

    monkeypatch.setattr(service, "record_study_session_finished", fail)
    failed = client.post(
        f"/api/v1/devices/me/focus-sessions/{session_id}/finish",
        headers={
            **device_headers,
            "Idempotency-Key": "atomic-finish",
        },
        json={},
    )
    assert failed.status_code == 500
    with container.db.query() as conn:
        status_row = conn.execute(
            "SELECT status FROM study_sessions WHERE id=?", (session_id,)
        ).fetchone()
        receipt = conn.execute(
            "SELECT 1 FROM desktop_device_session_commands WHERE device_id=? AND idempotency_key='atomic-finish'",
            (container.desktop_device_service.authenticate(credential).id,),
        ).fetchone()
    assert status_row["status"] == "active"
    assert receipt is None
    monkeypatch.setattr(service, "record_study_session_finished", original)
    retry = client.post(
        f"/api/v1/devices/me/focus-sessions/{session_id}/finish",
        headers={
            **device_headers,
            "Idempotency-Key": "atomic-finish",
        },
        json={},
    )
    assert retry.status_code == 200, retry.text
