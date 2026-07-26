"""多角色协同平台的仓库层 — 用户 / 课程 / 班级 / 选课 / 通知 / 任务 / 提交 / 附件。

设计原则:
- 沿用现有 Database 包装(transaction / query 上下文)。
- 写操作均使用 transaction,保证原子性。
- 查询使用聚合 SQL 避免 N+1。
- 邀请码、token 等使用 secrets 生成。
- 不在这里抛业务异常(留给 service / route 层),仅返回 Optional / row。
"""
from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from ..database.sqlite_db import Database
from ..models.multi_role import (
    AnnouncementRow,
    AssignmentRow,
    ClassGroupRow,
    CourseRow,
    EnrollmentRow,
    RefreshTokenRow,
    SubmissionAttachmentRow,
    SubmissionRow,
    UserRow,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _generate_invite_code() -> str:
    """生成 8 位邀请码(数字 + 大写字母,去除易混淆字符)。"""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去掉 I/O/0/1
    return "".join(secrets.choice(alphabet) for _ in range(8))


# ===== 用户仓库 =====


class UserRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        role: str = "student",
        display_name: Optional[str] = None,
        student_number: Optional[str] = None,
        teacher_number: Optional[str] = None,
        college: Optional[str] = None,
        major: Optional[str] = None,
        grade: Optional[str] = None,
        avatar_url: Optional[str] = None,
        is_active: bool = True,
    ) -> UserRow:
        uid = _new_id("usr")
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, role, display_name,
                    student_number, teacher_number, college, major, grade,
                    avatar_url, is_active, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    uid, username, password_hash, role, display_name,
                    student_number, teacher_number, college, major, grade,
                    avatar_url, int(is_active), now, now,
                ),
            )
        return self.get_user_by_id(uid)  # type: ignore[return-value]

    def get_user_by_id(self, user_id: str) -> Optional[UserRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            )
            row = cur.fetchone()
            return UserRow.from_row(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[UserRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            )
            row = cur.fetchone()
            return UserRow.from_row(row) if row else None

    def get_user_by_student_number(self, sn: str) -> Optional[UserRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM users WHERE student_number = ?", (sn,)
            )
            row = cur.fetchone()
            return UserRow.from_row(row) if row else None

    def get_user_by_teacher_number(self, tn: str) -> Optional[UserRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM users WHERE teacher_number = ?", (tn,)
            )
            row = cur.fetchone()
            return UserRow.from_row(row) if row else None

    def update_user(self, user_id: str, *, fields: dict) -> Optional[UserRow]:
        """仅更新指定字段;不允许通过此接口改 password_hash。"""
        if not fields:
            return self.get_user_by_id(user_id)
        # 允许更新的列白名单
        allowed = {
            "display_name", "college", "major", "grade",
            "avatar_url", "is_active", "role",
        }
        sets = []
        values: list = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == "is_active":
                v = int(bool(v))
            if k == "role" and v not in ("student", "teacher", "admin"):
                continue
            sets.append(f"{k} = ?")
            values.append(v)
        if not sets:
            return self.get_user_by_id(user_id)
        sets.append("updated_at = ?")
        values.append(_now_iso())
        values.append(user_id)
        with self._db.transaction() as conn:
            conn.execute(
                f"UPDATE users SET {', '.join(sets)} WHERE id = ?",
                values,
            )
        return self.get_user_by_id(user_id)

    def update_password(self, user_id: str, password_hash: str) -> None:
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash, now, user_id),
            )

    def list_users(
        self,
        *,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        query: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[UserRow], int]:
        """分页 + 角色筛选 + 模糊搜索(用户名/学号/工号/姓名)。"""
        conditions = []
        params: list = []
        if role:
            conditions.append("role = ?")
            params.append(role)
        if is_active is not None:
            conditions.append("is_active = ?")
            params.append(int(is_active))
        if query:
            conditions.append(
                "(username LIKE ? OR display_name LIKE ? OR student_number LIKE ? OR teacher_number LIKE ?)"
            )
            like = f"%{query}%"
            params.extend([like, like, like, like])
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"SELECT COUNT(*) AS n FROM users{where}", params
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT * FROM users{where}
                    ORDER BY created_at ASC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        return [UserRow.from_row(r) for r in rows], total

    def count_users(self, *, role: Optional[str] = None) -> int:
        if role:
            with self._db.query() as conn:
                cur = conn.execute(
                    "SELECT COUNT(*) AS n FROM users WHERE role = ?", (role,)
                )
                return int(cur.fetchone()["n"])
        with self._db.query() as conn:
            cur = conn.execute("SELECT COUNT(*) AS n FROM users")
            return int(cur.fetchone()["n"])


# ===== Refresh Token 仓库 =====


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


# ===== 课程仓库 =====


class CourseRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_course(
        self,
        *,
        name: str,
        teacher_id: str,
        code: Optional[str] = None,
        semester: Optional[str] = None,
        description: Optional[str] = None,
        status: str = "draft",
    ) -> CourseRow:
        cid = _new_id("crs")
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO courses (id, name, code, semester, description, teacher_id, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (cid, name, code, semester, description, teacher_id, status, now, now),
            )
        return self.get_course(cid)  # type: ignore[return-value]

    def get_course(self, course_id: str) -> Optional[CourseRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM courses WHERE id = ?", (course_id,)
            )
            row = cur.fetchone()
            return CourseRow.from_row(row) if row else None

    def update_course(self, course_id: str, *, fields: dict) -> Optional[CourseRow]:
        if not fields:
            return self.get_course(course_id)
        allowed = {"name", "code", "semester", "description", "status"}
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
        status: Optional[str] = None,
        query: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[CourseRow], int]:
        conditions = []
        params: list = []
        if teacher_id:
            conditions.append("teacher_id = ?")
            params.append(teacher_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if query:
            conditions.append("(name LIKE ? OR code LIKE ? OR description LIKE ?)")
            like = f"%{query}%"
            params.extend([like, like, like])
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        offset = (page - 1) * page_size
        with self._db.query() as conn:
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

    def count_courses(self, *, teacher_id: Optional[str] = None) -> int:
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


# ===== 班级仓库 =====


class ClassGroupRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_class(
        self,
        *,
        course_id: str,
        name: str,
        class_code: Optional[str] = None,
        description: Optional[str] = None,
        capacity: Optional[int] = None,
        invite_code: Optional[str] = None,
    ) -> ClassGroupRow:
        cid = _new_id("cls")
        now = _now_iso()
        code = invite_code or _generate_invite_code()
        # 保证 invite_code 唯一(重试 5 次)
        for _ in range(5):
            existing = self.get_class_by_invite_code(code)
            if existing is None:
                break
            code = _generate_invite_code()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO class_groups
                   (id, course_id, name, class_code, invite_code, description, capacity, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (cid, course_id, name, class_code, code, description, capacity, now, now),
            )
        return self.get_class(cid)  # type: ignore[return-value]

    def get_class(self, class_id: str) -> Optional[ClassGroupRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM class_groups WHERE id = ?", (class_id,)
            )
            row = cur.fetchone()
            return ClassGroupRow.from_row(row) if row else None

    def get_class_by_invite_code(self, code: str) -> Optional[ClassGroupRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM class_groups WHERE invite_code = ?", (code,)
            )
            row = cur.fetchone()
            return ClassGroupRow.from_row(row) if row else None

    def update_class(self, class_id: str, *, fields: dict) -> Optional[ClassGroupRow]:
        if not fields:
            return self.get_class(class_id)
        allowed = {"name", "class_code", "description", "capacity"}
        sets = []
        values: list = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            sets.append(f"{k} = ?")
            values.append(v)
        if not sets:
            return self.get_class(class_id)
        sets.append("updated_at = ?")
        values.append(_now_iso())
        values.append(class_id)
        with self._db.transaction() as conn:
            conn.execute(
                f"UPDATE class_groups SET {', '.join(sets)} WHERE id = ?",
                values,
            )
        return self.get_class(class_id)

    def reset_invite_code(self, class_id: str) -> Optional[ClassGroupRow]:
        new_code = _generate_invite_code()
        for _ in range(5):
            if self.get_class_by_invite_code(new_code) is None:
                break
            new_code = _generate_invite_code()
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                "UPDATE class_groups SET invite_code = ?, updated_at = ? WHERE id = ?",
                (new_code, now, class_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get_class(class_id)

    def list_classes(
        self,
        *,
        course_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[ClassGroupRow], int]:
        conditions = []
        params: list = []
        if course_id:
            conditions.append("course_id = ?")
            params.append(course_id)
        if teacher_id:
            conditions.append(
                "course_id IN (SELECT id FROM courses WHERE teacher_id = ?)"
            )
            params.append(teacher_id)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"SELECT COUNT(*) AS n FROM class_groups{where}", params
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT * FROM class_groups{where}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        return [ClassGroupRow.from_row(r) for r in rows], total

    def count_classes(self, *, teacher_id: Optional[str] = None) -> int:
        if teacher_id:
            with self._db.query() as conn:
                cur = conn.execute(
                    "SELECT COUNT(*) AS n FROM class_groups WHERE course_id IN (SELECT id FROM courses WHERE teacher_id = ?)",
                    (teacher_id,),
                )
                return int(cur.fetchone()["n"])
        with self._db.query() as conn:
            cur = conn.execute("SELECT COUNT(*) AS n FROM class_groups")
            return int(cur.fetchone()["n"])


# ===== 选课仓库 =====


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


# ===== 通知仓库 =====


class AnnouncementRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_announcement(
        self,
        *,
        class_group_id: str,
        author_id: str,
        title: str,
        content: str,
        require_read: bool = False,
        status: str = "draft",
    ) -> AnnouncementRow:
        aid = _new_id("ann")
        now = _now_iso()
        published_at = now if status == "published" else None
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO announcements
                   (id, class_group_id, author_id, title, content, require_read, status, published_at, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (aid, class_group_id, author_id, title, content,
                 int(require_read), status, published_at, now, now),
            )
        return self.get_announcement(aid)  # type: ignore[return-value]

    def get_announcement(self, announcement_id: str) -> Optional[AnnouncementRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM announcements WHERE id = ?", (announcement_id,)
            )
            row = cur.fetchone()
            return AnnouncementRow.from_row(row) if row else None

    def update_announcement(
        self, announcement_id: str, *, fields: dict
    ) -> Optional[AnnouncementRow]:
        if not fields:
            return self.get_announcement(announcement_id)
        allowed = {"title", "content", "require_read", "status"}
        sets = []
        values: list = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == "status" and v not in ("draft", "published", "archived"):
                continue
            if k == "require_read":
                v = int(bool(v))
            sets.append(f"{k} = ?")
            values.append(v)
        if not sets:
            return self.get_announcement(announcement_id)
        sets.append("updated_at = ?")
        values.append(_now_iso())
        values.append(announcement_id)
        with self._db.transaction() as conn:
            conn.execute(
                f"UPDATE announcements SET {', '.join(sets)} WHERE id = ?",
                values,
            )
        return self.get_announcement(announcement_id)

    def publish(self, announcement_id: str) -> Optional[AnnouncementRow]:
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """UPDATE announcements SET status = 'published', published_at = ?, updated_at = ?
                   WHERE id = ? AND status IN ('draft','archived')""",
                (now, now, announcement_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get_announcement(announcement_id)

    def archive(self, announcement_id: str) -> Optional[AnnouncementRow]:
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                "UPDATE announcements SET status = 'archived', updated_at = ? WHERE id = ?",
                (now, announcement_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get_announcement(announcement_id)

    def list_announcements(
        self,
        class_group_id: str,
        *,
        status: Optional[str] = "published",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[AnnouncementRow], int]:
        conditions = ["class_group_id = ?"]
        params: list = [class_group_id]
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"SELECT COUNT(*) AS n FROM announcements{where}", params
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT * FROM announcements{where}
                    ORDER BY published_at DESC NULLS LAST, created_at DESC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        return [AnnouncementRow.from_row(r) for r in rows], total

    # ===== 已读回执 =====

    def mark_read(
        self, announcement_id: str, student_id: str
    ) -> bool:
        """幂等记录已读;返回是否首次记录。"""
        now = _now_iso()
        with self._db.transaction() as conn:
            # 先检查是否已存在
            cur = conn.execute(
                "SELECT 1 FROM announcement_read_receipts WHERE announcement_id = ? AND student_id = ?",
                (announcement_id, student_id),
            )
            if cur.fetchone():
                return False
            conn.execute(
                """INSERT OR IGNORE INTO announcement_read_receipts (announcement_id, student_id, read_at)
                   VALUES (?,?,?)""",
                (announcement_id, student_id, now),
            )
            return True

    def is_read(self, announcement_id: str, student_id: str) -> bool:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT 1 FROM announcement_read_receipts WHERE announcement_id = ? AND student_id = ?",
                (announcement_id, student_id),
            )
            return cur.fetchone() is not None

    def count_reads(self, announcement_id: str) -> int:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) AS n FROM announcement_read_receipts WHERE announcement_id = ?",
                (announcement_id,),
            )
            return int(cur.fetchone()["n"])

    def list_read_receipts(
        self, announcement_id: str
    ) -> List[dict]:
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT users.id AS user_id, users.username, users.display_name,
                          users.student_number, receipt.read_at
                   FROM announcement_read_receipts receipt
                   JOIN users ON users.id = receipt.student_id
                   WHERE receipt.announcement_id = ?
                   ORDER BY receipt.read_at ASC""",
                (announcement_id,),
            )
            rows = cur.fetchall()
        return [
            {
                "user_id": r["user_id"],
                "username": r["username"],
                "display_name": r["display_name"],
                "student_number": r["student_number"],
                "read_at": r["read_at"],
            }
            for r in rows
        ]


# ===== 任务仓库 =====


class AssignmentRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_assignment(
        self,
        *,
        class_group_id: str,
        author_id: str,
        title: str,
        description: Optional[str] = None,
        deadline: Optional[str] = None,
        submission_types: Optional[List[str]] = None,
        max_score: Optional[float] = None,
        allow_resubmit: bool = True,
        status: str = "draft",
    ) -> AssignmentRow:
        aid = _new_id("asg")
        now = _now_iso()
        types_json = json.dumps(submission_types, ensure_ascii=False) if submission_types else None
        published_at = now if status == "published" else None
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO assignments
                   (id, class_group_id, author_id, title, description, deadline,
                    submission_types, max_score, allow_resubmit, status, published_at,
                    created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (aid, class_group_id, author_id, title, description, deadline,
                 types_json, max_score, int(allow_resubmit), status, published_at,
                 now, now),
            )
        return self.get_assignment(aid)  # type: ignore[return-value]

    def get_assignment(self, assignment_id: str) -> Optional[AssignmentRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM assignments WHERE id = ?", (assignment_id,)
            )
            row = cur.fetchone()
            return AssignmentRow.from_row(row) if row else None

    def update_assignment(
        self, assignment_id: str, *, fields: dict
    ) -> Optional[AssignmentRow]:
        if not fields:
            return self.get_assignment(assignment_id)
        allowed = {
            "title", "description", "deadline", "submission_types",
            "max_score", "allow_resubmit", "status",
        }
        sets = []
        values: list = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == "status" and v not in ("draft", "published", "closed", "archived"):
                continue
            if k == "allow_resubmit":
                v = int(bool(v))
            if k == "submission_types" and isinstance(v, list):
                v = json.dumps(v, ensure_ascii=False)
            sets.append(f"{k} = ?")
            values.append(v)
        if not sets:
            return self.get_assignment(assignment_id)
        sets.append("updated_at = ?")
        values.append(_now_iso())
        values.append(assignment_id)
        with self._db.transaction() as conn:
            conn.execute(
                f"UPDATE assignments SET {', '.join(sets)} WHERE id = ?",
                values,
            )
        return self.get_assignment(assignment_id)

    def publish(self, assignment_id: str) -> Optional[AssignmentRow]:
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """UPDATE assignments SET status = 'published', published_at = ?, updated_at = ?
                   WHERE id = ? AND status = 'draft'""",
                (now, now, assignment_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get_assignment(assignment_id)

    def close(self, assignment_id: str) -> Optional[AssignmentRow]:
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """UPDATE assignments SET status = 'closed', updated_at = ?
                   WHERE id = ? AND status = 'published'""",
                (now, assignment_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get_assignment(assignment_id)

    def list_assignments(
        self,
        class_group_id: str,
        *,
        status: Optional[str] = "published",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[AssignmentRow], int]:
        conditions = ["class_group_id = ?"]
        params: list = [class_group_id]
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"SELECT COUNT(*) AS n FROM assignments{where}", params
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT * FROM assignments{where}
                    ORDER BY deadline ASC NULLS LAST, created_at DESC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        return [AssignmentRow.from_row(r) for r in rows], total

    def list_assignments_for_student(
        self,
        user_id: str,
        *,
        due_within_days: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[dict], int]:
        """列出学生所在班级的所有已发布任务(含班级/课程信息)。"""
        conditions = [
            "assignments.status IN ('published','closed')",
            "enrollments.user_id = ?",
            "enrollments.status = 'active'",
        ]
        params: list = [user_id]
        if due_within_days is not None:
            conditions.append(
                "assignments.deadline IS NOT NULL AND assignments.deadline >= ?"
            )
            now = _now_iso()
            params.append(now)
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"""SELECT COUNT(*) AS n FROM assignments
                    JOIN class_groups ON class_groups.id = assignments.class_group_id
                    JOIN enrollments ON enrollments.class_group_id = class_groups.id
                    {where}""",
                params,
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT assignments.id AS assignment_id, assignments.class_group_id,
                           assignments.title, assignments.description, assignments.deadline,
                           assignments.submission_types, assignments.max_score,
                           assignments.allow_resubmit, assignments.status, assignments.published_at,
                           class_groups.name AS class_name, class_groups.course_id,
                           courses.name AS course_name, courses.code AS course_code,
                           courses.teacher_id AS teacher_id
                    FROM assignments
                    JOIN class_groups ON class_groups.id = assignments.class_group_id
                    JOIN courses ON courses.id = class_groups.course_id
                    JOIN enrollments ON enrollments.class_group_id = class_groups.id
                    {where}
                    ORDER BY assignments.deadline ASC NULLS LAST
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        items = []
        for r in rows:
            items.append({
                "assignment_id": r["assignment_id"],
                "class_group_id": r["class_group_id"],
                "title": r["title"],
                "description": r["description"],
                "deadline": r["deadline"],
                "submission_types": json.loads(r["submission_types"]) if r["submission_types"] else [],
                "max_score": r["max_score"],
                "allow_resubmit": bool(r["allow_resubmit"]),
                "status": r["status"],
                "published_at": r["published_at"],
                "class_name": r["class_name"],
                "course_id": r["course_id"],
                "course_name": r["course_name"],
                "course_code": r["course_code"],
                "teacher_id": r["teacher_id"],
            })
        return items, total

    def count_active_assignments(self, teacher_id: str) -> int:
        """教师所辖班级中已发布且未关闭的任务数。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(*) AS n FROM assignments
                   JOIN class_groups ON class_groups.id = assignments.class_group_id
                   JOIN courses ON courses.id = class_groups.course_id
                   WHERE courses.teacher_id = ? AND assignments.status = 'published'""",
                (teacher_id,),
            )
            return int(cur.fetchone()["n"])


# ===== 提交仓库 =====


class SubmissionRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def upsert_submission(
        self,
        *,
        assignment_id: str,
        student_id: str,
        text_content: Optional[str] = None,
        status: str = "draft",
    ) -> SubmissionRow:
        """新建或更新提交(UNIQUE(assignment_id, student_id) 保证幂等)。"""
        now = _now_iso()
        submitted_at = now if status in ("submitted", "resubmitted", "late") else None
        with self._db.transaction() as conn:
            cur = conn.execute(
                "SELECT id, status FROM submissions WHERE assignment_id = ? AND student_id = ?",
                (assignment_id, student_id),
            )
            existing = cur.fetchone()
            if existing:
                sid = existing["id"]
                conn.execute(
                    """UPDATE submissions
                       SET text_content = ?, status = ?, submitted_at = ?, updated_at = ?
                       WHERE id = ?""",
                    (text_content, status, submitted_at, now, sid),
                )
            else:
                sid = _new_id("sub")
                conn.execute(
                    """INSERT INTO submissions
                       (id, assignment_id, student_id, text_content, status,
                        submitted_at, updated_at, score, teacher_comment)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (sid, assignment_id, student_id, text_content, status,
                     submitted_at, now, None, None),
                )
        return self.get_submission(sid)  # type: ignore[return-value]

    def get_submission(self, submission_id: str) -> Optional[SubmissionRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM submissions WHERE id = ?", (submission_id,)
            )
            row = cur.fetchone()
            return SubmissionRow.from_row(row) if row else None

    def get_submission_for_student(
        self, assignment_id: str, student_id: str
    ) -> Optional[SubmissionRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM submissions WHERE assignment_id = ? AND student_id = ?",
                (assignment_id, student_id),
            )
            row = cur.fetchone()
            return SubmissionRow.from_row(row) if row else None

    def list_submissions(
        self,
        assignment_id: str,
        *,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[dict], int]:
        conditions = ["submissions.assignment_id = ?"]
        params: list = [assignment_id]
        if status:
            conditions.append("submissions.status = ?")
            params.append(status)
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"""SELECT COUNT(*) AS n FROM submissions{where}""", params
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT submissions.*, users.username, users.display_name,
                           users.student_number, users.college, users.major, users.grade
                    FROM submissions
                    JOIN users ON users.id = submissions.student_id
                    {where}
                    ORDER BY submissions.submitted_at DESC NULLS LAST
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        items = []
        for r in rows:
            items.append({
                "id": r["id"],
                "assignment_id": r["assignment_id"],
                "student_id": r["student_id"],
                "student_name": r["display_name"] or r["username"],
                "student_number": r["student_number"],
                "college": r["college"],
                "major": r["major"],
                "grade": r["grade"],
                "text_content": r["text_content"],
                "status": r["status"],
                "submitted_at": r["submitted_at"],
                "updated_at": r["updated_at"],
                "score": r["score"],
                "teacher_comment": r["teacher_comment"],
            })
        return items, total

    def grade(
        self,
        submission_id: str,
        *,
        score: Optional[float],
        teacher_comment: Optional[str],
    ) -> Optional[SubmissionRow]:
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """UPDATE submissions SET score = ?, teacher_comment = ?, updated_at = ?
                   WHERE id = ?""",
                (score, teacher_comment, now, submission_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get_submission(submission_id)

    def count_pending_submissions(self, teacher_id: str) -> int:
        """教师所辖任务中已提交但未评分的数量。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(*) AS n FROM submissions
                   JOIN assignments ON assignments.id = submissions.assignment_id
                   JOIN class_groups ON class_groups.id = assignments.class_group_id
                   JOIN courses ON courses.id = class_groups.course_id
                   WHERE courses.teacher_id = ?
                     AND submissions.status IN ('submitted','resubmitted','late')
                     AND submissions.score IS NULL""",
                (teacher_id,),
            )
            return int(cur.fetchone()["n"])

    # ===== 附件 =====

    def add_attachment(
        self,
        *,
        submission_id: str,
        original_filename: str,
        stored_filename: str,
        mime_type: Optional[str],
        size_bytes: int,
        storage_path: str,
    ) -> SubmissionAttachmentRow:
        aid = _new_id("att")
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO submission_attachments
                   (id, submission_id, original_filename, stored_filename,
                    mime_type, size_bytes, storage_path, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (aid, submission_id, original_filename, stored_filename,
                 mime_type, size_bytes, storage_path, now),
            )
        return self.get_attachment(aid)  # type: ignore[return-value]

    def get_attachment(self, attachment_id: str) -> Optional[SubmissionAttachmentRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM submission_attachments WHERE id = ?",
                (attachment_id,),
            )
            row = cur.fetchone()
            return SubmissionAttachmentRow.from_row(row) if row else None

    def list_attachments(self, submission_id: str) -> List[SubmissionAttachmentRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM submission_attachments WHERE submission_id = ? ORDER BY created_at ASC",
                (submission_id,),
            )
            return [SubmissionAttachmentRow.from_row(r) for r in cur.fetchall()]

    def delete_attachment(self, attachment_id: str) -> Optional[str]:
        """删除附件,返回其 storage_path(用于清理文件)。"""
        with self._db.transaction() as conn:
            cur = conn.execute(
                "SELECT storage_path FROM submission_attachments WHERE id = ?",
                (attachment_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            conn.execute(
                "DELETE FROM submission_attachments WHERE id = ?",
                (attachment_id,),
            )
            return row["storage_path"]

    # ===== 聚合统计 =====

    def assignment_stats(self, assignment_id: str, *, total_students: int) -> dict:
        """单任务的统计(单条聚合 SQL,避免 N+1)。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT
                       COUNT(*) AS total_submissions,
                       SUM(CASE WHEN status = 'submitted' THEN 1 ELSE 0 END) AS submitted,
                       SUM(CASE WHEN status = 'resubmitted' THEN 1 ELSE 0 END) AS resubmitted,
                       SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) AS late,
                       SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) AS draft,
                       SUM(CASE WHEN score IS NOT NULL THEN 1 ELSE 0 END) AS graded,
                       AVG(score) AS avg_score
                   FROM submissions
                   WHERE assignment_id = ?""",
                (assignment_id,),
            )
            row = cur.fetchone()
        submitted_total = int(row["submitted"] or 0) + int(row["resubmitted"] or 0) + int(row["late"] or 0)
        draft = int(row["draft"] or 0)
        graded = int(row["graded"] or 0)
        avg_score = float(row["avg_score"]) if row["avg_score"] is not None else None
        return {
            "assignment_id": assignment_id,
            "total_students": total_students,
            "submitted": submitted_total,
            "not_submitted": max(0, total_students - submitted_total - draft),
            "draft": draft,
            "late": int(row["late"] or 0),
            "graded": graded,
            "pending_grading": max(0, submitted_total - graded),
            "avg_score": avg_score,
        }

    def student_status(
        self,
        assignment_id: str,
        class_group_id: str,
        *,
        submission_status: Optional[str] = None,
        read_status: Optional[str] = None,
        query: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[List[dict], int]:
        """聚合查询每个学生的状态(提交状态/逾期/成绩)。

        read_status 字段对任务而言为 "not_required"(任务本身不要求已读回执,
        该字段保留用于前端兼容;若班级有同名通知可后续扩展关联)。
        使用 LEFT JOIN submissions,避免逐学生查询。
        """
        conditions = [
            "enrollments.class_group_id = ?",
            "enrollments.status = 'active'",
            "enrollments.member_role = 'student'",
        ]
        params: list = [class_group_id]
        if query:
            conditions.append(
                "(users.username LIKE ? OR users.display_name LIKE ? OR users.student_number LIKE ?)"
            )
            like = f"%{query}%"
            params.extend([like, like, like])
        if submission_status:
            if submission_status == "not_submitted":
                conditions.append("(submissions.status IS NULL OR submissions.status = 'draft')")
            else:
                conditions.append("submissions.status = ?")
                params.append(submission_status)
        # read_status 过滤对任务无意义(任务不要求已读回执),忽略以避免误导
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"""SELECT COUNT(*) AS n FROM enrollments
                    JOIN users ON users.id = enrollments.user_id
                    LEFT JOIN submissions ON submissions.assignment_id = ?
                        AND submissions.student_id = enrollments.user_id
                    {where}""",
                [assignment_id] + params,
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT users.id AS student_id, users.username,
                           users.display_name AS student_name,
                           users.student_number,
                           submissions.id AS submission_id,
                           submissions.status AS submission_status,
                           submissions.submitted_at,
                           submissions.score,
                           submissions.teacher_comment,
                           assignments.deadline
                    FROM enrollments
                    JOIN users ON users.id = enrollments.user_id
                    LEFT JOIN submissions ON submissions.assignment_id = ?
                        AND submissions.student_id = enrollments.user_id
                    LEFT JOIN assignments ON assignments.id = ?
                    {where}
                    ORDER BY users.student_number ASC NULLS LAST, users.username ASC
                    LIMIT ? OFFSET ?""",
                [assignment_id, assignment_id] + params + [page_size, offset],
            )
            rows = cur.fetchall()
        items = []
        for r in rows:
            sub_status = r["submission_status"]
            submitted_at = r["submitted_at"]
            deadline = r["deadline"]
            is_late = False
            if sub_status in ("submitted", "resubmitted", "late"):
                if deadline and submitted_at and submitted_at > deadline:
                    is_late = True
                    sub_status_display = "late"
                else:
                    sub_status_display = sub_status
            else:
                sub_status_display = sub_status if sub_status else "not_submitted"
            items.append({
                "student_id": r["student_id"],
                "student_name": r["student_name"] or r["username"],
                "student_number": r["student_number"],
                "submission_id": r["submission_id"],
                "submission_status": sub_status_display,
                "submitted_at": submitted_at,
                "is_late": is_late,
                "score": r["score"],
                "teacher_comment": r["teacher_comment"],
                "read_status": "not_required",
                "read_at": None,
            })
        return items, total

    def count_student_pending_assignments(self, user_id: str, *, now_iso: str) -> int:
        """学生未提交且未过期的任务数。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(*) AS n FROM assignments
                   JOIN class_groups ON class_groups.id = assignments.class_group_id
                   JOIN enrollments ON enrollments.class_group_id = class_groups.id
                   LEFT JOIN submissions ON submissions.assignment_id = assignments.id
                       AND submissions.student_id = enrollments.user_id
                   WHERE enrollments.user_id = ? AND enrollments.status = 'active'
                     AND assignments.status = 'published'
                     AND (submissions.status IS NULL OR submissions.status = 'draft')
                     AND (assignments.deadline IS NULL OR assignments.deadline >= ?)
                """,
                (user_id, now_iso),
            )
            return int(cur.fetchone()["n"])

    def count_student_overdue_assignments(self, user_id: str, *, now_iso: str) -> int:
        """学生已逾期的任务数(deadline < now 且未提交)。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(*) AS n FROM assignments
                   JOIN class_groups ON class_groups.id = assignments.class_group_id
                   JOIN enrollments ON enrollments.user_id = ?
                       AND enrollments.class_group_id = class_groups.id
                       AND enrollments.status = 'active'
                   LEFT JOIN submissions ON submissions.assignment_id = assignments.id
                       AND submissions.student_id = enrollments.user_id
                   WHERE assignments.status = 'published'
                     AND assignments.deadline IS NOT NULL
                     AND assignments.deadline < ?
                     AND (submissions.status IS NULL
                          OR submissions.status NOT IN ('submitted','resubmitted','late'))
                """,
                (user_id, now_iso),
            )
            return int(cur.fetchone()["n"])

    def count_student_unread_announcements(self, user_id: str) -> int:
        """学生未读且 require_read=1 的已发布通知数。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(*) AS n FROM announcements
                   JOIN class_groups ON class_groups.id = announcements.class_group_id
                   JOIN enrollments ON enrollments.user_id = ?
                       AND enrollments.class_group_id = class_groups.id
                       AND enrollments.status = 'active'
                   LEFT JOIN announcement_read_receipts receipt
                       ON receipt.announcement_id = announcements.id
                       AND receipt.student_id = enrollments.user_id
                   WHERE announcements.status = 'published'
                     AND announcements.require_read = 1
                     AND receipt.read_at IS NULL
                """,
                (user_id,),
            )
            return int(cur.fetchone()["n"])

    def count_student_enrolled_courses(self, user_id: str) -> int:
        """学生加入的不同课程数。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(DISTINCT courses.id) AS n
                   FROM enrollments
                   JOIN class_groups ON class_groups.id = enrollments.class_group_id
                   JOIN courses ON courses.id = class_groups.course_id
                   WHERE enrollments.user_id = ? AND enrollments.status = 'active'
                """,
                (user_id,),
            )
            return int(cur.fetchone()["n"])

    def count_teacher_unread_announcements(self, teacher_id: str) -> int:
        """教师在自己班级中发布的、需已读但未全部已读的通知数(粗略口径)。

        口径: 每条 require_read=1 的已发布通知,
        若已读人数 < 班级学生数,则视为"有待跟进的未读"。
        """
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(*) AS n FROM announcements ann
                   JOIN class_groups cg ON cg.id = ann.class_group_id
                   JOIN courses c ON c.id = cg.course_id
                   WHERE c.teacher_id = ?
                     AND ann.status = 'published'
                     AND ann.require_read = 1
                     AND (SELECT COUNT(*) FROM announcement_read_receipts r
                          WHERE r.announcement_id = ann.id)
                       < (SELECT COUNT(*) FROM enrollments e
                          WHERE e.class_group_id = cg.id AND e.status = 'active'
                            AND e.member_role = 'student')
                """,
                (teacher_id,),
            )
            return int(cur.fetchone()["n"])

    def count_teacher_overdue_students(self, teacher_id: str, *, now_iso: str) -> int:
        """教师所辖任务中已逾期且学生未提交的数量(人次数)。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(*) AS n FROM assignments a
                   JOIN class_groups cg ON cg.id = a.class_group_id
                   JOIN courses c ON c.id = cg.course_id
                   JOIN enrollments e ON e.class_group_id = cg.id
                       AND e.status = 'active' AND e.member_role = 'student'
                   LEFT JOIN submissions s ON s.assignment_id = a.id
                       AND s.student_id = e.user_id
                   WHERE c.teacher_id = ?
                     AND a.status = 'published'
                     AND a.deadline IS NOT NULL
                     AND a.deadline < ?
                     AND (s.status IS NULL OR s.status NOT IN ('submitted','resubmitted','late'))
                """,
                (teacher_id, now_iso),
            )
            return int(cur.fetchone()["n"])

    def count_teacher_students(self, teacher_id: str) -> int:
        """教师所辖班级的不同学生数。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(DISTINCT e.user_id) AS n
                   FROM enrollments e
                   JOIN class_groups cg ON cg.id = e.class_group_id
                   JOIN courses c ON c.id = cg.course_id
                   WHERE c.teacher_id = ? AND e.status = 'active'
                     AND e.member_role = 'student'
                """,
                (teacher_id,),
            )
            return int(cur.fetchone()["n"])

    def recent_teacher_assignments(self, teacher_id: str, *, limit: int = 5) -> List[dict]:
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT a.id, a.title, a.status, a.deadline, a.published_at,
                          cg.id AS class_id, cg.name AS class_name,
                          c.id AS course_id, c.name AS course_name
                   FROM assignments a
                   JOIN class_groups cg ON cg.id = a.class_group_id
                   JOIN courses c ON c.id = cg.course_id
                   WHERE c.teacher_id = ?
                   ORDER BY a.created_at DESC
                   LIMIT ?""",
                (teacher_id, limit),
            )
            rows = cur.fetchall()
        return [
            {
                "assignment_id": r["id"],
                "title": r["title"],
                "status": r["status"],
                "deadline": r["deadline"],
                "published_at": r["published_at"],
                "class_id": r["class_id"],
                "class_name": r["class_name"],
                "course_id": r["course_id"],
                "course_name": r["course_name"],
            }
            for r in rows
        ]

    def recent_student_announcements(self, user_id: str, *, limit: int = 5) -> List[dict]:
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT ann.id, ann.title, ann.published_at, ann.require_read,
                          cg.id AS class_id, cg.name AS class_name,
                          c.id AS course_id, c.name AS course_name,
                          receipt.read_at
                   FROM announcements ann
                   JOIN class_groups cg ON cg.id = ann.class_group_id
                   JOIN courses c ON c.id = cg.course_id
                   JOIN enrollments e ON e.class_group_id = cg.id AND e.user_id = ?
                       AND e.status = 'active'
                   LEFT JOIN announcement_read_receipts receipt
                       ON receipt.announcement_id = ann.id AND receipt.student_id = e.user_id
                   WHERE ann.status = 'published'
                   ORDER BY ann.published_at DESC NULLS LAST
                   LIMIT ?""",
                (user_id, limit),
            )
            rows = cur.fetchall()
        return [
            {
                "announcement_id": r["id"],
                "title": r["title"],
                "published_at": r["published_at"],
                "require_read": bool(r["require_read"]),
                "class_id": r["class_id"],
                "class_name": r["class_name"],
                "course_id": r["course_id"],
                "course_name": r["course_name"],
                "read_at": r["read_at"],
            }
            for r in rows
        ]

    def recent_student_assignments(
        self, user_id: str, *, due_within_days: int = 7, now_iso: str, limit: int = 5
    ) -> List[dict]:
        """列出学生最近 N 天内到期的任务。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT a.id, a.title, a.deadline, a.status,
                          cg.id AS class_id, cg.name AS class_name,
                          c.id AS course_id, c.name AS course_name,
                          s.id AS submission_id, s.status AS submission_status
                   FROM assignments a
                   JOIN class_groups cg ON cg.id = a.class_group_id
                   JOIN courses c ON c.id = cg.course_id
                   JOIN enrollments e ON e.class_group_id = cg.id AND e.user_id = ?
                       AND e.status = 'active'
                   LEFT JOIN submissions s ON s.assignment_id = a.id AND s.student_id = e.user_id
                   WHERE a.status = 'published' AND a.deadline IS NOT NULL
                       AND a.deadline >= ?
                       AND a.deadline <= datetime(?, '+' || ? || ' days')
                   ORDER BY a.deadline ASC
                   LIMIT ?""",
                (user_id, now_iso, now_iso, due_within_days, limit),
            )
            rows = cur.fetchall()
        return [
            {
                "assignment_id": r["id"],
                "title": r["title"],
                "deadline": r["deadline"],
                "status": r["status"],
                "class_id": r["class_id"],
                "class_name": r["class_name"],
                "course_id": r["course_id"],
                "course_name": r["course_name"],
                "submission_id": r["submission_id"],
                "submission_status": r["submission_status"],
            }
            for r in rows
        ]


__all__ = [
    "UserRepository",
    "RefreshTokenRepository",
    "CourseRepository",
    "ClassGroupRepository",
    "EnrollmentRepository",
    "AnnouncementRepository",
    "AssignmentRepository",
    "SubmissionRepository",
    "_generate_invite_code",
    "_new_id",
    "_now_iso",
]
