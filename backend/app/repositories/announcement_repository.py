"""SQLite data access for AnnouncementRepository."""
from __future__ import annotations

from typing import List, Optional
from ..database.sqlite_db import Database
from ..models.multi_role import AnnouncementRow
from ._multi_role_common import _new_id, _now_iso


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

    def delete_announcement(self, announcement_id: str) -> bool:
        """刪除通知(同時清理已讀回執)。返回是否實際刪除。"""
        with self._db.transaction() as conn:
            cur = conn.execute(
                "SELECT 1 FROM announcements WHERE id = ?", (announcement_id,)
            )
            if cur.fetchone() is None:
                return False
            conn.execute(
                "DELETE FROM announcement_read_receipts WHERE announcement_id = ?",
                (announcement_id,),
            )
            conn.execute(
                "DELETE FROM announcements WHERE id = ?", (announcement_id,)
            )
        return True

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
