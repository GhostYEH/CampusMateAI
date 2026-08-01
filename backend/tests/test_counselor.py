"""测试 AI 导员 (Counselor) API — fallback 模式下的检索摘要行为。

验证在 LLM_PROVIDER=none 时，counselor 接口仍能返回基于检索摘要的响应。
"""
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _make_client(*, import_demo: bool = True) -> TestClient:
    """创建测试客户端。

    Args:
        import_demo: 是否导入演示知识库（用于测试 RAG 检索链路）
    """
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=import_demo,
        llm_provider="none",
        enable_fallback_mode=True,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app())


def _login(client: TestClient, username: str = "student_demo") -> dict:
    """登录并返回请求头。"""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class TestCounselorFallbackMode:
    """在 fallback 模式下测试 counselor 接口。"""

    def test_chat_non_stream_returns_response(self):
        """非流式对话(stream=false)应返回 JSON 响应。"""
        client = _make_client()
        headers = _login(client)
        resp = client.post(
            "/api/v1/counselor/chat",
            headers=headers,
            json={"message": "奖学金怎么申请", "stream": False},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

    def test_chat_stream_returns_sse_events(self):
        """流式对话(stream=true, 默认)应返回 SSE 事件流。"""
        client = _make_client()
        headers = _login(client)
        resp = client.post(
            "/api/v1/counselor/chat",
            headers=headers,
            json={"message": "社会实践需要多少学时", "stream": True},
        )
        assert resp.status_code == 200, resp.text
        content = resp.text
        # SSE 事件格式: data: {...}
        assert "data:" in content

    def test_chat_with_irrelevant_question(self):
        """与知识库无关的问题应正常返回（不崩溃）。"""
        client = _make_client()
        headers = _login(client)
        resp = client.post(
            "/api/v1/counselor/chat",
            headers=headers,
            json={"message": "今天天气怎么样", "stream": False},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "answer" in data

    def test_chat_without_login(self):
        """未登录用户也可以访问 counselor（向后兼容）。"""
        client = _make_client()
        resp = client.post(
            "/api/v1/counselor/chat",
            json={"message": "课程补退选流程", "stream": False},
        )
        assert resp.status_code == 200, resp.text

    def test_empty_message_handled(self):
        """空消息应被 FastAPI 校验拒绝（422），不应 500。"""
        client = _make_client()
        resp = client.post(
            "/api/v1/counselor/chat",
            json={"message": "", "stream": False},
        )
        # 空消息会被 Pydantic min_length=1 校验拦截，返回 422
        assert resp.status_code == 422


class TestCounselorWithoutKnowledgeBase:
    """测试知识库为空时的 counselor 行为。"""

    def test_chat_without_demo_documents(self):
        """未导入演示文档时仍应正常响应（fallback 模式）。"""
        client = _make_client(import_demo=False)
        resp = client.post(
            "/api/v1/counselor/chat",
            json={"message": "奖学金怎么申请", "stream": False},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "answer" in data