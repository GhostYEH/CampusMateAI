"""通知工作流动作状态机与风险分级测试(§5.5、§7.3、§8.3)。"""
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


def _find_action(wf, action_type):
    for a in wf["actions"]:
        if a["action_type"] == action_type:
            return a
    return None


class TestRiskClassification:
    def test_auto_safe_notice_creates_auto_actions(self):
        _, client = _client()
        headers = _login(client)
        wf = _make_notice_and_workflow(
            client,
            headers,
            "奖学金申请",
            "请于2026年10月15日前提交申请表至教务处",
        )
        types = {a["action_type"] for a in wf["actions"]}
        assert "create_task" in types
        assert "generate_checklist" in types
        assert "add_reminder" in types
        for a in wf["actions"]:
            assert a["risk_level"] == "AUTO_SAFE"

    def test_manual_only_notice_creates_manual_action(self):
        _, client = _client()
        headers = _login(client)
        wf = _make_notice_and_workflow(
            client,
            headers,
            "缴费通知",
            "请于2026年10月15日前完成缴费付款,逾期不予受理",
        )
        manual = _find_action(wf, "external_submit")
        assert manual is not None
        assert manual["risk_level"] == "MANUAL_ONLY"

    def test_confirm_required_notice_creates_confirm_action(self):
        _, client = _client()
        headers = _login(client)
        wf = _make_notice_and_workflow(
            client,
            headers,
            "班委通知",
            "请各位回复班长确认参加班会,于2026年10月15日前回复",
        )
        confirm = _find_action(wf, "prepare_message")
        assert confirm is not None
        assert confirm["risk_level"] == "CONFIRM_REQUIRED"


class TestActionStateTransitions:
    def test_approve_auto_safe_executes(self):
        _, client = _client()
        headers = _login(client)
        wf = _make_notice_and_workflow(
            client,
            headers,
            "奖学金",
            "请于2026年10月15日前提交申请表至教务处",
        )
        task_action = _find_action(wf, "create_task")
        resp = client.post(
            f"/api/v1/notice-workflow-actions/{task_action['action_id']}/decision",
            json={"decision": "APPROVED"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "DONE"
        assert resp.json()["external_ref"]

    def test_reject_action(self):
        _, client = _client()
        headers = _login(client)
        wf = _make_notice_and_workflow(
            client,
            headers,
            "奖学金",
            "请于2026年10月15日前提交申请表至教务处",
        )
        action = _find_action(wf, "generate_checklist")
        resp = client.post(
            f"/api/v1/notice-workflow-actions/{action['action_id']}/decision",
            json={"decision": "REJECTED"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "REJECTED"

    def test_manual_only_execute_fails_not_executable(self):
        _, client = _client()
        headers = _login(client)
        wf = _make_notice_and_workflow(
            client,
            headers,
            "缴费",
            "请于2026年10月15日前完成缴费付款",
        )
        manual = _find_action(wf, "external_submit")
        resp = client.post(
            f"/api/v1/notice-workflow-actions/{manual['action_id']}/execute",
            json={},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "FAILED"
        assert body["error_code"] == "MANUAL_ONLY_NOT_EXECUTABLE"
        # 绝不声称已办理
        assert body.get("result") is None or not body["result"].get("done")

    def test_confirm_required_requires_approval_before_execute(self):
        _, client = _client()
        headers = _login(client)
        wf = _make_notice_and_workflow(
            client,
            headers,
            "班委通知",
            "请各位回复班长确认参加班会,于2026年10月15日前回复",
        )
        confirm = _find_action(wf, "prepare_message")
        # 未批准直接执行 → 冲突
        resp = client.post(
            f"/api/v1/notice-workflow-actions/{confirm['action_id']}/execute",
            json={},
            headers=headers,
        )
        assert resp.status_code == 409
        # 批准后执行
        resp_dec = client.post(
            f"/api/v1/notice-workflow-actions/{confirm['action_id']}/decision",
            json={"decision": "APPROVED"},
            headers=headers,
        )
        assert resp_dec.status_code == 200
        assert resp_dec.json()["status"] == "APPROVED"
        resp_exec = client.post(
            f"/api/v1/notice-workflow-actions/{confirm['action_id']}/execute",
            json={},
            headers=headers,
        )
        assert resp_exec.status_code == 200
        assert resp_exec.json()["status"] == "DONE"

    def test_invalid_transition_rejected_to_approved(self):
        _, client = _client()
        headers = _login(client)
        wf = _make_notice_and_workflow(
            client,
            headers,
            "奖学金",
            "请于2026年10月15日前提交申请表至教务处",
        )
        action = _find_action(wf, "create_task")
        client.post(
            f"/api/v1/notice-workflow-actions/{action['action_id']}/decision",
            json={"decision": "REJECTED"},
            headers=headers,
        )
        resp = client.post(
            f"/api/v1/notice-workflow-actions/{action['action_id']}/decision",
            json={"decision": "APPROVED"},
            headers=headers,
        )
        assert resp.status_code == 409


class TestAutomationDefaultOff:
    def test_auto_safe_not_executed_when_automation_disabled(self):
        _, client = _client()
        headers = _login(client)
        wf = _make_notice_and_workflow(
            client,
            headers,
            "奖学金",
            "请于2026年10月15日前提交申请表至教务处",
        )
        # 自动化默认关闭 → 所有 AUTO_SAFE action 保持 PROPOSED
        for a in wf["actions"]:
            assert a["status"] == "PROPOSED"
        # workflow 处于 WAITING_CONFIRMATION(等待用户手动操作)
        assert wf["status"] == "WAITING_CONFIRMATION"

    def test_auto_safe_executed_when_automation_enabled(self):
        container, client = _client()
        headers = _login(client)
        # 启用 manual_input 自动化
        sources = client.get(
            "/api/v1/notification-sources", headers=headers
        ).json()
        manual = next(s for s in sources if s["code"] == "manual_input")
        client.patch(
            f"/api/v1/notification-sources/{manual['source_id']}",
            json={"automation_enabled": True},
            headers=headers,
        )
        wf = _make_notice_and_workflow(
            client,
            headers,
            "奖学金",
            "请于2026年10月15日前提交申请表至教务处",
        )
        # 自动化开启 → AUTO_SAFE action 自动执行
        task_action = _find_action(wf, "create_task")
        assert task_action["status"] == "DONE"


class TestNoOfficialInterface:
    def test_manual_only_does_not_claim_done(self):
        _, client = _client()
        headers = _login(client)
        wf = _make_notice_and_workflow(
            client,
            headers,
            "作业提交",
            "请于2026年10月15日前提交作业上传作业至系统",
        )
        manual = _find_action(wf, "external_submit")
        assert manual["risk_level"] == "MANUAL_ONLY"
        # 执行后绝不声称已办理
        resp = client.post(
            f"/api/v1/notice-workflow-actions/{manual['action_id']}/execute",
            json={},
            headers=headers,
        )
        body = resp.json()
        assert body["status"] == "FAILED"
        assert not (body.get("result") or {}).get("done")
        assert not (body.get("result") or {}).get("submitted")

    def test_steps_generated_for_manual_only(self):
        _, client = _client()
        headers = _login(client)
        wf = _make_notice_and_workflow(
            client,
            headers,
            "缴费",
            "请于2026年10月15日前完成缴费付款",
        )
        # 仍生成步骤指导
        assert len(wf["steps"]) >= 1