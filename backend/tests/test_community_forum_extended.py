from __future__ import annotations

from datetime import datetime, timezone
import io

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _setup() -> tuple[TestClient, object]:
    settings = Settings(app_env="test1test", database_url="sqlite:///:memory:", auto_seed_demo_users=True, auto_import_demo=False)
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    now = datetime.now(timezone.utc).isoformat()
    with container.db.transaction() as conn:
        conn.execute("INSERT INTO universities (id,name,country,academic_system_type,academic_provider,forum_enabled,status,is_demo,created_at,updated_at) VALUES ('uni_b','Second','China','unsupported','unsupported',1,'active',1,?,?)", (now, now))
    user = container.user_repository.create_user(username="stu_forum", password_hash=hash_password("Demo123456"), role="student", display_name="stu_forum")
    container.user_repository.update_university(user.id, "uni_demo_university")
    return TestClient(create_app()), container


def _headers(client: TestClient, username: str = "stu_forum") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": "Demo123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_categories_endpoint_returns_all_meta() -> None:
    client, _ = _setup()
    h = _headers(client)
    resp = client.get("/api/v1/community/posts/categories")
    assert resp.status_code == 200, resp.text
    keys = {c["key"] for c in resp.json()["items"]}
    assert {"question", "recruit", "errand", "lostfound", "campus"}.issubset(keys)


def test_category_filter_isolates_posts() -> None:
    client, _ = _setup()
    h = _headers(client)
    client.post("/api/v1/community/posts", headers=h, json={"title": "Q", "content": "question post", "category": "question"})
    client.post("/api/v1/community/posts", headers=h, json={"title": "R", "content": "recruit post", "category": "recruit"})
    only_q = client.get("/api/v1/community/posts?category=question", headers=h).json()
    assert [i["title"] for i in only_q["items"]] == ["Q"]
    only_r = client.get("/api/v1/community/posts?category=recruit", headers=h).json()
    assert [i["title"] for i in only_r["items"]] == ["R"]


def test_hot_sort_ranks_by_interactions() -> None:
    client, _ = _setup()
    h = _headers(client)
    hot_id = client.post("/api/v1/community/posts", headers=h, json={"title": "Hot", "content": "liked", "category": "campus"}).json()["id"]
    cold_id = client.post("/api/v1/community/posts", headers=h, json={"title": "Cold", "content": "no interactions", "category": "campus"}).json()["id"]
    client.post(f"/api/v1/community/posts/{hot_id}/like", headers=h)
    client.post(f"/api/v1/community/posts/{hot_id}/comments", headers=h, json={"content": "comment"})
    feed = client.get("/api/v1/community/posts?sort=hot", headers=h).json()
    assert feed["items"][0]["title"] == "Hot"


def test_post_edit_updates_title_and_content() -> None:
    client, _ = _setup()
    h = _headers(client)
    post_id = client.post("/api/v1/community/posts", headers=h, json={"title": "Old", "content": "old content", "category": "campus"}).json()["id"]
    updated = client.put(f"/api/v1/community/posts/{post_id}", headers=h, json={"title": "New", "content": "new content"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "New"
    assert updated.json()["content"] == "new content"


def test_recruit_extra_is_validated_and_returned() -> None:
    client, _ = _setup()
    h = _headers(client)
    resp = client.post("/api/v1/community/posts", headers=h, json={
        "title": "招募队友", "content": "比赛组队", "category": "recruit",
        "extra": {"headcount": 3, "location": "教3-201", "deadline": "2026-12-31"},
    })
    assert resp.status_code == 201, resp.text
    extra = resp.json()["extra"]
    assert extra["headcount"] == 3
    assert extra["location"] == "教3-201"


def test_lostfound_extra_contact_is_masked_for_non_owner() -> None:
    client, container = _setup()
    owner = _headers(client, "stu_forum")
    peer_user = container.user_repository.create_user(username="stu_peer", password_hash=hash_password("Demo123456"), role="student", display_name="peer")
    container.user_repository.update_university(peer_user.id, "uni_demo_university")
    peer = _headers(client, "stu_peer")
    post_id = client.post("/api/v1/community/posts", headers=owner, json={
        "title": "丢了一本书", "content": "在图书馆", "category": "lostfound",
        "extra": {"kind": "lost", "location": "图书馆", "contact": "13800000000", "contact_visibility": "private"},
    }).json()["id"]
    detail = client.get(f"/api/v1/community/posts/{post_id}", headers=peer).json()
    assert detail["extra"]["contact"] is None
    owner_detail = client.get(f"/api/v1/community/posts/{post_id}", headers=owner).json()
    assert owner_detail["extra"]["contact"] == "13800000000"


def test_lostfound_legacy_route_proxies_to_forum() -> None:
    client, _ = _setup()
    h = _headers(client)
    created = client.post("/api/v1/student/lost-found", headers=h, json={
        "kind": "lost", "title": "钥匙", "content": "丢了一把钥匙", "location": "食堂", "contact": "123", "contact_visibility": "private",
    })
    assert created.status_code == 201, created.text
    assert created.json()["kind"] == "lost"
    legacy_list = client.get("/api/v1/student/lost-found", headers=h).json()
    assert any(i["title"] == "钥匙" for i in legacy_list)
    forum_list = client.get("/api/v1/community/posts?category=lostfound", headers=h).json()
    assert any(i["title"] == "钥匙" for i in forum_list["items"])


def test_image_upload_returns_url() -> None:
    client, _ = _setup()
    h = _headers(client)
    img_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    resp = client.post(
        "/api/v1/community/upload-image",
        headers=h,
        files={"image": ("test.png", io.BytesIO(img_bytes), "image/png")},
    )
    assert resp.status_code == 200, resp.text
    url = resp.json()["url"]
    assert url.startswith("/static/community_images/")
    assert url.endswith(".png")


def test_post_accepts_nine_images_for_forum_composer() -> None:
    client, _ = _setup()
    h = _headers(client)
    response = client.post("/api/v1/community/posts", headers=h, json={
        "title": "九宫格校园生活", "content": "配合发帖页的九张图片上限", "category": "campus",
        "images": [f"/static/community_images/{index}.png" for index in range(9)],
    })
    assert response.status_code == 201, response.text
    assert len(response.json()["images"]) == 9


def test_post_detail_increments_view_count() -> None:
    client, _ = _setup()
    h = _headers(client)
    post_id = client.post("/api/v1/community/posts", headers=h, json={"title": "View", "content": "view test", "category": "campus"}).json()["id"]
    client.get(f"/api/v1/community/posts/{post_id}", headers=h)
    client.get(f"/api/v1/community/posts/{post_id}", headers=h)
    detail = client.get(f"/api/v1/community/posts/{post_id}", headers=h).json()
    assert detail["view_count"] >= 2


def test_like_and_unlike_are_idempotent() -> None:
    client, _ = _setup()
    h = _headers(client)
    post_id = client.post("/api/v1/community/posts", headers=h, json={"title": "Like", "content": "like test", "category": "campus"}).json()["id"]
    liked = client.post(f"/api/v1/community/posts/{post_id}/like", headers=h).json()
    assert liked["liked"] is True
    assert liked["like_count"] == 1
    liked_again = client.post(f"/api/v1/community/posts/{post_id}/like", headers=h).json()
    assert liked_again["like_count"] == 1
    unliked = client.delete(f"/api/v1/community/posts/{post_id}/like", headers=h).json()
    assert unliked["liked"] is False
    assert unliked["like_count"] == 0
