import sqlite3
import pytest

from app.database.sqlite_db import Database, EDU_CONNECTOR_SCHEMA_SQL, _SchemaStep


def test_failed_schema_step_preserves_exception_and_names_phase(monkeypatch):
    monkeypatch.setattr(Database, "_schema_steps", lambda self: (
        _SchemaStep("broken_phase", "CREATE TABLE broken ("),
    ))
    with pytest.raises(sqlite3.OperationalError) as caught:
        Database(None)
    assert "schema migration phase: broken_phase" in caught.value.__notes__


def test_foreign_key_validation_names_phase_and_table():
    with sqlite3.connect(":memory:") as conn:
        conn.executescript(
            "CREATE TABLE parent (id TEXT PRIMARY KEY);"
            "CREATE TABLE child (parent_id TEXT REFERENCES parent(id));"
            "INSERT INTO child VALUES ('missing');"
        )
        with pytest.raises(sqlite3.IntegrityError, match=r"child_phase \(child\)"):
            Database._validate_schema_foreign_keys(conn, (
                _SchemaStep("child_phase", "CREATE TABLE IF NOT EXISTS child (parent_id TEXT);"),
            ))


@pytest.mark.parametrize("phase", [
    "_migrate_edu_bindings",
    "_prepare_legacy_learning_plan_runs",
    "_migrate_adaptive_intervention_statuses",
    "_migrate_runtime_indexes_and_observations",
    "_migrate",
    "_repair_edu_sync_binding_foreign_key",
])
def test_startup_migration_failure_rolls_back_schema_and_data(tmp_path, monkeypatch, phase):
    path = tmp_path / "interrupted.db"
    with sqlite3.connect(path) as conn:
        conn.executescript("CREATE TABLE existing (id TEXT PRIMARY KEY); INSERT INTO existing VALUES ('keep');")
    migrate = Database.__dict__[phase]

    def fail_after_migration(self, conn):
        migrate.__get__(self, Database)(conn)
        conn.execute("ALTER TABLE existing ADD COLUMN changed TEXT")
        self._execute_schema_script(conn, "CREATE TABLE transient (id TEXT); INSERT INTO transient VALUES ('discard');")
        raise RuntimeError("migration interrupted")

    with monkeypatch.context() as patcher:
        patcher.setattr(Database, phase, fail_after_migration)
        with pytest.raises(RuntimeError, match="interrupted"):
            Database(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [("existing",)]
        assert [r[1] for r in conn.execute("PRAGMA table_info(existing)")] == ["id"]
        assert conn.execute("SELECT * FROM existing").fetchall() == [("keep",)]
    # 同一个旧库下一次启动仍能完整成功。
    database = Database(path)
    with database.query() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("SELECT id FROM existing").fetchone()[0] == "keep"
    database.dispose()


def test_schema_executor_preserves_quoted_semicolons_and_trigger_bodies():
    with sqlite3.connect(":memory:") as conn:
        conn.execute("BEGIN")
        Database._execute_schema_script(conn, """
            CREATE TABLE messages (value TEXT);
            CREATE TABLE copies (value TEXT);
            CREATE TRIGGER copy_message AFTER INSERT ON messages BEGIN
                INSERT INTO copies VALUES (NEW.value);
                INSERT INTO copies VALUES ('extra;value');
            END;
            INSERT INTO messages VALUES ('original;value');
        """)
        assert conn.in_transaction
        assert conn.execute("SELECT value FROM copies").fetchall() == [("original;value",), ("extra;value",)]
        conn.rollback()
        assert not conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()


def test_legacy_edu_binding_upgrade_preserves_child_foreign_keys_and_cascades(tmp_path):
    path = tmp_path / "legacy-edu.db"
    database = Database(path)
    database.dispose()
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            INSERT INTO users (id, username, password_hash, created_at, updated_at)
                VALUES ('edu-user', 'edu-user', 'hash', 'now', 'now');
            INSERT INTO universities (id, name, created_at, updated_at)
                VALUES ('edu-school', '测试高校', 'now', 'now');
            DROP TABLE edu_bindings;
            CREATE TABLE edu_bindings (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, university_id TEXT NOT NULL,
                provider TEXT NOT NULL, system_type TEXT NOT NULL DEFAULT 'undergrad',
                external_student_id TEXT, external_student_name TEXT,
                status TEXT, credential_ref TEXT, last_synced_at TEXT,
                last_sync_status TEXT, last_error TEXT, created_at TEXT, updated_at TEXT
            );
            INSERT INTO edu_bindings (id, user_id, university_id, provider, status, created_at, updated_at)
                VALUES ('binding', 'edu-user', 'edu-school', 'zhengfang', 'bound', 'now', 'now');
            INSERT INTO edu_sync_records (id, binding_id, user_id, sync_type, started_at)
                VALUES ('sync', 'binding', 'edu-user', 'schedule', 'now');
        """)
    for _ in range(2):
        database = Database(path)
        with database.query() as conn:
            targets = {r['table'] for r in conn.execute("PRAGMA foreign_key_list(edu_sync_records)")}
            assert "edu_bindings" in targets
            assert "edu_bindings_legacy_v1" not in targets
            assert conn.execute("SELECT id FROM edu_sync_records").fetchone()[0] == "sync"
            assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        database.dispose()
    database = Database(path)
    with database.transaction() as conn:
        conn.execute("DELETE FROM edu_bindings WHERE id='binding'")
        assert conn.execute("SELECT COUNT(*) FROM edu_sync_records").fetchone()[0] == 0
    database.dispose()


def test_already_rewritten_edu_sync_foreign_key_is_repaired_without_losing_records(tmp_path):
    path = tmp_path / "damaged-edu.db"
    database = Database(path)
    with database.transaction() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash, created_at, updated_at) VALUES ('u', 'u', 'hash', 'now', 'now')")
        conn.execute("INSERT INTO universities (id, name, created_at, updated_at) VALUES ('school', '测试高校', 'now', 'now')")
        conn.execute("INSERT INTO edu_bindings (id, user_id, university_id, provider, created_at, updated_at) VALUES ('binding', 'u', 'school', 'zhengfang', 'now', 'now')")
        conn.execute("INSERT INTO edu_sync_records (id, binding_id, user_id, sync_type, started_at) VALUES ('sync', 'binding', 'u', 'schedule', 'now')")
    database.dispose()
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA legacy_alter_table=OFF")
        conn.execute("ALTER TABLE edu_bindings RENAME TO edu_bindings_legacy_v1")
        conn.executescript(EDU_CONNECTOR_SCHEMA_SQL)
        conn.execute("INSERT INTO edu_bindings SELECT * FROM edu_bindings_legacy_v1")
        assert "edu_bindings_legacy_v1" in {row[2] for row in conn.execute("PRAGMA foreign_key_list(edu_sync_records)")}
    database = Database(path)
    with database.transaction() as conn:
        assert "edu_bindings" in {row["table"] for row in conn.execute("PRAGMA foreign_key_list(edu_sync_records)")}
        assert conn.execute("SELECT id FROM edu_sync_records").fetchone()[0] == "sync"
        conn.execute("DELETE FROM edu_bindings WHERE id='binding'")
        assert conn.execute("SELECT COUNT(*) FROM edu_sync_records").fetchone()[0] == 0
    database.dispose()


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
