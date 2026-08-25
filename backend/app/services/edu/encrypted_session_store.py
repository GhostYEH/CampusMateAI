"""AES-GCM encrypted SQLite implementation of :class:`EduSessionStore`.

Only non-secret lookup metadata and a versioned authenticated-encryption
envelope are persisted.  Adapter state (cookies, CSRF tokens, user agent, and
URLs) exists on disk only inside the ciphertext.
"""
from __future__ import annotations

import base64
import binascii
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ...database.sqlite_db import Database
from ...models.edu import SESSION_BACKEND_COOKIE
from .session import EduSession, EduSessionStore


ENVELOPE_VERSION = 1
_NONCE_BYTES = 12
_PASSWORD_KEYS = {"password", "passwd", "pwd"}


class EncryptedSqliteEduSessionStore(EduSessionStore):
    """Persist recoverable education sessions as authenticated ciphertext."""

    def __init__(
        self,
        *,
        db: Database,
        encryption_key_base64: str,
        key_id: str,
        session_ttl_seconds: int = 1800,
    ) -> None:
        try:
            key = base64.b64decode(encryption_key_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(
                "EDU_SESSION_ENCRYPTION_KEY must be base64-encoded 32 bytes"
            ) from exc
        if len(key) != 32:
            raise ValueError(
                "EDU_SESSION_ENCRYPTION_KEY must be base64-encoded 32 bytes"
            )
        if not key_id:
            raise ValueError("EDU_SESSION_ENCRYPTION_KEY_ID must not be empty")

        self._db = db
        self._aesgcm = AESGCM(key)
        self._key_id = key_id
        self._ttl = session_ttl_seconds
        self._remove_invalid_records()

    def create_session(
        self,
        *,
        user_id: str,
        university_id: str,
        provider: str,
        system_type: str,
        session_type: str = SESSION_BACKEND_COOKIE,
        external_student_id: Optional[str] = None,
        internal: Optional[dict] = None,
        ttl_seconds: Optional[int] = None,
    ) -> EduSession:
        adapter_state = internal or {}
        self._assert_no_password(adapter_state)

        session_id = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc)
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl
        expires_at = (now + timedelta(seconds=ttl)).isoformat()
        session = EduSession(
            session_id=session_id,
            user_id=user_id,
            university_id=university_id,
            provider=provider,
            system_type=system_type,
            session_type=session_type,
            external_student_id=external_student_id,
            created_at=now.isoformat(),
            expires_at=expires_at,
            _internal=adapter_state,
        )
        plaintext = json.dumps(
            {
                "schema_version": ENVELOPE_VERSION,
                "session": {
                    "session_id": session.session_id,
                    "user_id": session.user_id,
                    "university_id": session.university_id,
                    "provider": session.provider,
                    "system_type": session.system_type,
                    "session_type": session.session_type,
                    "external_student_id": session.external_student_id,
                    "created_at": session.created_at,
                    "expires_at": session.expires_at,
                    "internal": session._internal,
                },
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        nonce = secrets.token_bytes(_NONCE_BYTES)
        aad = self._aad(
            user_id=user_id,
            connection_id=session_id,
            expires_at=expires_at,
            created_at=session.created_at,
        )
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, aad)

        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO edu_sessions (
                    connection_id, user_id, envelope_version, key_id,
                    nonce, ciphertext, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    user_id,
                    ENVELOPE_VERSION,
                    self._key_id,
                    nonce,
                    ciphertext,
                    expires_at,
                    session.created_at,
                ),
            )
        return session

    def get_session(self, session_id: str) -> Optional[EduSession]:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM edu_sessions WHERE connection_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            session = self._decode_row(row)
            if session is None:
                conn.execute(
                    "DELETE FROM edu_sessions WHERE connection_id = ?",
                    (session_id,),
                )
            return session

    def get_session_by_user(self, user_id: str) -> Optional[EduSession]:
        with self._db.transaction() as conn:
            rows = conn.execute(
                """
                SELECT * FROM edu_sessions
                WHERE user_id = ?
                ORDER BY created_at, connection_id
                """,
                (user_id,),
            ).fetchall()
            for row in rows:
                session = self._decode_row(row)
                if session is not None:
                    return session
                conn.execute(
                    "DELETE FROM edu_sessions WHERE connection_id = ?",
                    (row["connection_id"],),
                )
            return None

    def destroy_session(self, session_id: str) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "DELETE FROM edu_sessions WHERE connection_id = ?",
                (session_id,),
            )

    def destroy_user_sessions(self, user_id: str) -> None:
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM edu_sessions WHERE user_id = ?", (user_id,))

    def cleanup_expired(self, now: Optional[datetime] = None) -> int:
        """Delete expired or otherwise unreadable envelopes."""
        check_time = now or datetime.now(timezone.utc)
        removed = 0
        with self._db.transaction() as conn:
            rows = conn.execute("SELECT * FROM edu_sessions").fetchall()
            for row in rows:
                if self._decode_row(row, now=check_time) is None:
                    conn.execute(
                        "DELETE FROM edu_sessions WHERE connection_id = ?",
                        (row["connection_id"],),
                    )
                    removed += 1
        return removed

    def _remove_invalid_records(self) -> None:
        self.cleanup_expired()

    def _decode_row(
        self, row: Any, *, now: Optional[datetime] = None
    ) -> Optional[EduSession]:
        try:
            if row["envelope_version"] != ENVELOPE_VERSION:
                return None
            if row["key_id"] != self._key_id:
                return None
            expires_at = datetime.fromisoformat(row["expires_at"])
            check_time = now or datetime.now(timezone.utc)
            if expires_at <= check_time:
                return None

            aad = self._aad(
                user_id=row["user_id"],
                connection_id=row["connection_id"],
                expires_at=row["expires_at"],
                created_at=row["created_at"],
            )
            plaintext = self._aesgcm.decrypt(
                bytes(row["nonce"]), bytes(row["ciphertext"]), aad
            )
            payload = json.loads(plaintext.decode("utf-8"))
            if payload.get("schema_version") != ENVELOPE_VERSION:
                return None
            data = payload["session"]
            if (
                data["session_id"] != row["connection_id"]
                or data["user_id"] != row["user_id"]
                or data["expires_at"] != row["expires_at"]
                or data["created_at"] != row["created_at"]
            ):
                return None
            internal = data.get("internal")
            if not isinstance(internal, dict):
                return None
            self._assert_no_password(internal)
            return EduSession(
                session_id=data["session_id"],
                user_id=data["user_id"],
                university_id=data["university_id"],
                provider=data["provider"],
                system_type=data["system_type"],
                session_type=data["session_type"],
                external_student_id=data.get("external_student_id"),
                created_at=data["created_at"],
                expires_at=data["expires_at"],
                _internal=internal,
            )
        except Exception:
            return None

    def _aad(
        self,
        *,
        user_id: str,
        connection_id: str,
        expires_at: str,
        created_at: str,
    ) -> bytes:
        return json.dumps(
            {
                "connection_id": connection_id,
                "created_at": created_at,
                "expires_at": expires_at,
                "key_id": self._key_id,
                "schema_version": ENVELOPE_VERSION,
                "user_id": user_id,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    @classmethod
    def _assert_no_password(cls, value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if str(key).lower().replace("_", "") in _PASSWORD_KEYS:
                    raise ValueError("password fields must not be stored in education sessions")
                cls._assert_no_password(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                cls._assert_no_password(nested)


EncryptedEduSessionStore = EncryptedSqliteEduSessionStore


__all__ = [
    "EncryptedEduSessionStore",
    "EncryptedSqliteEduSessionStore",
    "ENVELOPE_VERSION",
]
