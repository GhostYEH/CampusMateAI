"""壁纸代理本地防刷：两个端点共享同一 ASGI peer 额度。

覆盖:
- 超限返回 RATE_LIMITED / 429 / Retry-After，并且不再调用上游
- 交替请求每日与历史端点无法绕过共同额度
- 保留上游 UAPI_RATE_LIMITED 契约（本地额度与上游额度是两回事）

全部使用假 HTTP 客户端，不访问真实 UAPI、不使用真实 Key。
"""
from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.routes import bing_daily_wallpaper
from app.core.config import Settings
from app.main import create_app


UAPI_URL = "https://uapis.cn/api/v1/image/bing-daily"
UAPI_HISTORY_URL = "https://uapis.cn/api/v1/image/bing-daily/history"


class FakeAsyncClient:
    def __init__(self, response: httpx.Response | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def get(self, url: str, *, params: dict[str, object], headers: dict[str, str]):
        self.calls.append({"url": url, "params": params, "headers": headers})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _response(status_code: int, *, json: object | None = None, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status_code, json=json, headers=headers, request=httpx.Request("GET", UAPI_URL))


def _client(
    monkeypatch: pytest.MonkeyPatch,
    fake_client: FakeAsyncClient,
    *,
    rate_max: int = 2,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[bing_daily_wallpaper.get_settings_dep] = lambda: Settings(
        uapi_api_key="uapi-test-key",
        uapi_timeout_seconds=7,
        wallpaper_rate_max=rate_max,
        wallpaper_rate_window_seconds=60,
    )
    monkeypatch.setattr(bing_daily_wallpaper.httpx, "AsyncClient", lambda **_kwargs: fake_client)
    return TestClient(app)


def _json_ok() -> httpx.Response:
    return _response(
        200,
        json={"date": "2026-04-07", "resolution": "1080", "image_url": "https://images.example.test/w.jpg"},
        headers={"content-type": "application/json"},
    )


def _history_ok() -> httpx.Response:
    return _response(
        200,
        json={"resolution": "1080", "items": [], "pagination": {"page": 1, "page_size": 30, "total": 0}},
        headers={"content-type": "application/json"},
    )


def test_local_rate_limit_blocks_before_calling_upstream(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeAsyncClient(_json_ok())
    client = _client(monkeypatch, fake_client, rate_max=2)

    for _ in range(2):
        assert client.get("/api/v1/wallpaper/bing-daily", params={"format": "json"}).status_code == 200
    blocked = client.get("/api/v1/wallpaper/bing-daily", params={"format": "json"})

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMITED"
    assert 1 <= int(blocked.headers["retry-after"]) <= 60
    # 超限请求不再触发上游调用。
    assert len(fake_client.calls) == 2


def test_both_wallpaper_endpoints_share_one_peer_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeAsyncClient(_json_ok())
    client = _client(monkeypatch, fake_client, rate_max=2)

    # 交替请求两个端点，合计只允许 2 次。
    assert client.get("/api/v1/wallpaper/bing-daily", params={"format": "json"}).status_code == 200
    monkeypatch.setattr(bing_daily_wallpaper.httpx, "AsyncClient", lambda **_kwargs: FakeAsyncClient(_history_ok()))
    assert client.get("/api/v1/wallpaper/bing-daily/history", params={"resolution": "1080"}).status_code == 200

    third = client.get("/api/v1/wallpaper/bing-daily", params={"format": "json"})
    assert third.status_code == 429
    assert third.json()["code"] == "RATE_LIMITED"


def test_local_limit_does_not_replace_upstream_rate_limit_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """上游 429 仍是 UAPI_RATE_LIMITED，并保留上游 Retry-After。"""
    fake_client = FakeAsyncClient(
        _response(429, json={"error": "请求过于频繁"}, headers={"Retry-After": "12"})
    )
    client = _client(monkeypatch, fake_client, rate_max=5)

    response = client.get("/api/v1/wallpaper/bing-daily", params={"format": "json"})

    assert response.status_code == 429
    assert response.json()["code"] == "UAPI_RATE_LIMITED"
    assert response.headers["retry-after"] == "12"
    assert len(fake_client.calls) == 1


def test_over_limit_does_not_expose_upstream_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeAsyncClient(_json_ok())
    client = _client(monkeypatch, fake_client, rate_max=1)
    assert client.get("/api/v1/wallpaper/bing-daily", params={"format": "json"}).status_code == 200
    blocked = client.get("/api/v1/wallpaper/bing-daily", params={"format": "json"})
    assert blocked.status_code == 429
    assert "uapi-test-key" not in blocked.text
