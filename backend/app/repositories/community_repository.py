from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from ..database.sqlite_db import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class CommunityRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_post(self, *, university_id: str, author_id: str, title: str, content: str,
                    category: str, images: list[str], is_anonymous: bool,
                    extra: Optional[dict[str, Any]] = None) -> dict:
        post_id, now = _id("post"), _now()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO forum_posts
                   (id,university_id,author_id,title,content,category,images_json,is_anonymous,status,extra_json,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,'published',?,?,?)""",
                (post_id, university_id, author_id, title, content, category,
                 json.dumps(images, ensure_ascii=False), int(is_anonymous),
                 json.dumps(extra or {}, ensure_ascii=False), now, now),
            )
        return self.get_post(post_id)  # type: ignore[return-value]

    def get_post(self, post_id: str) -> Optional[dict]:
        with self.db.query() as conn:
            row = conn.execute("SELECT * FROM forum_posts WHERE id = ?", (post_id,)).fetchone()
        return dict(row) if row else None

    def list_posts(self, university_id: str, *, q: Optional[str], page: int, page_size: int,
                   category: Optional[str] = None, sort: str = "time") -> tuple[list[dict], int]:
        conditions = ["university_id = ?", "status = 'published'"]
        params: list[object] = [university_id]
        if category:
            conditions.append("category = ?")
            params.append(category)
        if q:
            conditions.append("(title LIKE ? OR content LIKE ?)")
            params.extend([f"%{q.strip()}%", f"%{q.strip()}%"])
        where = " AND ".join(conditions)
        order = "like_count + comment_count * 2 DESC, created_at DESC" if sort == "hot" else "created_at DESC"
        with self.db.query() as conn:
            total = int(conn.execute(f"SELECT COUNT(*) n FROM forum_posts WHERE {where}", params).fetchone()["n"])
            rows = conn.execute(
                f"SELECT * FROM forum_posts WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
        return [dict(row) for row in rows], total

    def update_post(self, post_id: str, *, title: Optional[str] = None, content: Optional[str] = None,
                    category: Optional[str] = None, images: Optional[list[str]] = None,
                    is_anonymous: Optional[bool] = None, extra: Optional[dict] = None) -> Optional[dict]:
        sets: list[str] = []
        params: list[object] = []
        if title is not None:
            sets.append("title = ?"); params.append(title)
        if content is not None:
            sets.append("content = ?"); params.append(content)
        if category is not None:
            sets.append("category = ?"); params.append(category)
        if images is not None:
            sets.append("images_json = ?"); params.append(json.dumps(images, ensure_ascii=False))
        if is_anonymous is not None:
            sets.append("is_anonymous = ?"); params.append(int(is_anonymous))
        if extra is not None:
            sets.append("extra_json = ?"); params.append(json.dumps(extra, ensure_ascii=False))
        if not sets:
            return self.get_post(post_id)
        sets.append("updated_at = ?"); params.append(_now()); params.append(post_id)
        with self.db.transaction() as conn:
            conn.execute(f"UPDATE forum_posts SET {', '.join(sets)} WHERE id = ?", params)
        return self.get_post(post_id)

    def increment_view(self, post_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE forum_posts SET view_count = view_count + 1 WHERE id = ?", (post_id,))

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

    def is_liked(self, post_id: str, user_id: str) -> bool:
        with self.db.query() as conn:
            row = conn.execute("SELECT 1 FROM forum_likes WHERE post_id=? AND user_id=?", (post_id, user_id)).fetchone()
        return row is not None

    def is_favorited(self, post_id: str, user_id: str) -> bool:
        with self.db.query() as conn:
            row = conn.execute("SELECT 1 FROM forum_favorites WHERE post_id=? AND user_id=?", (post_id, user_id)).fetchone()
        return row is not None

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

    def list_reports(self, university_id: Optional[str] = None, *, status: Optional[str] = None,
                     page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        conditions: list[str] = []
        params: list[object] = []
        if university_id:
            conditions.append("university_id = ?"); params.append(university_id)
        if status:
            conditions.append("status = ?"); params.append(status)
        where = " AND ".join(conditions) if conditions else "1=1"
        with self.db.query() as conn:
            total = int(conn.execute(f"SELECT COUNT(*) n FROM forum_reports WHERE {where}", params).fetchone()["n"])
            rows = conn.execute(
                f"SELECT * FROM forum_reports WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
        return [dict(row) for row in rows], total

    def get_report(self, report_id: str) -> Optional[dict]:
        with self.db.query() as conn:
            row = conn.execute("SELECT * FROM forum_reports WHERE id = ?", (report_id,)).fetchone()
        return dict(row) if row else None

    def update_report_status(self, report_id: str, status: str) -> Optional[dict]:
        with self.db.transaction() as conn:
            conn.execute("UPDATE forum_reports SET status=?, updated_at=? WHERE id=?", (status, _now(), report_id))
        return self.get_report(report_id)

    def list_posts_admin(self, *, university_id: Optional[str] = None, status: Optional[str] = None,
                         q: Optional[str] = None, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        conditions: list[str] = []
        params: list[object] = []
        if university_id:
            conditions.append("university_id = ?"); params.append(university_id)
        if status:
            conditions.append("status = ?"); params.append(status)
        if q:
            conditions.append("(title LIKE ? OR content LIKE ?)")
            params.extend([f"%{q.strip()}%", f"%{q.strip()}%"])
        where = " AND ".join(conditions) if conditions else "1=1"
        with self.db.query() as conn:
            total = int(conn.execute(f"SELECT COUNT(*) n FROM forum_posts WHERE {where}", params).fetchone()["n"])
            rows = conn.execute(
                f"SELECT * FROM forum_posts WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
        return [dict(row) for row in rows], total

    def migrate_lost_found(self) -> int:
        """把 lost_found_items 旧数据迁移到 forum_posts(category=lostfound)。幂等：按 id 去重。返回迁移条数。"""
        try:
            with self.db.query() as conn:
                rows = conn.execute("SELECT * FROM lost_found_items").fetchall()
        except Exception:
            return 0
        if not rows:
            return 0
        migrated = 0
        for row in rows:
            r = dict(row)
            existing = self.get_post(r["id"])
            if existing:
                continue
            extra = {
                "kind": r.get("kind", "lost"),
                "location": r.get("location"),
                "contact": r.get("contact"),
                "contact_visibility": r.get("contact_visibility", "private"),
            }
            extra = {k: v for k, v in extra.items() if v is not None}
            now = r.get("created_at") or _now()
            with self.db.transaction() as conn:
                conn.execute(
                    """INSERT OR IGNORE INTO forum_posts
                       (id,university_id,author_id,title,content,category,images_json,is_anonymous,status,extra_json,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,'[]',0,?,?,?,?)""",
                    (r["id"], r.get("university_id") or "", r.get("owner_id", ""),
                     r.get("title", ""), r.get("content") or "", "lostfound",
                     json.dumps(extra, ensure_ascii=False), "published" if r.get("status", "open") == "open" else "deleted",
                     now, r.get("updated_at") or now),
                )
            migrated += 1
        return migrated
