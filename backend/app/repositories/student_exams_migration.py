"""student_exams 迁移 SQL。

学生端考试表由 `/student/exams` 路由、demo seeder 与期末复习校验共用。历史上
三处各自持有一份 DDL 副本(其中 final_review 缺 `(user_id, exam_date)` 复合索引),
先建表者决定 schema,任一处加列都会导致漂移。本模块收敛为唯一来源。

schema 在容器启动时幂等执行一次,不再位于请求路径上。
"""
from __future__ import annotations

import sqlite3

STUDENT_EXAMS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS student_exams (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    course_name TEXT NOT NULL,
    exam_date TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    location TEXT,
    seat_number TEXT,
    exam_type TEXT,
    reminder_enabled INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_student_exams_user_date ON student_exams(user_id, exam_date);
"""


def apply_student_exams_migration(conn: sqlite3.Connection) -> None:
    """幂等执行 student_exams schema。"""
    conn.executescript(STUDENT_EXAMS_SCHEMA_SQL)


__all__ = ["STUDENT_EXAMS_SCHEMA_SQL", "apply_student_exams_migration"]
