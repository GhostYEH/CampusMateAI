from __future__ import annotations

import json
from datetime import datetime, timezone

from ..core.security import decrypt, encrypt
from ..database.sqlite_db import Database


class ChaoxingRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save_credentials(self, user_id: str, cookies: dict):
        encrypted_cookies = encrypt(json.dumps(cookies))
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO chaoxing_credentials (user_id, encrypted_cookies, updated_at) VALUES (?, ?, ?)",
                (user_id, encrypted_cookies, datetime.now(timezone.utc).isoformat()),
            )

    def get_credentials(self, user_id: str) -> dict | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT encrypted_cookies FROM chaoxing_credentials WHERE user_id = ?", (user_id,)
            ).fetchone()
        if not row:
            return None
        try:
            decrypted_cookies = decrypt(row["encrypted_cookies"])
            return json.loads(decrypted_cookies)
        except Exception:
            return None
