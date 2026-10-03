from __future__ import annotations

import uuid
from typing import List, Optional, Tuple
from datetime import datetime, timezone

from ..database.sqlite_db import Database
from ..models.multi_role import NoticeRow


def normalize_notice_time(value: object) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().replace(".", "", 1).isdigit()):
        timestamp = float(value)
        if abs(timestamp) >= 10_000_000_000:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return str(value)


class NoticeRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_or_update_notice(
        self,
        user_id: str,
        source: str,
        external_id: str,
        title: str,
        content: Optional[str] = None,
        course_id: Optional[str] = None,
        published_at: Optional[str] = None,
        source_url: Optional[str] = None,
        last_synced_at: Optional[str] = None,
    ) -> NoticeRow:
        now_iso = datetime.now(timezone.utc).isoformat()
        
        with self._db.transaction() as conn:
            # Check if exists
            cur = conn.execute(
                "SELECT * FROM notices WHERE user_id = ? AND source = ? AND external_id = ?",
                (user_id, source, external_id)
            )
            row = cur.fetchone()
            
            if row:
                notice_id = row["id"]
                conn.execute(
                    """UPDATE notices SET 
                        title = ?, content = ?, course_id = ?, published_at = ?, 
                        source_url = ?, last_synced_at = ?, updated_at = ?
                       WHERE id = ?""",
                    (title, content, course_id, published_at, source_url, last_synced_at, now_iso, notice_id)
                )
                cur = conn.execute("SELECT * FROM notices WHERE id = ?", (notice_id,))
                return NoticeRow.from_row(cur.fetchone())
            else:
                notice_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO notices (
                        id, user_id, source, external_id, course_id, title, 
                        content, published_at, source_url, last_synced_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (notice_id, user_id, source, external_id, course_id, title, 
                     content, published_at, source_url, last_synced_at, now_iso, now_iso)
                )
                cur = conn.execute("SELECT * FROM notices WHERE id = ?", (notice_id,))
                return NoticeRow.from_row(cur.fetchone())

    def list_notices(self, user_id: str) -> List[NoticeRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM notices WHERE user_id = ? ORDER BY published_at DESC", (user_id,)
            )
            return [NoticeRow.from_row(r) for r in cur.fetchall()]

    def list_visible_notices(
        self,
        user_id: str,
        *,
        student: bool,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        """Merge both sources, applying visibility and pagination in the database."""
        visible = """WITH visible AS (
            SELECT n.id, n.title, n.source,
                   campus_notice_time(COALESCE(NULLIF(n.published_at, ''), n.created_at)) AS time,
                   0 AS unread, n.source AS category, n.content,
                   'unified' AS kind, n.source_url
            FROM notices n WHERE n.user_id = ?
            UNION ALL
            SELECT a.id, a.title,
                   COALESCE(NULLIF(g.name, ''), NULLIF(c.name, ''), a.author_id) AS source,
                   COALESCE(NULLIF(a.published_at, ''), a.created_at) AS time,
                   CASE WHEN ? AND receipt.announcement_id IS NULL THEN 1 ELSE 0 END AS unread,
                   c.name AS category, a.content, 'announcement' AS kind, NULL AS source_url
            FROM announcements a
            JOIN class_groups g ON g.id = a.class_group_id
            LEFT JOIN courses c ON c.id = g.course_id
            LEFT JOIN announcement_read_receipts receipt
                   ON receipt.announcement_id = a.id AND receipt.student_id = ?
            WHERE a.status = 'published' AND (
                NOT ? OR EXISTS (
                    SELECT 1 FROM enrollments e
                    WHERE e.class_group_id = g.id AND e.user_id = ? AND e.status = 'active'
                )
            )
        )"""
        params = [user_id, int(student), user_id, int(student), user_id]
        where = " WHERE unread = 1" if unread_only else ""
        with self._db.query() as conn:
            conn.create_function("campus_notice_time", 1, normalize_notice_time, deterministic=True)
            total = int(conn.execute(visible + " SELECT COUNT(*) AS n FROM visible" + where, params).fetchone()["n"])
            rows = conn.execute(
                visible + " SELECT * FROM visible" + where + " ORDER BY COALESCE(time, '') DESC, kind ASC, id ASC LIMIT ? OFFSET ?",
                params + [page_size, (page - 1) * page_size],
            ).fetchall()
        return [dict(row) for row in rows], total

    def list_chaoxing_for_event_backfill(
        self,
        *,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[List[NoticeRow], int]:
        """分页读取学习通通知，供受控 Learner Event 回填使用。"""
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must stay within 1..100")
        conditions = ["source = 'chaoxing'"]
        params: list = []
        if user_id is not None:
            conditions.insert(0, "user_id = ?")
            params.append(user_id)
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            total = int(
                conn.execute(f"SELECT COUNT(*) AS n FROM notices{where}", params)
                .fetchone()["n"]
            )
            rows = conn.execute(
                f"SELECT * FROM notices{where} ORDER BY user_id ASC, id ASC LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()
        return [NoticeRow.from_row(row) for row in rows], total
