import asyncio

from pydantic import BaseModel

from app.services.llm.base import LLMResponse, LLMTimeoutError
from app.services.llm.model_router import ModelRouter
from app.services.llm.provider_registry import ProviderRegistry


class Result(BaseModel):
    ok: bool


class FakeProvider:
    available = True

    def __init__(self, name, *, text='{"ok":true}', error=None):
        self.name, self.text, self.error = name, text, error

    async def chat(self, *_args, **_kwargs):
        if self.error:
            raise self.error
        return LLMResponse(self.text)


def test_reasoning_primary_falls_back_without_exposing_provider_config():
    registry = ProviderRegistry({
        "zhipu": FakeProvider("zhipu", error=LLMTimeoutError("secret endpoint")),
        "xunfei": FakeProvider("xunfei"),
    })
    result = asyncio.run(ModelRouter(registry).structured(
        "reasoning_primary", messages=[{"role": "user", "content": "safe"}], output_model=Result
    ))
    assert result.output.ok is True
    assert result.provider == "xunfei"
    assert result.fallback_reason == "PRIMARY_TIMEOUT"


def test_unconfigured_registry_reports_only_boolean_status():
    assert ProviderRegistry({}).diagnostic() == {"zhipu": False, "xunfei": False}
