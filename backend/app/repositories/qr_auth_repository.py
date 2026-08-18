"""QR 扫码登录与可信设备仓库层。

设计原则:
- 沿用现有 Database 包装(transaction / query 上下文)。
- 写操作均使用 transaction，保证原子性。
- token 仅保存 SHA-256 哈希，不保存明文。
- 状态迁移使用原子 UPDATE ... WHERE status=... 保证并发安全。
- 不在这里抛业务异常(留给 route 层)，仅返回 Optional / row。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from ..database.sqlite_db import Database
from ..models.qr_auth import QrLoginSessionRow, TrustedDeviceRow


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class QrLoginSessionRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_session(
        self,
        *,
        scan_token_hash: str,
        browser_token_hash: str,
        device_id: Optional[str],
        browser_name: Optional[str],
        os_name: Optional[str],
        device_label: Optional[str],
        user_agent: Optional[str],
        expires_at: str,
    ) -> QrLoginSessionRow:
        sid = _new_id("qrs")
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO qr_login_sessions (
                    id, scan_token_hash, browser_token_hash, status,
                    device_id, browser_name, os_name, device_label, user_agent,
                    trust_device, created_at, expires_at
                ) VALUES (?,?,?,?,?,?,?,?,?,0,?,?)
                """,
                (
                    sid, scan_token_hash, browser_token_hash, "PENDING",
                    device_id, browser_name, os_name, device_label, user_agent,
                    now, expires_at,
                ),
            )
        return self.get_session(sid)  # type: ignore[return-value]

    def get_session(self, session_id: str) -> Optional[QrLoginSessionRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM qr_login_sessions WHERE id = ?", (session_id,)
            )
            row = cur.fetchone()
            return QrLoginSessionRow.from_row(row) if row else None

    def get_by_scan_token_hash(self, scan_token_hash: str) -> Optional[QrLoginSessionRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM qr_login_sessions WHERE scan_token_hash = ?",
                (scan_token_hash,),
            )
            row = cur.fetchone()
            return QrLoginSessionRow.from_row(row) if row else None

    def mark_scanned(
        self,
        session_id: str,
        *,
        user_id: str,
    ) -> Optional[QrLoginSessionRow]:
        """原子地将 PENDING -> SCANNED，绑定 user_id。

        返回更新后的 row；若状态不是 PENDING 则返回 None(调用方据此判断冲突)。
        """
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """
                UPDATE qr_login_sessions
                SET status = 'SCANNED', user_id = ?, scanned_at = ?
                WHERE id = ? AND status = 'PENDING'
                """,
                (user_id, now, session_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get_session(session_id)

    def mark_confirmed(
        self,
        session_id: str,
        *,
        user_id: str,
        trust_device: bool,
    ) -> Optional[QrLoginSessionRow]:
        """原子地将 SCANNED -> CONFIRMED，校验 user_id 一致。

        返回更新后的 row；若状态不是 SCANNED 或 user_id 不匹配则返回 None。
        """
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """
                UPDATE qr_login_sessions
                SET status = 'CONFIRMED', trust_device = ?, confirmed_at = ?
                WHERE id = ? AND status = 'SCANNED' AND user_id = ?
                """,
                (int(trust_device), now, session_id, user_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get_session(session_id)

    def mark_cancelled(
        self,
        session_id: str,
        *,
        user_id: str,
    ) -> Optional[QrLoginSessionRow]:
        """原子地将 SCANNED/PENDING -> CANCELLED，校验 user_id(若已绑定)。

        返回更新后的 row；若状态不允许取消则返回 None。
        """
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """
                UPDATE qr_login_sessions
                SET status = 'CANCELLED', cancelled_at = ?
                WHERE id = ? AND status IN ('PENDING', 'SCANNED')
                  AND (user_id IS NULL OR user_id = ?)
                """,
                (now, session_id, user_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get_session(session_id)

    def mark_consumed(
        self,
        session_id: str,
        *,
        browser_token_hash: str,
    ) -> Optional[QrLoginSessionRow]:
        """原子地将 CONFIRMED -> CONSUMED，校验 browser_token_hash。

        返回更新后的 row；若状态不是 CONFIRMED 或 browser_token 不匹配则返回 None。
        这是 exchange 的核心原子操作，防止重放与并发双发。
        """
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """
                UPDATE qr_login_sessions
                SET status = 'CONSUMED', consumed_at = ?
                WHERE id = ? AND status = 'CONFIRMED' AND browser_token_hash = ?
                """,
                (now, session_id, browser_token_hash),
            )
            if cur.rowcount == 0:
                return None
        return self.get_session(session_id)

    def mark_expired(self, session_id: str) -> None:
        """将未完成的状态标记为 EXPIRED(惰性过期)。"""
        with self._db.transaction() as conn:
            conn.execute(
                """
                UPDATE qr_login_sessions
                SET status = 'EXPIRED'
                WHERE id = ? AND status IN ('PENDING', 'SCANNED')
                """,
                (session_id,),
            )

    def cleanup_expired(self, now_iso: str, batch_size: int = 50) -> int:
        """删除已过期且已终态的记录，返回删除条数。"""
        with self._db.transaction() as conn:
            cur = conn.execute(
                """
                DELETE FROM qr_login_sessions
                WHERE id IN (
                    SELECT id FROM qr_login_sessions
                    WHERE expires_at < ? AND status IN ('CONSUMED', 'CANCELLED', 'EXPIRED')
                    LIMIT ?
                )
                """,
                (now_iso, batch_size),
            )
            return cur.rowcount

    def count_recent_by_device(
        self,
        device_id: str,
        since_iso: str,
    ) -> int:
        """统计指定 device_id 在 since_iso 之后创建的 session 数(用于简单防刷)。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """
                SELECT COUNT(*) AS n FROM qr_login_sessions
                WHERE device_id = ? AND created_at >= ?
                """,
                (device_id, since_iso),
            )
            return int(cur.fetchone()["n"])


class TrustedDeviceRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_device(
        self,
        *,
        user_id: str,
        device_id: str,
        token_hash: str,
        device_name: Optional[str],
        browser_name: Optional[str],
        os_name: Optional[str],
        user_agent: Optional[str],
        expires_at: str,
    ) -> TrustedDeviceRow:
        tid = _new_id("tdev")
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO trusted_devices (
                    id, user_id, device_id, token_hash,
                    device_name, browser_name, os_name, user_agent,
                    created_at, last_used_at, expires_at, revoked_at
                ) VALUES (?,?,?,?,?,?,?,NULL,?,NULL,?,NULL)
                """,
                (
                    tid, user_id, device_id, token_hash,
                    device_name, browser_name, os_name,
                    now, expires_at,
                ),
            )
        return self.get_by_id(tid)  # type: ignore[return-value]

    def get_by_id(self, device_id_pk: str) -> Optional[TrustedDeviceRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM trusted_devices WHERE id = ?", (device_id_pk,)
            )
            row = cur.fetchone()
            return TrustedDeviceRow.from_row(row) if row else None

    def get_by_token_hash(self, token_hash: str) -> Optional[TrustedDeviceRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM trusted_devices WHERE token_hash = ?", (token_hash,)
            )
            row = cur.fetchone()
            return TrustedDeviceRow.from_row(row) if row else None

    def get_active_by_user_and_device(
        self,
        user_id: str,
        device_id: str,
    ) -> Optional[TrustedDeviceRow]:
        """获取用户在某设备上未撤销、未过期的可信记录。"""
        now = _now_iso()
        with self._db.query() as conn:
            cur = conn.execute(
                """
                SELECT * FROM trusted_devices
                WHERE user_id = ? AND device_id = ?
                  AND revoked_at IS NULL AND expires_at > ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (user_id, device_id, now),
            )
            row = cur.fetchone()
            return TrustedDeviceRow.from_row(row) if row else None

    def update_last_used(self, device_id_pk: str) -> None:
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE trusted_devices SET last_used_at = ? WHERE id = ?",
                (now, device_id_pk),
            )

    def revoke(self, device_id_pk: str) -> bool:
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                "UPDATE trusted_devices SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (now, device_id_pk),
            )
            return cur.rowcount > 0

    def revoke_by_token_hash(self, token_hash: str) -> bool:
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                "UPDATE trusted_devices SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
                (now, token_hash),
            )
            return cur.rowcount > 0

    def revoke_all_for_user(self, user_id: str) -> int:
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                "UPDATE trusted_devices SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (now, user_id),
            )
            return cur.rowcount

    def cleanup_expired(self, now_iso: str, batch_size: int = 100) -> int:
        with self._db.transaction() as conn:
            cur = conn.execute(
                """
                DELETE FROM trusted_devices
                WHERE id IN (
                    SELECT id FROM trusted_devices
                    WHERE expires_at < ? AND revoked_at IS NOT NULL
                    LIMIT ?
                )
                """,
                (now_iso, batch_size),
            )
            return cur.rowcount