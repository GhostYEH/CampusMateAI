"""Student self-registration preserves fields and maps uniqueness conflicts."""
from secrets import token_urlsafe
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app
from app.services.container import get_container, reset_container_for_tests


def _client():
    reset_container_for_tests(Settings(_env_file=None, app_env="test", auto_seed_demo_users=False, auto_import_demo=False))
    return TestClient(create_app())


def test_registration_preserves_user_fields_and_login():
    client = _client()
    payload = {"username": "public_student", "password": token_urlsafe(12), "role": "student",
               "display_name": "测试同学", "student_number": "S1001", "college": "计算机学院", "major": "软件工程", "grade": "2026"}
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    for name in ("username", "role", "display_name", "student_number", "college", "major", "grade"):
        assert response.json()[name] == payload[name]
    assert "password_hash" not in response.json()
    assert client.post("/api/v1/auth/login", json=payload).status_code == 200


def test_registration_rejects_duplicate_identifiers_and_teacher_number():
    client = _client()
    base = {"username": "first_student", "password": token_urlsafe(12), "student_number": "S2001"}
    assert client.post("/api/v1/auth/register", json=base).status_code == 201
    duplicate = client.post("/api/v1/auth/register", json=base)
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "USERNAME_EXISTS"
    duplicate = client.post("/api/v1/auth/register", json={**base, "username": "other_student"})
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "STUDENT_NUMBER_EXISTS"
    assert client.post("/api/v1/auth/register", json={**base, "username": "bad_student", "teacher_number": "T1"}).status_code == 422


def test_concurrent_registration_maps_student_number_unique_conflict(monkeypatch) -> None:
    client = _client()
    repository = get_container().user_repository
    original_create = repository.create_user
    both_checked = Barrier(2)
    insert_lock = Lock()

    def synchronized_create(**kwargs):
        # Both requests pass the preflight lookup before either inserts.
        both_checked.wait(timeout=5)
        with insert_lock:
            return original_create(**kwargs)

    monkeypatch.setattr(repository, "create_user", synchronized_create)
    password = token_urlsafe(12)

    def register(username):
        return client.post("/api/v1/auth/register", json={
            "username": username,
            "password": password,
            "role": "student",
            "student_number": "S-RACE-1",
        })

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(register, ("racing_student_a", "racing_student_b")))

    assert sorted(response.status_code for response in responses) == [201, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["code"] == "STUDENT_NUMBER_EXISTS"
