from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from ..database.sqlite_db import Database


class NoticeAutomationRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_ingest_result(self, user_id: str, client_fingerprint: str) -> Optional[str]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT response_json FROM notice_ingest_results WHERE user_id = ? AND client_fingerprint = ?",
                (user_id, client_fingerprint),
            ).fetchone()
            return str(row["response_json"]) if row else None

    def save_ingest_result(self, user_id: str, client_fingerprint: str, response_json: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO notice_ingest_results
                   (user_id, client_fingerprint, response_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, client_fingerprint) DO UPDATE SET
                     response_json = excluded.response_json, updated_at = excluded.updated_at""",
                (user_id, client_fingerprint, response_json, now, now),
            )
            conn.execute(
                "DELETE FROM notice_ingest_claims WHERE user_id = ? AND client_fingerprint = ?",
                (user_id, client_fingerprint),
            )

    def try_claim_ingest(self, user_id: str, client_fingerprint: str) -> bool:
        now = datetime.now(timezone.utc)
        stale_before = (now - timedelta(minutes=2)).isoformat()
        with self._db.transaction() as conn:
            conn.execute(
                "DELETE FROM notice_ingest_claims WHERE claimed_at < ?", (stale_before,)
            )
            cursor = conn.execute(
                "INSERT OR IGNORE INTO notice_ingest_claims(user_id, client_fingerprint, claimed_at) VALUES (?, ?, ?)",
                (user_id, client_fingerprint, now.isoformat()),
            )
            return cursor.rowcount == 1

    def release_ingest_claim(self, user_id: str, client_fingerprint: str) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "DELETE FROM notice_ingest_claims WHERE user_id = ? AND client_fingerprint = ?",
                (user_id, client_fingerprint),
            )

    def get_ai_cache(self, cache_key: str) -> Optional[str]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT response_json FROM notice_ai_cache WHERE cache_key = ?", (cache_key,)
            ).fetchone()
            return str(row["response_json"]) if row else None

    def save_ai_cache(self, cache_key: str, response_json: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO notice_ai_cache(cache_key, response_json, created_at) VALUES (?, ?, ?)",
                (cache_key, response_json, now),
            )
