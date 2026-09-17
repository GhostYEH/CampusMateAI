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


def test_legacy_study_sessions_gain_nullable_behavior_summary(tmp_path):
    db_path = tmp_path / "legacy-study.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE study_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                goal TEXT,
                related_task_id TEXT,
                started_at TEXT NOT NULL,
                paused_at TEXT,
                ended_at TEXT,
                duration_seconds INTEGER NOT NULL DEFAULT 0,
                pause_seconds INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                self_report TEXT,
                self_report_tags TEXT,
                expression_signal TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

    database = Database(db_path)

    with database.query() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(study_sessions)")}

    assert "behavior_summary" in columns


def test_legacy_database_gains_learner_events_idempotently(tmp_path):
    db_path = tmp_path / "legacy-events.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO users (id, username, password_hash, role, created_at, updated_at)
            VALUES ('user1', 'user1', 'hash', 'student', '2026-01-01', '2026-01-01');
            """
        )

    for _ in range(2):
        database = Database(db_path)
        with database.query() as conn:
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "learner_events" in tables
            indexes = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND tbl_name='learner_events'"
                ).fetchall()
            }
            assert {
                "idx_learner_events_user_time",
                "idx_learner_events_user_source_type",
                "idx_learner_events_user_course",
                "idx_learner_events_user_subject",
            } <= indexes
            unique_found = False
            for row in conn.execute("PRAGMA index_list(learner_events)").fetchall():
                if row["unique"] == 1:
                    cols = {
                        c["name"]
                        for c in conn.execute(
                            f"PRAGMA index_info({row['name']})"
                        ).fetchall()
                    }
                    if cols == {"user_id", "dedupe_key"}:
                        unique_found = True
            assert unique_found
            user = conn.execute(
                "SELECT username FROM users WHERE id='user1'"
            ).fetchone()
            assert tuple(user) == ("user1",)
        database.dispose()


def test_legacy_database_gains_learner_state_tables_and_indexes_idempotently(tmp_path):
    db_path = tmp_path / "legacy-state.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO users (id, username, password_hash, role, created_at, updated_at)
            VALUES ('state-user', 'state-user', 'hash', 'student', '2026-01-01', '2026-01-01');
            CREATE TABLE learner_state_projection_runs (
                run_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                as_of TEXT NOT NULL,
                computed_at TEXT NOT NULL,
                estimator_version TEXT NOT NULL,
                input_digest TEXT NOT NULL,
                trigger TEXT NOT NULL,
                is_current INTEGER NOT NULL DEFAULT 0,
                warnings_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE UNIQUE INDEX idx_learner_state_runs_current
                ON learner_state_projection_runs(user_id) WHERE is_current = 1;
            """
        )

    for _ in range(2):
        database = Database(db_path)
        with database.query() as conn:
            tables = {
                row["name"] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'learner_state_%'"
                )
            }
            assert {
                "learner_state_projection_runs",
                "learner_state_snapshots",
                "learner_state_evidence",
            } <= tables
            indexes = {
                row["name"] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='learner_state_projection_runs'"
                )
            }
            assert "idx_learner_state_runs_current" in indexes
            columns = {
                row["name"] for row in conn.execute(
                    "PRAGMA table_info(learner_state_projection_runs)"
                )
            }
            assert {"projection_kind", "projection_scope"} <= columns
        database.dispose()


def test_legacy_learning_plan_runs_gain_goal_id_before_goal_index(tmp_path):
    """A pre-goal_id plan table must start before its new index is created."""
    db_path = tmp_path / "legacy-learning-plan.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE learning_plan_runs (
                run_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                planner_version TEXT NOT NULL,
                input_digest TEXT NOT NULL,
                as_of TEXT NOT NULL,
                valid_until TEXT NOT NULL,
                available_minutes INTEGER NOT NULL,
                allocated_minutes INTEGER NOT NULL DEFAULT 0,
                course_scope TEXT,
                window_start TEXT,
                window_end TEXT,
                warning_codes_json TEXT NOT NULL DEFAULT '[]',
                idempotency_key TEXT,
                created_at TEXT NOT NULL
            );
            """
        )

    for _ in range(2):
        database = Database(db_path)
        with database.query() as conn:
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(learning_plan_runs)")
            }
            indexes = {
                row["name"]
                for row in conn.execute("PRAGMA index_list(learning_plan_runs)")
            }
        database.dispose()

    assert "goal_id" in columns
    assert "idx_learning_plan_runs_goal" in indexes
