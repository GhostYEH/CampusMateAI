"""期末复习 plan versions 测试。

覆盖:首版计划生成、plan 不可变、版本列表、激活、幂等。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes.final_review import router as final_review_router
from app.core.config import Settings
from app.main import create_app
from app.services.final_review.planner import _deterministic_plan
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


def _create_campaign(client, headers, exam_ids, capacity=120):
    resp = client.post(
        "/api/v1/final-review/campaigns",
        json={"exam_ids": exam_ids, "daily_capacity_minutes": capacity},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["campaign_id"]


class TestPlanGenerate:
    def test_deterministic_plan_caps_far_future_exam_horizon(self):
        plan = _deterministic_plan(
            exams=[{"id": "exam-future", "course_name": "高等数学", "exam_date": "2099-12-30"}],
            daily_capacity_minutes=120,
            intensity="medium",
            rest_days=[],
        )

        assert len(plan["days"]) <= 365
        assert plan["planning_horizon_days"] == 365
        assert plan["planning_horizon_truncated"] is True

    def test_generate_first_plan(self):
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_campaign(client, headers, [exam_id])
        resp = client.post(
            f"/api/v1/final-review/campaigns/{cid}/plans/generate",
            json={},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["version"] == 1
        assert "plan" in body
        assert body["risk_level"] == "CONFIRM_REQUIRED"
        assert body["requires_approval"] is True
        assert body["run_id"].startswith("run_")
        assert body["approval_id"].startswith("apv_")
        run = client.get(
            f"/api/v1/agent-runs/{body['run_id']}", headers=headers
        )
        assert run.status_code == 200, run.text
        assert len(run.json()["artifact_ids"]) == 1
        artifact = client.get(
            f"/api/v1/agent-artifacts/{run.json()['artifact_ids'][0]}",
            headers=headers,
        )
        assert artifact.status_code == 200, artifact.text
        assert artifact.json()["artifact_type"] == "FINAL_REVIEW_PLAN"

    def test_plan_cannot_activate_until_its_approval_is_resolved(self):
        container, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_campaign(client, headers, [exam_id])
        generated = client.post(
            f"/api/v1/final-review/campaigns/{cid}/plans/generate",
            json={}, headers=headers,
        ).json()

        blocked = client.post(
            f"/api/v1/final-review/campaigns/{cid}/activate",
            json={"version": 1}, headers=headers,
        )
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "AGENT_APPROVAL_REQUIRED"

        approved = client.post(
            f"/api/v1/agent-approvals/{generated['approval_id']}/decision",
            json={"decision": "APPROVED"}, headers=headers,
        )
        assert approved.status_code == 200, approved.text
        activated = client.post(
            f"/api/v1/final-review/campaigns/{cid}/activate",
            json={"version": 1}, headers=headers,
        )
        assert activated.status_code == 200, activated.text
        # 路由只创建命令:激活由 Worker 经 Gateway 完成。
        assert activated.json()["status"] == "PENDING"
        assert activated.json()["activated"] is False
        drain_worker(container)
        campaign = client.get(
            f"/api/v1/final-review/campaigns/{cid}", headers=headers
        ).json()
        assert campaign["active_version"] == 1

    def test_generate_plan_reuses_same_idempotency_key_and_rejects_conflict(self):
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_campaign(client, headers, [exam_id])
        headers = {**headers, "Idempotency-Key": "plan-generate-1"}

        first = client.post(
            f"/api/v1/final-review/campaigns/{cid}/plans/generate",
            json={}, headers=headers,
        )
        repeated = client.post(
            f"/api/v1/final-review/campaigns/{cid}/plans/generate",
            json={}, headers=headers,
        )
        assert repeated.status_code == 200
        assert repeated.json()["version"] == first.json()["version"]
        assert repeated.json()["run_id"] == first.json()["run_id"]

        conflict = client.post(
            f"/api/v1/final-review/campaigns/{cid}/plans/generate",
            json={"user_edits": {"daily_capacity_minutes": 30}}, headers=headers,
        )
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "AGENT_IDEMPOTENCY_CONFLICT"

    def test_generate_plan_has_days(self):
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_campaign(client, headers, [exam_id])
        resp = client.post(
            f"/api/v1/final-review/campaigns/{cid}/plans/generate",
            json={},
            headers=headers,
        )
        plan = resp.json()["plan"]
        assert "days" in plan
        assert isinstance(plan["days"], list)

    def test_list_plan_versions(self):
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_campaign(client, headers, [exam_id])
        client.post(
            f"/api/v1/final-review/campaigns/{cid}/plans/generate",
            json={}, headers=headers,
        )
        resp = client.get(
            f"/api/v1/final-review/campaigns/{cid}/plan-versions",
            headers=headers,
        )
        assert resp.status_code == 200
        versions = resp.json()
        assert len(versions) == 1
        assert versions[0]["version"] == 1

    def test_get_plan_version(self):
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_campaign(client, headers, [exam_id])
        client.post(
            f"/api/v1/final-review/campaigns/{cid}/plans/generate",
            json={}, headers=headers,
        )
        resp = client.get(
            f"/api/v1/final-review/campaigns/{cid}/plan-versions/1",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == 1

    def test_get_nonexistent_plan_version(self):
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_campaign(client, headers, [exam_id])
        resp = client.get(
            f"/api/v1/final-review/campaigns/{cid}/plan-versions/99",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_plan_version_immutable(self):
        """plan version 不可变:再次 generate 创建新版本而非覆盖。"""
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_campaign(client, headers, [exam_id])
        r1 = client.post(
            f"/api/v1/final-review/campaigns/{cid}/plans/generate",
            json={}, headers=headers,
        )
        r2 = client.post(
            f"/api/v1/final-review/campaigns/{cid}/plans/generate",
            json={}, headers=headers,
        )
        assert r1.json()["version"] == 1
        assert r2.json()["version"] == 2
        # v1 仍然可读且内容不变
        v1 = client.get(
            f"/api/v1/final-review/campaigns/{cid}/plan-versions/1",
            headers=headers,
        ).json()
        assert v1["version"] == 1

    def test_activate_campaign(self):
        container, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_campaign(client, headers, [exam_id])
        generated = client.post(
            f"/api/v1/final-review/campaigns/{cid}/plans/generate",
            json={}, headers=headers,
        ).json()
        client.post(
            f"/api/v1/agent-approvals/{generated['approval_id']}/decision",
            json={"decision": "APPROVED"}, headers=headers,
        )
        resp = client.post(
            f"/api/v1/final-review/campaigns/{cid}/activate",
            json={"version": 1}, headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["active_version"] == 1
        # 命令已受理但尚未执行:终态由 Worker 原子写入。
        assert resp.json()["activated"] is False
        assert resp.json()["run_id"].startswith("run_")

        drain_worker(container)

        campaign = client.get(
            f"/api/v1/final-review/campaigns/{cid}", headers=headers
        ).json()
        assert campaign["active_version"] == 1
        # 命令完成后重复调用是幂等的:不重复入队,直接返回已激活。
        again = client.post(
            f"/api/v1/final-review/campaigns/{cid}/activate",
            json={"version": 1}, headers=headers,
        )
        assert again.status_code == 200
        assert again.json()["activated"] is True
        assert again.json()["status"] == "ACTIVE"

    def test_activate_nonexistent_version(self):
        _, client = _setup()
        headers = _login(client)
        exam_id = _create_exam(client, headers)
        cid = _create_campaign(client, headers, [exam_id])
        resp = client.post(
            f"/api/v1/final-review/campaigns/{cid}/activate",
            json={"version": 99}, headers=headers,
        )
        assert resp.status_code == 404

    def test_generate_plan_nonexistent_campaign(self):
        _, client = _setup()
        headers = _login(client)
        resp = client.post(
            "/api/v1/final-review/campaigns/nonexistent/plans/generate",
            json={}, headers=headers,
        )
        assert resp.status_code == 404

    def test_cross_user_plan_access_denied(self):
        _, client = _setup()
        headers1 = _login(client, "student_demo")
        exam_id = _create_exam(client, headers1)
        cid = _create_campaign(client, headers1, [exam_id])
        client.post(
            f"/api/v1/final-review/campaigns/{cid}/plans/generate",
            json={}, headers=headers1,
        )
        headers2 = _login(client, "student_demo_01")
        resp = client.get(
            f"/api/v1/final-review/campaigns/{cid}/plan-versions",
            headers=headers2,
        )
        # 跨用户看不到对方的 plan versions
        assert resp.status_code == 200
        assert len(resp.json()) == 0
