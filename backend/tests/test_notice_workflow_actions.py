from notice_workflow_helpers import create_workflow, setup_student


def test_confirm_required_cannot_execute_before_confirmation():
    _container, client, _user, headers = setup_student()
    _notice, workflow = create_workflow(client, headers)
    response = client.post(f"/api/v1/notice-workflows/{workflow['workflow_id']}/execute", headers=headers, json={"idempotency_key": "early"})
    assert response.status_code == 409
    assert response.json()["code"] == "AGENT_APPROVAL_REQUIRED"


def test_manual_only_never_executes_even_after_approval_attempt():
    container, client, user, headers = setup_student()
    _notice, workflow = create_workflow(client, headers, "请立即转账缴费并提交身份证")
    assert workflow["action_risk"] == "MANUAL_ONLY"
    confirmed = client.post(f"/api/v1/notice-workflows/{workflow['workflow_id']}/confirm", headers=headers, json={"approved": True})
    assert confirmed.json()["status"] == "WAITING_CONFIRMATION"
    response = client.post(f"/api/v1/notice-workflows/{workflow['workflow_id']}/execute", headers=headers, json={"idempotency_key": "forbidden"})
    assert response.status_code == 409
    assert response.json()["code"] == "AGENT_ACTION_MANUAL_ONLY"
    assert container.personal_task_repository.list_tasks(user.id)[1] == 0
