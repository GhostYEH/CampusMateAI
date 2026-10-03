"""SQLite data access for RefreshTokenRepository."""
from __future__ import annotations

from typing import Optional
from ..database.sqlite_db import Database
from ..models.multi_role import RefreshTokenRow
from ._multi_role_common import _new_id, _now_iso


class RefreshTokenRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_token(
        self, *, user_id: str, token_hash: str, expires_at: str
    ) -> RefreshTokenRow:
        tid = _new_id("rft")
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, revoked, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (tid, user_id, token_hash, expires_at, 0, now),
            )
        return RefreshTokenRow(
            id=tid, user_id=user_id, token_hash=token_hash,
            expires_at=expires_at, revoked=False, created_at=now,
        )

    def get_by_hash(self, token_hash: str) -> Optional[RefreshTokenRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM refresh_tokens WHERE token_hash = ?", (token_hash,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return RefreshTokenRow(
                id=row["id"], user_id=row["user_id"], token_hash=row["token_hash"],
                expires_at=row["expires_at"], revoked=bool(row["revoked"]),
                created_at=row["created_at"],
            )

    def revoke(self, token_hash: str) -> bool:
        with self._db.transaction() as conn:
            cur = conn.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE token_hash = ? AND revoked = 0",
                (token_hash,),
            )
            return cur.rowcount > 0

    def revoke_all_for_user(self, user_id: str) -> int:
        with self._db.transaction() as conn:
            cur = conn.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ? AND revoked = 0",
                (user_id,),
            )
            return cur.rowcount

    def cleanup_expired(self, now_iso: str) -> int:
        with self._db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM refresh_tokens WHERE expires_at < ?", (now_iso,)
            )
            return cur.rowcount
