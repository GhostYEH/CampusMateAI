"""共同课堂专注监督：状态上报、老师自动提醒、发起人名单与提醒权限。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.database.sqlite_db import Database
from app.main import create_app
from app.services.container import reset_container_for_tests

BASE = "/api/v1/magicclass/learning-space"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    settings = Settings(
        app_env="test",
        database_url=f"sqlite:///{(tmp_path / 'supervision.db').as_posix()}",
        auto_seed_demo_users=False,
        llm_provider="none",
        agent_allow_mock_providers=True,
    )
    test_db = Database(tmp_path / "supervision.db")
    monkeypatch.setattr("app.database.sqlite_db.reset_db_for_tests", lambda: test_db)
    container = reset_container_for_tests(settings)
    client = TestClient(create_app())
    accounts = []
    for name in ("sup_host", "sup_guest", "sup_outsider"):
        client.post(
            "/api/v1/auth/register",
            json={"username": name, "password": "TestSup123", "role": "student"},
        )
        data = client.post(
            "/api/v1/auth/login",
            json={"username": name, "password": "TestSup123"},
        ).json()
        accounts.append(
            (data["user"]["uid"], {"Authorization": f"Bearer {data['access_token']}"})
        )
    return container, client, accounts


def make_room(client, headers):
    response = client.post(
        f"{BASE}/rooms/native", headers=headers, json={"title": "课堂监督"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def joined(setup):
    container, client, ((host, h), (guest, g), (outsider, o)) = setup
    room = make_room(client, h)
    assert client.post(
        f"{BASE}/rooms/{room}/invitations", headers=h, json={"uid": guest}
    ).status_code == 200
    assert client.post(
        f"{BASE}/invitations/{room}/accept", headers=g
    ).status_code == 200
    return container, client, room, (host, h), (guest, g), (outsider, o)


def test_attention_requires_membership_and_valid_enum(setup):
    _, client, room, (_, h), _, (_, o) = joined(setup)
    assert client.put(f"{BASE}/rooms/{room}/attention", json={"state": "FOCUSED"}).status_code == 401
    assert client.put(
        f"{BASE}/rooms/{room}/attention", headers=o, json={"state": "FOCUSED"}
    ).status_code == 404
    assert client.put(
        f"{BASE}/rooms/{room}/attention", headers=h, json={"state": "SLEEPING"}
    ).status_code == 422
    assert client.put(
        f"{BASE}/rooms/{room}/attention",
        headers=h,
        json={"state": "FOCUSED", "source": "CAMERA"},
    ).status_code == 422
    ok = client.put(
        f"{BASE}/rooms/{room}/attention",
        headers=h,
        json={"state": "FOCUSED", "source": "ON_DEVICE"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["state"] == "FOCUSED"
    assert ok.json()["teacher_reminder"] is None


def test_host_sees_roster_but_guest_only_sees_self(setup):
    _, client, room, (host, h), (guest, g), (_, _) = joined(setup)
    for headers, state in ((h, "FOCUSED"), (g, "AWAY")):
        assert client.put(
            f"{BASE}/rooms/{room}/attention",
            headers=headers,
            json={"state": state, "source": "HEARTBEAT"},
        ).status_code == 200

    host_view = client.get(f"{BASE}/rooms/{room}/supervision", headers=h).json()
    assert host_view["me"]["uid"] == host
    assert host_view["me"]["is_host"] is True
    assert host_view["me"]["name"]
    assert {item["uid"] for item in host_view["members"]} == {host, guest}
    assert host_view["stats"] == {
        "total": 1, "online": 1, "focused": 0, "needs_attention": 1,
    }
    assert host_view["teacher_summary"]
    assert host_view["teacher_name"] == "小伴老师"

    guest_view = client.get(f"{BASE}/rooms/{room}/supervision", headers=g).json()
    assert guest_view["me"]["state"] == "AWAY"
    assert guest_view["me"]["is_host"] is False
    assert guest_view["members"] == []
    assert guest_view["stats"] is None
    assert guest_view["nudges"] == []


def test_sustained_distraction_triggers_teacher_nudge_with_cooldown(setup):
    container, client, room, (_, h), (guest, g), _ = joined(setup)
    body = {"state": "DISTRACTED", "source": "ON_DEVICE"}
    assert client.put(f"{BASE}/rooms/{room}/attention", headers=g, json=body).json()["teacher_reminder"] is None

    # Simulate the client keeping the same state for longer than the 30 s threshold.
    past = (datetime.now(timezone.utc) - timedelta(seconds=40)).isoformat()
    with container.db.transaction() as conn:
        conn.execute(
            "UPDATE learning_room_attention SET low_since=? WHERE room_id=? AND user_id=?",
            (past, room, guest),
        )
    reminded = client.put(f"{BASE}/rooms/{room}/attention", headers=g, json=body)
    assert reminded.status_code == 200, reminded.text
    reminder = reminded.json()["teacher_reminder"]
    assert reminder and reminder["kind"] == "TEACHER"
    assert reminder["target_uid"] == guest
    assert "老师" in reminder["content"]
    first_id = reminder["id"]

    # The same state must not produce another reminder inside the cooldown.
    again = client.put(f"{BASE}/rooms/{room}/attention", headers=g, json=body)
    assert again.json()["teacher_reminder"] is None

    guest_view = client.get(
        f"{BASE}/rooms/{room}/supervision", headers=g, params={"after": "0"}
    ).json()
    assert [item["id"] for item in guest_view["nudges"]] == [first_id]
    host_view = client.get(f"{BASE}/rooms/{room}/supervision", headers=h).json()
    assert [item["id"] for item in host_view["nudges"]] == [first_id]

    # Recovery clears the sustained-low marker; a later episode can remind again.
    assert client.put(
        f"{BASE}/rooms/{room}/attention",
        headers=g,
        json={"state": "FOCUSED", "source": "ON_DEVICE"},
    ).status_code == 200
    with container.db.transaction() as conn:
        assert conn.execute(
            "SELECT low_since FROM learning_room_attention WHERE room_id=? AND user_id=?",
            (room, guest),
        ).fetchone()[0] is None


def test_auto_nudge_is_capped_per_member(setup):
    container, client, room, (_, _), (guest, g), _ = joined(setup)
    with container.db.transaction() as conn:
        for number in range(1, 6):
            conn.execute(
                "INSERT INTO learning_room_nudges(room_id,from_user_id,target_user_id,kind,content,created_at) "
                "VALUES (?,NULL,?,'TEACHER',?,?)",
                (room, guest, f"提醒 {number}", (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()),
            )
    past = (datetime.now(timezone.utc) - timedelta(seconds=40)).isoformat()
    with container.db.transaction() as conn:
        conn.execute(
            "INSERT INTO learning_room_attention(room_id,user_id,state,source,low_since,updated_at,created_at) "
            "VALUES (?,?,'DISTRACTED','ON_DEVICE',?,?,?)",
            (room, guest, past, past, past),
        )
    report = client.put(
        f"{BASE}/rooms/{room}/attention",
        headers=g,
        json={"state": "DISTRACTED", "source": "ON_DEVICE"},
    )
    assert report.json()["teacher_reminder"] is None


def test_host_can_remind_private_and_broadcast_but_guest_cannot(setup):
    _, client, room, (host, h), (guest, g), (_, o) = joined(setup)
    assert client.post(
        f"{BASE}/rooms/{room}/nudges", headers=g, json={"target_uid": host}
    ).status_code == 403
    assert client.post(
        f"{BASE}/rooms/{room}/nudges", headers=h, json={"target_uid": "usr_missing"}
    ).status_code == 404
    assert client.post(
        f"{BASE}/rooms/{room}/nudges", headers=h, json={"target_uid": guest}
    ).status_code == 201
    with_text = client.post(
        f"{BASE}/rooms/{room}/nudges",
        headers=h,
        json={"target_uid": guest, "content": "  看回第三页，老师等你。  "},
    )
    assert with_text.status_code == 201
    assert with_text.json()["content"] == "看回第三页，老师等你。"
    broadcast = client.post(f"{BASE}/rooms/{room}/nudges", headers=h, json={})
    assert broadcast.status_code == 201
    assert broadcast.json()["target_uid"] is None

    guest_view = client.get(f"{BASE}/rooms/{room}/supervision", headers=g).json()
    contents = [item["content"] for item in guest_view["nudges"]]
    assert "看回第三页，老师等你。" in contents
    assert broadcast.json()["content"] in contents
    assert len(guest_view["nudges"]) == 3
    # Only own and broadcast reminders are visible to the guest.
    assert all(item["target_uid"] in (None, guest) for item in guest_view["nudges"])

    host_view = client.get(f"{BASE}/rooms/{room}/supervision", headers=h).json()
    assert len(host_view["nudges"]) == 3


def test_incremental_nudges_and_stale_attention(setup):
    container, client, room, (host, h), (guest, g), _ = joined(setup)
    client.put(
        f"{BASE}/rooms/{room}/attention",
        headers=h,
        json={"state": "FOCUSED", "source": "HEARTBEAT"},
    )
    client.put(
        f"{BASE}/rooms/{room}/attention",
        headers=g,
        json={"state": "FOCUSED", "source": "PAGE_VISIBILITY"},
    )
    old = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    with container.db.transaction() as conn:
        conn.execute(
            "UPDATE learning_room_attention SET updated_at=? WHERE room_id=? AND user_id=?",
            (old, room, guest),
        )
    view = client.get(f"{BASE}/rooms/{room}/supervision", headers=h).json()
    member = next(item for item in view["members"] if item["uid"] == guest)
    assert member["online"] is False
    assert member["attention_age_seconds"] >= 55
    assert view["stats"]["online"] == 0
    assert view["stats"]["total"] == 1

    first = client.post(
        f"{BASE}/rooms/{room}/nudges", headers=h, json={"target_uid": guest}
    ).json()
    after_first = client.get(
        f"{BASE}/rooms/{room}/supervision",
        headers=g,
        params={"after": str(first["id"])},
    ).json()
    assert after_first["nudges"] == []


def test_leaving_and_ending_room_stop_attention_writes(setup):
    _, client, room, (host, h), (guest, g), _ = joined(setup)
    assert client.post(f"{BASE}/rooms/{room}/leave", headers=g).status_code == 204
    assert client.put(
        f"{BASE}/rooms/{room}/attention", headers=g, json={"state": "FOCUSED"}
    ).status_code == 404
    assert client.get(f"{BASE}/rooms/{room}/supervision", headers=g).status_code == 404

    assert client.post(f"{BASE}/rooms/{room}/leave", headers=h).status_code == 204
    assert client.put(
        f"{BASE}/rooms/{room}/attention", headers=h, json={"state": "FOCUSED"}
    ).status_code == 404
