import sqlite3

from app.database.sqlite_db import Database


def test_legacy_courses_schema_is_migrated_before_external_id_index(tmp_path):
    """An existing courses table must start even when it predates Chaoxing fields."""
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE courses (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT,
                semester TEXT,
                description TEXT,
                teacher_id TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO courses (id, name, status, created_at, updated_at)
            VALUES ('legacy-course', 'Legacy course', 'published', '2026-01-01', '2026-01-01');
            """
        )

    database = Database(db_path)

    with database.query() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(courses)")}
        indexes = {row["name"] for row in conn.execute("PRAGMA index_list(courses)")}
        course = conn.execute("SELECT name, external_id FROM courses WHERE id = 'legacy-course'").fetchone()

    assert {"provider", "external_id", "source_url", "last_synced_at"} <= columns
    assert "idx_courses_external_id" in indexes
    assert tuple(course) == ("Legacy course", None)
