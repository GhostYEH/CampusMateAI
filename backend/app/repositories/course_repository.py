"""SQLite data access for CourseRepository."""
from __future__ import annotations

from typing import List, Optional
from ..database.sqlite_db import Database
from ..models.multi_role import CourseRow
from ._multi_role_common import _new_id, _now_iso


class CourseRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_course(
        self,
        *,
        name: str,
        teacher_id: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        remote_teacher_name: Optional[str] = None,
        remote_class_id: Optional[str] = None,
        remote_cpi: Optional[str] = None,
        remote_school_name: Optional[str] = None,
        remote_class_name: Optional[str] = None,
        remote_student_count: Optional[int] = None,
        cover_url: Optional[str] = None,
        starts_at: Optional[str] = None,
        ends_at: Optional[str] = None,
        code: Optional[str] = None,
        semester: Optional[str] = None,
        description: Optional[str] = None,
        status: str = "draft",
        provider: Optional[str] = None,
        external_id: Optional[str] = None,
        source_url: Optional[str] = None,
        last_synced_at: Optional[str] = None,
    ) -> CourseRow:
        cid = _new_id("crs")
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO courses
                   (id, name, code, semester, description, teacher_id, owner_user_id, remote_teacher_name,
                    remote_class_id, remote_cpi, remote_school_name, remote_class_name,
                    remote_student_count, cover_url, starts_at, ends_at, status, provider,
                    external_id, source_url, last_synced_at, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cid, name, code, semester, description, teacher_id, owner_user_id, remote_teacher_name,
                 remote_class_id, remote_cpi, remote_school_name, remote_class_name,
                 remote_student_count, cover_url, starts_at, ends_at, status, provider,
                 external_id, source_url, last_synced_at, now, now),
            )
        return self.get_course(cid)  # type: ignore[return-value]

    def get_course(self, course_id: str) -> Optional[CourseRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM courses WHERE id = ?", (course_id,)
            )
            row = cur.fetchone()
            return CourseRow.from_row(row) if row else None

    def get_course_by_external_id(self, external_id: str, *, teacher_id: Optional[str] = None, owner_user_id: Optional[str] = None) -> Optional[CourseRow]:
        with self._db.query() as conn:
            if owner_user_id is not None:
                cur = conn.execute(
                    "SELECT * FROM courses WHERE external_id = ? AND owner_user_id = ?", (external_id, owner_user_id)
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM courses WHERE external_id = ? AND teacher_id = ?", (external_id, teacher_id)
                )
            row = cur.fetchone()
            return CourseRow.from_row(row) if row else None

    def update_course(self, course_id: str, *, fields: dict) -> Optional[CourseRow]:
        if not fields:
            return self.get_course(course_id)
        allowed = {"name", "code", "semester", "description", "status", "provider", "external_id", "source_url", "last_synced_at", "remote_teacher_name", "remote_class_id", "remote_cpi", "remote_school_name", "remote_class_name", "remote_student_count", "cover_url", "starts_at", "ends_at", "owner_user_id"}
        sets = []
        values: list = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == "status" and v not in ("draft", "active", "archived"):
                continue
            sets.append(f"{k} = ?")
            values.append(v)
        if not sets:
            return self.get_course(course_id)
        sets.append("updated_at = ?")
        values.append(_now_iso())
        values.append(course_id)
        with self._db.transaction() as conn:
            conn.execute(
                f"UPDATE courses SET {', '.join(sets)} WHERE id = ?",
                values,
            )
        return self.get_course(course_id)

    def list_courses(
        self,
        *,
        teacher_id: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        status: Optional[str] = None,
        query: Optional[str] = None,
        student_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[CourseRow], int]:
        conditions = []
        params: list = []
        if student_id is not None:
            conditions.append("""((provider = 'chaoxing' AND owner_user_id = ?)
                OR EXISTS (
                    SELECT 1 FROM class_groups g
                    JOIN enrollments e ON e.class_group_id = g.id
                    WHERE g.course_id = courses.id AND e.user_id = ? AND e.status = 'active'
                ))""")
            params.extend([student_id, student_id])
        if teacher_id:
            conditions.append("teacher_id = ?")
            params.append(teacher_id)
        if owner_user_id:
            conditions.append("owner_user_id = ?")
            params.append(owner_user_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if query:
            if student_id is not None:
                # Preserve literal Unicode substring search, including % and _.
                conditions.append("(instr(campus_lower(name), ?) > 0 OR instr(campus_lower(code), ?) > 0 OR instr(campus_lower(description), ?) > 0)")
                params.extend([query.lower()] * 3)
            else:
                conditions.append("(name LIKE ? OR code LIKE ? OR description LIKE ?)")
                like = f"%{query}%"
                params.extend([like, like, like])
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            if student_id is not None and query:
                conn.create_function("campus_lower", 1, lambda value: (value or "").lower(), deterministic=True)
            cur = conn.execute(
                f"SELECT COUNT(*) AS n FROM courses{where}", params
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT * FROM courses{where}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        return [CourseRow.from_row(r) for r in rows], total

    def count_courses(self, *, teacher_id: Optional[str] = None, owner_user_id: Optional[str] = None) -> int:
        if owner_user_id:
            with self._db.query() as conn:
                cur = conn.execute(
                    "SELECT COUNT(*) AS n FROM courses WHERE owner_user_id = ?",
                    (owner_user_id,),
                )
                return int(cur.fetchone()["n"])
        if teacher_id:
            with self._db.query() as conn:
                cur = conn.execute(
                    "SELECT COUNT(*) AS n FROM courses WHERE teacher_id = ?",
                    (teacher_id,),
                )
                return int(cur.fetchone()["n"])
        with self._db.query() as conn:
            cur = conn.execute("SELECT COUNT(*) AS n FROM courses")
            return int(cur.fetchone()["n"])

    def list_chaoxing_for_event_backfill(
        self,
        *,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[List[CourseRow], int]:
        """分页读取学习通课程，供受控 Learner Event 回填使用。"""
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must stay within 1..100")
        conditions = ["provider = 'chaoxing'", "owner_user_id IS NOT NULL"]
        params: list = []
        if user_id is not None:
            conditions.insert(0, "owner_user_id = ?")
            params.append(user_id)
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            total = int(
                conn.execute(f"SELECT COUNT(*) AS n FROM courses{where}", params)
                .fetchone()["n"]
            )
            rows = conn.execute(
                f"SELECT * FROM courses{where} ORDER BY owner_user_id ASC, id ASC LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()
        return [CourseRow.from_row(row) for row in rows], total
