"""CampusMate EduConnector 仓库层。

管理 edu_systems / edu_bindings / edu_connections / edu_sync_records 四张表。
兼容旧 edu_system_configs 表（迁移到 edu_systems）。
所有写入操作均通过 Database.transaction() 上下文，保证原子性。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from ..database.sqlite_db import Database
from ..models.edu import (
    BINDING_ACTIVE,
    BINDING_UNBOUND,
    CONN_AUTH_REQUIRED,
    CONN_IDLE,
    CONN_WAITING_USER_LOGIN,
    EDU_PROVIDER_UNKNOWN,
    EDU_SYSTEM_UNKNOWN,
    EduBindingRow,
    EduConnectionRow,
    EduSyncRecordRow,
    EduSystemConfigRow,
    EduSystemRow,
    LOGIN_EXEC_UNSUPPORTED,
    SYSTEM_KEY_UNDERGRADUATE_MAIN,
    URL_NOT_DISCOVERED,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid_like(seed: str) -> str:
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()[:16]
    return f"esys_{digest}"


class EduRepository:
    """EduConnector 仓库：统一管理教务系统、用户绑定、连接与同步记录。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    # ===== edu_systems (1:N) =====

    def list_systems_by_university(self, university_id: str) -> list[EduSystemRow]:
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT * FROM edu_systems WHERE university_id = ? ORDER BY created_at ASC",
                (university_id,),
            ).fetchall()
        return [EduSystemRow.from_row(row) for row in rows]

    def get_system_by_id(self, system_id: str) -> Optional[EduSystemRow]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM edu_systems WHERE id = ?",
                (system_id,),
            ).fetchone()
        return EduSystemRow.from_row(row) if row else None

    def get_system_by_key(self, university_id: str, system_key: str) -> Optional[EduSystemRow]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM edu_systems WHERE university_id = ? AND system_key = ?",
                (university_id, system_key),
            ).fetchone()
        return EduSystemRow.from_row(row) if row else None

    def upsert_system(
        self,
        *,
        university_id: str,
        system_key: str,
        school_code: Optional[str] = None,
        name: Optional[str] = None,
        system_type: Optional[str] = None,
        provider: Optional[str] = None,
        provider_version: Optional[str] = None,
        base_url: Optional[str] = None,
        login_url: Optional[str] = None,
        sso_url: Optional[str] = None,
        vpn_url: Optional[str] = None,
        auth_type: Optional[str] = None,
        login_execution_mode: Optional[str] = None,
        captcha_type: Optional[str] = None,
        requires_campus_network: Optional[bool] = None,
        requires_vpn: Optional[bool] = None,
        status: Optional[str] = None,
        verification_status: Optional[str] = None,
        supported_features: Optional[list[str]] = None,
        source: Optional[str] = None,
        notes: Optional[str] = None,
        is_mock: Optional[bool] = None,
    ) -> EduSystemRow:
        existing = self.get_system_by_key(university_id, system_key)
        now = _now_iso()
        sys_id = existing.id if existing else _uuid_like(f"{university_id}:{system_key}")

        def _merge(new, old, default=None):
            return new if new is not None else (old if old is not None else default)

        cur_provider = _merge(provider, existing.provider if existing else None, EDU_PROVIDER_UNKNOWN)
        cur_system_type = _merge(system_type, existing.system_type if existing else None, EDU_SYSTEM_UNKNOWN)
        cur_auth_type = _merge(auth_type, existing.auth_type if existing else None, "unknown")
        cur_exec_mode = _merge(login_execution_mode, existing.login_execution_mode if existing else None, LOGIN_EXEC_UNSUPPORTED)
        cur_captcha = _merge(captcha_type, existing.captcha_type if existing else None, "unknown")
        cur_status = _merge(status, existing.status if existing else None, "active")
        cur_verif = _merge(verification_status, existing.verification_status if existing else None, "unverified")
        cur_source = _merge(source, existing.source if existing else None, "unknown")
        cur_name = _merge(name, existing.name if existing else None, None)
        cur_school_code = _merge(school_code, existing.school_code if existing else None, None)
        cur_base_url = _merge(base_url, existing.base_url if existing else None, None)
        cur_login_url = _merge(login_url, existing.login_url if existing else None, None)
        cur_sso_url = _merge(sso_url, existing.sso_url if existing else None, None)
        cur_vpn_url = _merge(vpn_url, existing.vpn_url if existing else None, None)
        cur_pv = _merge(provider_version, existing.provider_version if existing else None, None)
        cur_notes = _merge(notes, existing.notes if existing else None, None)

        cur_rcn = int(requires_campus_network) if requires_campus_network is not None else (
            int(existing.requires_campus_network) if existing else 0
        )
        cur_vpn_req = int(requires_vpn) if requires_vpn is not None else (
            int(existing.requires_vpn) if existing else 0
        )
        cur_is_mock = int(is_mock) if is_mock is not None else (
            int(existing.is_mock) if existing else 0
        )

        if supported_features is None:
            features_json = existing.supported_features if existing else "[]"
        else:
            features_json = json.dumps(supported_features, ensure_ascii=False)

        created_at = existing.created_at if existing else now

        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO edu_systems (
                    id, university_id, school_code, system_key, name, system_type,
                    provider, provider_version, base_url, login_url, sso_url, vpn_url,
                    auth_type, login_execution_mode, captcha_type,
                    requires_campus_network, requires_vpn, status, verification_status,
                    supported_features, last_verified_at, source, notes, is_mock,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?
                )
                ON CONFLICT(university_id, system_key) DO UPDATE SET
                    school_code = COALESCE(excluded.school_code, edu_systems.school_code),
                    name = COALESCE(excluded.name, edu_systems.name),
                    system_type = excluded.system_type,
                    provider = excluded.provider,
                    provider_version = COALESCE(excluded.provider_version, edu_systems.provider_version),
                    base_url = COALESCE(excluded.base_url, edu_systems.base_url),
                    login_url = COALESCE(excluded.login_url, edu_systems.login_url),
                    sso_url = COALESCE(excluded.sso_url, edu_systems.sso_url),
                    vpn_url = COALESCE(excluded.vpn_url, edu_systems.vpn_url),
                    auth_type = excluded.auth_type,
                    login_execution_mode = excluded.login_execution_mode,
                    captcha_type = excluded.captcha_type,
                    requires_campus_network = excluded.requires_campus_network,
                    requires_vpn = excluded.requires_vpn,
                    status = excluded.status,
                    verification_status = excluded.verification_status,
                    supported_features = excluded.supported_features,
                    source = excluded.source,
                    notes = COALESCE(excluded.notes, edu_systems.notes),
                    is_mock = excluded.is_mock,
                    updated_at = excluded.updated_at
                """,
                (
                    sys_id, university_id, cur_school_code, system_key, cur_name, cur_system_type,
                    cur_provider, cur_pv, cur_base_url, cur_login_url, cur_sso_url, cur_vpn_url,
                    cur_auth_type, cur_exec_mode, cur_captcha,
                    cur_rcn, cur_vpn_req, cur_status, cur_verif,
                    features_json, cur_source, cur_notes, cur_is_mock,
                    created_at, now,
                ),
            )
        result = self.get_system_by_key(university_id, system_key)
        assert result is not None
        return result

    def ensure_default_system(self, university_id: str, school_code: Optional[str] = None) -> EduSystemRow:
        """确保学校有默认本科教务系统记录。"""
        existing = self.get_system_by_key(university_id, SYSTEM_KEY_UNDERGRADUATE_MAIN)
        if existing is not None:
            return existing
        return self.upsert_system(
            university_id=university_id,
            system_key=SYSTEM_KEY_UNDERGRADUATE_MAIN,
            school_code=school_code,
        )

    # ===== edu_system_configs (旧表兼容) =====

    def get_config_by_university(self, university_id: str) -> Optional[EduSystemConfigRow]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM edu_system_configs WHERE university_id = ?",
                (university_id,),
            ).fetchone()
        return EduSystemConfigRow.from_row(row) if row else None

    def upsert_config(self, university_id: str, **kwargs) -> EduSystemConfigRow:
        existing = self.get_config_by_university(university_id)
        now = _now_iso()
        cfg_id = existing.id if existing else f"edu_cfg_{hashlib.md5(university_id.encode()).hexdigest()[:16]}"

        def _merge(new, old, default=None):
            return new if new is not None else (old if old is not None else default)

        def _merge_url(url, url_status, old_url, old_status):
            merged_url = url if url is not None else old_url
            if url_status is not None:
                merged_status = url_status
            elif url is not None:
                merged_status = URL_NOT_DISCOVERED
            else:
                merged_status = old_status if old_status is not None else URL_NOT_DISCOVERED
            return merged_url, merged_status

        provider = kwargs.get("provider")
        system_type = kwargs.get("system_type")
        cur_provider = _merge(provider, existing.provider if existing else None, EDU_PROVIDER_UNKNOWN)
        cur_system_type = _merge(system_type, existing.system_type if existing else None, EDU_SYSTEM_UNKNOWN)
        cur_academic_url, cur_academic_status = _merge_url(
            kwargs.get("academic_system_url"), kwargs.get("academic_system_url_status"),
            existing.academic_system_url if existing else None,
            existing.academic_system_url_status if existing else None,
        )
        cur_undergrad_url, cur_undergrad_status = _merge_url(
            kwargs.get("undergrad_system_url"), kwargs.get("undergrad_system_url_status"),
            existing.undergrad_system_url if existing else None,
            existing.undergrad_system_url_status if existing else None,
        )
        cur_postgrad_url, cur_postgrad_status = _merge_url(
            kwargs.get("postgrad_system_url"), kwargs.get("postgrad_system_url_status"),
            existing.postgrad_system_url if existing else None,
            existing.postgrad_system_url_status if existing else None,
        )
        cur_sso_url, cur_sso_status = _merge_url(
            kwargs.get("sso_url"), kwargs.get("sso_url_status"),
            existing.sso_url if existing else None,
            existing.sso_url_status if existing else None,
        )
        cur_cas_url, cur_cas_status = _merge_url(
            kwargs.get("cas_url"), kwargs.get("cas_url_status"),
            existing.cas_url if existing else None,
            existing.cas_url_status if existing else None,
        )
        cur_webvpn_url, cur_webvpn_status = _merge_url(
            kwargs.get("webvpn_url"), kwargs.get("webvpn_url_status"),
            existing.webvpn_url if existing else None,
            existing.webvpn_url_status if existing else None,
        )
        cur_login_method = _merge(kwargs.get("login_method"), existing.login_method if existing else None, "unknown")
        cur_captcha = _merge(kwargs.get("captcha_type"), existing.captcha_type if existing else None, "unknown")
        cur_data_source = _merge(kwargs.get("data_source"), existing.data_source if existing else None, "unknown")
        cur_school_code = _merge(kwargs.get("school_code"), existing.school_code if existing else None, None)
        cur_notes = _merge(kwargs.get("notes"), existing.notes if existing else None, None)

        rcn = kwargs.get("requires_campus_network")
        if rcn is not None:
            cur_rcn: Optional[int] = 1 if rcn else 0
        elif existing is not None and existing.requires_campus_network is not None:
            cur_rcn = 1 if existing.requires_campus_network else 0
        else:
            cur_rcn = None

        sf = kwargs.get("supported_features")
        if sf is None:
            features_json = existing.supported_features if existing else "[]"
        else:
            features_json = json.dumps(sf, ensure_ascii=False)

        created_at = existing.created_at if existing else now

        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO edu_system_configs (
                    id, university_id, provider, system_type,
                    academic_system_url, academic_system_url_status,
                    undergrad_system_url, undergrad_system_url_status,
                    postgrad_system_url, postgrad_system_url_status,
                    sso_url, sso_url_status,
                    cas_url, cas_url_status,
                    webvpn_url, webvpn_url_status,
                    login_method, captcha_type, requires_campus_network,
                    supported_features, school_code, notes, data_source,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(university_id) DO UPDATE SET
                    provider = excluded.provider,
                    system_type = excluded.system_type,
                    academic_system_url = excluded.academic_system_url,
                    academic_system_url_status = excluded.academic_system_url_status,
                    undergrad_system_url = excluded.undergrad_system_url,
                    undergrad_system_url_status = excluded.undergrad_system_url_status,
                    postgrad_system_url = excluded.postgrad_system_url,
                    postgrad_system_url_status = excluded.postgrad_system_url_status,
                    sso_url = excluded.sso_url,
                    sso_url_status = excluded.sso_url_status,
                    cas_url = excluded.cas_url,
                    cas_url_status = excluded.cas_url_status,
                    webvpn_url = excluded.webvpn_url,
                    webvpn_url_status = excluded.webvpn_url_status,
                    login_method = excluded.login_method,
                    captcha_type = excluded.captcha_type,
                    requires_campus_network = excluded.requires_campus_network,
                    supported_features = excluded.supported_features,
                    school_code = excluded.school_code,
                    notes = excluded.notes,
                    data_source = excluded.data_source,
                    updated_at = excluded.updated_at
                """,
                (
                    cfg_id, university_id, cur_provider, cur_system_type,
                    cur_academic_url, cur_academic_status,
                    cur_undergrad_url, cur_undergrad_status,
                    cur_postgrad_url, cur_postgrad_status,
                    cur_sso_url, cur_sso_status,
                    cur_cas_url, cur_cas_status,
                    cur_webvpn_url, cur_webvpn_status,
                    cur_login_method, cur_captcha, cur_rcn,
                    features_json, cur_school_code, cur_notes, cur_data_source,
                    created_at, now,
                ),
            )
        result = self.get_config_by_university(university_id)
        assert result is not None
        return result

    # ===== edu_bindings =====

    def get_binding_by_user(self, user_id: str, edu_system_id: Optional[str] = None) -> Optional[EduBindingRow]:
        with self._db.query() as conn:
            if edu_system_id:
                row = conn.execute(
                    "SELECT * FROM edu_bindings WHERE user_id = ? AND edu_system_id = ?",
                    (user_id, edu_system_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM edu_bindings WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
                    (user_id,),
                ).fetchone()
        return EduBindingRow.from_row(row) if row else None

    def list_bindings_by_user(self, user_id: str) -> list[EduBindingRow]:
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT * FROM edu_bindings WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [EduBindingRow.from_row(row) for row in rows]

    def upsert_binding(
        self,
        *,
        user_id: str,
        university_id: str,
        provider: str,
        edu_system_id: Optional[str] = None,
        system_type: str = "undergrad",
        external_student_id: Optional[str] = None,
        external_student_name: Optional[str] = None,
        connection_status: str = BINDING_ACTIVE,
        session_type: Optional[str] = None,
        credential_ref: Optional[str] = None,
        last_authenticated_at: Optional[str] = None,
        session_expires_at: Optional[str] = None,
        last_synced_at: Optional[str] = None,
        last_sync_status: Optional[str] = None,
        last_error: Optional[str] = None,
    ) -> EduBindingRow:
        existing = self.get_binding_by_user(user_id, edu_system_id)
        now = _now_iso()
        binding_id = existing.id if existing else f"edu_bind_{hashlib.md5(f'{user_id}:{edu_system_id}'.encode()).hexdigest()[:16]}"
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO edu_bindings (
                    id, user_id, edu_system_id, university_id, provider, system_type,
                    external_student_id, external_student_name, connection_status,
                    session_type, credential_ref, last_authenticated_at, session_expires_at,
                    last_synced_at, last_sync_status, last_error,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(user_id, edu_system_id) DO UPDATE SET
                    university_id = excluded.university_id,
                    provider = excluded.provider,
                    system_type = excluded.system_type,
                    external_student_id = COALESCE(excluded.external_student_id, edu_bindings.external_student_id),
                    external_student_name = COALESCE(excluded.external_student_name, edu_bindings.external_student_name),
                    connection_status = excluded.connection_status,
                    session_type = COALESCE(excluded.session_type, edu_bindings.session_type),
                    credential_ref = COALESCE(excluded.credential_ref, edu_bindings.credential_ref),
                    last_authenticated_at = COALESCE(excluded.last_authenticated_at, edu_bindings.last_authenticated_at),
                    session_expires_at = COALESCE(excluded.session_expires_at, edu_bindings.session_expires_at),
                    last_synced_at = COALESCE(excluded.last_synced_at, edu_bindings.last_synced_at),
                    last_sync_status = COALESCE(excluded.last_sync_status, edu_bindings.last_sync_status),
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
                """,
                (
                    binding_id, user_id, edu_system_id, university_id, provider, system_type,
                    external_student_id, external_student_name, connection_status,
                    session_type, credential_ref, last_authenticated_at, session_expires_at,
                    last_synced_at, last_sync_status, last_error,
                    existing.created_at if existing else now,
                    now,
                ),
            )
        result = self.get_binding_by_user(user_id, edu_system_id)
        assert result is not None
        return result

    def update_binding_status(
        self,
        user_id: str,
        *,
        edu_system_id: Optional[str] = None,
        connection_status: Optional[str] = None,
        last_synced_at: Optional[str] = None,
        last_sync_status: Optional[str] = None,
        last_error: Optional[str] = None,
    ) -> Optional[EduBindingRow]:
        now = _now_iso()
        with self._db.transaction() as conn:
            if edu_system_id:
                conn.execute(
                    """
                    UPDATE edu_bindings SET
                        connection_status = COALESCE(?, connection_status),
                        last_synced_at = COALESCE(?, last_synced_at),
                        last_sync_status = COALESCE(?, last_sync_status),
                        last_error = ?,
                        updated_at = ?
                    WHERE user_id = ? AND edu_system_id = ?
                    """,
                    (connection_status, last_synced_at, last_sync_status, last_error, now, user_id, edu_system_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE edu_bindings SET
                        connection_status = COALESCE(?, connection_status),
                        last_synced_at = COALESCE(?, last_synced_at),
                        last_sync_status = COALESCE(?, last_sync_status),
                        last_error = ?,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (connection_status, last_synced_at, last_sync_status, last_error, now, user_id),
                )
        return self.get_binding_by_user(user_id, edu_system_id)

    def delete_binding(self, user_id: str, edu_system_id: Optional[str] = None) -> None:
        with self._db.transaction() as conn:
            if edu_system_id:
                conn.execute(
                    "DELETE FROM edu_bindings WHERE user_id = ? AND edu_system_id = ?",
                    (user_id, edu_system_id),
                )
            else:
                conn.execute("DELETE FROM edu_bindings WHERE user_id = ?", (user_id,))

    # ===== edu_connections =====

    def create_connection(
        self,
        *,
        user_id: str,
        edu_system_id: str,
        university_id: str,
        provider: str = EDU_PROVIDER_UNKNOWN,
        login_execution_mode: str = LOGIN_EXEC_UNSUPPORTED,
        portal_url: Optional[str] = None,
    ) -> EduConnectionRow:
        now = _now_iso()
        conn_id = f"edu_conn_{hashlib.md5(f'{user_id}:{edu_system_id}:{now}'.encode()).hexdigest()[:16]}"
        initial_state = (
            CONN_WAITING_USER_LOGIN
            if login_execution_mode == "client_webview"
            else CONN_AUTH_REQUIRED
            if login_execution_mode == "backend_http"
            else CONN_IDLE
        )
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO edu_connections (
                    id, user_id, edu_system_id, university_id, state,
                    provider, login_execution_mode, portal_url, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (conn_id, user_id, edu_system_id, university_id, initial_state, provider, login_execution_mode, portal_url, now, now),
            )
        with self._db.query() as conn:
            row = conn.execute("SELECT * FROM edu_connections WHERE id = ?", (conn_id,)).fetchone()
        return EduConnectionRow.from_row(row)

    def get_connection(self, connection_id: str) -> Optional[EduConnectionRow]:
        with self._db.query() as conn:
            row = conn.execute("SELECT * FROM edu_connections WHERE id = ?", (connection_id,)).fetchone()
        return EduConnectionRow.from_row(row) if row else None

    def get_active_connection_by_user(self, user_id: str, edu_system_id: Optional[str] = None) -> Optional[EduConnectionRow]:
        """查找用户的活跃连接（非终态）。"""
        active_states = (
            "idle", "auth_required", "waiting_user_login", "connecting",
            "authenticated", "connected", "syncing",
        )
        placeholders = ",".join("?" for _ in active_states)
        with self._db.query() as conn:
            if edu_system_id:
                row = conn.execute(
                    f"SELECT * FROM edu_connections WHERE user_id = ? AND edu_system_id = ? AND state IN ({placeholders}) ORDER BY updated_at DESC LIMIT 1",
                    (user_id, edu_system_id, *active_states),
                ).fetchone()
            else:
                row = conn.execute(
                    f"SELECT * FROM edu_connections WHERE user_id = ? AND state IN ({placeholders}) ORDER BY updated_at DESC LIMIT 1",
                    (user_id, *active_states),
                ).fetchone()
        return EduConnectionRow.from_row(row) if row else None

    def update_connection_state(
        self,
        connection_id: str,
        *,
        state: str,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        external_student_id: Optional[str] = None,
        external_student_name: Optional[str] = None,
        credential_ref: Optional[str] = None,
    ) -> Optional[EduConnectionRow]:
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """
                UPDATE edu_connections SET
                    state = ?,
                    error_code = ?,
                    error_message = ?,
                    external_student_id = COALESCE(?, external_student_id),
                    external_student_name = COALESCE(?, external_student_name),
                    credential_ref = COALESCE(?, credential_ref),
                    updated_at = ?
                WHERE id = ?
                """,
                (state, error_code, error_message, external_student_id, external_student_name, credential_ref, now, connection_id),
            )
        return self.get_connection(connection_id)

    # ===== edu_sync_records =====

    def create_sync_record(
        self,
        *,
        binding_id: str,
        user_id: str,
        sync_type: str,
        status: str = "pending",
        adapter: Optional[str] = None,
        adapter_version: Optional[str] = None,
    ) -> EduSyncRecordRow:
        now = _now_iso()
        record_id = f"edu_sync_{hashlib.md5(f'{binding_id}{sync_type}{now}'.encode()).hexdigest()[:16]}"
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO edu_sync_records (
                    id, binding_id, user_id, sync_type, status,
                    items_count, adapter, adapter_version, error_code, error_message,
                    started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, NULL, NULL, ?, NULL)
                """,
                (record_id, binding_id, user_id, sync_type, status, adapter, adapter_version, now),
            )
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM edu_sync_records WHERE id = ?",
                (record_id,),
            ).fetchone()
        return EduSyncRecordRow.from_row(row)

    def finish_sync_record(
        self,
        record_id: str,
        *,
        status: str,
        items_count: int = 0,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """
                UPDATE edu_sync_records SET
                    status = ?, items_count = ?, error_code = ?, error_message = ?, finished_at = ?
                WHERE id = ?
                """,
                (status, items_count, error_code, error_message, now, record_id),
            )

    def list_sync_records(
        self,
        user_id: str,
        *,
        limit: int = 20,
    ) -> list[EduSyncRecordRow]:
        with self._db.query() as conn:
            rows = conn.execute(
                """
                SELECT * FROM edu_sync_records
                WHERE user_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [EduSyncRecordRow.from_row(row) for row in rows]


__all__ = ["EduRepository"]
