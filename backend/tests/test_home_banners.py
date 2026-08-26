from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import get_container, reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _setup() -> TestClient:
    settings = Settings(
        app_env="test-home-banners",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app())


def _headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _draft_payload(title: str = "新的软件能力") -> dict[str, object]:
    return {
        "eyebrow": "CAMPUSMATE UPDATE",
        "title": title,
        "subtitle": "集中配置后，各学生客户端自动获取。",
        "cta_label": "快来体验吧",
        "image_url": "/static/banner-images/new-feature.png",
        "action_key": "CPM_ASSISTANT",
        "theme_key": "INDIGO",
        "sort_order": 25,
    }


def test_public_feed_contains_global_seed_banners_in_display_order() -> None:
    client = _setup()

    response = client.get("/api/v1/home-banners")

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["action_key"] for item in body["items"]] == [
        "CPM_ASSISTANT",
        "CHAOXING",
        "EDU_SYSTEM",
        "TASKS",
        "COMMUNITY",
    ]
    assert all(item["status"] == "PUBLISHED" for item in body["items"])
    assert all("university_id" not in item for item in body["items"])
    assert all(client.get(item["image_url"]).status_code == 200 for item in body["items"])


def test_admin_can_create_publish_update_and_archive_banner() -> None:
    client = _setup()
    admin = _headers(client, "admin_demo")
    before_ids = {item["id"] for item in client.get("/api/v1/home-banners").json()["items"]}

    created = client.post("/api/v1/admin/home-banners", headers=admin, json=_draft_payload())
    assert created.status_code == 201, created.text
    banner_id = created.json()["id"]
    assert created.json()["status"] == "DRAFT"
    assert banner_id not in {item["id"] for item in client.get("/api/v1/home-banners").json()["items"]}

    published = client.post(f"/api/v1/admin/home-banners/{banner_id}/publish", headers=admin)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "PUBLISHED"
    assert banner_id in {item["id"] for item in client.get("/api/v1/home-banners").json()["items"]}

    updated = client.put(
        f"/api/v1/admin/home-banners/{banner_id}",
        headers=admin,
        json={**_draft_payload("已更新的软件能力"), "sort_order": 0},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "已更新的软件能力"
    assert client.get("/api/v1/home-banners").json()["items"][0]["id"] == banner_id

    archived = client.post(f"/api/v1/admin/home-banners/{banner_id}/archive", headers=admin)
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "ARCHIVED"
    assert {item["id"] for item in client.get("/api/v1/home-banners").json()["items"]} == before_ids


def test_public_schedule_compares_equivalent_instants_across_timezones() -> None:
    client = _setup()
    admin = _headers(client, "admin_demo")
    created = client.post(
        "/api/v1/admin/home-banners",
        headers=admin,
        json={**_draft_payload("跨时区生效"), "starts_at": "2026-08-26T08:00:00+08:00"},
    )
    assert created.status_code == 201, created.text
    banner_id = created.json()["id"]
    published = client.post(f"/api/v1/admin/home-banners/{banner_id}/publish", headers=admin)
    assert published.status_code == 200, published.text

    visible_ids = {
        item.id
        for item in get_container().home_banner_repository.list_public("2026-08-26T00:30:00+00:00")
    }

    assert banner_id in visible_ids


def test_banner_admin_requires_admin_role_and_valid_action_key() -> None:
    client = _setup()
    student = _headers(client, "student_demo")
    admin = _headers(client, "admin_demo")

    forbidden = client.post("/api/v1/admin/home-banners", headers=student, json=_draft_payload())
    assert forbidden.status_code == 403

    invalid = client.post(
        "/api/v1/admin/home-banners",
        headers=admin,
        json={**_draft_payload(), "action_key": "UNKNOWN_MODULE"},
    )
    assert invalid.status_code == 422


def test_admin_image_upload_returns_banner_static_url() -> None:
    client = _setup()
    admin = _headers(client, "admin_demo")
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )

    response = client.post(
        "/api/v1/admin/home-banners/images",
        headers=admin,
        files={"image": ("feature.png", png, "image/png")},
    )

    assert response.status_code == 201, response.text
    image_url = response.json()["image_url"]
    assert image_url.startswith("/static/banner-images/")
    assert client.get(image_url).status_code == 200
    uploaded = Path(__file__).resolve().parents[1] / "data" / "banner_images" / response.json()["filename"]
    uploaded.unlink(missing_ok=True)
