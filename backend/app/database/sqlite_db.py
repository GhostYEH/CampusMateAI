"""SQLite 数据库初始化(基于 sqlite3，无 ORM 依赖)。

为后续迁移 PostgreSQL 保留空间：所有 SQL 使用标准方言，
切换时仅需替换连接层。

设计要点：
- 文件模式：每请求新连接 + WAL，避免多线程读阻塞。
- 内存模式：使用单条共享连接(`check_same_thread=False`)，
  因为 `:memory:` 库的 schema 仅存在于打开它的连接中。
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.config import Settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_department TEXT,
    source_type TEXT,
    original_filename TEXT,
    content_hash TEXT UNIQUE NOT NULL,
    content_text TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    published_at TEXT,
    updated_at TEXT,
    effective_from TEXT,
    effective_to TEXT,
    version TEXT,
    applicable_students TEXT,
    is_official INTEGER DEFAULT 0,
    is_expired INTEGER DEFAULT 0,
    is_demo INTEGER DEFAULT 0,
    file_size INTEGER,
    file_ext TEXT,
    imported_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_title ON documents(title);
-- idx_documents_is_demo 在 _migrate() 中创建:旧库可能缺 is_demo 列,
-- 在 ALTER TABLE 之前创建索引会触发 "no such column: is_demo"。

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    section TEXT,
    position INTEGER NOT NULL,
    content TEXT NOT NULL,
    page_number INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES documents(document_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    last_message_at TEXT
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    actor_user_id TEXT,
    actor_name_snapshot TEXT,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    description TEXT NOT NULL,
    result TEXT NOT NULL DEFAULT 'success',
    request_id TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_user_id);
"""


# 多角色协同平台 schema —— 教师/课程/班级/学生/任务/提交。
# 所有新表均使用 IF NOT EXISTS，保证幂等。
# 不破坏既有 documents/chunks/conversations/app_meta 表。
MULTI_ROLE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'student',
    display_name TEXT,
    student_number TEXT,
    teacher_number TEXT,
    college TEXT,
    major TEXT,
    grade TEXT,
    avatar_url TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_student_number ON users(student_number);
CREATE INDEX IF NOT EXISTS idx_users_teacher_number ON users(teacher_number);
-- SQLite 支持部分唯一索引(NULL 不参与唯一约束)
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_student_number_unique
    ON users(student_number) WHERE student_number IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_teacher_number_unique
    ON users(teacher_number) WHERE teacher_number IS NOT NULL;

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    revoked INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);

CREATE TABLE IF NOT EXISTS courses (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT,
    semester TEXT,
    description TEXT,
    teacher_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(teacher_id) REFERENCES users(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_courses_teacher_id ON courses(teacher_id);
CREATE INDEX IF NOT EXISTS idx_courses_status ON courses(status);

CREATE TABLE IF NOT EXISTS class_groups (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL,
    name TEXT NOT NULL,
    class_code TEXT,
    invite_code TEXT NOT NULL UNIQUE,
    description TEXT,
    capacity INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_class_groups_course_id ON class_groups(course_id);

CREATE TABLE IF NOT EXISTS enrollments (
    id TEXT PRIMARY KEY,
    class_group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    member_role TEXT NOT NULL DEFAULT 'student',
    status TEXT NOT NULL DEFAULT 'active',
    joined_at TEXT NOT NULL,
    UNIQUE(class_group_id, user_id),
    FOREIGN KEY(class_group_id) REFERENCES class_groups(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_enrollments_class_group_id ON enrollments(class_group_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_user_id ON enrollments(user_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_status ON enrollments(status);

CREATE TABLE IF NOT EXISTS announcements (
    id TEXT PRIMARY KEY,
    class_group_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    require_read INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft',
    published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(class_group_id) REFERENCES class_groups(id) ON DELETE CASCADE,
    FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_announcements_class_group_id ON announcements(class_group_id);
CREATE INDEX IF NOT EXISTS idx_announcements_status ON announcements(status);
CREATE INDEX IF NOT EXISTS idx_announcements_published_at ON announcements(published_at);

CREATE TABLE IF NOT EXISTS campus_activities (
    id TEXT PRIMARY KEY,
    author_id TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    content TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'campus',
    location TEXT,
    registration_deadline TEXT,
    starts_at TEXT,
    ends_at TEXT,
    capacity INTEGER,
    status TEXT NOT NULL DEFAULT 'draft',
    published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_campus_activities_status ON campus_activities(status);
CREATE INDEX IF NOT EXISTS idx_campus_activities_starts_at ON campus_activities(starts_at);
CREATE INDEX IF NOT EXISTS idx_campus_activities_deadline ON campus_activities(registration_deadline);

CREATE TABLE IF NOT EXISTS announcement_read_receipts (
    announcement_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    read_at TEXT NOT NULL,
    PRIMARY KEY (announcement_id, student_id),
    FOREIGN KEY(announcement_id) REFERENCES announcements(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_read_receipts_announcement_id ON announcement_read_receipts(announcement_id);
CREATE INDEX IF NOT EXISTS idx_read_receipts_student_id ON announcement_read_receipts(student_id);

CREATE TABLE IF NOT EXISTS assignments (
    id TEXT PRIMARY KEY,
    class_group_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    deadline TEXT,
    submission_types TEXT,
    max_score REAL,
    allow_resubmit INTEGER DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft',
    published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(class_group_id) REFERENCES class_groups(id) ON DELETE CASCADE,
    FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_assignments_class_group_id ON assignments(class_group_id);
CREATE INDEX IF NOT EXISTS idx_assignments_status ON assignments(status);
CREATE INDEX IF NOT EXISTS idx_assignments_deadline ON assignments(deadline);

CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    text_content TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    submitted_at TEXT,
    updated_at TEXT NOT NULL,
    score REAL,
    teacher_comment TEXT,
    UNIQUE(assignment_id, student_id),
    FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_submissions_assignment_id ON submissions(assignment_id);
CREATE INDEX IF NOT EXISTS idx_submissions_student_id ON submissions(student_id);
CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);

CREATE TABLE IF NOT EXISTS submission_attachments (
    id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER,
    storage_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(submission_id) REFERENCES submissions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_submission_attachments_submission_id ON submission_attachments(submission_id);

CREATE TABLE IF NOT EXISTS assignment_attachments (
    id TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER,
    storage_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_assignment_attachments_assignment_id ON assignment_attachments(assignment_id);
"""


# 个人待办 schema —— 学生从通知抽取生成的个人任务。
# 与 assignments(教师发布的班级作业)严格分离:
# - user_id 绑定 JWT 用户,禁止跨用户读取
# - source_text 保留原通知文本,确保可追溯
# - deleted_at 软删除字段,避免立即物理删除
PERSONAL_TASK_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS personal_tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    target_students TEXT,
    deadline TEXT,
    materials TEXT,
    submission_method TEXT,
    location TEXT,
    source_name TEXT,
    source_text TEXT,
    source_notice_id TEXT,
    priority TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'pending',
    reminder_minutes INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    deleted_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_personal_tasks_user_id ON personal_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_personal_tasks_status ON personal_tasks(status);
CREATE INDEX IF NOT EXISTS idx_personal_tasks_deadline ON personal_tasks(deadline);
CREATE INDEX IF NOT EXISTS idx_personal_tasks_priority ON personal_tasks(priority);
CREATE INDEX IF NOT EXISTS idx_personal_tasks_user_status ON personal_tasks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_personal_tasks_user_deadline ON personal_tasks(user_id, deadline);
"""


# 学习陪伴 schema —— 学习会话 / 休息记录。
# 所有记录绑定 user_id(JWT 用户隔离)。状态机由仓库层与路由层共同校验。
STUDY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS study_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    goal TEXT,
    related_task_id TEXT,
    started_at TEXT NOT NULL,
    paused_at TEXT,
    ended_at TEXT,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    pause_seconds INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    self_report TEXT,
    self_report_tags TEXT,
    expression_signal TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_study_sessions_user_id ON study_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_study_sessions_status ON study_sessions(status);
CREATE INDEX IF NOT EXISTS idx_study_sessions_user_status ON study_sessions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_study_sessions_started_at ON study_sessions(started_at);

CREATE TABLE IF NOT EXISTS study_breaks (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    reason TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES study_sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_study_breaks_session_id ON study_breaks(session_id);
"""


class Database:
    """线程安全的 SQLite 包装。

    - 文件模式：每请求新连接，WAL + 短超时。
    - 内存模式：单条共享连接(必须 `check_same_thread=False`)，
      所有读写都通过同一连接，保证 schema 与数据可见性。
    """

    def __init__(self, db_path: Path | None) -> None:
        self._is_memory = db_path is None
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        # 内存模式：共享单连接；文件模式：None
        self._shared_conn: sqlite3.Connection | None = None
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        if self._is_memory:
            # 内存模式必须复用同一连接
            if self._shared_conn is None:
                self._shared_conn = sqlite3.connect(
                    ":memory:",
                    check_same_thread=False,
                    timeout=30.0,
                )
                self._shared_conn.row_factory = sqlite3.Row
                self._shared_conn.execute("PRAGMA foreign_keys=ON;")
            return self._shared_conn
        conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _release(self, conn: sqlite3.Connection) -> None:
        """关闭连接(内存模式下的共享连接不关闭)。"""
        if self._is_memory:
            return
        conn.close()

    def _init_schema(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(SCHEMA_SQL)
                conn.executescript(MULTI_ROLE_SCHEMA_SQL)
                conn.executescript(PERSONAL_TASK_SCHEMA_SQL)
                conn.executescript(STUDY_SCHEMA_SQL)
                self._migrate(conn)
                conn.commit()
            finally:
                self._release(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """轻量级迁移：补齐旧库缺失的列(幂等)。"""
        # 获取 documents 表的现有列
        cur = conn.execute("PRAGMA table_info(documents)")
        existing_cols = {row["name"] for row in cur.fetchall()}
        if "is_demo" not in existing_cols:
            conn.execute(
                "ALTER TABLE documents ADD COLUMN is_demo INTEGER DEFAULT 0"
            )
            # 旧数据默认非演示资料
            conn.execute("UPDATE documents SET is_demo = 0 WHERE is_demo IS NULL")
        # 补建索引(若旧库不存在)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_documents_is_demo ON documents(is_demo)"
        )
        # 多角色表均为 CREATE TABLE IF NOT EXISTS，已自动幂等。

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """事务上下文：成功提交，异常回滚。"""
        with self._lock:
            conn = self._connect()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                self._release(conn)

    @contextmanager
    def query(self) -> Iterator[sqlite3.Connection]:
        """只读查询上下文(自动关闭连接)。"""
        with self._lock:
            conn = self._connect()
            try:
                yield conn
            finally:
                self._release(conn)

    def dispose(self) -> None:
        """释放底层连接(主要用于测试清理)。

        - 内存模式: 关闭共享连接。
        - 文件模式: 执行 WAL checkpoint(TRUNCATE) 以便释放 -wal/-shm 文件锁,
          让外部 cleanup(如 TemporaryDirectory) 能在 Windows 上删除 db 文件。
        """
        with self._lock:
            if self._is_memory:
                if self._shared_conn is not None:
                    try:
                        self._shared_conn.close()
                    finally:
                        self._shared_conn = None
                return
            # 文件模式: 短连接做 checkpoint
            try:
                conn = sqlite3.connect(self._db_path, timeout=30.0)
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                conn.commit()
                conn.close()
            except Exception:
                # 测试清理不应因 checkpoint 失败而中断
                pass


_db_instance: Database | None = None


def init_db(settings: Settings) -> Database:
    """初始化全局 Database 单例。"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(settings.database_path)
    return _db_instance


def get_db() -> Database:
    """FastAPI 依赖：返回全局 Database 实例。"""
    if _db_instance is None:
        raise RuntimeError("Database 未初始化，请先调用 init_db()")
    return _db_instance


def reset_db_for_tests() -> Database:
    """测试专用：创建一个全新的内存库并替换单例。"""
    global _db_instance
    if _db_instance is not None and _db_instance._is_memory:
        # 关闭旧的共享连接
        try:
            if _db_instance._shared_conn is not None:
                _db_instance._shared_conn.close()
        except Exception:
            pass
    _db_instance = Database(None)
    return _db_instance


__all__ = ["Database", "init_db", "get_db", "reset_db_for_tests"]
