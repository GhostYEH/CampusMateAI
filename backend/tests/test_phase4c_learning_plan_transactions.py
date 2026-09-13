from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from test_phase4_learning_plans import _request, _setup


def _accepted_plan():
    client, container, headers, _ = _setup()
    user_id = container.user_repository.get_user_by_username("phase4_student").id
    course = container.course_repository.create_course(name="Atomic C", owner_user_id=user_id)
    container.personal_task_repository.create_task(
        user_id=user_id, title="测试任务", source="test", external_id="t1", course_id=course.id,
    )
    container.personal_task_repository.create_task(
        user_id=user_id, title="测试任务2", source="test", external_id="t2", course_id=course.id,
    )
    result = client.post("/api/v1/learning-plans/generate", json=_request(60, course_id=course.id), headers=headers)
    assert result.status_code == 200, result.text
    plan = result.json()
    assert len(plan["items"]) >= 2
    assert client.post(f"/api/v1/learning-plans/{plan['plan_id']}/decision", json={"decision": "ACCEPT"}, headers=headers).status_code == 200
    return client, container, headers, plan["plan_id"], user_id


def test_second_task_failure_rolls_back_all_execute_writes(monkeypatch) -> None:
    client, container, headers, plan_id, user_id = _accepted_plan()
    original = container.personal_task_repository.create_task
    calls = 0

    def fail_second(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected")
        return original(**kwargs)

    monkeypatch.setattr(container.personal_task_repository, "create_task", fail_second)
    response = client.post(f"/api/v1/learning-plans/{plan_id}/execute", headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "LEARNING_PLAN_EXECUTION_FAILED"
    assert container.learning_plan_repository.list_actions(plan_id=plan_id, user_id=user_id) == []
    rows, _ = container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert not any(row.source == "learning_plan" for row in rows)


def test_action_write_failure_does_not_create_a_task(monkeypatch) -> None:
    client, container, headers, plan_id, user_id = _accepted_plan()
    monkeypatch.setattr(container.learning_plan_repository, "create_action", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("injected")))
    response = client.post(f"/api/v1/learning-plans/{plan_id}/execute", headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "LEARNING_PLAN_EXECUTION_FAILED"
    rows, _ = container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert not any(row.source == "learning_plan" for row in rows)


def test_concurrent_execute_creates_one_set_of_actions_and_tasks() -> None:
    client, container, headers, plan_id, user_id = _accepted_plan()

    def execute_once():
        return client.post(f"/api/v1/learning-plans/{plan_id}/execute", headers=headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: execute_once(), range(2)))
    assert all(response.status_code == 200 for response in responses)
    actions = container.learning_plan_repository.list_actions(plan_id=plan_id, user_id=user_id)
    rows, _ = container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    created = [row for row in rows if row.source == "learning_plan"]
    assert len(actions) == len(created)
    assert len({row.external_id for row in created}) == len(created)


def test_undo_conflict_is_recorded_without_overwriting_manual_task_change() -> None:
    client, container, headers, plan_id, user_id = _accepted_plan()
    assert client.post(f"/api/v1/learning-plans/{plan_id}/execute", headers=headers).status_code == 200
    rows, _ = container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    generated = next(row for row in rows if row.source == "learning_plan")
    container.personal_task_repository.update_task(generated.id, user_id=user_id, fields={"title": "用户后来修改"})
    response = client.post(f"/api/v1/learning-plans/{plan_id}/undo", headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "LEARNING_PLAN_UNDO_CONFLICT"
    current = container.personal_task_repository.get_task(generated.id, user_id=user_id)
    assert current is not None and current.status == "pending" and current.title == "用户后来修改"
