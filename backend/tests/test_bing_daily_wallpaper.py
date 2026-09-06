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
    def __init__(self, response: httpx.Response | Exception):
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
    request = httpx.Request("GET", UAPI_URL)
    return httpx.Response(status_code, json=json, headers=headers, request=request)


def _client(
    monkeypatch: pytest.MonkeyPatch,
    fake_client: FakeAsyncClient,
    *,
    api_key: str = "uapi-test-key",
) -> TestClient:
    app = create_app()
    app.dependency_overrides[bing_daily_wallpaper.get_settings_dep] = lambda: Settings(
        uapi_api_key=api_key,
        uapi_timeout_seconds=7,
    )
    monkeypatch.setattr(bing_daily_wallpaper.httpx, "AsyncClient", lambda **_kwargs: fake_client)
    return TestClient(app)


def test_bing_daily_json_proxy_uses_documented_endpoint_auth_and_random_history(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "date": "2026-04-07",
        "market": "zh-CN",
        "title": "河狸，德国",
        "subtitle": "国际河狸日",
        "headline": "一根树枝，一点工程",
        "description": "壁纸说明",
        "copyright": "版权信息",
        "copyright_link": "https://www.bing.com/",
        "quiz_id": "HPQuiz_20260409_SeattleSunrise",
        "trivia": {"question": "问题", "options": [{"bullet": "A", "text": "答案", "url": "https://www.bing.com/"}]},
        "resolution": "1080",
        "image_url": "https://cn.bing.com/th?id=OHR.example.jpg",
        "image_url_4k": "https://cn.bing.com/th?id=OHR.example.jpg",
        "image_url_1080": "https://cn.bing.com/th?id=OHR.example.jpg&pid=hp&w=1920",
        "fetched_at": "2026-04-08T18:52:39.82+08:00",
        "updated_at": "2026-04-08T18:52:41.739+08:00",
    }
    fake_client = FakeAsyncClient(_response(200, json=payload, headers={"content-type": "application/json"}))
    client = _client(monkeypatch, fake_client)

    response = client.get("/api/v1/wallpaper/bing-daily", params={"random": "true", "resolution": "1080", "format": "json"})

    assert response.status_code == 200, response.text
    assert response.json() == payload
    assert fake_client.calls == [{
        "url": UAPI_URL,
        "params": {"random": True, "resolution": "1080", "format": "json"},
        "headers": {"Authorization": "Bearer uapi-test-key"},
    }]


def test_bing_daily_json_proxy_works_anonymously_when_key_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"date": "2026-04-07", "resolution": "1080", "image_url": "https://images.example.test/wallpaper.webp"}
    fake_client = FakeAsyncClient(_response(200, json=payload, headers={"content-type": "application/json"}))
    client = _client(monkeypatch, fake_client, api_key="")

    response = client.get("/api/v1/wallpaper/bing-daily", params={"format": "json", "resolution": "1080"})

    assert response.status_code == 200
    assert response.json() == payload
    assert fake_client.calls[0]["headers"] == {}


def test_bing_daily_history_forwards_documented_params_and_omits_pagination_for_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "resolution": "1080",
        "items": [{"date": "2026-04-07", "image_url": "https://images.example.test/wallpaper.webp"}],
        "pagination": {"page": 1, "page_size": 1, "total": 1},
    }
    fake_client = FakeAsyncClient(_response(200, json=payload, headers={"content-type": "application/json"}))
    client = _client(monkeypatch, fake_client)

    response = client.get(
        "/api/v1/wallpaper/bing-daily/history",
        params={"date": "2026-04-07", "resolution": "1080", "page": 2, "page_size": 99},
    )

    assert response.status_code == 200
    assert response.json() == payload
    assert fake_client.calls == [{
        "url": UAPI_HISTORY_URL,
        "params": {"date": "2026-04-07", "resolution": "1080"},
        "headers": {"Authorization": "Bearer uapi-test-key"},
    }]


def test_bing_daily_history_uses_anonymous_request_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"resolution": "4k", "items": [], "pagination": {"page": 1, "page_size": 30, "total": 0}}
    fake_client = FakeAsyncClient(_response(200, json=payload, headers={"content-type": "application/json"}))
    client = _client(monkeypatch, fake_client, api_key="")

    response = client.get("/api/v1/wallpaper/bing-daily/history", params={"page": 2, "page_size": 10})

    assert response.status_code == 200
    assert fake_client.calls[0]["url"] == UAPI_HISTORY_URL
    assert fake_client.calls[0]["headers"] == {}
    assert fake_client.calls[0]["params"] == {"resolution": "4k", "page": 2, "page_size": 10}


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page_size": 0}, {"page_size": 101}, {"date": "2026-02-30"}],
)
def test_bing_daily_history_rejects_invalid_params_before_calling_uapi(
    monkeypatch: pytest.MonkeyPatch,
    params: dict[str, object],
) -> None:
    fake_client = FakeAsyncClient(_response(500, json={"error": "不应请求上游"}))
    client = _client(monkeypatch, fake_client)

    response = client.get("/api/v1/wallpaper/bing-daily/history", params=params)

    assert response.status_code == 400
    assert fake_client.calls == []


def test_bing_daily_rejects_date_and_random_before_calling_uapi(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeAsyncClient(_response(500, json={"error": "不应请求上游"}))
    client = _client(monkeypatch, fake_client)

    response = client.get("/api/v1/wallpaper/bing-daily", params={"date": "2026-04-07", "random": "true"})

    assert response.status_code == 400
    assert "random" in response.json()["message"]
    assert fake_client.calls == []


@pytest.mark.parametrize(
    ("status_code", "upstream_message", "expected_message"),
    [
        (400, "resolution 只能传 4k 或 1080", "resolution 只能传 4k 或 1080"),
        (404, "没有找到对应日期的必应壁纸", "没有找到对应日期的必应壁纸"),
        (500, "必应壁纸获取失败", "必应壁纸获取失败"),
    ],
)
def test_bing_daily_maps_documented_upstream_errors(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    upstream_message: str,
    expected_message: str,
) -> None:
    fake_client = FakeAsyncClient(_response(status_code, json={"error": upstream_message}))
    client = _client(monkeypatch, fake_client)

    response = client.get("/api/v1/wallpaper/bing-daily", params={"format": "json"})

    assert response.status_code == status_code
    assert response.json()["message"] == expected_message


def test_bing_daily_preserves_rate_limit_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeAsyncClient(_response(429, json={"error": "请求过于频繁"}, headers={"Retry-After": "12"}))
    client = _client(monkeypatch, fake_client)

    response = client.get("/api/v1/wallpaper/bing-daily", params={"format": "json"})

    assert response.status_code == 429
    assert response.headers["retry-after"] == "12"
    assert response.json()["message"] == "请求过于频繁"


def test_bing_daily_redirect_forwards_location(monkeypatch: pytest.MonkeyPatch) -> None:
    target = "https://cn.bing.com/th?id=OHR.example_EN-US.jpg"
    fake_client = FakeAsyncClient(_response(302, headers={"location": target}))
    client = _client(monkeypatch, fake_client)

    response = client.get("/api/v1/wallpaper/bing-daily", params={"format": "redirect"}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == target


def test_bing_daily_returns_timeout_without_exposing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeAsyncClient(httpx.ReadTimeout("uapi timed out"))
    client = _client(monkeypatch, fake_client)

    response = client.get("/api/v1/wallpaper/bing-daily", params={"format": "json"})

    assert response.status_code == 504
    assert response.json()["code"] == "UAPI_TIMEOUT"
    assert "uapi-test-key" not in response.text


def test_bing_daily_rejects_success_payload_without_image_url(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeAsyncClient(_response(200, json={"date": "2026-04-07"}))
    client = _client(monkeypatch, fake_client)

    response = client.get("/api/v1/wallpaper/bing-daily", params={"format": "json"})

    assert response.status_code == 502
    assert response.json()["code"] == "UAPI_INVALID_RESPONSE"
