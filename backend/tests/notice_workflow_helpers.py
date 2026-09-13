from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests


def setup_student(username="notice_student"):
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:", llm_provider="none"))
    user = container.user_repository.create_user(username=username, password_hash=hash_password("Demo123456"), role="student", display_name="Notice Student")
    client = TestClient(create_app())
    token = client.post("/api/v1/auth/login", json={"username": username, "password": "Demo123456"}).json()["access_token"]
    return container, client, user, {"Authorization": f"Bearer {token}"}


def create_workflow(client, headers, content="请于2026-10-20前提交课程报告"):
    notice = client.post("/api/v1/notices/manual", headers=headers, json={"content": content, "title": "提交课程报告"}).json()
    response = client.post(f"/api/v1/notices/{notice['notice_id']}/workflow", headers=headers)
    assert response.status_code == 200
    return notice, response.json()
