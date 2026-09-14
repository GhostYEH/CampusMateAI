"""期末复习 daily agenda 测试。

覆盖:今日议程生成、幂等、完成 item、每日签到。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes.final_review import router as final_review_router
from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data

from final_review_helpers import drain_worker


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
    resp = client.post(
        "/api/v1/student/exams",
        json={"course_name": course_name, "exam_date": exam_date},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_active_campaign(container, client, headers, exam_ids, capacity=120):
    """创建 campaign → 生成 plan → 审批 → 激活(由 Worker 完成)。返回 campaign_id。"""
    cid = client.post(
        "/api/v1/final-review/campaigns",
        json={"exam_ids": exam_ids, "daily_capacity_minutes": capacity},
        headers=headers,
    ).json()["campaign_id"]
    generated = client.post(
        f"/api/v1/final-review/campaigns/{cid}/plans/generate",
        json={}, headers=headers,
    )
    assert generated.status_code == 200, generated.text
    approval_id = generated.json()["approval_id"]
    approved = client.post(
        f"/api/v1/agent-approvals/{approval_id}/decision",
        json={"decision": "APPROVED", "reason": "daily agenda test"},
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    activated = client.post(
        f"/api/v1/final-review/campaigns/{cid}/activate",
        json={"version": 1}, headers=headers,
    )
    assert activated.status_code == 200, activated.text
    # 激活是异步命令:驱动 Worker 执行审批后的实际写入。
    drain_worker(container)
    return cid


class TestDailyAgenda:
    def test_get_today_agenda(self):
        container, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_active_campaign(container, client, headers, [exam_id])
        resp = client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["campaign_id"] == cid
        assert body["plan_version"] == 1
        assert "items" in body

    def test_today_agenda_idempotent(self):
        """重复获取今日议程返回相同 agenda_id(幂等)。"""
        container, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_active_campaign(container, client, headers, [exam_id])
        r1 = client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers,
        )
        r2 = client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers,
        )
        assert r1.json()["agenda_id"] == r2.json()["agenda_id"]

    def test_today_agenda_items_have_personal_tasks(self):
        """agenda items 物化为 personal_tasks。"""
        container, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_active_campaign(container, client, headers, [exam_id])
        resp = client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers,
        )
        items = resp.json()["items"]
        # 如果有 items,每个应有 personal_task_id
        for item in items:
            if item["status"] == "pending":
                assert item["personal_task_id"] is not None

    def test_today_agenda_not_activated(self):
        """未激活的 campaign 不能获取 agenda。"""
        container, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        # 创建 campaign 但不激活
        cid = client.post(
            "/api/v1/final-review/campaigns",
            json={"exam_ids": [exam_id], "daily_capacity_minutes": 120},
            headers=headers,
        ).json()["campaign_id"]
        client.post(
            f"/api/v1/final-review/campaigns/{cid}/plans/generate",
            json={}, headers=headers,
        )
        resp = client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers,
        )
        assert resp.status_code == 409

    def test_complete_item(self):
        container, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_active_campaign(container, client, headers, [exam_id])
        agenda = client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers,
        ).json()
        items = agenda["items"]
        if not items:
            return  # 无 items 时跳过
        item_id = items[0]["item_id"]
        resp = client.post(
            f"/api/v1/final-review/daily-items/{item_id}/complete",
            json={"difficulty": "medium"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "completed"

    def test_complete_item_idempotent(self):
        """重复完成同一 item 不报错。"""
        container, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_active_campaign(container, client, headers, [exam_id])
        agenda = client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers,
        ).json()
        items = agenda["items"]
        if not items:
            return
        item_id = items[0]["item_id"]
        r1 = client.post(
            f"/api/v1/final-review/daily-items/{item_id}/complete",
            json={}, headers=headers,
        )
        r2 = client.post(
            f"/api/v1/final-review/daily-items/{item_id}/complete",
            json={}, headers=headers,
        )
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_complete_nonexistent_item(self):
        container, client = _setup()
        headers = _login(client)
        resp = client.post(
            "/api/v1/final-review/daily-items/nonexistent/complete",
            json={}, headers=headers,
        )
        assert resp.status_code == 404

    def test_daily_checkin(self):
        container, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_active_campaign(container, client, headers, [exam_id])
        agenda = client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers,
        ).json()
        items = agenda["items"]
        resp = client.post(
            f"/api/v1/final-review/campaigns/{cid}/daily-checkins",
            json={
                "report_date": agenda["agenda_date"],
                "completed_item_ids": [it["item_id"] for it in items],
                "insufficient_time": False,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["recorded"] is True

    def test_daily_checkin_with_insufficient_time(self):
        container, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_active_campaign(container, client, headers, [exam_id])
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        resp = client.post(
            f"/api/v1/final-review/campaigns/{cid}/daily-checkins",
            json={
                "report_date": today,
                "completed_item_ids": [],
                "insufficient_time": True,
                "difficulty_notes": "时间不够",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["evidence_count"] >= 1

    def test_cross_user_agenda_denied(self):
        container, client = _setup()
        headers1 = _login(client, "student_demo")
        exam_id = _create_exam(client, headers1)
        cid = _create_active_campaign(container, client, headers1, [exam_id])
        headers2 = _login(client, "student_demo_01")
        resp = client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers2,
        )
        assert resp.status_code == 404
