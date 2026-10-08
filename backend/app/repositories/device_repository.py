from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from ..core.exceptions import DeviceBindingInvalid, DeviceCommandConflict
from ..database.sqlite_db import Database
from ..models.device import DesktopDevice
from ._multi_role_common import _new_id, _now_iso


def _device(row: Any) -> DesktopDevice:
    return DesktopDevice(
        id=row["id"],
        owner_user_id=row["owner_user_id"],
        device_name=row["device_name"],
        platform=row["platform"],
        hardware_model=row["hardware_model"],
        app_version=row["app_version"],
        status=row["status"],
        created_at=row["created_at"],
        bound_at=row["bound_at"],
        last_heartbeat_at=row["last_heartbeat_at"],
        revoked_at=row["revoked_at"],
        capabilities=json.loads(row["capabilities_json"] or "{}"),
        model_versions=json.loads(row["model_versions_json"] or "{}"),
    )


class DesktopDeviceRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_binding(
        self,
        *,
        device_name: str,
        platform: str,
        hardware_model: Optional[str],
        app_version: Optional[str],
        bind_token_hash: str,
        poll_token_hash: str,
        expires_at: str,
    ) -> tuple[str, str]:
        device_id = _new_id("desk")
        binding_id = _new_id("bind")
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO desktop_devices
                   (id, owner_user_id, device_name, platform, hardware_model, app_version,
                    status, created_at, bound_at, last_heartbeat_at, revoked_at)
                   VALUES (?,NULL,?,?,?,?, 'PENDING', ?,NULL,NULL,NULL)""",
                (device_id, device_name, platform, hardware_model, app_version, now),
            )
            conn.execute(
                """INSERT INTO desktop_device_bindings
                   (id, device_id, bind_token_hash, poll_token_hash, status, created_at,
                    expires_at, confirmed_at)
                   VALUES (?,?,?,?, 'PENDING', ?,?,NULL)""",
                (
                    binding_id,
                    device_id,
                    bind_token_hash,
                    poll_token_hash,
                    now,
                    expires_at,
                ),
            )
        return binding_id, device_id

    def get_binding(self, binding_id: str) -> Optional[dict[str, Any]]:
        with self._db.query() as conn:
            row = conn.execute(
                """SELECT b.*, d.owner_user_id, d.status AS device_status
                   FROM desktop_device_bindings b JOIN desktop_devices d ON d.id=b.device_id
                   WHERE b.id=?""",
                (binding_id,),
            ).fetchone()
        return dict(row) if row else None

    def confirm_binding(
        self,
        *,
        binding_id: str,
        bind_token_hash: str,
        owner_user_id: str,
        now: datetime,
    ) -> Optional[dict[str, Any]]:
        now_iso = now.astimezone(timezone.utc).isoformat()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """UPDATE desktop_device_bindings
                   SET status='CONFIRMED', confirmed_at=?
                   WHERE id=? AND bind_token_hash=? AND status='PENDING' AND expires_at>?""",
                (now_iso, binding_id, bind_token_hash, now_iso),
            )
            if cur.rowcount != 1:
                return None
            binding = conn.execute(
                "SELECT device_id FROM desktop_device_bindings WHERE id=?",
                (binding_id,),
            ).fetchone()
            cur = conn.execute(
                """UPDATE desktop_devices SET owner_user_id=?, status='ACTIVE',
                   credential_hash=?, bound_at=? WHERE id=? AND status='PENDING'
                   AND EXISTS(SELECT 1 FROM users u WHERE u.id=? AND u.is_active=1 AND u.role='student')""",
                (owner_user_id, None, now_iso, binding["device_id"], owner_user_id),
            )
            if cur.rowcount != 1:
                raise DeviceBindingInvalid("绑定账号已停用或不允许桌面设备访问")
        return self.get_binding(binding_id)

    def poll_binding(
        self, *, binding_id: str, poll_token_hash: str
    ) -> Optional[dict[str, Any]]:
        with self._db.query() as conn:
            row = conn.execute(
                """SELECT b.*, d.owner_user_id, d.status AS device_status
                   FROM desktop_device_bindings b JOIN desktop_devices d ON d.id=b.device_id
                   WHERE b.id=? AND b.poll_token_hash=?""",
                (binding_id, poll_token_hash),
            ).fetchone()
        return dict(row) if row else None

    def get_device_by_credential_hash(self, token_hash: str) -> Optional[DesktopDevice]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM desktop_devices WHERE credential_hash=? AND status='ACTIVE'",
                (token_hash,),
            ).fetchone()
        return _device(row) if row else None

    def get_device(self, device_id: str) -> Optional[DesktopDevice]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM desktop_devices WHERE id=?", (device_id,)
            ).fetchone()
        return _device(row) if row else None

    def set_derived_credential_hash(self, device_id: str, credential_hash: str) -> bool:
        with self._db.transaction() as conn:
            cur = conn.execute(
                """UPDATE desktop_devices SET credential_hash=? WHERE id=? AND status='ACTIVE'
                   AND EXISTS(SELECT 1 FROM users u WHERE u.id=desktop_devices.owner_user_id
                     AND u.is_active=1 AND u.role='student')""",
                (credential_hash, device_id),
            )
        return cur.rowcount == 1

    def list_devices(self, owner_user_id: str) -> list[DesktopDevice]:
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT * FROM desktop_devices WHERE owner_user_id=? ORDER BY created_at DESC",
                (owner_user_id,),
            ).fetchall()
        return [_device(row) for row in rows]

    def revoke_device(
        self, *, device_id: str, owner_user_id: str, now: datetime
    ) -> bool:
        now_iso = now.astimezone(timezone.utc).isoformat()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """UPDATE desktop_devices SET status='REVOKED', revoked_at=?, credential_hash=NULL
                   WHERE id=? AND owner_user_id=? AND status='ACTIVE'""",
                (now_iso, device_id, owner_user_id),
            )
        return cur.rowcount == 1

    def update_heartbeat(
        self,
        *,
        device_id: str,
        app_version: str,
        os_version: Optional[str],
        network_state: str,
        temperature_c: Optional[float],
        free_storage_mb: Optional[int],
        capabilities: dict[str, bool],
        model_versions: dict[str, str],
        now: datetime,
    ) -> bool:
        now_iso = now.astimezone(timezone.utc).isoformat()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """UPDATE desktop_devices SET app_version=?, os_version=?, network_state=?,
                   temperature_c=?, free_storage_mb=?, capabilities_json=?, model_versions_json=?,
                   last_heartbeat_at=? WHERE id=? AND status='ACTIVE'
                   AND EXISTS(SELECT 1 FROM users u WHERE u.id=desktop_devices.owner_user_id
                     AND u.is_active=1 AND u.role='student')""",
                (
                    app_version,
                    os_version,
                    network_state,
                    temperature_c,
                    free_storage_mb,
                    json.dumps(capabilities, sort_keys=True),
                    json.dumps(model_versions, sort_keys=True),
                    now_iso,
                    device_id,
                ),
            )
        return cur.rowcount == 1

    def get_session_for_owner(
        self, *, session_id: str, owner_user_id: str
    ) -> Optional[dict[str, Any]]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT id,user_id,mode,status,started_at,ended_at FROM study_sessions WHERE id=? AND user_id=?",
                (session_id, owner_user_id),
            ).fetchone()
        return dict(row) if row else None

    def execute_session_command(
        self,
        *,
        device_id: str,
        idempotency_key: str,
        action: str,
        request_hash: str,
        execute: Callable[[], dict[str, Any]],
    ) -> tuple[dict[str, Any], bool]:
        """Commit a session operation and its replay receipt atomically."""
        with self._db.transaction(immediate=True) as conn:
            active = conn.execute(
                """SELECT 1 FROM desktop_devices d JOIN users u ON u.id=d.owner_user_id
                   WHERE d.id=? AND d.status='ACTIVE' AND u.is_active=1 AND u.role='student'""",
                (device_id,),
            ).fetchone()
            if active is None:
                raise DeviceBindingInvalid("设备已撤销")
            existing = conn.execute(
                "SELECT action,request_hash,response_json FROM desktop_device_session_commands "
                "WHERE device_id=? AND idempotency_key=?",
                (device_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if (
                    existing["action"] != action
                    or existing["request_hash"] != request_hash
                ):
                    raise DeviceCommandConflict()
                return json.loads(existing["response_json"]), True
            result = execute()
            response_json = json.dumps(
                result, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            conn.execute(
                "INSERT INTO desktop_device_session_commands "
                "(device_id,idempotency_key,action,request_hash,response_json,created_at) VALUES(?,?,?,?,?,?)",
                (
                    device_id,
                    idempotency_key,
                    action,
                    request_hash,
                    response_json,
                    _now_iso(),
                ),
            )
            return result, False

    def link_device_session(
        self, *, device_id: str, session_id: str, created_at: datetime
    ) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO desktop_device_sessions(device_id,study_session_id,created_at) VALUES(?,?,?)",
                (
                    device_id,
                    session_id,
                    created_at.astimezone(timezone.utc).isoformat(),
                ),
            )

    def device_owns_session(self, *, device_id: str, session_id: str) -> bool:
        with self._db.query() as conn:
            return (
                conn.execute(
                    "SELECT 1 FROM desktop_device_sessions WHERE device_id=? AND study_session_id=?",
                    (device_id, session_id),
                ).fetchone()
                is not None
            )

    def append_event_batch(
        self,
        *,
        device_id: str,
        events: list[dict[str, Any]],
        received_at: datetime,
    ) -> tuple[list[str], list[str]]:
        received = received_at.astimezone(timezone.utc).isoformat()
        accepted: list[str] = []
        duplicates: list[str] = []
        with self._db.transaction(immediate=True) as conn:
            active = conn.execute(
                """SELECT 1 FROM desktop_devices d JOIN users u ON u.id=d.owner_user_id
                   WHERE d.id=? AND d.status='ACTIVE' AND u.is_active=1 AND u.role='student'""",
                (device_id,),
            ).fetchone()
            if active is None:
                raise DeviceBindingInvalid("设备已撤销")
            for event in events:
                insert = conn.execute(
                    """INSERT INTO desktop_device_events
                       (device_id,event_id,study_session_id,event_type,occurred_at,received_at,
                        model_version,payload_json,payload_hash)
                       VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(device_id,event_id) DO NOTHING""",
                    (
                        device_id,
                        event["event_id"],
                        event["session_id"],
                        event["event_type"],
                        event["occurred_at"],
                        received,
                        event["model_version"],
                        event["payload_json"],
                        event["payload_hash"],
                    ),
                )
                row = conn.execute(
                    "SELECT payload_hash FROM desktop_device_events WHERE device_id=? AND event_id=?",
                    (device_id, event["event_id"]),
                ).fetchone()
                if row["payload_hash"] != event["payload_hash"]:
                    raise ValueError("event id reused with different content")
                (accepted if insert.rowcount == 1 else duplicates).append(
                    event["event_id"]
                )
        return accepted, duplicates


__all__ = ["DesktopDeviceRepository"]
