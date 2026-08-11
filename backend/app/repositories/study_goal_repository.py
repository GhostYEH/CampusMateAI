from __future__ import annotations

from datetime import datetime, timezone

from ..database.sqlite_db import Database
from ..models.study_goal import StudyGoalRow


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StudyGoalRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_or_create(self, user_id: str) -> StudyGoalRow:
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO study_goals (user_id, target_minutes, updated_at) VALUES (?, ?, ?)",
                (user_id, 60, now),
            )
            row = conn.execute(
                "SELECT user_id, target_minutes, updated_at FROM study_goals WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return StudyGoalRow.from_row(row)

    def set_target(self, user_id: str, target_minutes: int) -> StudyGoalRow:
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO study_goals (user_id, target_minutes, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET target_minutes = excluded.target_minutes, updated_at = excluded.updated_at",
                (user_id, target_minutes, now),
            )
            row = conn.execute(
                "SELECT user_id, target_minutes, updated_at FROM study_goals WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return StudyGoalRow.from_row(row)
