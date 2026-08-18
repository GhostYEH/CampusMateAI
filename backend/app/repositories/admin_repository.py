"""管理员只读聚合查询。

这些查询直接在 SQLite 中完成 COUNT / GROUP BY，避免管理端下载列表后再计算统计。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..database.sqlite_db import Database


class AdminRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def overview(self, *, recent_limit: int = 5) -> dict[str, Any]:
        with self._db.query() as conn:
            def scalar(sql: str, params: tuple = ()) -> int:
                return int(conn.execute(sql, params).fetchone()["n"])

            role_rows = conn.execute(
                "SELECT role, COUNT(*) AS n FROM users GROUP BY role"
            ).fetchall()
            roles = {row["role"]: int(row["n"]) for row in role_rows}
            recent_users = conn.execute(
                """SELECT id, username, display_name, role, created_at
                   FROM users ORDER BY created_at DESC LIMIT ?""",
                (recent_limit,),
            ).fetchall()
            growth = conn.execute(
                """SELECT date(created_at) AS day, COUNT(*) AS count
                   FROM users
                   WHERE created_at >= datetime('now', '-6 days')
                   GROUP BY date(created_at) ORDER BY day ASC"""
            ).fetchall()
            active_students = conn.execute(
                """SELECT COUNT(DISTINCT e.user_id) AS n
                   FROM enrollments e JOIN users u ON u.id = e.user_id
                   WHERE e.status = 'active' AND u.role = 'student' AND u.is_active = 1"""
            ).fetchone()["n"]
            return {
                "user_count": scalar("SELECT COUNT(*) AS n FROM users"),
                "student_count": roles.get("student", 0),
                "teacher_count": roles.get("teacher", 0),
                "admin_count": roles.get("admin", 0),
                "active_user_count": scalar("SELECT COUNT(*) AS n FROM users WHERE is_active = 1"),
                "inactive_count": scalar("SELECT COUNT(*) AS n FROM users WHERE is_active = 0"),
                "today_new_user_count": scalar("SELECT COUNT(*) AS n FROM users WHERE date(created_at) = date('now')"),
                "last_7_days_new_user_count": scalar("SELECT COUNT(*) AS n FROM users WHERE created_at >= datetime('now', '-6 days')"),
                "course_count": scalar("SELECT COUNT(*) AS n FROM courses"),
                "active_course_count": scalar("SELECT COUNT(*) AS n FROM courses WHERE status = 'active'"),
                "class_count": scalar("SELECT COUNT(*) AS n FROM class_groups"),
                "active_student_count": int(active_students),
                "document_count": scalar("SELECT COUNT(*) AS n FROM documents"),
                "chunk_count": scalar("SELECT COUNT(*) AS n FROM chunks"),
                "user_growth": [dict(row) for row in growth],
                "role_distribution": roles,
                "recent_users": [dict(row) for row in recent_users],
                "recent_admin_operations": [],
            }

    def system_probe(self) -> dict[str, Any]:
        started = datetime.now(timezone.utc)
        with self._db.query() as conn:
            before = datetime.now(timezone.utc)
            conn.execute("SELECT 1").fetchone()
            latency_ms = round((datetime.now(timezone.utc) - before).total_seconds() * 1000, 2)
            document_count = int(conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"])
            chunk_count = int(conn.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"])
        return {
            "api_status": "ok",
            "database_status": "ok",
            "database_query_latency_ms": latency_ms,
            "knowledge_base_initialized": chunk_count > 0,
            "document_count": document_count,
            "chunk_count": chunk_count,
            "knowledge_base_status": "ready" if chunk_count > 0 else "empty",
            "probe_started_at": started.isoformat(),
        }
