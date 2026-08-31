from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _setup() -> tuple[TestClient, object]:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    now = datetime.now(timezone.utc).isoformat()
    with container.db.transaction() as conn:
        conn.execute(
            """INSERT INTO universities
               (id,name,country,academic_system_type,academic_provider,forum_enabled,status,is_demo,created_at,updated_at)
               VALUES ('uni_b','Second University','China','unsupported','unsupported',1,'active',1,?,?)""",
            (now, now),
        )
    for username, university_id in (
        ("student_a", "uni_demo_university"),
        ("student_a_peer", "uni_demo_university"),
        ("student_b", "uni_b"),
    ):
        user = container.user_repository.create_user(
            username=username,
            password_hash=hash_password("Demo123456"),
            role="student",
            display_name=username,
        )
        container.user_repository.update_university(user.id, university_id)
    return TestClient(create_app()), container


def _headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_feed_is_isolated_by_authenticated_users_university() -> None:
    client, _ = _setup()
    a = _headers(client, "student_a")
    b = _headers(client, "student_b")

    created = client.post(
        "/api/v1/community/posts",
        headers=a,
        json={"title": "A campus only", "content": "Private campus discussion", "category": "campus"},
    )
    assert created.status_code == 201, created.text

    a_feed = client.get("/api/v1/community/posts", headers=a).json()
    b_feed = client.get("/api/v1/community/posts", headers=b).json()
    assert "A campus only" in [item["title"] for item in a_feed["items"]]
    assert b_feed["items"] == []


def test_demo_student_receives_seeded_hot_campus_posts() -> None:
    client, _ = _setup()
    student = _headers(client, "student_demo")

    response = client.get(
        "/api/v1/community/posts?sort=hot&page=1&page_size=3",
        headers=student,
    )

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [item["title"] for item in items] == [
        "图书馆自习室座位怎么选？这份避坑清单请收好",
        "新学期选课互助：这些公共课还有空位吗？",
        "求推荐：校内适合小组讨论的安静地点",
    ]
    assert all(item["like_count"] > 0 for item in items)
    assert all(item["comment_count"] > 0 for item in items)


def test_post_ownership_and_admin_moderation_are_enforced() -> None:
    client, _ = _setup()
    a = _headers(client, "student_a")
    peer = _headers(client, "student_a_peer")
    admin = _headers(client, "admin_demo")
    post_id = client.post(
        "/api/v1/community/posts",
        headers=a,
        json={"title": "Owned by A", "content": "A owns this", "category": "study"},
    ).json()["id"]

    denied = client.delete(f"/api/v1/community/posts/{post_id}", headers=peer)
    assert denied.status_code == 403

    hidden = client.post(f"/api/v1/admin/community/posts/{post_id}/hide", headers=admin)
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["status"] == "hidden"
    assert "Owned by A" not in [
        item["title"]
        for item in client.get("/api/v1/community/posts", headers=a).json()["items"]
    ]


def test_anonymous_post_hides_identity_but_preserves_backend_ownership() -> None:
    client, container = _setup()
    a = _headers(client, "student_a")
    response = client.post(
        "/api/v1/community/posts",
        headers=a,
        json={
            "title": "Anonymous question",
            "content": "Please hide my public identity",
            "category": "question",
            "is_anonymous": True,
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["author_name"] == "校园同学"
    assert payload["author_id"] is None
    assert "images_json" not in payload
    with container.db.query() as conn:
        stored = conn.execute("SELECT author_id FROM forum_posts WHERE id = ?", (payload["id"],)).fetchone()
    assert stored["author_id"]


def test_comments_likes_favorites_and_reports_use_idempotent_contracts() -> None:
    client, _ = _setup()
    a = _headers(client, "student_a")
    post_id = client.post(
        "/api/v1/community/posts",
        headers=a,
        json={"title": "Interactions", "content": "Interact here", "category": "life"},
    ).json()["id"]

    comment = client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        headers=a,
        json={"content": "First comment"},
    )
    assert comment.status_code == 201, comment.text
    assert client.get(f"/api/v1/community/posts/{post_id}/comments", headers=a).json()["total"] == 1

    assert client.post(f"/api/v1/community/posts/{post_id}/like", headers=a).status_code == 200
    assert client.post(f"/api/v1/community/posts/{post_id}/like", headers=a).json()["like_count"] == 1
    assert client.post(f"/api/v1/community/posts/{post_id}/favorite", headers=a).status_code == 200
    report = client.post(
        "/api/v1/community/reports",
        headers=a,
        json={"target_type": "post", "target_id": post_id, "reason": "垃圾广告"},
    )
    assert report.status_code == 201, report.text


def test_community_requires_a_selected_university() -> None:
    client, _ = _setup()
    headers = _headers(client, "student_demo_01")
    response = client.get("/api/v1/community/posts", headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "UNIVERSITY_REQUIRED"
