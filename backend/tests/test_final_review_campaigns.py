"""期末复习 campaign 测试。

覆盖:campaign 创建、server exam ID 校验、幂等、跨用户拒绝。
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.final_review import router as final_review_router
from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _setup():
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
    # 添加 fake provider
    container.agent_provider_registry.add_fake("fake")
    app = create_app()
    app.include_router(final_review_router, prefix="/api/v1")
    return container, TestClient(app)


def _login(client, username="student_demo"):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_exam(client, headers, course_name="高等数学", exam_date="2026-12-30"):
    """通过 /student/exams 创建考试,返回 exam_id。"""
    resp = client.post(
        "/api/v1/student/exams",
        json={"course_name": course_name, "exam_date": exam_date},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


class TestCampaignCreate:
    def test_create_campaign_with_valid_exam_ids(self):
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        resp = client.post(
            "/api/v1/final-review/campaigns",
            json={"exam_ids": [exam_id], "daily_capacity_minutes": 120},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "draft"
        assert body["exam_ids"] == [exam_id]
        assert body["daily_capacity_minutes"] == 120

    def test_create_campaign_rejects_invalid_exam_id(self):
        _, client = _setup()
        headers = _login(client)
        resp = client.post(
            "/api/v1/final-review/campaigns",
            json={"exam_ids": ["exam_nonexistent"], "daily_capacity_minutes": 120},
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["code"] == "VALIDATION_FAILED"

    def test_create_campaign_idempotency(self):
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        payload = {"exam_ids": [exam_id], "daily_capacity_minutes": 90}
        resp1 = client.post(
            "/api/v1/final-review/campaigns",
            json=payload,
            headers={**headers, "Idempotency-Key": "camp-1"},
        )
        resp2 = client.post(
            "/api/v1/final-review/campaigns",
            json=payload,
            headers={**headers, "Idempotency-Key": "camp-1"},
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["campaign_id"] == resp2.json()["campaign_id"]

    def test_list_campaigns(self):
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        client.post(
            "/api/v1/final-review/campaigns",
            json={"exam_ids": [exam_id], "daily_capacity_minutes": 120},
            headers=headers,
        )
        resp = client.get("/api/v1/final-review/campaigns", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_campaign(self):
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        create = client.post(
            "/api/v1/final-review/campaigns",
            json={"exam_ids": [exam_id], "daily_capacity_minutes": 120},
            headers=headers,
        )
        cid = create.json()["campaign_id"]
        resp = client.get(f"/api/v1/final-review/campaigns/{cid}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["campaign_id"] == cid

    def test_get_nonexistent_campaign(self):
        _, client = _setup()
        headers = _login(client)
        resp = client.get(
            "/api/v1/final-review/campaigns/nonexistent", headers=headers
        )
        assert resp.status_code == 404

    def test_cross_user_access_denied(self):
        _, client = _setup()
        # student_demo 创建 campaign
        headers1 = _login(client, "student_demo")
        exam_id = _create_exam(client, headers1)
        create = client.post(
            "/api/v1/final-review/campaigns",
            json={"exam_ids": [exam_id], "daily_capacity_minutes": 120},
            headers=headers1,
        )
        cid = create.json()["campaign_id"]
        # student_demo_01 尝试访问
        headers2 = _login(client, "student_demo_01")
        resp = client.get(
            f"/api/v1/final-review/campaigns/{cid}", headers=headers2
        )
        assert resp.status_code == 404

    def test_requires_student_role(self):
        _, client = _setup()
        # 无 token
        resp = client.post(
            "/api/v1/final-review/campaigns",
            json={"exam_ids": ["x"], "daily_capacity_minutes": 120},
        )
        assert resp.status_code == 401