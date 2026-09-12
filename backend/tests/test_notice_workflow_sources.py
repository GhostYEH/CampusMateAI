"""通知来源注册与自动化开关测试(§7.3、§8.3、§9.4)。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client():
    container = reset_container_for_tests(
        Settings(
            app_env="test",
            database_url="sqlite:///:memory:",
            auto_seed_demo_users=True,
            auto_import_demo=False,
            llm_provider="none",
            agent_allow_mock_providers=True,
        )
    )
    seed_demo_data(container, force=True)
    return container, TestClient(create_app())


def _login(client, username="student_demo"):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class TestNotificationSources:
    def test_requires_auth(self):
        _, client = _client()
        assert client.get("/api/v1/notification-sources").status_code == 401

    def test_lists_default_sources(self):
        _, client = _client()
        headers = _login(client)
        resp = client.get("/api/v1/notification-sources", headers=headers)
        assert resp.status_code == 200, resp.text
        codes = {s["code"] for s in resp.json()}
        assert "android_system" in codes
        assert "chaoxing" in codes
        assert "campus_announcement" in codes
        assert "manual_input" in codes

    def test_automation_disabled_by_default(self):
        _, client = _client()
        headers = _login(client)
        resp = client.get("/api/v1/notification-sources", headers=headers)
        for s in resp.json():
            assert s["automation_enabled"] is False

    def test_patch_automation_enabled(self):
        _, client = _client()
        headers = _login(client)
        sources = client.get(
            "/api/v1/notification-sources", headers=headers
        ).json()
        manual = next(s for s in sources if s["code"] == "manual_input")
        resp = client.patch(
            f"/api/v1/notification-sources/{manual['source_id']}",
            json={"automation_enabled": True},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["automation_enabled"] is True
        # 再次列表确认持久化
        sources2 = client.get(
            "/api/v1/notification-sources", headers=headers
        ).json()
        manual2 = next(s for s in sources2 if s["code"] == "manual_input")
        assert manual2["automation_enabled"] is True

    def test_patch_display_name(self):
        _, client = _client()
        headers = _login(client)
        sources = client.get(
            "/api/v1/notification-sources", headers=headers
        ).json()
        src = sources[0]
        resp = client.patch(
            f"/api/v1/notification-sources/{src['source_id']}",
            json={"display_name": "自定义名称"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "自定义名称"

    def test_patch_nonexistent_source(self):
        _, client = _client()
        headers = _login(client)
        resp = client.patch(
            "/api/v1/notification-sources/nwfsrc_nonexistent",
            json={"automation_enabled": True},
            headers=headers,
        )
        assert resp.status_code == 404