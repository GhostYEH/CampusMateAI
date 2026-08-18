import sqlite3

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.database.sqlite_db import Database
from app.main import create_app
from app.services.container import reset_container_for_tests


def test_database_drops_legacy_campus_activity_tables(tmp_path):
    db_path = tmp_path / "legacy-activities.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE campus_activities (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'draft',
                starts_at TEXT,
                registration_deadline TEXT
            );
            CREATE TABLE activity_registrations (
                id TEXT PRIMARY KEY,
                activity_id TEXT NOT NULL
            );
            INSERT INTO campus_activities (id, status) VALUES ('activity-1', 'published');
            """
        )

    database = Database(db_path)

    with database.query() as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert "campus_activities" not in tables
    assert "activity_registrations" not in tables


def test_removed_activity_urls_return_404():
    reset_container_for_tests(
        Settings(
            app_env="test-activity-removal",
            database_url="sqlite:///:memory:",
            auto_seed_demo_users=False,
            auto_import_demo=False,
        )
    )
    client = TestClient(create_app())

    assert client.get("/api/v1/activities").status_code == 404
    assert client.post("/api/v1/admin/activities", json={}).status_code == 404
