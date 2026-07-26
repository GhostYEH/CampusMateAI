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
CREATE INDEX IF NOT EXISTS idx_documents_is_demo ON documents(is_demo);

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
