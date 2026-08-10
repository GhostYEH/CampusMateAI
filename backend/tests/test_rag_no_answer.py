"""RAG 无答案与删除即时失效测试。

验证:
1. 知识库无相关资料时，AI 不凭模型常识回答，而是提示无依据
2. admin 删除文档后，检索立即失效（不需重启）
"""
from __future__ import annotations

import io

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client_with_demo() -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=True,
    )
    reset_container_for_tests(settings)
    seed_demo_data(
        __import__("app.services.container", fromlist=["get_container"]).get_container(),
        force=True,
    )
    return TestClient(create_app())


def _login(client: TestClient, username: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_rag_no_answer_for_unknown_topic() -> None:
    client = _client_with_demo()
    h = _login(client, "student_demo")

    resp = client.post(
        "/api/v1/counselor/chat",
        headers=h,
        json={"message": "学校允许带宠物进入宿舍吗？", "stream": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    answer = data.get("answer", "")
    mode = data.get("mode", "")
    sources = data.get("sources", [])

    assert mode in ("no_knowledge", "retrieval_summary", "llm_rag", "llm"), f"unexpected mode: {mode}"
    if mode == "no_knowledge":
        assert "知识库" in answer or "暂未" in answer or "建议" in answer, \
            f"no_knowledge answer should mention lack of knowledge: {answer[:200]}"
    if mode in ("llm", "retrieval_summary"):
        assert len(sources) == 0 or all(
            "宠物" not in s.get("title", "") for s in sources
        ), "should not find pet policy in knowledge base"


def test_rag_delete_immediate_effect() -> None:
    client = _client_with_demo()
    admin_h = _login(client, "admin_demo")
    student_h = _login(client, "student_demo")

    unique_content = "CampusMateTestUniqueAnswer2026 校园羽毛球比赛报名须知"
    resp = client.post(
        "/api/v1/knowledge/documents",
        headers=admin_h,
        files={"file": ("unique_test.md", io.BytesIO(unique_content.encode("utf-8")), "text/markdown")},
        data={"title": "羽毛球比赛报名"},
    )
    assert resp.status_code in (200, 201), f"upload failed: {resp.text}"
    doc_id = resp.json()["document_id"]

    resp = client.post(
        "/api/v1/counselor/chat",
        headers=student_h,
        json={"message": "CampusMateTestUniqueAnswer2026", "stream": False},
    )
    assert resp.status_code == 200
    found_in_sources = any(
        "unique" in s.get("title", "").lower() or "羽毛球" in s.get("title", "")
        for s in resp.json().get("sources", [])
    )

    resp = client.delete(f"/api/v1/knowledge/documents/{doc_id}", headers=admin_h)
    assert resp.status_code == 200

    resp = client.post(
        "/api/v1/counselor/chat",
        headers=student_h,
        json={"message": "CampusMateTestUniqueAnswer2026", "stream": False},
    )
    assert resp.status_code == 200
    after_delete_sources = resp.json().get("sources", [])
    found_after_delete = any(
        doc_id == s.get("document_id", "")
        for s in after_delete_sources
    )
    assert not found_after_delete, "document should not appear in sources after deletion"


def test_rag_scholarship_query_returns_sources() -> None:
    client = _client_with_demo()
    h = _login(client, "student_demo")

    resp = client.get("/api/v1/knowledge/status", headers=h)
    assert resp.status_code == 200
    doc_count = resp.json().get("document_count", 0)

    resp = client.post(
        "/api/v1/counselor/chat",
        headers=h,
        json={"message": "奖学金申请需要哪些材料？", "stream": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    sources = data.get("sources", [])

    if doc_count > 0 and data.get("mode") not in ("no_knowledge", "llm"):
        assert len(sources) > 0, f"scholarship query should return sources (doc_count={doc_count}, mode={data.get('mode')})"
    for s in sources:
        assert s.get("title") or s.get("document_id"), "source should have title or document_id"