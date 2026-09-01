from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client() -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app())


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_analyze_task_material_turns_checklist_into_editable_drafts() -> None:
    client = _client()
    response = client.post(
        "/api/v1/tasks/import/analyze",
        headers=_headers(client),
        json={
            "content": "# 本周计划\n- [ ] 阅读第三章\n- [x] 整理实验数据\n3. 完成课程报告",
            "source_name": "数据结构复习计划",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "structured_text"
    assert [item["title"] for item in body["tasks"]] == [
        "阅读第三章",
        "整理实验数据",
        "完成课程报告",
    ]
    assert all(item["selected"] for item in body["tasks"])
    assert all(item["source_name"] == "数据结构复习计划" for item in body["tasks"])


def test_analyze_marks_existing_title_without_overwriting_progress() -> None:
    client = _client()
    headers = _headers(client)
    created = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={"title": "阅读第三章"},
    )
    assert created.status_code == 201
    completed = client.post(
        f"/api/v1/tasks/{created.json()['id']}/complete", headers=headers
    )
    assert completed.status_code == 200

    analyzed = client.post(
        "/api/v1/tasks/import/analyze",
        headers=headers,
        json={"content": "- 阅读第三章\n- 完成课程报告"},
    )

    assert analyzed.status_code == 200
    duplicate = analyzed.json()["tasks"][0]
    assert duplicate["existing_task_id"] == created.json()["id"]
    assert duplicate["existing_status"] == "completed"
    assert duplicate["selected"] is False


def test_commit_import_creates_selected_tasks_and_skips_existing_titles() -> None:
    client = _client()
    headers = _headers(client)
    existing = client.post(
        "/api/v1/tasks", headers=headers, json={"title": "阅读第三章"}
    )
    assert existing.status_code == 201

    committed = client.post(
        "/api/v1/tasks/import/commit",
        headers=headers,
        json={
            "tasks": [
                {"title": "阅读第三章", "source_text": "课程计划"},
                {
                    "title": "完成课程报告",
                    "description": "先完成初稿，再校对引用。",
                    "priority": "high",
                    "source_name": "课程计划",
                    "source_text": "课程计划",
                },
            ]
        },
    )

    assert committed.status_code == 201
    body = committed.json()
    assert [item["title"] for item in body["created"]] == ["完成课程报告"]
    assert body["skipped_existing"][0]["task_id"] == existing.json()["id"]
    assert body["skipped_existing"][0]["status"] == "pending"


def test_commit_import_accepts_source_text_returned_by_analyze() -> None:
    client = _client()
    headers = _headers(client)
    content = f"{'课程背景' * 2500}\n- 阅读第三章\n- 完成课程报告"

    analyzed = client.post(
        "/api/v1/tasks/import/analyze",
        headers=headers,
        json={"content": content, "source_name": "长篇课程计划"},
    )

    assert analyzed.status_code == 200
    draft = analyzed.json()["tasks"][0]
    committed = client.post(
        "/api/v1/tasks/import/commit",
        headers=headers,
        json={
            "tasks": [
                {
                    "title": draft["title"],
                    "source_name": draft["source_name"],
                    "source_text": draft["source_text"],
                    "priority": draft["priority"],
                }
            ]
        },
    )

    assert committed.status_code == 201
    assert committed.json()["created"][0]["source_text"] == content


def test_analyze_detects_existing_titles_beyond_first_task_page() -> None:
    client = _client()
    headers = _headers(client)
    existing = client.post(
        "/api/v1/tasks", headers=headers, json={"title": "较早的长期任务"}
    )
    assert existing.status_code == 201
    for index in range(200):
        created = client.post(
            "/api/v1/tasks", headers=headers, json={"title": f"新任务 {index:03d}"}
        )
        assert created.status_code == 201

    analyzed = client.post(
        "/api/v1/tasks/import/analyze",
        headers=headers,
        json={"content": "- 较早的长期任务\n- 新的课程报告"},
    )

    assert analyzed.status_code == 200
    duplicate = analyzed.json()["tasks"][0]
    assert duplicate["existing_task_id"] == existing.json()["id"]
    assert duplicate["selected"] is False


def test_analyze_limits_drafts_to_commit_capacity() -> None:
    client = _client()
    content = "\n".join(f"- 复习知识点 {index:02d}" for index in range(51))

    analyzed = client.post(
        "/api/v1/tasks/import/analyze",
        headers=_headers(client),
        json={"content": content},
    )

    assert analyzed.status_code == 200
    body = analyzed.json()
    assert len(body["tasks"]) == 50
    assert body["needs_user_confirmation"] is True
    assert "最多保留 50 项" in body["split_reason"]


def test_deleted_title_can_be_imported_again() -> None:
    client = _client()
    headers = _headers(client)
    deleted = client.post(
        "/api/v1/tasks", headers=headers, json={"title": "重新开始阅读计划"}
    )
    assert deleted.status_code == 201
    removed = client.delete(f"/api/v1/tasks/{deleted.json()['id']}", headers=headers)
    assert removed.status_code == 200

    analyzed = client.post(
        "/api/v1/tasks/import/analyze",
        headers=headers,
        json={"content": "- 重新开始阅读计划\n- 整理阅读笔记"},
    )

    assert analyzed.status_code == 200
    draft = analyzed.json()["tasks"][0]
    assert draft["existing_task_id"] is None
    assert draft["selected"] is True


def test_commit_reports_source_notice_conflict_as_skipped_not_created() -> None:
    client = _client()
    committed = client.post(
        "/api/v1/tasks/import/commit",
        headers=_headers(client),
        json={
            "tasks": [
                {"title": "阅读课程通知", "source_notice_id": "notice-shared"},
                {"title": "整理课程要求", "source_notice_id": "notice-shared"},
            ]
        },
    )

    assert committed.status_code == 201
    body = committed.json()
    assert [item["title"] for item in body["created"]] == ["阅读课程通知"]
    assert [item["title"] for item in body["skipped_existing"]] == ["阅读课程通知"]


def test_analyze_keeps_overlong_checklist_title_editable() -> None:
    client = _client()
    long_title = "复习" * 150

    analyzed = client.post(
        "/api/v1/tasks/import/analyze",
        headers=_headers(client),
        json={"content": f"- {long_title}\n- 完成课程报告"},
    )

    assert analyzed.status_code == 200
    draft = analyzed.json()["tasks"][0]
    assert len(draft["title"]) == 256
    assert draft["needs_confirmation"] is True
    assert "标题过长" in draft["warnings"]
    assert analyzed.json()["needs_user_confirmation"] is True
