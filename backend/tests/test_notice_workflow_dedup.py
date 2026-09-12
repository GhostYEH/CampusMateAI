"""通知工作流去重与手工 notice_id 桥接测试(§8.3、§9.4)。"""
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


def _manual_notice(client, headers, title, content):
    resp = client.post(
        "/api/v1/notices/manual",
        json={"title": title, "content": content},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestManualNoticeBridge:
    def test_manual_returns_notice_id(self):
        _, client = _client()
        headers = _login(client)
        body = _manual_notice(
            client, headers, "奖学金申请", "请于2026年10月15日前提交申请表至教务处"
        )
        assert body["notice_id"]
        assert body["title"] == "奖学金申请"
        assert body["duplicate"] is False

    def test_manual_dedup_same_content(self):
        _, client = _client()
        headers = _login(client)
        content = "请于2026年10月15日前提交申请表至教务处"
        b1 = _manual_notice(client, headers, "奖学金", content)
        b2 = _manual_notice(client, headers, "奖学金", content)
        assert b1["notice_id"] == b2["notice_id"]
        assert b2["duplicate"] is True

    def test_manual_different_content_different_id(self):
        _, client = _client()
        headers = _login(client)
        b1 = _manual_notice(client, headers, "通知A", "内容A" * 10)
        b2 = _manual_notice(client, headers, "通知B", "内容B" * 10)
        assert b1["notice_id"] != b2["notice_id"]


class TestWorkflowDedup:
    def _make_workflow(self, client, headers, content):
        notice = _manual_notice(client, headers, "测试通知", content)
        resp = client.post(
            f"/api/v1/notices/{notice['notice_id']}/workflow",
            json={},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    def test_workflow_created_for_notice(self):
        _, client = _client()
        headers = _login(client)
        wf = self._make_workflow(
            client, headers, "请于2026年10月15日前提交申请表至教务处"
        )
        assert wf["workflow_id"]
        assert wf["status"] in ("WAITING_CONFIRMATION", "PROCESSING", "COMPLETED")
        assert wf["confidence"] >= 0.0

    def test_same_notice_workflow_dedup(self):
        _, client = _client()
        headers = _login(client)
        content = "请于2026年10月15日前提交申请表至教务处"
        notice = _manual_notice(client, headers, "通知", content)
        r1 = client.post(
            f"/api/v1/notices/{notice['notice_id']}/workflow", json={}, headers=headers
        )
        r2 = client.post(
            f"/api/v1/notices/{notice['notice_id']}/workflow", json={}, headers=headers
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["workflow_id"] == r2.json()["workflow_id"]

    def test_idempotency_key_returns_same_workflow(self):
        _, client = _client()
        headers = _login(client)
        notice = _manual_notice(
            client, headers, "通知", "请于2026年10月15日前提交申请表"
        )
        r1 = client.post(
            f"/api/v1/notices/{notice['notice_id']}/workflow",
            json={},
            headers={**headers, "Idempotency-Key": "wf-key-1"},
        )
        r2 = client.post(
            f"/api/v1/notices/{notice['notice_id']}/workflow",
            json={},
            headers={**headers, "Idempotency-Key": "wf-key-1"},
        )
        assert r1.json()["workflow_id"] == r2.json()["workflow_id"]

    def test_missing_deadline_marked_uncertain(self):
        _, client = _client()
        headers = _login(client)
        # 无截止时间、无材料
        wf = self._make_workflow(client, headers, "图书馆开放时间调整请知悉")
        assert "deadline_missing" in wf["uncertainty"]

    def test_missing_materials_marked_uncertain(self):
        _, client = _client()
        headers = _login(client)
        # 有截止但无材料关键词
        wf = self._make_workflow(
            client, headers, "请于2026年10月15日前到教务处签到"
        )
        assert "materials_missing" in wf["uncertainty"]