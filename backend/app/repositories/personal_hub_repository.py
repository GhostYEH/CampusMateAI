"""个人中心仓库 —— 用户私有文件与跨模块收藏。

设计要点(与 PersonalTaskRepository 一致):
- `user_id` 强制绑定: 所有读写都按 JWT 用户的 `user_id` 过滤,禁止跨用户读取。
- 仓库层不抛业务异常(留给 route 层),仅返回 Optional / row / 列表。
- `favorites` 使用 (user_id, id) 复合主键,同一逻辑 id 在不同用户间隔离。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from ..database.sqlite_db import Database
from ..models.personal_hub import FavoriteRow, PersonalFileRow


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_file_id() -> str:
    return f"pfile_{uuid.uuid4().hex[:16]}"


class PersonalFileRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def list_files(self, user_id: str) -> List[PersonalFileRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT * FROM personal_files
                   WHERE user_id = ?
                   ORDER BY is_favorite DESC, created_at DESC""",
                (user_id,),
            )
            rows = cur.fetchall()
        return [PersonalFileRow.from_row(r) for r in rows]

    def get_file(self, file_id: str, *, user_id: str) -> Optional[PersonalFileRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM personal_files WHERE id = ? AND user_id = ?",
                (file_id, user_id),
            )
            row = cur.fetchone()
            return PersonalFileRow.from_row(row) if row else None

    def create_file(
        self,
        *,
        user_id: str,
        name: str,
        category: Optional[str] = None,
        size_label: Optional[str] = None,
        source: Optional[str] = None,
    ) -> PersonalFileRow:
        fid = _new_file_id()
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO personal_files
                   (id, user_id, name, category, size_label, updated_at,
                    source, is_favorite, created_at)
                   VALUES (?,?,?,?,?,?,?,0,?)""",
                (fid, user_id, name, category, size_label, now, source, now),
            )
        return self.get_file(fid, user_id=user_id)  # type: ignore[return-value]

    def update_file(
        self,
        file_id: str,
        *,
        user_id: str,
        fields: dict,
    ) -> Optional[PersonalFileRow]:
        allowed = {"name", "category", "size_label", "source", "is_favorite"}
        sets: List[str] = []
        values: List[object] = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key == "is_favorite":
                value = 1 if value else 0
            sets.append(f"{key} = ?")
            values.append(value)
        if not sets:
            return self.get_file(file_id, user_id=user_id)
        sets.append("updated_at = ?")
        values.append(_now_iso())
        values.append(file_id)
        values.append(user_id)
        with self._db.transaction() as conn:
            conn.execute(
                f"UPDATE personal_files SET {', '.join(sets)} "
                "WHERE id = ? AND user_id = ?",
                values,
            )
        return self.get_file(file_id, user_id=user_id)

    def set_favorite(self, file_id: str, *, user_id: str, favorite: bool) -> Optional[PersonalFileRow]:
        return self.update_file(
            file_id, user_id=user_id, fields={"is_favorite": favorite}
        )

    def delete_file(self, file_id: str, *, user_id: str) -> bool:
        with self._db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM personal_files WHERE id = ? AND user_id = ?",
                (file_id, user_id),
            )
            return cur.rowcount > 0


class FavoriteRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def list_favorites(self, user_id: str) -> List[FavoriteRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT * FROM favorites
                   WHERE user_id = ?
                   ORDER BY created_at DESC""",
                (user_id,),
            )
            rows = cur.fetchall()
        return [FavoriteRow.from_row(r) for r in rows]

    def get_favorite(self, favorite_id: str, *, user_id: str) -> Optional[FavoriteRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM favorites WHERE id = ? AND user_id = ?",
                (favorite_id, user_id),
            )
            row = cur.fetchone()
            return FavoriteRow.from_row(row) if row else None

    def add_favorite(
        self,
        *,
        user_id: str,
        favorite_id: str,
        title: str,
        type: Optional[str] = None,
        subtitle: Optional[str] = None,
        saved_at: Optional[str] = None,
        source_route: Optional[str] = None,
    ) -> FavoriteRow:
        now = _now_iso()
        with self._db.transaction() as conn:
            # 幂等: 已存在则更新 title/subtitle 等字段
            existing = conn.execute(
                "SELECT * FROM favorites WHERE id = ? AND user_id = ?",
                (favorite_id, user_id),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """INSERT INTO favorites
                       (user_id, id, title, type, subtitle, saved_at,
                        source_route, created_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        user_id, favorite_id, title, type, subtitle,
                        saved_at or now, source_route, now,
                    ),
                )
            else:
                conn.execute(
                    """UPDATE favorites
                       SET title = ?, type = ?, subtitle = ?, saved_at = ?,
                           source_route = ?
                       WHERE id = ? AND user_id = ?""",
                    (title, type, subtitle, saved_at or now, source_route,
                     favorite_id, user_id),
                )
        return self.get_favorite(favorite_id, user_id=user_id)  # type: ignore[return-value]

    def remove_favorite(self, favorite_id: str, *, user_id: str) -> bool:
        with self._db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM favorites WHERE id = ? AND user_id = ?",
                (favorite_id, user_id),
            )
            return cur.rowcount > 0


__all__ = ["PersonalFileRepository", "FavoriteRepository"]
