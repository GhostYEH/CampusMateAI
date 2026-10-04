"""Removed global write APIs stay unavailable to authenticated and anonymous callers."""
import pytest
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests


@pytest.mark.parametrize("method,path,expected", [
    ("post", "/api/v1/knowledge/documents", 405),
    ("delete", "/api/v1/knowledge/documents/fake-id", 404),
    ("post", "/api/v1/knowledge/rebuild", 404),
    ("post", "/api/v1/knowledge/manage/delete_all_documents", 404),
    ("post", "/api/v1/auth/admin/users", 404),
])
def test_global_management_routes_are_removed(method, path, expected):
    reset_container_for_tests(Settings(_env_file=None, app_env="test", auto_seed_demo_users=False, auto_import_demo=False))
    client = TestClient(create_app())
    payload = {"username": "ordinary_user", "password": "Test-password-123"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    pair = client.post("/api/v1/auth/login", json=payload).json()
    for headers in ({}, {"Authorization": f"Bearer {pair['access_token']}"}):
        response = client.request(method, path, headers=headers, json={})
        assert response.status_code == expected, response.text
