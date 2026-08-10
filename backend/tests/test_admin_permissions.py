"""管理员权限校验与 RAG 知识库管理闭环测试。

验证:
1. student 角色访问 admin-only 端点返回 403 Forbidden
2. admin 角色可以正常访问 admin-only 端点
3. RAG 知识库管理闭环: 上传 → 列表 → 删除 → 重建索引
4. /knowledge/manage/{action} 必须要求 admin 权限
"""
from __future__ import annotations

import io

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


def _login(client: TestClient, username: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert resp.status_code == 200, f"login failed for {username}: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ===== 权限拒绝测试 =====


def test_student_rejected_from_knowledge_upload() -> None:
    client = _client()
    h = _login(client, "student_demo")
    resp = client.post(
        "/api/v1/knowledge/documents",
        headers=h,
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        data={"title": "test"},
    )
    assert resp.status_code == 403


def test_student_rejected_from_knowledge_delete() -> None:
    client = _client()
    h = _login(client, "student_demo")
    resp = client.delete("/api/v1/knowledge/documents/fake-id", headers=h)
    assert resp.status_code == 403


def test_student_rejected_from_knowledge_rebuild() -> None:
    client = _client()
    h = _login(client, "student_demo")
    resp = client.post("/api/v1/knowledge/rebuild", headers=h)
    assert resp.status_code == 403


def test_student_rejected_from_knowledge_manage() -> None:
    client = _client()
    h = _login(client, "student_demo")
    resp = client.post(
        "/api/v1/knowledge/manage/delete_user_documents", headers=h
    )
    assert resp.status_code == 403


def test_student_rejected_from_admin_user_create() -> None:
    client = _client()
    h = _login(client, "student_demo")
    resp = client.post(
        "/api/v1/auth/admin/users",
        headers=h,
        json={
            "username": "newuser",
            "password": "Test123456",
            "display_name": "Test",
            "role": "student",
        },
    )
    assert resp.status_code == 403


def test_anonymous_rejected_from_knowledge_manage() -> None:
    client = _client()
    resp = client.post("/api/v1/knowledge/manage/delete_all_documents")
    assert resp.status_code == 401


# ===== admin 正常访问测试 =====


def test_admin_can_access_knowledge_status() -> None:
    client = _client()
    h = _login(client, "admin_demo")
    resp = client.get("/api/v1/knowledge/status", headers=h)
    assert resp.status_code == 200


def test_admin_can_list_documents() -> None:
    client = _client()
    h = _login(client, "admin_demo")
    resp = client.get("/api/v1/knowledge/documents", headers=h)
    assert resp.status_code == 200


def test_admin_can_rebuild_index() -> None:
    client = _client()
    h = _login(client, "admin_demo")
    resp = client.post("/api/v1/knowledge/rebuild", headers=h)
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ===== RAG 管理闭环: 上传 → 列表 → 删除 =====


def test_rag_management_lifecycle() -> None:
    client = _client()
    h = _login(client, "admin_demo")

    # 1. 上传文档
    content = "# 测试文档\n\n这是用于闭环测试的知识库文档。"
    resp = client.post(
        "/api/v1/knowledge/documents",
        headers=h,
        files={"file": ("lifecycle_test.md", io.BytesIO(content.encode("utf-8")), "text/markdown")},
        data={"title": "闭环测试文档", "source_department": "测试部门"},
    )
    assert resp.status_code in (200, 201), f"upload failed: {resp.text}"
    doc_id = resp.json()["document_id"]

    # 2. 列表确认文档存在
    resp = client.get("/api/v1/knowledge/documents", headers=h)
    assert resp.status_code == 200
    ids = [d["document_id"] for d in resp.json()]
    assert doc_id in ids

    # 3. 知识库状态确认有文档
    resp = client.get("/api/v1/knowledge/status", headers=h)
    assert resp.status_code == 200
    assert resp.json()["document_count"] >= 1

    # 4. 删除文档
    resp = client.delete(f"/api/v1/knowledge/documents/{doc_id}", headers=h)
    assert resp.status_code == 200, f"delete failed: {resp.text}"
    assert resp.json()["success"] is True

    # 5. 列表确认文档已删除
    resp = client.get("/api/v1/knowledge/documents", headers=h)
    assert resp.status_code == 200
    ids = [d["document_id"] for d in resp.json()]
    assert doc_id not in ids


def test_admin_can_manage_user_documents() -> None:
    client = _client()
    h = _login(client, "admin_demo")
    resp = client.post(
        "/api/v1/knowledge/manage/delete_user_documents", headers=h
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True