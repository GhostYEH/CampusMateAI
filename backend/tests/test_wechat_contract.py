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
        llm_provider="none",
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app())


def _login(client: TestClient) -> tuple[dict, dict[str, str]]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert response.status_code == 200
    payload = response.json()
    return payload, {"Authorization": f"Bearer {payload['access_token']}"}


def test_wechat_auth_contract_exposes_tokens_and_student_profile() -> None:
    with _client() as client:
        payload, headers = _login(client)
        assert payload["refresh_token"]
        assert payload["user"]["role"] == "student"
        assert payload["user"]["display_name"]
        assert payload["user"]["student_number"]

        me = client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["user"]["role"] == "student"


def test_wechat_page_data_contracts_are_paginated() -> None:
    with _client() as client:
        _, headers = _login(client)
        for path in ("/api/v1/tasks", "/api/v1/courses", "/api/v1/notices"):
            response = client.get(path, headers=headers)
            assert response.status_code == 200
            body = response.json()
            assert isinstance(body["items"], list)
            assert isinstance(body["total"], int)


def test_wechat_task_lifecycle_contract() -> None:
    with _client() as client:
        _, headers = _login(client)
        created = client.post(
            "/api/v1/tasks",
            headers=headers,
            json={
                "title": "微信联调待办",
                "deadline": "2026-08-20T18:00:00+08:00",
                "source_name": "联调检查",
                "source_text": "请于8月20日18点前完成微信联调检查。",
            },
        )
        assert created.status_code == 201
        task_id = created.json()["id"]

        completed = client.post(f"/api/v1/tasks/{task_id}/complete", headers=headers)
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"

        restored = client.post(f"/api/v1/tasks/{task_id}/restore", headers=headers)
        assert restored.status_code == 200
        assert restored.json()["status"] == "pending"

        deleted = client.delete(f"/api/v1/tasks/{task_id}", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["status"] == "deleted"


def test_wechat_notice_and_counselor_non_stream_contracts() -> None:
    with _client() as client:
        _, headers = _login(client)
        extraction = client.post(
            "/api/v1/notices/extract-multi",
            headers=headers,
            json={
                "content": "请于2026年8月20日18点前提交实验报告。",
                "allow_multi_task": True,
            },
        )
        assert extraction.status_code == 200
        assert isinstance(extraction.json()["tasks"], list)
        assert extraction.json()["tasks"]

        chat = client.post(
            "/api/v1/counselor/chat",
            headers=headers,
            json={
                "message": "请介绍校园奖学金申请流程",
                "conversation_id": "wx-contract",
                "stream": False,
            },
        )
        assert chat.status_code == 200
        assert isinstance(chat.json()["answer"], str)
        assert chat.json()["conversation_id"] == "wx-contract"


def test_wechat_study_session_contract() -> None:
    with _client() as client:
        _, headers = _login(client)
        created = client.post(
            "/api/v1/study/sessions",
            headers=headers,
            json={"mode": "focus"},
        )
        assert created.status_code == 201
        session_id = created.json()["id"]

        paused = client.post(f"/api/v1/study/sessions/{session_id}/pause", headers=headers)
        assert paused.status_code == 200
        assert paused.json()["status"] == "paused"

        resumed = client.post(f"/api/v1/study/sessions/{session_id}/resume", headers=headers)
        assert resumed.status_code == 200
        assert resumed.json()["status"] == "active"

        finished = client.post(
            f"/api/v1/study/sessions/{session_id}/finish",
            headers=headers,
            json={"self_report": "状态不错", "self_report_tags": ["状态不错"]},
        )
        assert finished.status_code == 200
        assert finished.json()["status"] == "completed"
