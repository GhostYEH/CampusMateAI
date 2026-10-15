"""RTC control-plane checks; no real cloud sessions or billed calls are started."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
import io
import json
import struct
import threading
from types import SimpleNamespace
import zipfile

from app.core.exceptions import AppException
from app.database.sqlite_db import Database
from app.repositories.learning_room_repository import LearningRoomRepository
from app.services.learning_room_creation import archive_scene_count
import test_learning_rooms as room_tests
from test_learning_rooms import BASE, create, joined

setup = room_tests.setup


def enable_rtc(container):
    container.settings.volc_rtc_app_id = "0123456789abcdef01234567"
    container.settings.volc_rtc_app_key = "test-only-app-key"


def unpack_bytes(data, offset=0):
    size = struct.unpack_from("<H", data, offset)[0]
    return data[offset + 2 : offset + 2 + size], offset + 2 + size


def decode_token(value):
    raw = base64.b64decode(value[27:])
    message, offset = unpack_bytes(raw)
    signature, end = unpack_bytes(raw, offset)
    assert end == len(raw)
    _, issued, expires = struct.unpack_from("<III", message)
    room_id, offset = unpack_bytes(message, 12)
    user_id, offset = unpack_bytes(message, offset)
    size = struct.unpack_from("<H", message, offset)[0]
    privileges = dict(
        struct.unpack_from("<HI", message, offset + 2 + index * 6)
        for index in range(size)
    )
    return (
        message,
        signature,
        issued,
        expires,
        room_id.decode(),
        user_id.decode(),
        privileges,
    )


def test_rtc_status_is_authenticated_and_never_exposes_secrets(setup):
    container, client, ((_, headers), *_) = setup
    container.settings.volc_rtc_app_id = ""
    url = f"{BASE}/rtc/status"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=headers).json()["available"] is False
    enable_rtc(container)
    body = client.get(url, headers=headers).json()
    assert body == {
        "available": True,
        "provider": "volcengine",
        "max_members": 8,
        "reason": None,
    }
    assert "test-only-app-key" not in json.dumps(body)


def test_tokens_require_accepted_membership_and_valid_configuration(setup):
    container, client, ((_, h), (guest, g), (_, o)) = setup
    container.settings.volc_rtc_app_id = ""
    room = create(client, h)
    url = f"{BASE}/rooms/{room}/rtc-token"
    assert client.post(url).status_code == 401
    assert client.post(url, headers=o).status_code == 404
    client.post(f"{BASE}/rooms/{room}/invitations", headers=h, json={"uid": guest})
    assert client.post(url, headers=g).status_code == 404
    assert client.post(url, headers=h).status_code == 503
    enable_rtc(container)
    container.settings.volc_rtc_app_id = "malformed"
    assert client.post(url, headers=h).json()["code"] == "CLASSROOM_RTC_UNAVAILABLE"
    enable_rtc(container)
    client.post(f"{BASE}/invitations/{room}/accept", headers=g)
    assert client.post(url, headers=g).status_code == 200


def test_official_token_wire_format_signature_scope_and_expiry(setup, monkeypatch):
    container, client, room, (host, h), (guest, g), _ = joined(setup)
    enable_rtc(container)
    monkeypatch.setattr(
        "app.services.learning_room_rtc.time", SimpleNamespace(time=lambda: 1800000000)
    )
    url = f"{BASE}/rooms/{room}/rtc-token"
    first = client.post(url, headers=h)
    second = client.post(url, headers=h)
    assert first.status_code == 200 and first.headers["Cache-Control"] == "no-store"
    body = first.json()
    assert body["token"] != second.json()["token"]
    assert body["refresh_after_seconds"] == 60
    assert body["token"].startswith("001" + container.settings.volc_rtc_app_id)
    message, signature, issued, expires, rtc_room, rtc_uid, privileges = decode_token(
        body["token"]
    )
    assert hmac.compare_digest(
        signature, hmac.digest(b"test-only-app-key", message, "sha256")
    )
    assert issued == 1800000000 and expires == body["expires_at"] == issued + 120
    assert privileges == {index: expires for index in range(5)}
    assert (
        rtc_room
        == body["room_id"]
        == "class_" + hashlib.sha256(room.encode()).hexdigest()[:40]
    )
    assert rtc_uid == body["user_id"] == host
    other = client.post(url, headers=g).json()
    assert other["room_id"] == rtc_room and other["user_id"] == guest
    assert "test-only-app-key" not in first.text
    # A client cannot select another identity or wildcard room through the request body.
    assert (
        client.post(url, headers=g, json={"room_id": "*", "user_id": host}).json()[
            "user_id"
        ]
        == guest
    )
    another = create(client, h)
    assert (
        client.post(f"{BASE}/rooms/{another}/rtc-token", headers=h).json()["room_id"]
        != rtc_room
    )


def test_leave_and_end_prevent_token_renewal(setup):
    container, client, room, (_, h), (_, g), _ = joined(setup)
    enable_rtc(container)
    url = f"{BASE}/rooms/{room}"
    assert client.post(f"{url}/rtc-token", headers=g).status_code == 200
    assert client.post(f"{url}/leave", headers=g).status_code == 204
    assert client.post(f"{url}/rtc-token", headers=g).status_code == 404
    assert client.post(f"{url}/leave", headers=h).status_code == 204
    assert client.post(f"{url}/rtc-token", headers=h).status_code == 404


def test_native_room_reuses_archive_invitations_and_limits(setup):
    _, client, ((_, h), (guest, g), *_) = setup
    url = f"{BASE}/rooms/native"
    assert client.post(url, json={"title": "课堂"}).status_code == 401
    for title in ("", "   ", "x" * 201):
        assert client.post(url, headers=h, json={"title": title}).status_code == 422
    response = client.post(url, headers=h, json={"title": "  一起复习  "})
    assert response.status_code == 201
    room = response.json()
    assert room["title"] == "一起复习" and room["scene_count"] == 1
    archive = client.get(f"{BASE}/rooms/{room['id']}/archive", headers=h).content
    assert archive_scene_count(archive) == 1
    # The Web importer reads canvas.elements; an incomplete placeholder must
    # not break existing Web users who accept an Android invitation.
    with zipfile.ZipFile(io.BytesIO(archive)) as portable:
        manifest = json.loads(portable.read("manifest.json"))
    assert manifest["agents"] == [] and manifest["mediaIndex"] == {}
    slide = manifest["scenes"][0]["content"]["canvas"]
    assert slide["elements"] == [] and slide["viewportSize"] == 1000
    assert slide["theme"]["fontColor"]
    assert (
        client.post(
            f"{BASE}/rooms/{room['id']}/invitations", headers=h, json={"uid": guest}
        ).status_code
        == 200
    )
    assert (
        client.post(f"{BASE}/invitations/{room['id']}/accept", headers=g).status_code
        == 200
    )
    for _ in range(19):
        assert client.post(url, headers=h, json={"title": "课堂"}).status_code == 201
    assert client.post(url, headers=h, json={"title": "超额"}).status_code == 409


def test_message_retry_conflict_and_sqlite_cursor_boundary(setup):
    _, client, room, (_, h), *_ = joined(setup)
    url = f"{BASE}/rooms/{room}/messages"
    body = {"content": "第一条", "client_id": "same-attempt"}
    first = client.post(url, headers=h, json=body)
    assert client.post(url, headers=h, json=body).json()["id"] == first.json()["id"]
    assert (
        client.post(url, headers=h, json={**body, "content": "另一条"}).status_code
        == 409
    )
    assert client.get(url, headers=h, params={"after": 2**63 - 1}).json() == {
        "items": []
    }
    assert client.get(url, headers=h, params={"after": 2**63}).status_code == 422


def synchronize_deferred_counts(databases, monkeypatch):
    barrier = threading.Barrier(2)
    for database in databases:
        original = database._connect

        def connect(original=original):
            connection = original()

            class CountCursor:
                def __init__(self, cursor):
                    self.cursor = cursor

                def fetchone(self):
                    row = self.cursor.fetchone()
                    if not connection.in_transaction:
                        barrier.wait(timeout=3)
                    return row

            class Connection:
                def __getattr__(self, name):
                    return getattr(connection, name)

                def execute(self, sql, *args):
                    cursor = connection.execute(sql, *args)
                    if sql.startswith("SELECT COUNT(*) FROM learning_room"):
                        return CountCursor(cursor)
                    return cursor

            return Connection()

        monkeypatch.setattr(database, "_connect", connect)


def test_native_creation_limit_is_atomic_across_database_instances(setup, monkeypatch):
    container, _, ((host, _), *_) = setup
    repo = container.learning_room_repository
    for _ in range(19):
        repo.create(host, "课堂", "stage", b"archive", 1)
    other = LearningRoomRepository(Database(container.settings.database_path))
    synchronize_deferred_counts((repo.db, other.db), monkeypatch)

    def attempt(repository):
        try:
            return repository.create(host, "并发", "stage", b"archive", 1)["id"]
        except AppException as error:
            assert error.http_status == 409
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (repo, other)))
    assert sum(result is not None for result in results) == 1
    assert len(repo.list_rooms(host)) == 20


def test_corrupt_deflated_manifest_is_a_validation_error(setup):
    _, client, ((_, headers), *_) = setup
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", '{"stage":{},"scenes":[]}')
    data = bytearray(output.getvalue())
    # A deflate block with reserved BTYPE=3 triggers zlib.error, not BadZipFile.
    offset = 30 + len("manifest.json")
    data[offset] = 0x07
    response = client.post(
        f"{BASE}/rooms",
        headers=headers,
        data={"title": "坏文件", "stage_id": "stage"},
        files={"file": ("bad.zip", bytes(data))},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_CLASSROOM_ARCHIVE"


def test_eight_member_limit_is_atomic_across_database_instances(setup, monkeypatch):
    container, _, ((host, _), (guest, _), (outsider, _)) = setup
    repo = container.learning_room_repository
    room = repo.create(host, "讨论", "stage", b"archive", 1)["id"]
    for index in range(6):
        filler = container.user_repository.create_user(
            username=f"rtc_filler_{index}", password_hash="unused-test-hash"
        )
        repo.invite(room, host, filler.id)
    other = LearningRoomRepository(Database(container.settings.database_path))
    synchronize_deferred_counts((repo.db, other.db), monkeypatch)

    def attempt(args):
        repository, uid = args
        try:
            return repository.invite(room, host, uid)["status"]
        except AppException as error:
            assert error.http_status == 409
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ((repo, guest), (other, outsider))))
    assert results.count("pending") == 1
    assert len(repo.get(room, host)["members"]) == 8
