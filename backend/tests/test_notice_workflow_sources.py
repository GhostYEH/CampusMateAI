from notice_workflow_helpers import setup_student


def test_manual_notice_returns_authoritative_id_and_deduplicates():
    _container, client, _user, headers = setup_student()
    payload = {"content": "请于2026-10-20前提交课程报告", "title": "课程报告"}
    first = client.post("/api/v1/notices/manual", headers=headers, json=payload)
    second = client.post("/api/v1/notices/manual", headers=headers, json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["notice_id"] == second.json()["notice_id"]
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True
    assert second.json()["source_code"] == "manual_input"


def test_source_automation_is_off_by_default_and_user_isolated():
    container, client, user, headers = setup_student()
    assert container.notice_workflow_repository.automation_enabled(user.id, "manual_input") is False
    enabled = client.put("/api/v1/notice-sources/manual_input/automation", headers=headers, json={"enabled": True})
    assert enabled.status_code == 200
    other = container.user_repository.create_user(username="other_student", password_hash="x", role="student", display_name="Other")
    assert container.notice_workflow_repository.automation_enabled(user.id, "manual_input") is True
    assert container.notice_workflow_repository.automation_enabled(other.id, "manual_input") is False
