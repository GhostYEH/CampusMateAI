"""验证 LLM 网络/TLS 失败不会向用户抛 500，而是归一为 LLMError 并触发规则降级。

背景: 代理/网关偶发的 ssl.SSLError 会穿透 httpx 包装层。
若客户端不把它归一为 LLMError，任务拆解服务无法进入 rule_fallback，
最终被全局异常处理器包成 500 —— 这就是浏览器里 /study/task-breakdown
偶发 500 的真实原因之一。
"""
import asyncio
import ssl
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.database.sqlite_db import reset_db_for_tests
from app.repositories.document_repository import DocumentRepository
from app.repositories.personal_task_repository import PersonalTaskRepository
from app.schemas.study import TaskBreakdownRequest
from app.services.llm.base import LLMError
from app.services.llm.openai_compatible import OpenAICompatibleClient
from app.services.retrieval_service import RetrievalService
from app.services.task_breakdown_service import TaskBreakdownService


class _SslFailingTransport:
    """httpx.AsyncClient.post 的行为替身：抛出原始 ssl.SSLError。"""

    async def post(self, *args, **kwargs):
        raise ssl.SSLError("SSLV3_ALERT_BAD_RECORD_MAC")


class _SslFailingLLM:
    """LLM 层面测试用：chat 直接抛原始 ssl.SSLError。"""

    name = "ssl-failing"
    available = True

    async def chat(self, messages, **kwargs):
        raise ssl.SSLError("tls handshake failed")


def test_openai_client_normalizes_ssl_error_to_llm_error() -> None:
    """openai_compatible.chat 必须把原始 ssl.SSLError 归一为 LLMError。"""
    client = OpenAICompatibleClient(
        base_url="https://llm.test", api_key="test-key", model="test-model"
    )
    client._ensure_client = lambda: _SslFailingTransport()  # type: ignore[method-assign]

    with pytest.raises(LLMError, match="网络错误"):
        asyncio.run(
            client.chat([{"role": "user", "content": "你好"}], timeout=3.0)
        )


def _build_service(llm) -> TaskBreakdownService:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        llm_provider="openai_compatible",
        llm_base_url="http://localhost",
        llm_api_key="test-key",
        llm_model="test-model",
    )
    db = reset_db_for_tests()
    task_repo = PersonalTaskRepository(db)
    doc_repo = DocumentRepository(db)
    retrieval = RetrievalService(doc_repo)
    return TaskBreakdownService(
        personal_task_repo=task_repo,
        retrieval=retrieval,
        llm=llm,
        settings=settings,
    )


def test_task_breakdown_ssl_failure_degrades_to_rule_fallback() -> None:
    """LLM 抛 ssl.SSLError 时，task-breakdown 返回 rule_fallback 而不是 500。"""
    service = _build_service(_SslFailingLLM())
    user = SimpleNamespace(id="usr_test", role="student")

    response = asyncio.run(
        service.breakdown(
            TaskBreakdownRequest(goal="复习高等数学第一章并完成课后习题"),
            user=user,
        )
    )

    assert response.mode == "rule_fallback"
    assert response.steps, "规则降级也必须产出步骤"
    # warnings 必须是用户友好中文,不得暴露内部异常类名(如 SSLError)
    assert any("不可用" in warning or "降级" in warning for warning in response.warnings)
    assert all("SSLError" not in warning and "Error" not in warning for warning in response.warnings), \
        "warnings 不得向用户暴露内部异常类名"


def test_task_breakdown_with_valid_llm_returns_llm_mode() -> None:
    """LLM 正常输出 JSON 时保持 llm 模式（回归保护）。"""
    from app.services.llm.openai_compatible import StubLLMClient

    stub = StubLLMClient(
        response_text=(
            '[{"step_number":1,"title":"复习定义","description":"重读教材第一小节",'
            '"estimated_minutes":20,"dependencies":[],"completion_criteria":"能复述定义",'
            '"is_policy_step":false,"knowledge_source":null}]'
        )
    )
    service = _build_service(stub)
    user = SimpleNamespace(id="usr_test", role="student")

    response = asyncio.run(
        service.breakdown(
            TaskBreakdownRequest(goal="复习高等数学第一章定义"),
            user=user,
        )
    )

    assert response.mode == "llm"
    assert response.steps[0].title == "复习定义"


def test_task_breakdown_does_not_use_run_until_complete() -> None:
    """breakdown 必须是 async 协程,不再使用 run_until_complete 同步包装。"""
    import inspect

    from app.services.task_breakdown_service import TaskBreakdownService
    assert inspect.iscoroutinefunction(TaskBreakdownService.breakdown), \
        "TaskBreakdownService.breakdown 必须是 async 方法"
    assert inspect.iscoroutinefunction(TaskBreakdownService._build_llm_steps), \
        "_build_llm_steps 必须是 async 方法"


def test_task_breakdown_timeout_uses_settings_not_hardcoded() -> None:
    """LLM 调用超时必须来自 Settings.llm_timeout_seconds,不再是硬编码 20.0。"""
    from app.services.llm.openai_compatible import StubLLMClient

    captured = {}

    class _TimeoutCapturingStub(StubLLMClient):
        async def chat(self, messages, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            return await super().chat(messages, **kwargs)

    stub = _TimeoutCapturingStub(response_text="[]")
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        llm_provider="openai_compatible",
        llm_base_url="http://localhost",
        llm_api_key="test-key",
        llm_model="test-model",
        llm_timeout_seconds=42,
    )
    db = reset_db_for_tests()
    task_repo = PersonalTaskRepository(db)
    doc_repo = DocumentRepository(db)
    retrieval = RetrievalService(doc_repo)
    service = TaskBreakdownService(
        personal_task_repo=task_repo,
        retrieval=retrieval,
        llm=stub,
        settings=settings,
    )
    user = SimpleNamespace(id="usr_test", role="student")

    asyncio.run(
        service.breakdown(TaskBreakdownRequest(goal="复习高数"), user=user)
    )

    assert captured["timeout"] == 42.0, \
        "LLM 调用超时必须使用 Settings.llm_timeout_seconds(42),而非硬编码 20.0"