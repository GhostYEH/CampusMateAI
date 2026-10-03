"""SQLite data access for EnrollmentRepository."""
from __future__ import annotations

from typing import List, Optional
from ..database.sqlite_db import Database
from ..models.multi_role import EnrollmentRow
from ..models.multi_role import ClassGroupRow
from ._multi_role_common import _new_id, _now_iso


class EnrollmentRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def enroll(
        self,
        *,
        class_group_id: str,
        user_id: str,
        member_role: str = "student",
    ) -> EnrollmentRow:
        eid = _new_id("enr")
        now = _now_iso()
        with self._db.transaction() as conn:
            # UNIQUE(class_group_id, user_id) 保证不会重复插入
            conn.execute(
                """INSERT INTO enrollments (id, class_group_id, user_id, member_role, status, joined_at)
                   VALUES (?,?,?,?,?,?)""",
                (eid, class_group_id, user_id, member_role, "active", now),
            )
        return EnrollmentRow(
            id=eid, class_group_id=class_group_id, user_id=user_id,
            member_role=member_role, status="active", joined_at=now,
        )

    def reactivate(self, class_group_id: str, user_id: str) -> bool:
        """如果存在 removed 的记录,将其重新激活。"""
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """UPDATE enrollments SET status = 'active', joined_at = ?
                   WHERE class_group_id = ? AND user_id = ? AND status = 'removed'""",
                (now, class_group_id, user_id),
            )
            return cur.rowcount > 0

    def get_enrollment(
        self, class_group_id: str, user_id: str
    ) -> Optional[EnrollmentRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT * FROM enrollments
                   WHERE class_group_id = ? AND user_id = ?""",
                (class_group_id, user_id),
            )
            row = cur.fetchone()
            return EnrollmentRow.from_row(row) if row else None

    def list_members(
        self,
        class_group_id: str,
        *,
        status: Optional[str] = "active",
        member_role: Optional[str] = None,
        query: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[List[dict], int]:
        """列出班级成员(含用户基本信息),返回 dict 列表(不含 password_hash)。"""
        conditions = ["enrollments.class_group_id = ?"]
        params: list = [class_group_id]
        if status:
            conditions.append("enrollments.status = ?")
            params.append(status)
        if member_role:
            conditions.append("enrollments.member_role = ?")
            params.append(member_role)
        if query:
            conditions.append(
                "(users.username LIKE ? OR users.display_name LIKE ? OR users.student_number LIKE ?)"
            )
            like = f"%{query}%"
            params.extend([like, like, like])
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"""SELECT COUNT(*) AS n FROM enrollments
                    JOIN users ON users.id = enrollments.user_id{where}""",
                params,
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT users.id AS user_id, users.username, users.display_name,
                           users.student_number, users.teacher_number, users.college,
                           users.major, users.grade, users.avatar_url, users.role,
                           enrollments.id AS enrollment_id, enrollments.member_role,
                           enrollments.status, enrollments.joined_at
                    FROM enrollments
                    JOIN users ON users.id = enrollments.user_id{where}
                    ORDER BY enrollments.joined_at ASC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        members = [
            {
                "user_id": r["user_id"],
                "username": r["username"],
                "display_name": r["display_name"],
                "student_number": r["student_number"],
                "teacher_number": r["teacher_number"],
                "college": r["college"],
                "major": r["major"],
                "grade": r["grade"],
                "avatar_url": r["avatar_url"],
                "role": r["role"],
                "enrollment_id": r["enrollment_id"],
                "member_role": r["member_role"],
                "status": r["status"],
                "joined_at": r["joined_at"],
            }
            for r in rows
        ]
        return members, total

    def count_members(self, class_group_id: str, *, status: str = "active") -> int:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) AS n FROM enrollments WHERE class_group_id = ? AND status = ?",
                (class_group_id, status),
            )
            return int(cur.fetchone()["n"])

    def remove_member(self, class_group_id: str, user_id: str) -> bool:
        with self._db.transaction() as conn:
            cur = conn.execute(
                """UPDATE enrollments SET status = 'removed'
                   WHERE class_group_id = ? AND user_id = ? AND status = 'active'""",
                (class_group_id, user_id),
            )
            return cur.rowcount > 0

    def list_user_classes(
        self,
        user_id: str,
        *,
        status: Optional[str] = "active",
    ) -> List[dict]:
        """列出学生已加入的班级(含课程信息)。"""
        conditions = ["enrollments.user_id = ?"]
        params: list = [user_id]
        if status:
            conditions.append("enrollments.status = ?")
            params.append(status)
        where = " WHERE " + " AND ".join(conditions)
        with self._db.query() as conn:
            cur = conn.execute(
                f"""SELECT class_groups.id AS class_id, class_groups.name AS class_name,
                           class_groups.course_id, class_groups.invite_code,
                           courses.name AS course_name, courses.code AS course_code,
                           courses.semester AS course_semester, courses.teacher_id AS teacher_id,
                           enrollments.member_role, enrollments.status, enrollments.joined_at
                    FROM enrollments
                    JOIN class_groups ON class_groups.id = enrollments.class_group_id
                    JOIN courses ON courses.id = class_groups.course_id
                    {where}
                    ORDER BY enrollments.joined_at DESC""",
                params,
            )
            rows = cur.fetchall()
        return [
            {
                "class_id": r["class_id"],
                "class_name": r["class_name"],
                "course_id": r["course_id"],
                "invite_code": r["invite_code"],
                "course_name": r["course_name"],
                "course_code": r["course_code"],
                "course_semester": r["course_semester"],
                "teacher_id": r["teacher_id"],
                "member_role": r["member_role"],
                "status": r["status"],
                "joined_at": r["joined_at"],
            }
            for r in rows
        ]

    def list_user_class_page(
        self, user_id: str, *, course_id: Optional[str], page: int, page_size: int,
    ) -> tuple[list[ClassGroupRow], int]:
        conditions = ["e.user_id = ?", "e.status = 'active'"]
        params: list = [user_id]
        if course_id:
            conditions.append("g.course_id = ?")
            params.append(course_id)
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            total = int(conn.execute(
                f"SELECT COUNT(*) AS n FROM enrollments e JOIN class_groups g ON g.id=e.class_group_id{where}",
                params,
            ).fetchone()["n"])
            rows = conn.execute(
                f"""SELECT g.* FROM enrollments e JOIN class_groups g ON g.id=e.class_group_id
                    {where} ORDER BY e.joined_at DESC LIMIT ? OFFSET ?""",
                [*params, page_size, offset],
            ).fetchall()
        return [ClassGroupRow.from_row(row) for row in rows], total

    def is_member(self, class_group_id: str, user_id: str) -> bool:
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT 1 FROM enrollments
                   WHERE class_group_id = ? AND user_id = ? AND status = 'active'""",
                (class_group_id, user_id),
            )
            return cur.fetchone() is not None

    def is_teacher_of_class(self, class_id: str, user_id: str) -> bool:
        """判断 user_id 是否为该班级对应课程的教师。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT 1 FROM class_groups
                   JOIN courses ON courses.id = class_groups.course_id
                   WHERE class_groups.id = ? AND courses.teacher_id = ?""",
                (class_id, user_id),
            )
            return cur.fetchone() is not None

    def is_teacher_of_course(self, course_id: str, user_id: str) -> bool:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT 1 FROM courses WHERE id = ? AND teacher_id = ?",
                (course_id, user_id),
            )
            return cur.fetchone() is not None

    def list_student_ids_in_class(self, class_group_id: str) -> List[str]:
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT user_id FROM enrollments
                   WHERE class_group_id = ? AND status = 'active' AND member_role = 'student'""",
                (class_group_id,),
            )
            return [r["user_id"] for r in cur.fetchall()]
