"""SQLite data access for UserRepository."""
from __future__ import annotations

from typing import List, Optional
from ..database.sqlite_db import Database
from ..models.multi_role import UserRow
from ._multi_role_common import _new_id, _now_iso


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

    def get_display_names(self, user_ids: List[str]) -> dict[str, str]:
        """Read names for a result page without fetching each user's full record."""
        ids = list(dict.fromkeys(user_ids))
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        with self._db.query() as conn:
            rows = conn.execute(
                f"SELECT id, display_name, username FROM users WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
        return {row["id"]: row["display_name"] or row["username"] for row in rows}

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

    def update_university(self, user_id: str, university_id: Optional[str]) -> UserRow:
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE users SET university_id = ?, updated_at = ? WHERE id = ?",
                (university_id, _now_iso(), user_id),
            )
        return self.get_user_by_id(user_id)  # type: ignore[return-value]

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
