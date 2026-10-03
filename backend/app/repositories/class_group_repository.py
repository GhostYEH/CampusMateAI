"""SQLite data access for ClassGroupRepository."""
from __future__ import annotations

from typing import List, Optional
from ..database.sqlite_db import Database
from ..models.multi_role import ClassGroupRow
from ._multi_role_common import _generate_invite_code, _new_id, _now_iso


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
