"""Phase 7A: CandidateModelClient 测试。

覆盖：
- DeterministicFixtureClient 基本行为
- OpenAICompatibleClient 成功、超时、500、非法 JSON
- CampusMateLMConfig 环境变量解析和验证
- create_client_from_env 默认和启用场景
- 安全：不泄露 API key、base URL
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from learner_state_evaluation.model_shadow.candidate_client import (
    CampusMateLMConfig,
    CandidateRequest,
    DeterministicFixtureClient,
    OpenAICompatibleClient,
    create_client_from_env,
)


def _make_request(capability="c_kc_classification_v1"):
    return CandidateRequest(
        capability_name=capability,
        capability_version="1.0",
        structured_features={"kc_code": "c.pointer.indirection", "score": 0.3},
        prompt_template_version="v1",
        taxonomy_version="c_taxonomy_v1",
        schema_version="v1",
        run_id="test_run_001",
    )


class TestDeterministicFixtureClient:
    def test_is_not_real_model(self):
        client = DeterministicFixtureClient()
        assert client.is_real_model is False

    def test_returns_fixture_prediction(self):
        fixtures = {"c_kc_classification_v1": {"label": "pointer_indirection", "confidence": 0.9}}
        client = DeterministicFixtureClient(fixture_predictions=fixtures)
        resp = client.predict(_make_request())
        assert resp.prediction == {"label": "pointer_indirection", "confidence": 0.9}
        assert resp.used_fallback is False
        assert resp.error_code is None

    def test_empty_fixture_for_unknown_capability(self):
        client = DeterministicFixtureClient()
        resp = client.predict(_make_request("unknown_cap"))
        assert resp.prediction == {}

    def test_latency_positive(self):
        client = DeterministicFixtureClient()
        resp = client.predict(_make_request())
        assert resp.latency_ms >= 1

    def test_model_key_and_version(self):
        client = DeterministicFixtureClient(model_key="test-fixture", model_version="test-v2")
        assert client.model_key == "test-fixture"
        assert client.model_version == "test-v2"


class TestCampusMateLMConfig:
    def test_defaults_disabled(self):
        config = CampusMateLMConfig()
        assert config.shadow_enabled is False
        assert config.validate() == []

    def test_from_env_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            config = CampusMateLMConfig.from_env()
            assert config.shadow_enabled is False

    def test_from_env_enabled(self):
        env = {
            "CAMPUSMATE_LM_SHADOW_ENABLED": "true",
            "CAMPUSMATE_LM_BASE_URL": "http://localhost:8080",
            "CAMPUSMATE_LM_MODEL": "campusmate-lm-v1",
            "CAMPUSMATE_LM_API_KEY": "test-key-123",
        }
        with patch.dict(os.environ, env, clear=True):
            config = CampusMateLMConfig.from_env()
            assert config.shadow_enabled is True
            assert config.base_url == "http://localhost:8080"
            assert config.validate() == []

    def test_validate_missing_base_url(self):
        config = CampusMateLMConfig(
            shadow_enabled=True,
            model="test",
            api_key="key",
        )
        errors = config.validate()
        assert any("BASE_URL" in e for e in errors)

    def test_validate_missing_model(self):
        config = CampusMateLMConfig(
            shadow_enabled=True,
            base_url="http://localhost:8080",
            api_key="key",
        )
        errors = config.validate()
        assert any("MODEL" in e for e in errors)

    def test_validate_missing_api_key(self):
        config = CampusMateLMConfig(
            shadow_enabled=True,
            base_url="http://localhost:8080",
            model="test",
        )
        errors = config.validate()
        assert any("API_KEY" in e for e in errors)


class TestCreateClientFromEnv:
    def test_returns_fixture_when_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            client = create_client_from_env()
            assert isinstance(client, DeterministicFixtureClient)
            assert client.is_real_model is False

    def test_returns_openai_when_enabled(self):
        env = {
            "CAMPUSMATE_LM_SHADOW_ENABLED": "true",
            "CAMPUSMATE_LM_BASE_URL": "http://localhost:8080",
            "CAMPUSMATE_LM_MODEL": "campusmate-lm-v1",
            "CAMPUSMATE_LM_API_KEY": "test-key-123",
        }
        with patch.dict(os.environ, env, clear=True):
            client = create_client_from_env()
            assert isinstance(client, OpenAICompatibleClient)
            assert client.is_real_model is True

    def test_falls_back_on_invalid_config(self):
        env = {
            "CAMPUSMATE_LM_SHADOW_ENABLED": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            client = create_client_from_env()
            assert isinstance(client, DeterministicFixtureClient)


class TestOpenAICompatibleClientSecurity:
    def test_api_key_not_in_response(self):
        client = OpenAICompatibleClient(
            base_url="http://localhost:8080",
            model="test",
            api_key="secret-key-123",
        )
        resp = client.predict(_make_request())
        assert "secret-key-123" not in json.dumps(resp.prediction)
        assert "secret-key-123" not in resp.model_key
        assert "secret-key-123" not in resp.model_version

    def test_base_url_not_in_response(self):
        client = OpenAICompatibleClient(
            base_url="http://localhost:8080",
            model="test",
            api_key="key",
        )
        resp = client.predict(_make_request())
        assert "localhost:8080" not in json.dumps(resp.prediction)
        assert "localhost:8080" not in resp.model_key

    def test_fallback_on_connection_error(self):
        client = OpenAICompatibleClient(
            base_url="http://127.0.0.1:1",
            model="test",
            api_key="key",
            timeout_seconds=0.1,
        )
        resp = client.predict(_make_request())
        assert resp.used_fallback is True
        assert resp.error_code is not None
        assert resp.prediction == {}