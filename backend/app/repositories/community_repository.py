from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database.sqlite_db import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class CommunityRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_post(self, *, university_id: str, author_id: str, title: str, content: str,
                    category: str, images: list[str], is_anonymous: bool) -> dict:
        post_id, now = _id("post"), _now()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO forum_posts
                   (id,university_id,author_id,title,content,category,images_json,is_anonymous,status,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?, 'published',?,?)""",
                (post_id, university_id, author_id, title, content, category,
                 json.dumps(images, ensure_ascii=False), int(is_anonymous), now, now),
            )
        return self.get_post(post_id)  # type: ignore[return-value]

    def get_post(self, post_id: str) -> Optional[dict]:
        with self.db.query() as conn:
            row = conn.execute("SELECT * FROM forum_posts WHERE id = ?", (post_id,)).fetchone()
        return dict(row) if row else None

    def list_posts(self, university_id: str, *, q: Optional[str], page: int, page_size: int) -> tuple[list[dict], int]:
        conditions = ["university_id = ?", "status = 'published'"]
        params: list[object] = [university_id]
        if q:
            conditions.append("(title LIKE ? OR content LIKE ?)")
            params.extend([f"%{q.strip()}%", f"%{q.strip()}%"])
        where = " AND ".join(conditions)
        with self.db.query() as conn:
            total = int(conn.execute(f"SELECT COUNT(*) n FROM forum_posts WHERE {where}", params).fetchone()["n"])
            rows = conn.execute(
                f"SELECT * FROM forum_posts WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
        return [dict(row) for row in rows], total

    def set_post_status(self, post_id: str, status: str) -> Optional[dict]:
        with self.db.transaction() as conn:
            conn.execute("UPDATE forum_posts SET status=?, updated_at=? WHERE id=?", (status, _now(), post_id))
        return self.get_post(post_id)

    def create_comment(self, *, post: dict, author_id: str, content: str,
                       parent_comment_id: Optional[str], is_anonymous: bool) -> dict:
        comment_id, now = _id("comment"), _now()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO forum_comments
                   (id,post_id,university_id,author_id,parent_comment_id,content,is_anonymous,status,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,'published',?,?)""",
                (comment_id, post["id"], post["university_id"], author_id, parent_comment_id,
                 content, int(is_anonymous), now, now),
            )
            conn.execute("UPDATE forum_posts SET comment_count=comment_count+1,updated_at=? WHERE id=?", (now, post["id"]))
            row = conn.execute("SELECT * FROM forum_comments WHERE id=?", (comment_id,)).fetchone()
        return dict(row)

    def list_comments(self, post_id: str) -> list[dict]:
        with self.db.query() as conn:
            rows = conn.execute(
                "SELECT * FROM forum_comments WHERE post_id=? AND status='published' ORDER BY created_at",
                (post_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def toggle(self, table: str, count_column: str, post_id: str, user_id: str, enabled: bool) -> dict:
        now = _now()
        with self.db.transaction() as conn:
            if enabled:
                cursor = conn.execute(
                    f"INSERT OR IGNORE INTO {table} (post_id,user_id,created_at) VALUES (?,?,?)",
                    (post_id, user_id, now),
                )
                delta = 1 if cursor.rowcount else 0
            else:
                cursor = conn.execute(f"DELETE FROM {table} WHERE post_id=? AND user_id=?", (post_id, user_id))
                delta = -1 if cursor.rowcount else 0
            if delta:
                conn.execute(
                    f"UPDATE forum_posts SET {count_column}=MAX(0,{count_column}+?),updated_at=? WHERE id=?",
                    (delta, now, post_id),
                )
        return self.get_post(post_id)  # type: ignore[return-value]

    def create_report(self, *, university_id: str, reporter_id: str, target_type: str,
                      target_id: str, reason: str, details: Optional[str]) -> dict:
        report_id, now = _id("report"), _now()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO forum_reports
                   (id,university_id,reporter_id,target_type,target_id,reason,details,status,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,'pending',?,?)""",
                (report_id, university_id, reporter_id, target_type, target_id, reason, details, now, now),
            )
            row = conn.execute("SELECT * FROM forum_reports WHERE id=?", (report_id,)).fetchone()
        return dict(row)

