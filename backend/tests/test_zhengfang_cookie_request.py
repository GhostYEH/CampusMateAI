from __future__ import annotations

import httpx
import pytest

from app.services.edu.adapters.ssrf_guard import SSRFBlockedError
from app.services.edu.adapters.zhengfang_http import ZhengfangHttpClient


def _install_transport(monkeypatch, handler) -> None:
    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(transport=transport, **kwargs),
    )


@pytest.mark.asyncio
async def test_unknown_path_cookie_pairs_reach_final_request_in_input_order(monkeypatch):
    captured: list[str] = []
    _install_transport(
        monkeypatch,
        lambda request: captured.append(request.headers.get("cookie", ""))
        or httpx.Response(200, text="ok", request=request),
    )
    client = ZhengfangHttpClient(base_url="https://jwxt.example.edu.cn")
    client.set_cookie_jar([
        {"name": "sid", "value": "deep", "source_url": "https://jwxt.example.edu.cn/deep", "path": None},
        {"name": "sid", "value": "root", "source_url": "https://jwxt.example.edu.cn/root", "path": None},
    ])

    await client.get("/jwglxt/profile")

    assert captured == ["sid=deep; sid=root"]
    assert [entry["value"] for entry in client.cookie_jar] == ["deep", "root"]
    assert all(entry["path"] is None for entry in client.cookie_jar)


@pytest.mark.asyncio
async def test_known_cookie_wins_name_conflict_without_dropping_other_observed_pairs(monkeypatch):
    captured: list[str] = []
    _install_transport(
        monkeypatch,
        lambda request: captured.append(request.headers.get("cookie", ""))
        or httpx.Response(200, text="ok", request=request),
    )
    client = ZhengfangHttpClient(base_url="https://jwxt.example.edu.cn")
    client.set_cookie_jar([
        {"name": "sid", "value": "known", "domain": "jwxt.example.edu.cn", "host_only": True, "path": "/"},
        {"name": "sid", "value": "observed", "source_url": "https://jwxt.example.edu.cn/login", "path": None},
        {"name": "csrf", "value": "observed-csrf", "source_url": "https://jwxt.example.edu.cn/login", "path": None},
    ])

    await client.post("/jwglxt/profile", data={})

    assert captured == ["sid=known; csrf=observed-csrf"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example.edu.cn/profile",
        "http://jwxt.example.edu.cn/profile",
        "https://sub.jwxt.example.edu.cn/profile",
    ],
)
async def test_observed_cookies_never_leave_exact_https_allowed_origin(monkeypatch, url):
    sent: list[httpx.Request] = []
    _install_transport(
        monkeypatch,
        lambda request: sent.append(request) or httpx.Response(200, text="ok", request=request),
    )
    client = ZhengfangHttpClient(base_url="https://jwxt.example.edu.cn")
    client.set_cookie_jar([
        {"name": "sid", "value": "observed", "source_url": "https://jwxt.example.edu.cn/login", "path": None},
    ])

    with pytest.raises(SSRFBlockedError, match="allowed origin"):
        await client.get(url)

    assert sent == []


@pytest.mark.asyncio
async def test_server_parent_domain_cookie_round_trips_with_known_scope(monkeypatch):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                200,
                headers={"set-cookie": "server=known; Domain=example.edu.cn; Path=/auth; Secure; Max-Age=3600"},
                request=request,
            )
        return httpx.Response(200, text="ok", request=request)

    _install_transport(monkeypatch, handler)
    client = ZhengfangHttpClient(base_url="https://jwxt.example.edu.cn")
    await client.get("/auth/login")

    snapshot = client.cookie_jar
    assert len(snapshot) == 1
    assert snapshot[0]["domain"].lstrip(".") == "example.edu.cn"
    assert snapshot[0]["host_only"] is False
    assert snapshot[0]["path"] == "/auth"
    assert snapshot[0]["secure"] is True
    assert isinstance(snapshot[0]["expires"], int)

    restored = ZhengfangHttpClient(base_url="https://jwxt.example.edu.cn")
    restored.set_cookie_jar(snapshot)
    await restored.get("/auth/profile")

    assert requests[-1].headers["cookie"] == "server=known"


@pytest.mark.asyncio
async def test_host_only_cookie_round_trip_uses_exact_response_host_with_multiple_origins(monkeypatch):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                200,
                headers={"set-cookie": "host=parent; Path=/; Secure"},
                request=request,
            )
        return httpx.Response(200, request=request)

    _install_transport(monkeypatch, handler)
    parent = "https://example.edu.cn"
    child = "https://jw.example.edu.cn"
    client = ZhengfangHttpClient(base_url=parent)
    client._allowed_origins = {parent, child}
    await client.get("/")
    snapshot = client.cookie_jar

    assert snapshot[0]["domain"] == "example.edu.cn"
    assert snapshot[0]["host_only"] is True
    assert snapshot[0]["source_url"] == parent

    for origins in ([parent, child], [child, parent]):
        restored = ZhengfangHttpClient(base_url=parent)
        restored.set_cookie_jar(snapshot, allowed_origins=origins)
        await restored.get(parent + "/profile")
        await restored.get(child + "/profile")

    assert requests[-4].headers["cookie"] == "host=parent"
    assert "cookie" not in requests[-3].headers
    assert requests[-2].headers["cookie"] == "host=parent"
    assert "cookie" not in requests[-1].headers


def test_host_only_reload_without_source_prefers_exact_cookie_domain() -> None:
    cookie = {
        "name": "host",
        "value": "parent",
        "domain": "example.edu.cn",
        "host_only": True,
        "path": "/",
    }
    for origins in (
        ["https://example.edu.cn", "https://jw.example.edu.cn"],
        ["https://jw.example.edu.cn", "https://example.edu.cn"],
    ):
        client = ZhengfangHttpClient(base_url="https://example.edu.cn")
        client.set_cookie_jar([cookie], allowed_origins=origins)
        assert client.cookie_jar[0]["domain"] == "example.edu.cn"


def test_parent_domain_cookie_reload_remains_domain_scoped() -> None:
    client = ZhengfangHttpClient(base_url="https://jw.example.edu.cn")
    client.set_cookie_jar([{
        "name": "domain",
        "value": "shared",
        "domain": "example.edu.cn",
        "host_only": False,
        "path": "/",
    }], allowed_origins=["https://example.edu.cn", "https://jw.example.edu.cn"])

    assert client.cookie_jar[0]["host_only"] is False
    assert client.cookie_jar[0]["domain"] == "example.edu.cn"


def test_external_headers_cannot_inject_cookie_header():
    with pytest.raises(ValueError, match="Cookie header"):
        ZhengfangHttpClient(
            base_url="https://jwxt.example.edu.cn",
            extra_headers={"Cookie": "sid=attacker"},
        )
