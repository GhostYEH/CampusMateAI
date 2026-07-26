"""LLM Provider 抽象。

设计目标：
- 业务层只依赖 LLMClient 接口
- 多个具体实现(OpenAI 兼容 / Fallback)
- 单元测试用 stub
"""
from __future__ import annotations

from typing import List, Optional, Protocol


class LLMMessage(dict):
    """简化消息类型(对齐 OpenAI Chat Messages 格式)。"""


class LLMResponse:
    """LLM 一次完整响应(非流式)。"""

    def __init__(
        self,
        content: str,
        *,
        finish_reason: str = "stop",
        raw: Optional[dict] = None,
    ) -> None:
        self.content = content
        self.finish_reason = finish_reason
        self.raw = raw


class LLMClient(Protocol):
    """LLM 客户端协议。"""

    @property
    def name(self) -> str:
        """provider 名称(用于日志/状态)。"""
        ...

    @property
    def available(self) -> bool:
        """是否实际可用(配置完整且未降级)。"""
        ...

    async def chat(
        self,
        messages: List[dict],
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> LLMResponse:
        """非流式对话。返回完整响应。"""
        ...


    async def stream_chat(
        self,
        messages: List[dict],
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        """流式对话。异步生成器，逐个产出增量 chunk 字符串。"""
        ...


class LLMError(Exception):
    """LLM 调用错误。"""


class LLMTimeoutError(LLMError):
    """LLM 超时。"""


class LLMConfigError(LLMError):
    """LLM 配置错误(无 base_url/api_key 等)。"""


__all__ = [
    "LLMResponse",
    "LLMClient",
    "LLMError",
    "LLMTimeoutError",
    "LLMConfigError",
]
