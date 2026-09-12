"""期末复习 adjustment proposals 测试。

覆盖:evidence 后产生 proposal、审批后生成 v2 且 v1 保留、
拒绝后不改计划、provider fallback、partial result。
"""
from __future__ import annotations

import pytest
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


def _create_active_campaign(client, headers, exam_ids, capacity=120):
    cid = client.post(
        "/api/v1/final-review/campaigns",
        json={"exam_ids": exam_ids, "daily_capacity_minutes": capacity},
        headers=headers,
    ).json()["campaign_id"]
    client.post(
        f"/api/v1/final-review/campaigns/{cid}/plans/generate",
        json={}, headers=headers,
    )
    client.post(
        f"/api/v1/final-review/campaigns/{cid}/activate",
        json={"version": 1}, headers=headers,
    )
    return cid


class TestAdjustmentAnalyze:
    def test_analyze_produces_proposal_not_direct_change(self):
        """Analyzer 只产生 proposal,不直接改 active version。"""
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_active_campaign(client, headers, [exam_id])
        # 获取今日议程(不完成任何 item → 产生 missed evidence)
        client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers,
        )
        resp = client.post(
            f"/api/v1/final-review/campaigns/{cid}/adjustments/analyze",
            json={}, headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["proposal_id"]
        # active version 仍然是 1(proposal 不直接改 plan)
        campaign = client.get(
            f"/api/v1/final-review/campaigns/{cid}", headers=headers
        ).json()
        assert campaign["active_version"] == 1

    def test_analyze_creates_proposal_record(self):
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_active_campaign(client, headers, [exam_id])
        client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers,
        )
        client.post(
            f"/api/v1/final-review/campaigns/{cid}/adjustments/analyze",
            json={}, headers=headers,
        )
        resp = client.get(
            f"/api/v1/final-review/campaigns/{cid}/adjustment-proposals",
            headers=headers,
        )
        assert resp.status_code == 200
        proposals = resp.json()
        assert len(proposals) >= 1
        assert proposals[0]["status"] == "pending"

    def test_analyze_requires_active_campaign(self):
        _, client = _setup()
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
        resp = client.post(
            f"/api/v1/final-review/campaigns/{cid}/adjustments/analyze",
            json={}, headers=headers,
        )
        assert resp.status_code == 409


class TestAdjustmentDecision:
    def test_approve_creates_v2_and_retains_v1(self):
        """审批通过后创建 v2,v1 保留可读。"""
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_active_campaign(client, headers, [exam_id])
        client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers,
        )
        analyze = client.post(
            f"/api/v1/final-review/campaigns/{cid}/adjustments/analyze",
            json={}, headers=headers,
        ).json()
        proposal_id = analyze["proposal_id"]
        resp = client.post(
            f"/api/v1/final-review/adjustment-proposals/{proposal_id}/decision",
            json={"decision": "APPROVED"}, headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "approved"
        assert body["new_version"] == 2
        assert body["active_version"] == 2
        # v1 保留可读
        v1 = client.get(
            f"/api/v1/final-review/campaigns/{cid}/plan-versions/1",
            headers=headers,
        )
        assert v1.status_code == 200
        assert v1.json()["version"] == 1
        # v2 存在
        v2 = client.get(
            f"/api/v1/final-review/campaigns/{cid}/plan-versions/2",
            headers=headers,
        )
        assert v2.status_code == 200
        assert v2.json()["supersedes_version"] == 1

    def test_reject_does_not_change_plan(self):
        """拒绝后不改计划,active version 不变。"""
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_active_campaign(client, headers, [exam_id])
        client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers,
        )
        analyze = client.post(
            f"/api/v1/final-review/campaigns/{cid}/adjustments/analyze",
            json={}, headers=headers,
        ).json()
        proposal_id = analyze["proposal_id"]
        resp = client.post(
            f"/api/v1/final-review/adjustment-proposals/{proposal_id}/decision",
            json={"decision": "REJECTED"}, headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "rejected"
        assert body["new_version"] is None
        # active version 仍然是 1
        campaign = client.get(
            f"/api/v1/final-review/campaigns/{cid}", headers=headers
        ).json()
        assert campaign["active_version"] == 1

    def test_decision_on_nonexistent_proposal(self):
        _, client = _setup()
        headers = _login(client)
        resp = client.post(
            "/api/v1/final-review/adjustment-proposals/nonexistent/decision",
            json={"decision": "APPROVED"}, headers=headers,
        )
        assert resp.status_code == 404

    def test_double_decision_idempotent(self):
        """重复审批同一 proposal 不创建多个版本。"""
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_active_campaign(client, headers, [exam_id])
        client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers,
        )
        analyze = client.post(
            f"/api/v1/final-review/campaigns/{cid}/adjustments/analyze",
            json={}, headers=headers,
        ).json()
        proposal_id = analyze["proposal_id"]
        r1 = client.post(
            f"/api/v1/final-review/adjustment-proposals/{proposal_id}/decision",
            json={"decision": "APPROVED"}, headers=headers,
        )
        r2 = client.post(
            f"/api/v1/final-review/adjustment-proposals/{proposal_id}/decision",
            json={"decision": "APPROVED"}, headers=headers,
        )
        assert r1.status_code == 200
        # 第二次决策:proposal 已非 pending,返回已有状态
        assert r2.status_code == 200
        assert r2.json()["new_version"] == r1.json()["new_version"]

    def test_cross_user_proposal_denied(self):
        _, client = _setup()
        headers1 = _login(client, "student_demo")
        exam_id = _create_exam(client, headers1)
        cid = _create_active_campaign(client, headers1, [exam_id])
        client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers1,
        )
        analyze = client.post(
            f"/api/v1/final-review/campaigns/{cid}/adjustments/analyze",
            json={}, headers=headers1,
        ).json()
        proposal_id = analyze["proposal_id"]
        headers2 = _login(client, "student_demo_01")
        resp = client.post(
            f"/api/v1/final-review/adjustment-proposals/{proposal_id}/decision",
            json={"decision": "APPROVED"}, headers=headers2,
        )
        assert resp.status_code == 404


class TestProviderFallback:
    def test_plan_generation_falls_back_to_deterministic(self):
        """无可用 provider 时,planner 降级到确定性规则。"""
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = client.post(
            "/api/v1/final-review/campaigns",
            json={"exam_ids": [exam_id], "daily_capacity_minutes": 120},
            headers=headers,
        ).json()["campaign_id"]
        resp = client.post(
            f"/api/v1/final-review/campaigns/{cid}/plans/generate",
            json={}, headers=headers,
        )
        assert resp.status_code == 200
        plan = resp.json()["plan"]
        # 确定性降级计划有 strategy 字段
        assert "strategy" in plan or "days" in plan

    def test_adjustment_falls_back_to_rules(self):
        """无可用 provider 时,analyzer 降级到规则分析。"""
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_active_campaign(client, headers, [exam_id])
        client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers,
        )
        resp = client.post(
            f"/api/v1/final-review/campaigns/{cid}/adjustments/analyze",
            json={}, headers=headers,
        )
        assert resp.status_code == 200
        # proposal 应存在(规则降级)
        proposals = client.get(
            f"/api/v1/final-review/campaigns/{cid}/adjustment-proposals",
            headers=headers,
        ).json()
        assert len(proposals) >= 1


class TestPartialResult:
    def test_agenda_with_no_items_for_today(self):
        """今日无计划项时,agenda 为空但不报错(partial result)。"""
        _, client = _setup()
        headers = _login(client)
        # 创建一个考试,日期很远
        exam_id = _create_exam(client, headers, exam_date="2099-12-30")
        cid = _create_active_campaign(client, headers, [exam_id])
        resp = client.get(
            f"/api/v1/final-review/campaigns/{cid}/agendas/today",
            headers=headers,
        )
        assert resp.status_code == 200
        # items 可能为空(今日无计划)
        assert "items" in resp.json()

    def test_analyze_with_no_evidence(self):
        """无 evidence 时,analyzer 仍产生 proposal(no_change)。"""
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_active_campaign(client, headers, [exam_id])
        # 不获取 agenda(无 evidence)
        resp = client.post(
            f"/api/v1/final-review/campaigns/{cid}/adjustments/analyze",
            json={}, headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["proposal_id"]