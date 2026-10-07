"""User-scoped access to manual exams shared by student and review workflows."""

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..database.sqlite_db import Database

_EDITABLE_COLUMNS = (
    "course_name",
    "exam_date",
    "start_time",
    "end_time",
    "location",
    "seat_number",
    "exam_type",
    "reminder_enabled",
    "notes",
)


def _values(fields: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(
        int(fields[column]) if column == "reminder_enabled" else fields[column]
        for column in _EDITABLE_COLUMNS
    )


class StudentExamRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def list_exams(self, *, user_id: str) -> list[dict[str, Any]]:
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT * FROM student_exams WHERE user_id = ? ORDER BY exam_date, start_time",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_exam(self, *, user_id: str, fields: Mapping[str, Any]) -> dict[str, Any]:
        exam_id = f"exam_{uuid4().hex[:16]}"
        now = datetime.now(timezone.utc).isoformat()
        columns = ("id", "user_id", *_EDITABLE_COLUMNS, "created_at", "updated_at")
        placeholders = ",".join("?" for _ in columns)
        with self._db.transaction() as conn:
            conn.execute(
                f"INSERT INTO student_exams ({','.join(columns)}) VALUES ({placeholders})",
                (exam_id, user_id, *_values(fields), now, now),
            )
            row = conn.execute(
                "SELECT * FROM student_exams WHERE id = ? AND user_id = ?",
                (exam_id, user_id),
            ).fetchone()
        return dict(row)

    def update_exam(
        self, *, exam_id: str, user_id: str, fields: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        assignments = ",".join(f"{column}=?" for column in _EDITABLE_COLUMNS)
        now = datetime.now(timezone.utc).isoformat()
        with self._db.transaction() as conn:
            result = conn.execute(
                f"UPDATE student_exams SET {assignments},updated_at=? WHERE id=? AND user_id=?",
                (*_values(fields), now, exam_id, user_id),
            )
            if result.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM student_exams WHERE id = ? AND user_id = ?",
                (exam_id, user_id),
            ).fetchone()
        return dict(row)

    def delete_exam(self, *, exam_id: str, user_id: str) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "DELETE FROM student_exams WHERE id = ? AND user_id = ?",
                (exam_id, user_id),
            )

    def owned_ids(self, *, user_id: str, exam_ids: list[str]) -> set[str]:
        if not exam_ids:
            return set()
        placeholders = ",".join("?" for _ in exam_ids)
        with self._db.query() as conn:
            rows = conn.execute(
                f"SELECT id FROM student_exams WHERE user_id = ? AND id IN ({placeholders})",
                (user_id, *exam_ids),
            ).fetchall()
        return {row["id"] for row in rows}

    def list_for_context(
        self, *, user_id: str, exam_ids: list[str]
    ) -> list[dict[str, Any]]:
        if not exam_ids:
            return []
        placeholders = ",".join("?" for _ in exam_ids)
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT id, course_name, exam_date, start_time, end_time, location, exam_type, notes "
                f"FROM student_exams WHERE user_id = ? AND id IN ({placeholders}) ORDER BY exam_date ASC",
                (user_id, *exam_ids),
            ).fetchall()
        return [dict(row) for row in rows]
