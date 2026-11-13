"""多人在线自习室：成员状态、共享番茄钟、房内鼓励。

覆盖：身份/邀请/接受、成员隔离、人数与房间上限、发起人独占的计时控制、
在线心跳与离开判定、消息幂等与分页、离开与结束。
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.database.sqlite_db import Database
from app.main import create_app
from app.repositories.study_room_repository import StudyRoomRepository
from app.services.container import reset_container_for_tests

BASE = "/api/v1/study/rooms"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    settings = Settings(
        app_env="test",
        database_url=f"sqlite:///{(tmp_path / 'studyrooms.db').as_posix()}",
        auto_seed_demo_users=False,
        llm_provider="none",
        agent_allow_mock_providers=True,
    )
    test_db = Database(tmp_path / "studyrooms.db")
    monkeypatch.setattr("app.database.sqlite_db.reset_db_for_tests", lambda: test_db)
    container = reset_container_for_tests(settings)
    client = TestClient(create_app())
    accounts = []
    for name in ("study_host", "study_guest", "study_outsider"):
        client.post(
            "/api/v1/auth/register",
            json={"username": name, "password": "TestStudy123", "role": "student"},
        )
        data = client.post(
            "/api/v1/auth/login",
            json={"username": name, "password": "TestStudy123"},
        ).json()
        accounts.append(
            (data["user"]["uid"], {"Authorization": f"Bearer {data['access_token']}"})
        )
    return container, client, accounts


def _clear_rate_limit(client):
    # 测试里所有请求同源，注册限流(5/60s)会误伤批量建号；直接清空限流窗口。
    limiter = getattr(client.app.state, "request_rate_limiter", None)
    if limiter is not None:
        limiter._requests.clear()


def make_room(client, headers, title="晚自习", focus=25, brk=5):
    return client.post(
        f"{BASE}/",
        headers=headers,
        json={"title": title, "focus_minutes": focus, "break_minutes": brk},
    )


def joined(setup):
    container, client, ((host, h), (guest, g), (outsider, o)) = setup
    room = make_room(client, h).json()["id"]
    assert (
        client.post(
            f"{BASE}/{room}/invitations", headers=h, json={"uid": guest}
        ).status_code
        == 200
    )
    assert (
        client.post(f"{BASE}/invitations/{room}/accept", headers=g).status_code == 200
    )
    return container, client, room, (host, h), (guest, g), (outsider, o)


def test_identity_and_student_lookup(setup):
    _, client, ((host, h), (guest, g), _) = setup
    me = client.get(f"{BASE}/identity", headers=h).json()
    assert me["uid"] == host
    assert client.get(f"{BASE}/students/{guest}", headers=h).status_code == 200
    assert client.get(f"{BASE}/students/{host}", headers=h).status_code == 422
    assert client.get(f"{BASE}/students/usr_missing", headers=h).status_code == 404
    assert client.get(f"{BASE}/identity").status_code == 401


def test_create_list_invite_accept_flow(setup):
    container, client, ((host, h), (guest, g), (outsider, o)) = setup
    created = make_room(client, h, title="考前冲刺")
    assert created.status_code == 201, created.text
    room = created.json()
    assert room["host_uid"] == host
    assert room["timer"]["phase"] == "idle"
    assert room["timer"]["remaining_seconds"] == 25 * 60
    assert len(room["members"]) == 1 and room["members"][0]["uid"] == host

    listed = client.get(f"{BASE}/", headers=h).json()["items"]
    assert [item["id"] for item in listed] == [room["id"]]
    assert listed[0]["member_count"] == 1

    rid = room["id"]
    assert client.post(
        f"{BASE}/{rid}/invitations", headers=h, json={"uid": guest}
    ).json() == {
        "uid": guest,
        "status": "pending",
    }
    inv = client.get(f"{BASE}/invitations", headers=g).json()["items"]
    assert inv and inv[0]["room_id"] == rid

    # pending 成员看不到自习室内容
    assert client.get(f"{BASE}/{rid}", headers=g).status_code == 404
    accepted = client.post(f"{BASE}/invitations/{rid}/accept", headers=g)
    assert accepted.status_code == 200
    detail = client.get(f"{BASE}/{rid}", headers=g).json()
    assert {m["uid"] for m in detail["members"]} == {host, guest}
    # 已加入的普通成员不是发起人，不能邀请其他人
    assert (
        client.post(
            f"{BASE}/{rid}/invitations", headers=g, json={"uid": outsider}
        ).status_code
        == 403
    )


def test_member_isolation_and_decline(setup):
    container, client, room, (host, h), (guest, g), (outsider, o) = joined(setup)
    for headers in ({}, o):
        assert client.get(f"{BASE}/{room}", headers=headers).status_code in (401, 404)
        assert client.get(f"{BASE}/{room}/messages", headers=headers).status_code in (
            401,
            404,
        )
    # 另一个被邀请者拒绝
    assert (
        client.post(
            f"{BASE}/{room}/invitations", headers=h, json={"uid": outsider}
        ).status_code
        == 200
    )
    assert (
        client.post(f"{BASE}/invitations/{room}/decline", headers=o).status_code == 204
    )
    assert (
        client.post(f"{BASE}/invitations/{room}/accept", headers=o).status_code == 404
    )


def test_member_and_room_caps(setup):
    container, client, ((host, h), *rest) = setup
    room = make_room(client, h).json()["id"]
    # 造 7 个额外学生填满 8 人（含 host）
    for i in range(7):
        name = f"study_extra_{i}"
        _clear_rate_limit(client)
        client.post(
            "/api/v1/auth/register",
            json={"username": name, "password": "TestStudy123", "role": "student"},
        )
        data = client.post(
            "/api/v1/auth/login", json={"username": name, "password": "TestStudy123"}
        ).json()
        uid = data["user"]["uid"]
        assert (
            client.post(
                f"{BASE}/{room}/invitations", headers=h, json={"uid": uid}
            ).status_code
            == 200
        )
    # 第 8 位之外再邀请应 409
    _clear_rate_limit(client)
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "study_overflow",
            "password": "TestStudy123",
            "role": "student",
        },
    )
    over = client.post(
        "/api/v1/auth/login",
        json={"username": "study_overflow", "password": "TestStudy123"},
    ).json()["user"]["uid"]
    assert (
        client.post(
            f"{BASE}/{room}/invitations", headers=h, json={"uid": over}
        ).status_code
        == 409
    )
    # 活动房间上限 20
    for i in range(19):
        assert make_room(client, h, title=f"r{i}").status_code == 201
    assert make_room(client, h, title="r-over").status_code == 409


def test_timer_control_is_host_only_and_stateful(setup):
    container, client, room, (host, h), (guest, g), _ = joined(setup)
    # 普通成员不能操作计时器
    assert (
        client.post(
            f"{BASE}/{room}/timer", headers=g, json={"action": "start_focus"}
        ).status_code
        == 403
    )
    started = client.post(
        f"{BASE}/{room}/timer", headers=h, json={"action": "start_focus"}
    )
    assert started.status_code == 200
    timer = started.json()["timer"]
    assert timer["phase"] == "focus" and timer["running"] is True
    assert 0 < timer["remaining_seconds"] <= 25 * 60
    paused = client.post(
        f"{BASE}/{room}/timer", headers=h, json={"action": "pause"}
    ).json()["timer"]
    assert paused["paused"] is True and paused["running"] is False
    remaining_at_pause = paused["remaining_seconds"]
    still = client.get(f"{BASE}/{room}", headers=g).json()["timer"]
    assert still["paused"] is True
    assert abs(still["remaining_seconds"] - remaining_at_pause) <= 2
    resumed = client.post(
        f"{BASE}/{room}/timer", headers=h, json={"action": "resume"}
    ).json()["timer"]
    assert resumed["running"] is True and resumed["paused"] is False
    reset = client.post(
        f"{BASE}/{room}/timer", headers=h, json={"action": "reset"}
    ).json()["timer"]
    assert reset["phase"] == "idle"
    assert (
        client.post(
            f"{BASE}/{room}/timer", headers=h, json={"action": "bogus"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{BASE}/{room}/timer",
            headers=h,
            json={"action": "start_focus", "focus_minutes": 999},
        ).status_code
        == 422
    )


def test_presence_heartbeat_state_and_away(setup):
    container, client, room, (host, h), (guest, g), _ = joined(setup)
    assert client.post(f"{BASE}/{room}/heartbeat", headers=g).status_code == 200
    assert (
        client.patch(
            f"{BASE}/{room}/state",
            headers=g,
            json={"study_state": "focus", "status_message": "刷题"},
        ).status_code
        == 204
    )
    detail = client.get(f"{BASE}/{room}", headers=h).json()
    guest_view = next(m for m in detail["members"] if m["uid"] == guest)
    assert guest_view["online"] is True
    assert guest_view["study_state"] == "focus"
    assert guest_view["status_message"] == "刷题"
    assert (
        client.patch(
            f"{BASE}/{room}/state", headers=g, json={"study_state": "sleeping"}
        ).status_code
        == 422
    )
    old = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    with container.db.transaction(immediate=True) as conn:
        conn.execute(
            "UPDATE study_room_members SET last_seen_at=? WHERE room_id=? AND user_id=?",
            (old, room, guest),
        )
    detail = client.get(f"{BASE}/{room}", headers=h).json()
    guest_view = next(m for m in detail["members"] if m["uid"] == guest)
    assert guest_view["online"] is False and guest_view["study_state"] == "away"


def test_messages_are_scoped_ordered_and_idempotent(setup):
    container, client, room, (host, h), (guest, g), (_, o) = joined(setup)
    url = f"{BASE}/{room}/messages"
    body = {"content": "  一起加油  ", "client_id": "m1"}
    first = client.post(url, headers=g, json=body)
    repeat = client.post(url, headers=g, json=body)
    assert first.status_code == repeat.status_code == 201
    assert first.json()["id"] == repeat.json()["id"]
    client.post(url, headers=h, json={"content": "开始专注", "client_id": "m2"})
    msgs = client.get(url, headers=h).json()["items"]
    assert (
        len(msgs) == 2 and msgs[0]["uid"] == guest and msgs[0]["content"] == "一起加油"
    )
    assert (
        len(client.get(url, headers=g, params={"after": msgs[0]["id"]}).json()["items"])
        == 1
    )
    assert client.get(url, headers=o).status_code == 404
    assert (
        client.post(url, headers=g, json={**body, "content": "   "}).status_code == 422
    )
    assert (
        client.post(
            url, headers=g, json={"content": "x", "client_id": "m1"}
        ).status_code
        == 409
    )


def test_message_pagination(setup):
    container, client, room, (host, h), (guest, g), _ = joined(setup)
    repo = container.study_room_repository
    for i in range(205):
        repo.send(room, host if i % 2 == 0 else guest, f"消息{i}", f"c{i}")
    received, after, pages = [], 0, []
    while True:
        page = client.get(
            f"{BASE}/{room}/messages", headers=h, params={"after": after}
        ).json()["items"]
        pages.append(len(page))
        received.extend(page)
        if len(page) < 100:
            break
        after = page[-1]["id"]
    assert pages == [100, 100, 5]
    assert [m["content"] for m in received] == [f"消息{i}" for i in range(205)]


def test_leave_and_host_end(setup):
    container, client, room, (host, h), (guest, g), _ = joined(setup)
    assert client.post(f"{BASE}/{room}/leave", headers=g).status_code == 204
    assert client.get(f"{BASE}/{room}", headers=g).status_code == 404
    assert client.get(f"{BASE}/{room}", headers=h).status_code == 200
    assert client.post(f"{BASE}/{room}/leave", headers=h).status_code == 204
    assert client.get(f"{BASE}/{room}", headers=h).status_code in (404, 410)


def test_concurrent_accept_cap_is_atomic(setup):
    container, client, ((host, h), *rest) = setup
    room = make_room(client, h).json()["id"]
    repos = [
        StudyRoomRepository(Database(container.settings.database_path))
        for _ in range(2)
    ]
    barrier = threading.Barrier(2)

    def send(repo):
        barrier.wait(timeout=5)
        return repo.send(room, host, "并发送达", "same-client")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, repos))
    assert results[0]["id"] == results[1]["id"]
    msgs = client.get(f"{BASE}/{room}/messages", headers=h).json()["items"]
    assert [m["id"] for m in msgs] == [results[0]["id"]]
