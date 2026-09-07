from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..database.sqlite_db import Database
from ..models.study_checkin import StudyCheckinRow


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StudyCheckinRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_today(
        self, user_id: str, *, scene: str, mood: str | None = None
    ) -> tuple[StudyCheckinRow, bool]:
        now = _now_iso()
        date_key = datetime.now(timezone.utc).date().isoformat()
        with self._db.transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM study_checkins WHERE user_id = ? AND date_key = ?",
                (user_id, date_key),
            ).fetchone()
            if existing:
                return StudyCheckinRow.from_row(existing), False

            checkin_id = f"chk_{uuid.uuid4().hex[:16]}"
            conn.execute(
                """INSERT INTO study_checkins
                   (id, user_id, date_key, scene, mood, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (checkin_id, user_id, date_key, scene, mood, now),
            )
            row = conn.execute(
                "SELECT * FROM study_checkins WHERE id = ?", (checkin_id,)
            ).fetchone()
        return StudyCheckinRow.from_row(row), True

    def list_checkins(self, user_id: str) -> list[StudyCheckinRow]:
        with self._db.query() as conn:
            rows = conn.execute(
                """SELECT * FROM study_checkins
                   WHERE user_id = ? ORDER BY date_key DESC""",
                (user_id,),
            ).fetchall()
        return [StudyCheckinRow.from_row(row) for row in rows]


__all__ = ["StudyCheckinRepository"]
