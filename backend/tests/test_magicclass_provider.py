"""Providers 状态路由测试：只转发能力布尔，永不透传任意字段。"""
from __future__ import annotations

from app.api.routes import magicclass_provider, magicclass_workspaces
from app.services.magicclass.fusion_client import MagicClassFusionClient

from test_magicclass_workspaces import _setup


def _override(container, transport):
    return MagicClassFusionClient(
        base_url=container.settings.magicclass_service_url,
        secret=container.settings.magicclass_internal_secret,
        transport=transport,
    )


def test_providers_route_reports_booleans_and_drops_unknown_fields():
    payload = {
        "llm": True,
        "web_search": False,
        "image": False,
        "video": False,
        "tts": True,
        "render": False,
        "external_3d": False,
        # 上游多出来的字段（例如未来的调试信息）不允许透传。
        "base_url": "https://upstream.internal/v1",
        "api_key": "sk-leak",
    }
    container, transport, http, headers, _ = _setup([(200, payload)])
    http.app.dependency_overrides[magicclass_provider._client] = lambda: _override(container, transport)

    response = http.get("/api/v1/magicclass/fusion/providers", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "ready"
    assert body["providers"] == {
        "llm": True,
        "web_search": False,
        "image": False,
        "video": False,
        "tts": True,
        "render": False,
        "external_3d": False,
    }
    assert "sk-leak" not in response.text and "upstream.internal" not in response.text
    from app.services.magicclass.service_assertion import decode_service_assertion

    claims = decode_service_assertion(
        transport.calls[0]["headers"]["X-CampusMate-Service-Assertion"],
        secret=container.settings.magicclass_internal_secret,
    )
    assert claims["scope"] == ["service:status"]


def test_providers_route_answers_disabled_without_contacting_service():
    container, transport, http, headers, _ = _setup(
        magicclass_fusion_enabled=False,
        magicclass_service_url="",
        magicclass_internal_secret="",
    )
    http.app.dependency_overrides[magicclass_provider._client] = lambda: _override(container, transport)

    response = http.get("/api/v1/magicclass/fusion/providers", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"state": "disabled", "providers": {}}
    assert transport.calls == []
