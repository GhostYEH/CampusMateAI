from __future__ import annotations


from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import get_container, reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _setup() -> TestClient:
    settings = Settings(
        app_env="test",
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


def test_public_schedule_compares_equivalent_instants_across_timezones() -> None:
    client = _setup()
    repository = get_container().home_banner_repository
    row = repository.create({**_draft_payload("跨时区生效"), "starts_at": "2026-08-26T08:00:00+08:00"})
    repository.set_status(row.id, "PUBLISHED")
    banner_id = row.id

    visible_ids = {
        item.id
        for item in get_container().home_banner_repository.list_public("2026-08-26T00:30:00+00:00")
    }

    assert banner_id in visible_ids
