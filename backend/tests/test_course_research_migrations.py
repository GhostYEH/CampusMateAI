from __future__ import annotations

import sqlite3

from app.database.sqlite_db import Database
from app.repositories.course_research_repository import CourseResearchRepository


def _create_legacy_course_research_schema(db_path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO users (id, username, password_hash, role, created_at, updated_at)
            VALUES ('user-1', 'user-1', 'hash', 'student', '2026-01-01', '2026-01-01');

            CREATE TABLE course_research_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                course_id TEXT,
                question_digest TEXT NOT NULL,
                requested_mode TEXT NOT NULL,
                effective_mode TEXT NOT NULL,
                academic_policy TEXT NOT NULL,
                source_policy_json TEXT NOT NULL,
                status TEXT NOT NULL,
                roles_json TEXT NOT NULL,
                warning_codes_json TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, idempotency_key)
            );
            INSERT INTO course_research_sessions
                (id, user_id, course_id, question_digest, requested_mode, effective_mode,
                 academic_policy, source_policy_json, status, roles_json, warning_codes_json,
                 idempotency_key, request_hash, created_at, updated_at)
            VALUES
                ('research-1', 'user-1', 'course-1', 'question digest', 'guided', 'guided',
                 'verified_only', '{}', 'COMPLETED', '[]', '[]', 'idem-1', 'hash-1',
                 '2026-01-01', '2026-01-01');

            CREATE TABLE course_research_sources (
                id TEXT PRIMARY KEY,
                research_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                safe_label TEXT NOT NULL,
                content_ref TEXT,
                content_digest TEXT NOT NULL,
                verification_status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(research_id) REFERENCES course_research_sessions(id) ON DELETE CASCADE
            );
            INSERT INTO course_research_sources
                (id, research_id, source_type, safe_label, content_ref, content_digest,
                 verification_status, created_at)
            VALUES
                ('source-1', 'research-1', 'course_material', '讲义', 'item-1', 'digest-1',
                 'verified', '2026-01-01');

            CREATE TABLE course_research_steps (
                id TEXT PRIMARY KEY,
                research_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL,
                public_summary TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(research_id, sequence),
                FOREIGN KEY(research_id) REFERENCES course_research_sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE course_research_reports (
                id TEXT PRIMARY KEY,
                research_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                citation_ids_json TEXT NOT NULL,
                artifact_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(research_id) REFERENCES course_research_sessions(id) ON DELETE CASCADE
            );
            """
        )


def test_legacy_course_research_schema_is_upgraded_idempotently(tmp_path):
    db_path = tmp_path / "legacy-course-research.db"
    _create_legacy_course_research_schema(db_path)

    database = Database(db_path)
    repository = CourseResearchRepository(database)

    session = repository.get_session("research-1")
    assert session is not None
    assert session.run_id == "legacy-course-research-research-1"
    assert session.question == "question digest"

    sources = repository.list_sources("research-1", user_id="user-1")
    assert len(sources) == 1
    assert sources[0].title == "讲义"
    assert sources[0].is_verified is True
    assert sources[0].source_ref == "item-1"

    CourseResearchRepository(database)
    with database.query() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM course_research_sessions"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM course_research_sources"
        ).fetchone()[0] == 1

    database.dispose()
