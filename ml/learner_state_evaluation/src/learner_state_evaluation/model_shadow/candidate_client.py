"""Phase 7A: 候选模型客户端抽象。

支持：
- DeterministicFixtureClient：仅供测试的确定性 fixture 客户端。
- OpenAICompatibleClient：用于真实 CampusMate-LM 服务的 OpenAI 兼容 HTTP 客户端。

配置使用环境变量，不硬编码本机地址：
- CAMPUSMATE_LM_SHADOW_ENABLED
- CAMPUSMATE_LM_BASE_URL
- CAMPUSMATE_LM_MODEL
- CAMPUSMATE_LM_API_KEY
- CAMPUSMATE_LM_TIMEOUT_SECONDS
- CAMPUSMATE_LM_MAX_CONCURRENCY

安全要求：
- 默认关闭。
- 不自动下载权重。
- 不把 API key、base URL、绝对路径写入数据库、响应或日志。
- 仅发送受控结构化特征，不发送源码、答案、课程正文、通知正文、聊天原文或凭据。
- 非法 JSON、超时、连接失败、未知枚举、prompt injection、输出越权全部回退确定性生产逻辑。
- 候选失败不能影响生产响应。
- 日志只包含 run_id、capability、model key/version、异常类型，不记录异常消息或模型原文。
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable


_OUTPUT_FIELDS = {
    "student_state_summary_v1": "summary, claim_codes",
    "campus_intent_routing_v1": "intent_code, confidence, abstained",
    "notice_action_classification_v1": "action_code, confidence, abstained",
    "goal_support_classification_v1": "support_level, confidence, abstained",
    "read_only_tool_routing_v1": "tool_name, arguments, confidence, abstained",
}


@dataclass(frozen=True)
class CandidateRequest:
    """受控结构化特征请求，不包含源码、答案、课程正文、通知正文、聊天原文或凭据。"""
    capability_name: str
    capability_version: str
    structured_features: dict[str, Any]
    prompt_template_version: str
    taxonomy_version: str
    schema_version: str
    run_id: str
    generation_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateResponse:
    """候选模型响应。"""
    prediction: dict[str, Any]
    model_key: str
    model_version: str
    latency_ms: int
    used_fallback: bool = False
    error_code: Optional[str] = None


@runtime_checkable
class CandidateModelClient(Protocol):
    """候选模型客户端协议。"""

    @property
    def is_real_model(self) -> bool: ...

    @property
    def model_key(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    @property
    def provenance(self) -> str: ...

    def predict(self, request: CandidateRequest) -> CandidateResponse: ...


class DeterministicFixtureClient:
    """确定性 fixture 客户端，仅供测试。"""

    def __init__(
        self,
        *,
        fixture_predictions: Optional[dict[str, dict[str, Any]]] = None,
        model_key: str = "deterministic-fixture",
        model_version: str = "deterministic-baseline-v1",
    ) -> None:
        self._fixtures = fixture_predictions or {}
        self._model_key = model_key
        self._model_version = model_version

    @property
    def is_real_model(self) -> bool:
        return False

    @property
    def model_key(self) -> str:
        return self._model_key

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def provenance(self) -> str:
        return "FIXTURE"

    def predict(self, request: CandidateRequest) -> CandidateResponse:
        start = time.monotonic()
        fixture = self._fixtures.get(request.capability_name, {})
        latency = int((time.monotonic() - start) * 1000)
        return CandidateResponse(
            prediction=fixture,
            model_key=self._model_key,
            model_version=self._model_version,
            latency_ms=max(latency, 1),
        )


class OpenAICompatibleClient:
    """OpenAI 兼容的本地 HTTP 客户端，用于真实 CampusMate-LM 服务。

    使用标准库 urllib，不引入第三方依赖。
    默认关闭，需通过 CAMPUSMATE_LM_SHADOW_ENABLED=true 显式开启。
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        timeout_seconds: float = 30.0,
        max_concurrency: int = 4,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._max_concurrency = max_concurrency

    @property
    def is_real_model(self) -> bool:
        return True

    @property
    def model_key(self) -> str:
        return "campusmate-lm"

    @property
    def model_version(self) -> str:
        return self._model

    @property
    def provenance(self) -> str:
        return "OPENAI_COMPATIBLE_SERVICE"

    @property
    def timeout_seconds(self) -> float:
        return self._timeout

    def predict(self, request: CandidateRequest) -> CandidateResponse:
        """执行预测。失败时回退确定性逻辑，不抛异常。"""
        start = time.monotonic()
        try:
            params = dict(request.generation_params)
            temperature = float(params.get("temperature", 0.0))
            max_tokens = int(params.get("max_tokens", 512))
            if not 0.0 <= temperature <= 2.0 or not 1 <= max_tokens <= 4096:
                raise ValueError("invalid generation parameters")
            payload_data = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": (
                        "You are a constrained structured prediction model for "
                        f"{request.capability_name}. Return one JSON object with exactly these fields: "
                        f"{_OUTPUT_FIELDS.get(request.capability_name, 'none')}. "
                        "Use only values present in the structured input allowlists; never invent identifiers, "
                        "write actions, private data, or additional fields."
                    )},
                    {"role": "user", "content": json.dumps(request.structured_features, ensure_ascii=False)},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if params.get("seed") is not None:
                payload_data["seed"] = int(params["seed"])
            payload = json.dumps(payload_data).encode("utf-8")

            req = urllib.request.Request(
                f"{self._base_url}/v1/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                content = body["choices"][0]["message"]["content"]
                prediction = json.loads(content)

            latency = int((time.monotonic() - start) * 1000)
            return CandidateResponse(
                prediction=prediction,
                model_key=self.model_key,
                model_version=self.model_version,
                latency_ms=max(latency, 1),
            )

        except (urllib.error.URLError, TimeoutError, ConnectionError):
            latency = int((time.monotonic() - start) * 1000)
            return CandidateResponse(
                prediction={},
                model_key=self.model_key,
                model_version=self.model_version,
                latency_ms=max(latency, 1),
                used_fallback=True,
                error_code="MODEL_TIMEOUT",
            )
        except (json.JSONDecodeError, KeyError, IndexError):
            latency = int((time.monotonic() - start) * 1000)
            return CandidateResponse(
                prediction={},
                model_key=self.model_key,
                model_version=self.model_version,
                latency_ms=max(latency, 1),
                used_fallback=True,
                error_code="MODEL_SCHEMA_INVALID",
            )
        except Exception:
            latency = int((time.monotonic() - start) * 1000)
            return CandidateResponse(
                prediction={},
                model_key=self.model_key,
                model_version=self.model_version,
                latency_ms=max(latency, 1),
                used_fallback=True,
                error_code="MODEL_ERROR",
            )


@dataclass
class CampusMateLMConfig:
    """从环境变量解析的 CampusMate-LM 配置。"""
    shadow_enabled: bool = False
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    timeout_seconds: float = 30.0
    max_concurrency: int = 4

    @classmethod
    def from_env(cls) -> "CampusMateLMConfig":
        """从环境变量解析配置。"""
        return cls(
            shadow_enabled=os.getenv("CAMPUSMATE_LM_SHADOW_ENABLED", "").lower() in ("true", "1", "yes"),
            base_url=os.getenv("CAMPUSMATE_LM_BASE_URL", ""),
            model=os.getenv("CAMPUSMATE_LM_MODEL", ""),
            api_key=os.getenv("CAMPUSMATE_LM_API_KEY", ""),
            timeout_seconds=float(os.getenv("CAMPUSMATE_LM_TIMEOUT_SECONDS", "30")),
            max_concurrency=int(os.getenv("CAMPUSMATE_LM_MAX_CONCURRENCY", "4")),
        )

    def validate(self) -> list[str]:
        """返回配置错误列表，不抛异常。"""
        errors = []
        if self.shadow_enabled:
            if not self.base_url:
                errors.append("CAMPUSMATE_LM_BASE_URL is required when shadow is enabled")
            if not self.model:
                errors.append("CAMPUSMATE_LM_MODEL is required when shadow is enabled")
            if not self.api_key:
                errors.append("CAMPUSMATE_LM_API_KEY is required when shadow is enabled")
            if self.timeout_seconds <= 0:
                errors.append("CAMPUSMATE_LM_TIMEOUT_SECONDS must be positive")
            if self.max_concurrency <= 0:
                errors.append("CAMPUSMATE_LM_MAX_CONCURRENCY must be positive")
        return errors


def create_client_from_env(
    *,
    fixture_predictions: Optional[dict[str, dict[str, Any]]] = None,
) -> CandidateModelClient:
    """从环境变量创建客户端。默认返回 fixture client。"""
    config = CampusMateLMConfig.from_env()
    if not config.shadow_enabled:
        return DeterministicFixtureClient(fixture_predictions=fixture_predictions)
    errors = config.validate()
    if errors:
        return DeterministicFixtureClient(fixture_predictions=fixture_predictions)
    return OpenAICompatibleClient(
        base_url=config.base_url,
        model=config.model,
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
        max_concurrency=config.max_concurrency,
    )


__all__ = [
    "CandidateModelClient",
    "CandidateRequest",
    "CandidateResponse",
    "DeterministicFixtureClient",
    "OpenAICompatibleClient",
    "CampusMateLMConfig",
    "create_client_from_env",
]
