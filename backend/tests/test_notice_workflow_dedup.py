from notice_workflow_helpers import create_workflow, setup_student


def test_analyze_and_execute_retries_do_not_duplicate_workflow_or_task():
    container, client, user, headers = setup_student()
    notice, workflow = create_workflow(client, headers)
    replay = client.post(f"/api/v1/notices/{notice['notice_id']}/workflow", headers=headers).json()
    assert replay["workflow_id"] == workflow["workflow_id"]
    assert client.post(f"/api/v1/notice-workflows/{workflow['workflow_id']}/confirm", headers=headers, json={"approved": True}).status_code == 200
    endpoint = f"/api/v1/notice-workflows/{workflow['workflow_id']}/execute"
    first = client.post(endpoint, headers=headers, json={"idempotency_key": "create-task-1"})
    second = client.post(endpoint, headers=headers, json={"idempotency_key": "create-task-1"})
    assert first.status_code == second.status_code == 200
    assert first.json()["actions"][0]["task_id"] == second.json()["actions"][0]["task_id"]
    tasks, total = container.personal_task_repository.list_tasks(user.id)
    assert total == 1
