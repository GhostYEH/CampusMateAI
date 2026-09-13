from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database.sqlite_db import Database
from ..models.student_goal import StudentGoalProgressRow, StudentGoalRow


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class StudentGoalRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_goal(
        self,
        *,
        user_id: str,
        name: str,
        category: str,
        target_date: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        initial_progress_percent: float = 0.0,
        milestone_count: int = 0,
    ) -> tuple[StudentGoalRow, bool]:
        now = _now_iso()
        with self._db.transaction() as conn:
            if idempotency_key:
                existing = conn.execute(
                    "SELECT goal_id FROM student_goals WHERE user_id=? AND idempotency_key=?",
                    (user_id, idempotency_key),
                ).fetchone()
                if existing:
                    row = conn.execute(
                        "SELECT * FROM student_goals WHERE goal_id=?",
                        (existing["goal_id"],),
                    ).fetchone()
                    return StudentGoalRow.from_row(row), False
            goal_id = _id("goal")
            conn.execute(
                """INSERT INTO student_goals
                   (goal_id,user_id,name,category,status,target_date,archived_at,
                    progress_percent,milestone_count,created_at,updated_at,idempotency_key)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    goal_id, user_id, name, category, "active", target_date, None,
                    initial_progress_percent, milestone_count, now, now, idempotency_key,
                ),
            )
            row = conn.execute(
                "SELECT * FROM student_goals WHERE goal_id=?", (goal_id,)
            ).fetchone()
        return StudentGoalRow.from_row(row), True

    def list_goals(
        self,
        *,
        user_id: str,
        status: Optional[str] = None,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[StudentGoalRow], int]:
        offset = (page - 1) * page_size
        clauses = ["user_id=?"]
        params: list = [user_id]
        if status:
            clauses.append("status=?")
            params.append(status)
        if category:
            clauses.append("category=?")
            params.append(category)
        where = " AND ".join(clauses)
        with self._db.query() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) AS c FROM student_goals WHERE {where}", tuple(params)
            ).fetchone()["c"]
            rows = conn.execute(
                f"""SELECT * FROM student_goals WHERE {where}
                    ORDER BY created_at DESC, goal_id DESC LIMIT ? OFFSET ?""",
                (*params, page_size, offset),
            ).fetchall()
        return [StudentGoalRow.from_row(row) for row in rows], int(total)

    def get_goal(self, *, user_id: str, goal_id: str) -> Optional[StudentGoalRow]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM student_goals WHERE goal_id=? AND user_id=?",
                (goal_id, user_id),
            ).fetchone()
        return StudentGoalRow.from_row(row) if row else None

    def update_goal(
        self,
        *,
        user_id: str,
        goal_id: str,
        name: Optional[str] = None,
        category: Optional[str] = None,
        target_date: Optional[str] = None,
        milestone_count: Optional[int] = None,
    ) -> Optional[StudentGoalRow]:
        now = _now_iso()
        sets: list[str] = []
        params: list = []
        if name is not None:
            sets.append("name=?")
            params.append(name)
        if category is not None:
            sets.append("category=?")
            params.append(category)
        if target_date is not None:
            sets.append("target_date=?")
            params.append(target_date)
        if milestone_count is not None:
            sets.append("milestone_count=?")
            params.append(milestone_count)
        if not sets:
            return self.get_goal(user_id=user_id, goal_id=goal_id)
        sets.append("updated_at=?")
        params.append(now)
        params.extend([goal_id, user_id])
        with self._db.transaction() as conn:
            conn.execute(
                f"UPDATE student_goals SET {', '.join(sets)} WHERE goal_id=? AND user_id=?",
                tuple(params),
            )
            row = conn.execute(
                "SELECT * FROM student_goals WHERE goal_id=? AND user_id=?",
                (goal_id, user_id),
            ).fetchone()
        return StudentGoalRow.from_row(row) if row else None

    def add_progress(
        self,
        *,
        user_id: str,
        goal_id: str,
        progress_percent: float,
        milestone_reached: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        occurred_at: Optional[str] = None,
    ) -> tuple[StudentGoalProgressRow, bool]:
        now = _now_iso()
        when = occurred_at or now
        with self._db.transaction() as conn:
            if idempotency_key:
                existing = conn.execute(
                    "SELECT progress_id FROM student_goal_progress WHERE goal_id=? AND idempotency_key=?",
                    (goal_id, idempotency_key),
                ).fetchone()
                if existing:
                    row = conn.execute(
                        "SELECT * FROM student_goal_progress WHERE progress_id=?",
                        (existing["progress_id"],),
                    ).fetchone()
                    return StudentGoalProgressRow.from_row(row), False
            progress_id = _id("gp")
            conn.execute(
                """INSERT INTO student_goal_progress
                   (progress_id,goal_id,user_id,progress_percent,milestone_reached,
                    occurred_at,idempotency_key,created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    progress_id, goal_id, user_id, progress_percent, milestone_reached,
                    when, idempotency_key, now,
                ),
            )
            conn.execute(
                "UPDATE student_goals SET progress_percent=?, updated_at=? WHERE goal_id=? AND user_id=?",
                (progress_percent, now, goal_id, user_id),
            )
            row = conn.execute(
                "SELECT * FROM student_goal_progress WHERE progress_id=?", (progress_id,)
            ).fetchone()
        return StudentGoalProgressRow.from_row(row), True

    def archive_goal(self, *, user_id: str, goal_id: str) -> Optional[StudentGoalRow]:
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE student_goals SET status='archived', archived_at=?, updated_at=? WHERE goal_id=? AND user_id=? AND status='active'",
                (now, now, goal_id, user_id),
            )
            row = conn.execute(
                "SELECT * FROM student_goals WHERE goal_id=? AND user_id=?",
                (goal_id, user_id),
            ).fetchone()
        return StudentGoalRow.from_row(row) if row else None

    def delete_for_user(self, *, user_id: str) -> int:
        with self._db.transaction() as conn:
            result = conn.execute(
                "DELETE FROM student_goals WHERE user_id=?", (user_id,)
            )
            return int(result.rowcount or 0)