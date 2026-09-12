"""课程研究仓储(§7.4)。

封装 course_research_sessions / sources / reports 的 CRUD。
表结构由本仓储在初始化时通过 `CREATE TABLE IF NOT EXISTS` 创建,
不修改共享的 sqlite_db.py schema 字符串(保持 additive、幂等)。
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from ..database.sqlite_db import Database
from ..models.course_research import (
    CourseResearchReportRow,
    CourseResearchSessionRow,
    CourseResearchSourceRow,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS course_research_sessions (
    session_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    job_id TEXT,
    user_id TEXT NOT NULL,
    course_id TEXT,
    question TEXT NOT NULL,
    assistance_mode TEXT NOT NULL,
    academic_policy TEXT NOT NULL,
    source_policy_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'QUEUED',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finished_at TEXT,
    error_code TEXT,
    error_message TEXT,
    idempotency_key TEXT,
    UNIQUE(user_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_crs_user ON course_research_sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_crs_run ON course_research_sessions(run_id);

CREATE TABLE IF NOT EXISTS course_research_sources (
    source_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    source_ref TEXT,
    snippet TEXT,
    accessed_at TEXT NOT NULL,
    is_verified INTEGER NOT NULL DEFAULT 0,
    verification_note TEXT,
    supports_claim INTEGER,
    is_fabricated INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES course_research_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_crs_sources_session ON course_research_sources(session_id);
CREATE INDEX IF NOT EXISTS idx_crs_sources_user ON course_research_sources(user_id);

CREATE TABLE IF NOT EXISTS course_research_reports (
    report_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    verified_source_count INTEGER NOT NULL DEFAULT 0,
    unverified_source_count INTEGER NOT NULL DEFAULT 0,
    fallback_used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES course_research_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_crs_reports_session ON course_research_reports(session_id);
"""


class CourseResearchRepository:
    """course_research_sessions / sources / reports 仓储。"""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = self._db._connect()
        try:
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
        finally:
            self._db._release(conn)

    def _conn(self) -> sqlite3.Connection:
        return self._db._connect()

    def _release(self, conn: sqlite3.Connection) -> None:
        self._db._release(conn)

    # ===== Session =====

    def create_session(
        self,
        *,
        run_id: str,
        user_id: str,
        question: str,
        assistance_mode: str,
        academic_policy: str,
        source_policy: dict,
        course_id: Optional[str] = None,
        job_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        status: str = "QUEUED",
    ) -> CourseResearchSessionRow:
        session_id = _id("crs")
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO course_research_sessions "
                "(session_id, run_id, job_id, user_id, course_id, question, "
                "assistance_mode, academic_policy, source_policy_json, status, "
                "created_at, updated_at, idempotency_key) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id, run_id, job_id, user_id, course_id, question,
                    assistance_mode, academic_policy,
                    json.dumps(source_policy, ensure_ascii=False),
                    status, now, now, idempotency_key,
                ),
            )
            conn.commit()
        finally:
            self._release(conn)
        return self.get_session_by_run(run_id)  # type: ignore[return-value]

    def get_session(self, session_id: str) -> Optional[CourseResearchSessionRow]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM course_research_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return self._row_to_session(row) if row else None
        finally:
            self._release(conn)

    def get_session_by_run(self, run_id: str) -> Optional[CourseResearchSessionRow]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM course_research_sessions WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            return self._row_to_session(row) if row else None
        finally:
            self._release(conn)

    def find_session_by_idempotency(
        self, user_id: str, idempotency_key: str
    ) -> Optional[CourseResearchSessionRow]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM course_research_sessions "
                "WHERE user_id = ? AND idempotency_key = ?",
                (user_id, idempotency_key),
            ).fetchone()
            return self._row_to_session(row) if row else None
        finally:
            self._release(conn)

    def update_session(
        self,
        session_id: str,
        *,
        status: Optional[str] = None,
        finished_at: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        now = _now()
        fields: list[str] = ["updated_at = ?"]
        params: list[Any] = [now]
        for name, value in [
            ("status", status),
            ("finished_at", finished_at),
            ("error_code", error_code),
            ("error_message", error_message),
        ]:
            if value is not None:
                fields.append(f"{name} = ?")
                params.append(value)
        params.append(session_id)
        conn = self._conn()
        try:
            conn.execute(
                f"UPDATE course_research_sessions SET {', '.join(fields)} WHERE session_id = ?",
                params,
            )
            conn.commit()
        finally:
            self._release(conn)

    def list_sessions_by_user(
        self, user_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[CourseResearchSessionRow]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM course_research_sessions WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset),
            ).fetchall()
            return [self._row_to_session(r) for r in rows]
        finally:
            self._release(conn)

    @staticmethod
    def _row_to_session(row) -> CourseResearchSessionRow:
        data = dict(row)
        return CourseResearchSessionRow(
            session_id=data["session_id"],
            run_id=data["run_id"],
            user_id=data["user_id"],
            course_id=data["course_id"],
            question=data["question"],
            assistance_mode=data["assistance_mode"],
            academic_policy=data["academic_policy"],
            source_policy_json=data["source_policy_json"],
            status=data["status"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            job_id=data["job_id"],
            idempotency_key=data["idempotency_key"],
            finished_at=data["finished_at"],
            error_code=data["error_code"],
            error_message=data["error_message"],
        )

    # ===== Sources =====

    def add_source(
        self,
        *,
        session_id: str,
        user_id: str,
        source_type: str,
        title: str,
        accessed_at: str,
        url: Optional[str] = None,
        source_ref: Optional[str] = None,
        snippet: Optional[str] = None,
        is_verified: bool = False,
        verification_note: Optional[str] = None,
        supports_claim: Optional[bool] = None,
        is_fabricated: bool = False,
        metadata: Optional[dict] = None,
    ) -> CourseResearchSourceRow:
        source_id = _id("crso")
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO course_research_sources "
                "(source_id, session_id, user_id, source_type, title, url, source_ref, "
                "snippet, accessed_at, is_verified, verification_note, supports_claim, "
                "is_fabricated, metadata_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    source_id, session_id, user_id, source_type, title, url, source_ref,
                    snippet, accessed_at, int(is_verified), verification_note,
                    None if supports_claim is None else int(supports_claim),
                    int(is_fabricated),
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()
        finally:
            self._release(conn)
        return self.get_source(source_id, user_id=user_id)  # type: ignore[return-value]

    def update_source(
        self,
        source_id: str,
        *,
        is_verified: Optional[bool] = None,
        verification_note: Optional[str] = None,
        supports_claim: Optional[bool] = None,
        is_fabricated: Optional[bool] = None,
    ) -> None:
        fields: list[str] = []
        params: list[Any] = []
        for name, value in [
            ("is_verified", is_verified),
            ("verification_note", verification_note),
            ("supports_claim", supports_claim),
            ("is_fabricated", is_fabricated),
        ]:
            if value is not None:
                fields.append(f"{name} = ?")
                if name in ("is_verified", "is_fabricated"):
                    params.append(int(value))
                elif name == "supports_claim":
                    params.append(int(value))
                else:
                    params.append(value)
        if not fields:
            return
        params.append(source_id)
        conn = self._conn()
        try:
            conn.execute(
                f"UPDATE course_research_sources SET {', '.join(fields)} WHERE source_id = ?",
                params,
            )
            conn.commit()
        finally:
            self._release(conn)

    def get_source(
        self, source_id: str, *, user_id: str
    ) -> Optional[CourseResearchSourceRow]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM course_research_sources WHERE source_id = ? AND user_id = ?",
                (source_id, user_id),
            ).fetchone()
            return self._row_to_source(row) if row else None
        finally:
            self._release(conn)

    def list_sources(
        self, session_id: str, *, user_id: str
    ) -> list[CourseResearchSourceRow]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM course_research_sources "
                "WHERE session_id = ? AND user_id = ? ORDER BY created_at ASC",
                (session_id, user_id),
            ).fetchall()
            return [self._row_to_source(r) for r in rows]
        finally:
            self._release(conn)

    @staticmethod
    def _row_to_source(row) -> CourseResearchSourceRow:
        data = dict(row)
        return CourseResearchSourceRow(
            source_id=data["source_id"],
            session_id=data["session_id"],
            user_id=data["user_id"],
            source_type=data["source_type"],
            title=data["title"],
            url=data["url"],
            accessed_at=data["accessed_at"],
            created_at=data["created_at"],
            snippet=data["snippet"],
            source_ref=data["source_ref"],
            is_verified=bool(data["is_verified"]),
            verification_note=data["verification_note"],
            supports_claim=None if data["supports_claim"] is None else bool(data["supports_claim"]),
            is_fabricated=bool(data["is_fabricated"]),
            metadata_json=data["metadata_json"],
        )

    # ===== Report =====

    def create_report(
        self,
        *,
        session_id: str,
        user_id: str,
        artifact_id: str,
        content_hash: str,
        mime_type: str,
        size_bytes: int,
        verified_source_count: int = 0,
        unverified_source_count: int = 0,
        fallback_used: bool = False,
    ) -> CourseResearchReportRow:
        report_id = _id("crr")
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO course_research_reports "
                "(report_id, session_id, user_id, artifact_id, content_hash, mime_type, "
                "size_bytes, verified_source_count, unverified_source_count, fallback_used, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    report_id, session_id, user_id, artifact_id, content_hash, mime_type,
                    size_bytes, verified_source_count, unverified_source_count,
                    int(fallback_used), now,
                ),
            )
            conn.commit()
        finally:
            self._release(conn)
        return self.get_report_by_session(session_id, user_id=user_id)  # type: ignore[return-value]

    def get_report_by_session(
        self, session_id: str, *, user_id: str
    ) -> Optional[CourseResearchReportRow]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM course_research_reports WHERE session_id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
            if not row:
                return None
            data = dict(row)
            return CourseResearchReportRow(
                report_id=data["report_id"],
                session_id=data["session_id"],
                user_id=data["user_id"],
                artifact_id=data["artifact_id"],
                content_hash=data["content_hash"],
                mime_type=data["mime_type"],
                size_bytes=data["size_bytes"],
                created_at=data["created_at"],
                verified_source_count=data["verified_source_count"],
                unverified_source_count=data["unverified_source_count"],
                fallback_used=bool(data["fallback_used"]),
            )
        finally:
            self._release(conn)


__all__ = ["CourseResearchRepository"]