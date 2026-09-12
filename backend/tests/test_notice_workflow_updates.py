"""通知工作流重新分析、跨用户隔离与敏感字段脱敏测试(§8.3、§11)。"""
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


def _make_notice_and_workflow(client, headers, title, content):
    notice = client.post(
        "/api/v1/notices/manual",
        json={"title": title, "content": content},
        headers=headers,
    ).json()
    wf = client.post(
        f"/api/v1/notices/{notice['notice_id']}/workflow",
        json={},
        headers=headers,
    ).json()
    return wf


class TestReanalyze:
    def test_reanalyze_workflow(self):
        _, client = _client()
        headers = _login(client)
        wf = _make_notice_and_workflow(
            client,
            headers,
            "奖学金",
            "请于2026年10月15日前提交申请表至教务处",
        )
        resp = client.post(
            f"/api/v1/notice-workflows/{wf['workflow_id']}/reanalyze",
            json={},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["workflow_id"] == wf["workflow_id"]

    def test_reanalyze_nonexistent(self):
        _, client = _client()
        headers = _login(client)
        resp = client.post(
            "/api/v1/notice-workflows/nwf_nonexistent/reanalyze",
            json={},
            headers=headers,
        )
        assert resp.status_code == 404


class TestCrossUserIsolation:
    def test_other_user_cannot_read_workflow(self):
        _, client = _client()
        h1 = _login(client, "student_demo")
        wf = _make_notice_and_workflow(
            client,
            h1,
            "私密通知",
            "请于2026年10月15日前提交申请表至教务处",
        )
        # student_demo_01 登录
        h2 = _login(client, "student_demo_01")
        resp = client.get(
            f"/api/v1/notice-workflows/{wf['workflow_id']}", headers=h2
        )
        assert resp.status_code == 404

    def test_other_user_cannot_decide_action(self):
        _, client = _client()
        h1 = _login(client, "student_demo")
        wf = _make_notice_and_workflow(
            client,
            h1,
            "私密通知",
            "请于2026年10月15日前提交申请表至教务处",
        )
        action = wf["actions"][0]
        h2 = _login(client, "student_demo_01")
        resp = client.post(
            f"/api/v1/notice-workflow-actions/{action['action_id']}/decision",
            json={"decision": "APPROVED"},
            headers=h2,
        )
        assert resp.status_code == 404

    def test_other_user_cannot_access_manual_notice(self):
        # manual notice 通过 user_id 隔离;另一用户创建同名 notice 得到不同 id
        _, client = _client()
        h1 = _login(client, "student_demo")
        h2 = _login(client, "student_demo_01")
        content = "请于2026年10月15日前提交申请表至教务处"
        n1 = client.post(
            "/api/v1/notices/manual",
            json={"title": "通知", "content": content},
            headers=h1,
        ).json()
        n2 = client.post(
            "/api/v1/notices/manual",
            json={"title": "通知", "content": content},
            headers=h2,
        ).json()
        assert n1["notice_id"] != n2["notice_id"]


class TestSensitiveFieldRedaction:
    def test_workflow_response_has_no_raw_content(self):
        _, client = _client()
        headers = _login(client)
        secret_content = "请于2026年10月15日前提交申请表至教务处,密码123456"
        wf = _make_notice_and_workflow(
            client, headers, "通知", secret_content
        )
        # WorkflowOut 不含 content 字段
        assert "content" not in wf
        # 不含原始敏感内容
        import json

        body_str = json.dumps(wf, ensure_ascii=False)
        assert "123456" not in body_str

    def test_action_params_not_leaked_in_response(self):
        _, client = _client()
        headers = _login(client)
        wf = _make_notice_and_workflow(
            client,
            headers,
            "奖学金",
            "请于2026年10月15日前提交申请表至教务处",
        )
        # WorkflowActionOut 不含 params_json
        for a in wf["actions"]:
            assert "params_json" not in a
            assert "params" not in a

    def test_source_evidence_no_credentials(self):
        _, client = _client()
        headers = _login(client)
        wf = _make_notice_and_workflow(
            client,
            headers,
            "通知",
            "请于2026年10月15日前提交申请表至教务处",
        )
        for ev in wf["source_evidence"]:
            assert "api_key" not in ev
            assert "token" not in ev.lower()


class TestWorkflowCompletion:
    def test_workflow_completes_after_all_actions_resolved(self):
        _, client = _client()
        headers = _login(client)
        wf = _make_notice_and_workflow(
            client,
            headers,
            "奖学金",
            "请于2026年10月15日前提交申请表至教务处",
        )
        # 对所有 action 执行决策
        for a in wf["actions"]:
            client.post(
                f"/api/v1/notice-workflow-actions/{a['action_id']}/decision",
                json={"decision": "APPROVED"},
                headers=headers,
            )
        # 查询最终状态
        resp = client.get(
            f"/api/v1/notice-workflows/{wf['workflow_id']}", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "COMPLETED"