from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.database.sqlite_db import Database
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client() -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app())


def _headers(client: TestClient, username: str = "student_demo") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_legacy_users_gain_nullable_university_id_without_data_loss(tmp_path) -> None:
    """Removing the migration would leave legacy users unusable by university features."""
    db_path = tmp_path / "legacy-users.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE users (
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
            INSERT INTO users (id, username, password_hash, role, created_at, updated_at)
            VALUES ('legacy-user', 'legacy', 'kept-secret-hash', 'student', '2026-01-01', '2026-01-01');
            """
        )

    database = Database(db_path)

    with database.query() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        university = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'universities'"
        ).fetchone()
        user = conn.execute(
            "SELECT username, password_hash, university_id FROM users WHERE id = 'legacy-user'"
        ).fetchone()

    assert "university_id" in columns
    assert university is not None
    assert tuple(user) == ("legacy", "kept-secret-hash", None)


def test_universities_search_filter_and_paginate_with_stable_contract() -> None:
    """Removing repository filtering or pagination must change this public result."""
    client = _client()

    response = client.get(
        "/api/v1/universities",
        params={"q": "Demo", "province": "Demo Province", "city": "Demo City", "page": 1, "page_size": 1},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload) >= {"items", "page", "page_size", "total"}
    assert payload["page"] == 1
    assert payload["page_size"] == 1
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    university = payload["items"][0]
    assert university["name"] == "Demo University"
    assert university["province"] == "Demo Province"
    assert university["city"] == "Demo City"
    assert university["is_demo"] is True
    assert university["academic_system_type"] == "unsupported"
    assert university["academic_provider"] == "unsupported"
    assert "password" not in university
    assert "credential" not in university


def test_university_detail_returns_not_found_for_unknown_id() -> None:
    """Replacing detail lookup with an empty response must fail this API contract."""
    client = _client()

    response = client.get("/api/v1/universities/missing-university")

    assert response.status_code == 404
    assert response.json()["code"] == "UNIVERSITY_NOT_FOUND"


def test_authenticated_profile_university_selection_updates_user_and_demo_binding() -> None:
    """Removing ownership-bound profile updates must fail the authenticated contract."""
    client = _client()
    headers = _headers(client)
    university = client.get("/api/v1/universities").json()["items"][0]

    response = client.put(
        "/api/v1/profile/university",
        headers=headers,
        json={"university_id": university["id"]},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["university_id"] == university["id"]
    assert payload["university"]["id"] == university["id"]
    assert payload["university"]["is_demo"] is True
    assert payload["university"]["academic_system_type"] == "unsupported"
    assert "password_hash" not in payload
    assert "credential" not in payload

    me_response = client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["user"]["university_id"] == university["id"]


def test_profile_university_selection_requires_authentication() -> None:
    """Removing the auth dependency must expose profile tenancy mutation."""
    client = _client()
    university = client.get("/api/v1/universities").json()["items"][0]

    response = client.put("/api/v1/profile/university", json={"university_id": university["id"]})

    assert response.status_code == 401
