import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from app.services.edu import discovery_service as discovery
from app.services.edu.adapters.ssrf_guard import assert_safe_url


EDU_HTML = (
    '<title>正方教务管理系统</title>'
    '<meta name="generator" content="正方软件股份有限公司">'
)
URL = "https://portal.example.edu/login"


@pytest.fixture
def discovery_env(tmp_path, monkeypatch):
    path = tmp_path / "candidates.json"
    monkeypatch.setattr(discovery, "_CANDIDATES_FILE", path)
    monkeypatch.setattr(discovery, "_load_universities", lambda: [{
        "school_code": "test-school", "name": "测试高校", "official_domain": "example.edu",
    }])
    monkeypatch.setattr(discovery, "get_settings", lambda: SimpleNamespace(
        app_env="test", edu_allow_insecure_ssl=False,
    ))
    checked = []
    monkeypatch.setattr(discovery, "assert_safe_url", checked.append)
    client_class = httpx.AsyncClient

    def transport(handler):
        monkeypatch.setattr(discovery.httpx, "AsyncClient", lambda **kwargs: client_class(
            **{key: value for key, value in kwargs.items() if key not in ("transport", "trust_env")}, transport=httpx.MockTransport(handler), trust_env=False,
        ))

    return path, checked, transport


@pytest.mark.asyncio
async def test_submit_url_fetches_body_and_saves_serializable_evidence(discovery_env):
    path, checked, transport = discovery_env
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, text=EDU_HTML)

    transport(handler)
    result = await discovery.submit_url("test-school", URL)
    assert [r.method for r in requests] == ["GET"]
    assert checked == [URL]
    assert result["error"] is None
    assert result["provider"] == "ZHENGFANG"
    assert result["is_edu_page"] is True
    assert result["verification_status"] == "VERIFIED_OFFICIAL"
    saved = json.loads(path.read_text(encoding="utf-8"))["candidates"][0]
    assert saved["evidence"] == result["evidence"]
    assert isinstance(saved["evidence"][0], dict)


@pytest.mark.asyncio
async def test_redirect_checks_each_target_and_uses_final_origin(discovery_env):
    _, checked, transport = discovery_env
    final_url = "https://vendor.example.com/login"

    def handler(request):
        if str(request.url) == URL:
            return httpx.Response(302, headers={"location": final_url})
        return httpx.Response(200, text=EDU_HTML)

    transport(handler)
    result = await discovery.submit_url("test-school", URL)
    assert checked == [URL, final_url]
    assert result["final_url"] == final_url
    assert result["verification_status"] == "VERIFIED_LIVE"


@pytest.mark.asyncio
async def test_redirect_to_loopback_is_blocked_before_fetch(discovery_env, monkeypatch):
    _, _, transport = discovery_env
    requests = []
    monkeypatch.setattr(discovery, "assert_safe_url", lambda url: (
        assert_safe_url(url) if "127.0.0.1" in url else None
    ))

    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    transport(handler)
    result = await discovery.submit_url("test-school", URL)
    assert len(requests) == 1
    assert result["verification_status"] == "DEAD"
    assert "loopback" in result["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status, html, expected", [
    (200, "<title>普通网页</title>", "CANDIDATE"),
    (503, EDU_HTML, "DEAD"),
])
async def test_submit_url_does_not_verify_non_edu_or_error_pages(discovery_env, status, html, expected):
    _, _, transport = discovery_env
    transport(lambda request: httpx.Response(status, text=html))
    result = await discovery.submit_url("test-school", URL)
    assert result["verification_status"] == expected
    assert result["error"] is None


@pytest.mark.asyncio
async def test_detector_bug_does_not_persist_a_dead_candidate(discovery_env, monkeypatch):
    path, _, transport = discovery_env
    transport(lambda request: httpx.Response(200, text=EDU_HTML))

    def broken_detector(*args, **kwargs):
        raise TypeError("detector implementation failed")

    monkeypatch.setattr(discovery.ProviderDetector, "detect", broken_detector)
    with pytest.raises(TypeError, match="implementation failed"):
        await discovery.submit_url("test-school", URL)
    assert not path.exists()


@pytest.mark.asyncio
async def test_unreachable_page_is_saved_as_dead(discovery_env):
    path, _, transport = discovery_env

    def handler(request):
        raise httpx.ConnectError("connection unavailable", request=request)

    transport(handler)
    result = await discovery.submit_url("test-school", URL)
    assert result["reachable"] is False
    assert result["verification_status"] == "DEAD"
    assert path.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("university_id, school_code, school_name", [
    ("shared", "shared", "代码最后项"),
    ("同名高校", "name-last", "同名高校"),
])
async def test_university_lookup_loads_once_and_preserves_code_priority(
    discovery_env, monkeypatch, university_id, school_code, school_name,
):
    _, _, transport = discovery_env
    load_universities = Mock(return_value=[
        {"school_code": "shared", "name": "代码首项"},
        {"school_code": "shared", "name": "代码最后项"},
        {"school_code": "name-collision", "name": "shared"},
        {"school_code": "name-first", "name": "同名高校"},
        {"school_code": "name-last", "name": "同名高校"},
    ])
    monkeypatch.setattr(discovery, "_load_universities", load_universities)
    transport(lambda request: httpx.Response(200, text=EDU_HTML))

    result = await discovery.submit_url(university_id, URL)

    assert result["school_code"] == school_code
    assert result["school_name"] == school_name
    assert result["error"] is None
    load_universities.assert_called_once_with()
