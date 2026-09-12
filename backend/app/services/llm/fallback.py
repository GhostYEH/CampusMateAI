"""LLM Provider 工厂 — 根据 Settings 选择具体实现。

未配置 LLM 时返回 None，业务层使用降级模式。
"""
from __future__ import annotations

from typing import Optional

from ...core.config import Settings
from .base import LLMClient, LLMConfigError
from .openai_compatible import OpenAICompatibleClient


def build_llm_client(settings: Settings) -> Optional[LLMClient]:
    """根据 Settings 构造 LLM 客户端。

    LLMConfigError(如非法 TLS 版本)向上抛出,便于诊断;
    其他构造期异常记录后返回 None,保持降级路径可用。
    """
    if not settings.llm_available:
        return None
    if settings.llm_provider == "openai_compatible":
        try:
            return OpenAICompatibleClient(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                timeout=float(settings.llm_timeout_seconds),
                tls_max_version=settings.llm_tls_max_version or None,
            )
        except LLMConfigError:
            raise
        except Exception:
            return None
    return None


__all__ = ["build_llm_client"]
