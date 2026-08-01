from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client() -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app())


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_demo_personal_task_uses_readable_chinese_copy() -> None:
    client = _client()
    response = client.get("/api/v1/tasks", headers=_headers(client))

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert "整理本周学习任务" in titles
    assert all("???" not in title for title in titles)


def test_personal_task_rejects_likely_garbled_text_on_create_and_update() -> None:
    client = _client()
    headers = _headers(client)

    garbled = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={"title": "???????????", "description": "9?20????"},
    )
    assert garbled.status_code == 422
    assert "疑似在传输过程中丢失字符" in garbled.text

    created = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "title": "整理实验报告素材",
            "description": "整理本周实验记录和截图，周末前完成初稿。",
        },
    )
    assert created.status_code == 201

    rejected_update = client.patch(
        f"/api/v1/tasks/{created.json()['id']}",
        headers=headers,
        json={"description": "9?20????"},
    )
    assert rejected_update.status_code == 422

    current = client.get(f"/api/v1/tasks/{created.json()['id']}", headers=headers)
    assert current.status_code == 200
    assert current.json()["description"] == "整理本周实验记录和截图，周末前完成初稿。"
