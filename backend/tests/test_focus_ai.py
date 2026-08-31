"""Focus AI 最小文本问答接口测试；所有 LLM 调用使用 Stub。"""
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.llm.base import LLMError, LLMResponse, LLMTimeoutError
from app.services.demo_seeder import seed_demo_data


class StubFocusLlm:
    available = True
    def __init__(self, response: str = "可以先写出已知条件。", error: Exception | None = None):
        self.response, self.error, self.calls = response, error, []
    async def chat(self, messages, **kwargs):
        self.calls.append(messages)
        if self.error: raise self.error
        return LLMResponse(self.response)


def make_client(llm=None):
    settings = Settings(
        app_env="test", database_url="sqlite:///:memory:", auto_seed_demo_users=True,
        llm_provider="openai_compatible", llm_base_url="https://example.test", llm_api_key="test", llm_model="test",
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    container.llm = llm
    return TestClient(create_app()), llm


def auth(client):
    response = client.post("/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_focus_ai_asks_with_safe_prompt():
    llm = StubFocusLlm()
    client, _ = make_client(llm)
    response = client.post("/api/v1/focus/ai/ask", headers=auth(client), json={"text": "  微积分怎么复习  "})
    assert response.status_code == 200
    assert response.json() == {"answer": "可以先写出已知条件。"}
    assert "没有摄像头画面" in llm.calls[0][0]["content"]
    assert llm.calls[0][1]["content"] == "微积分怎么复习"


def test_focus_ai_validates_text_and_requires_authentication():
    client, _ = make_client(StubFocusLlm())
    assert client.post("/api/v1/focus/ai/ask", json={"text": "问题"}).status_code == 401
    assert client.post("/api/v1/focus/ai/ask", headers=auth(client), json={"text": "   "}).status_code == 422
    assert client.post("/api/v1/focus/ai/ask", headers=auth(client), json={"text": "x" * 801}).status_code == 422


def test_focus_ai_maps_safe_provider_errors():
    client, _ = make_client(StubFocusLlm(error=LLMTimeoutError("provider secret")))
    timeout = client.post("/api/v1/focus/ai/ask", headers=auth(client), json={"text": "问题"})
    assert timeout.status_code == 504
    assert timeout.json()["code"] == "HTTP_ERROR"
    assert "secret" not in timeout.json()["message"]

    client, _ = make_client(StubFocusLlm(error=LLMError("provider secret")))
    failure = client.post("/api/v1/focus/ai/ask", headers=auth(client), json={"text": "问题"})
    assert failure.status_code == 502
    assert failure.json()["code"] == "HTTP_ERROR"
    assert "secret" not in failure.json()["message"]


def test_focus_ai_rejects_unavailable_provider():
    client, _ = make_client(None)
    assert client.post("/api/v1/focus/ai/ask", headers=auth(client), json={"text": "问题"}).status_code == 503
