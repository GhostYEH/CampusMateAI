from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.database.sqlite_db import Database
from app.main import create_app
from app.repositories.learning_room_repository import LearningRoomRepository
from app.services.container import reset_container_for_tests

BASE = "/api/v1/magicclass/learning-space"


def classroom_zip():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(zipfile.ZipInfo("manifest.json"), json.dumps({"formatVersion": 1, "stage": {"name": "共同学习"}, "scenes": [{"title": "第一页", "content": {"type": "slide"}}, {"title": "第二页", "content": {"type": "quiz"}}]}))
        archive.writestr(zipfile.ZipInfo("media/example.png"), b"shared-media")
    return output.getvalue()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    settings = Settings(app_env="test", database_url=f"sqlite:///{(tmp_path / 'rooms.db').as_posix()}", auto_seed_demo_users=False, llm_provider="none", agent_allow_mock_providers=True)
    test_db = Database(tmp_path / "rooms.db")
    monkeypatch.setattr("app.database.sqlite_db.reset_db_for_tests", lambda: test_db)
    container = reset_container_for_tests(settings)
    client = TestClient(create_app())
    accounts = []
    for name in ("room_host", "room_guest", "room_outsider"):
        response = client.post("/api/v1/auth/register", json={"username": name, "password": "TestRoom123", "role": "student"})
        assert response.status_code in (200, 201), response.text
        assert response.json()["uid"] == response.json()["id"]
        data = client.post("/api/v1/auth/login", json={"username": name, "password": "TestRoom123"}).json()
        accounts.append((data["user"]["uid"], {"Authorization": f"Bearer {data['access_token']}"}))
    return container, client, accounts


def create(client, headers):
    response = client.post(f"{BASE}/rooms", headers=headers, data={"title": "共同学习", "stage_id": "stage-test"}, files={"file": ("classroom.maic.zip", classroom_zip(), "application/zip")})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def joined(setup):
    container, client, ((host, h), (guest, g), (outsider, o)) = setup
    room = create(client, h)
    assert client.post(f"{BASE}/rooms/{room}/invitations", headers=h, json={"uid": guest}).status_code == 200
    assert client.post(f"{BASE}/invitations/{room}/accept", headers=g).status_code == 200
    return container, client, room, (host, h), (guest, g), (outsider, o)


def test_existing_account_uid_is_stable_and_matches_auth(setup):
    _, client, ((uid, headers), *_) = setup
    assert client.get(f"{BASE}/identity", headers=headers).json()["uid"] == uid
    me = client.get("/api/v1/auth/me", headers=headers).json()["user"]
    assert me["id"] == me["uid"] == uid
    login = client.post("/api/v1/auth/login", json={"username": "room_host", "password": "TestRoom123"})
    assert login.json()["user"]["uid"] == uid


def test_invitation_requires_consent_and_never_exposes_archive_before_accept(setup):
    _, client, ((_, h), (guest, g), (_, o)) = setup
    room = create(client, h)
    for headers in ({}, o, g):
        assert client.get(f"{BASE}/rooms/{room}/archive", headers=headers).status_code in (401, 404)
    client.post(f"{BASE}/rooms/{room}/invitations", headers=h, json={"uid": f"  {guest}  "})
    invitations = client.get(f"{BASE}/invitations", headers=g).json()["items"]
    assert invitations[0]["room_id"] == room
    assert "archive" not in invitations[0]
    assert client.get(f"{BASE}/rooms/{room}", headers=g).status_code == 404
    assert client.post(f"{BASE}/invitations/{room}/accept", headers=o).status_code == 404
    assert client.post(f"{BASE}/invitations/{room}/accept", headers=g).status_code == 200
    assert client.get(f"{BASE}/rooms/{room}/archive", headers=g).content == classroom_zip()
    assert client.get(f"{BASE}/rooms/{room}/archive", headers=h).content == client.get(f"{BASE}/rooms/{room}/archive", headers=g).content


def test_invalid_duplicate_declined_and_disabled_invites(setup):
    container, client, ((host, h), (guest, g), (_, o)) = setup
    room = create(client, h)
    invite_url = f"{BASE}/rooms/{room}/invitations"
    assert client.post(invite_url, headers=h, json={"uid": host}).status_code == 422
    assert client.post(invite_url, headers=h, json={"uid": "usr_missing"}).status_code == 404
    assert client.post(invite_url, headers=o, json={"uid": guest}).status_code == 404
    for _ in range(2):
        assert client.post(invite_url, headers=h, json={"uid": guest}).status_code == 200
    assert len(client.get(f"{BASE}/invitations", headers=g).json()["items"]) == 1
    assert client.post(f"{BASE}/invitations/{room}/decline", headers=g).status_code == 204
    assert client.post(f"{BASE}/invitations/{room}/accept", headers=g).status_code == 404
    container.user_repository.update_user(guest, fields={"is_active": False})
    assert client.post(invite_url, headers=h, json={"uid": guest}).status_code == 404


def test_messages_are_isolated_ordered_and_idempotent(setup):
    _, client, room, (_, h), (guest, g), (_, o) = joined(setup)
    url = f"{BASE}/rooms/{room}/messages"
    body = {"content": "  这道题怎么理解？  ", "client_id": "msg-1"}
    first = client.post(url, headers=g, json=body)
    repeat = client.post(url, headers=g, json=body)
    assert first.status_code == repeat.status_code == 201
    assert first.json()["id"] == repeat.json()["id"]
    client.post(url, headers=h, json={"content": "一起看第二页", "client_id": "msg-2"})
    messages = client.get(url, headers=h).json()["items"]
    assert len(messages) == 2 and messages[0]["uid"] == guest
    assert messages[0]["content"] == "这道题怎么理解？"
    assert len(client.get(url, headers=g, params={"after": messages[0]["id"]}).json()["items"]) == 1
    assert client.get(url, headers=o).status_code == 404
    assert client.post(url, headers=o, json=body).status_code == 404
    assert client.post(url, headers=g, json={**body, "content": "   "}).status_code == 422
    assert client.post(url, headers=g, json={**body, "content": "a" * 2001}).status_code == 422
    another = create(client, h)
    assert client.get(f"{BASE}/rooms/{another}/messages", headers=h).json()["items"] == []


def test_host_cursor_and_leave_revoke_access(setup):
    _, client, room, (_, h), (guest, g), _ = joined(setup)
    url = f"{BASE}/rooms/{room}"
    assert client.patch(f"{url}/cursor", headers=g, json={"scene_index": 1}).status_code == 403
    assert client.patch(f"{url}/cursor", headers=h, json={"scene_index": 2}).status_code == 422
    assert client.patch(f"{url}/cursor", headers=h, json={"scene_index": 1}).status_code == 204
    assert client.get(url, headers=g).json()["scene_index"] == 1
    assert client.post(f"{url}/leave", headers=g).status_code == 204
    assert client.get(f"{url}/archive", headers=g).status_code == 404
    assert client.post(f"{url}/invitations", headers=h, json={"uid": guest}).status_code == 200
    assert client.post(f"{url}/leave", headers=h).status_code == 204
    assert client.get(f"{BASE}/invitations", headers=g).json()["items"] == []
    assert client.post(f"{BASE}/invitations/{room}/accept", headers=g).status_code == 404


def test_archive_validation_and_data_survive_new_repository(setup, tmp_path):
    container, client, room, (host, h), (guest, g), _ = joined(setup)
    client.post(f"{BASE}/rooms/{room}/messages", headers=g, json={"content": "下次继续", "client_id": "saved"})
    repo = LearningRoomRepository(Database(tmp_path / "rooms.db"))
    assert repo.get(room, guest)["host_uid"] == host
    assert repo.messages(room, host, 0)[0]["content"] == "下次继续"
    assert repo.archive(room, guest) == classroom_zip()
    response = client.post(f"{BASE}/rooms", headers=h, data={"title": "invalid", "stage_id": "test"}, files={"file": ("bad.zip", b"invalid")})
    assert response.status_code == 422
