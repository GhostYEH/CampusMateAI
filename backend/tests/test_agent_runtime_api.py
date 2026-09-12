"""Agent runtime API 测试。"""
from __future__ import annotations

import pytest
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


class TestCapabilities:
    def test_requires_auth(self):
        _, client = _client()
        assert client.get("/api/v1/agent-runtime/capabilities").status_code == 401

    def test_returns_contract_version(self):
        _, client = _client()
        headers = _login(client)
        resp = client.get("/api/v1/agent-runtime/capabilities", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["contract_version"] == "v1"
        assert len(body["capabilities"]) > 0

    def test_capability_has_no_credentials(self):
        _, client = _client()
        headers = _login(client)
        resp = client.get("/api/v1/agent-runtime/capabilities", headers=headers)
        for cap in resp.json()["capabilities"]:
            assert "api_key" not in cap
            assert "endpoint" not in cap


class TestJobs:
    def test_create_job(self):
        _, client = _client()
        headers = _login(client)
        resp = client.post(
            "/api/v1/agent-jobs",
            json={"job_kind": "final_review"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["job_kind"] == "final_review"
        assert body["status"] == "QUEUED"

    def test_create_job_idempotency_key(self):
        _, client = _client()
        headers = _login(client)
        # 第一次创建
        resp1 = client.post(
            "/api/v1/agent-jobs",
            json={"job_kind": "final_review"},
            headers={**headers, "Idempotency-Key": "k1"},
        )
        assert resp1.status_code == 200
        # 相同 idempotency_key 返回已有 job
        resp2 = client.post(
            "/api/v1/agent-jobs",
            json={"job_kind": "final_review"},
            headers={**headers, "Idempotency-Key": "k1"},
        )
        assert resp2.status_code == 200
        assert resp1.json()["job_id"] == resp2.json()["job_id"]

    def test_get_job(self):
        _, client = _client()
        headers = _login(client)
        create = client.post(
            "/api/v1/agent-jobs", json={"job_kind": "course_research"}, headers=headers
        )
        job_id = create.json()["job_id"]
        resp = client.get(f"/api/v1/agent-jobs/{job_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["job_id"] == job_id

    def test_get_nonexistent_job(self):
        _, client = _client()
        headers = _login(client)
        resp = client.get("/api/v1/agent-jobs/nonexistent", headers=headers)
        assert resp.status_code == 404
        assert resp.json()["code"] == "AGENT_RUN_NOT_FOUND"

    def test_error_envelope_has_request_id(self):
        _, client = _client()
        headers = _login(client)
        resp = client.get("/api/v1/agent-jobs/nonexistent", headers=headers)
        body = resp.json()
        assert "request_id" in body
        assert body["request_id"]


class TestRuns:
    def test_get_run_not_found(self):
        _, client = _client()
        headers = _login(client)
        resp = client.get("/api/v1/agent-runs/nonexistent", headers=headers)
        assert resp.status_code == 404

    def test_cancel_nonexistent_run(self):
        _, client = _client()
        headers = _login(client)
        resp = client.post(
            "/api/v1/agent-runs/nonexistent/cancel",
            json={},
            headers=headers,
        )
        assert resp.status_code == 404


class TestEvents:
    def test_list_events_not_found(self):
        _, client = _client()
        headers = _login(client)
        resp = client.get("/api/v1/agent-runs/nonexistent/events", headers=headers)
        assert resp.status_code == 404


class TestApprovals:
    def test_resolve_nonexistent_approval(self):
        _, client = _client()
        headers = _login(client)
        resp = client.post(
            "/api/v1/agent-approvals/nonexistent/decision",
            json={"decision": "APPROVED"},
            headers=headers,
        )
        assert resp.status_code == 404


class TestArtifacts:
    def test_get_nonexistent_artifact(self):
        _, client = _client()
        headers = _login(client)
        resp = client.get("/api/v1/agent-artifacts/nonexistent", headers=headers)
        assert resp.status_code == 404


class TestNoticesManual:
    def test_create_manual_notice(self):
        _, client = _client()
        headers = _login(client)
        resp = client.post(
            "/api/v1/notices/manual",
            json={"title": "测试通知", "content": "请在周五前提交作业"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "QUEUED"
        assert body["job_id"]

    def test_manual_notice_idempotency(self):
        _, client = _client()
        headers = _login(client)
        resp1 = client.post(
            "/api/v1/notices/manual",
            json={"title": "测试", "content": "内容"},
            headers={**headers, "Idempotency-Key": "n1"},
        )
        resp2 = client.post(
            "/api/v1/notices/manual",
            json={"title": "测试", "content": "内容"},
            headers={**headers, "Idempotency-Key": "n1"},
        )
        assert resp1.json()["job_id"] == resp2.json()["job_id"]