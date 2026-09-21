"""阶段 1 —— 部署配置、契约指纹与服务兼容性。

覆盖：
- 内部 `MAGICCLASS_BASE_URL` 与浏览器 `MAGICCLASS_EMBED_ORIGIN` 分离，公开 Origin 不得是内部地址；
- 三个**只读**探针组成的契约指纹（绝不创建生成任务）；
- configured / available / unavailable / incompatible / degraded 五态；
- 健康探测不得因为"配置非空"就返回可用；
- 版本字符串只用于记录，不能单独决定兼容；
- URL 校验比较 scheme + host + port。

全部通过 `httpx.MockTransport` 模拟 magic class，不伪造真实生成结果。
"""
from __future__ import annotations

import base64
from typing import Any, Callable, Dict, List

import httpx
import pytest

from app.core.config import Settings
from app.core.semver import (
    DEFAULT_ALLOWED_VERSIONS,
    parse_semver,
    parse_version_spec,
    version_satisfies,
)
from app.services.magicclass.classroom_service import MagicClassClassroomService
from app.services.magicclass.client import MagicClassClient
from app.services.magicclass.errors import MagicClassInvalidOrigin
from app.services.magicclass.result_store import MagicClassResultStore

INTERNAL = "http://magicclass.internal:3000"
PUBLIC = "https://classroom.example.com"

FULL_CAPS = {
    "webSearch": True,
    "imageGeneration": True,
    "videoGeneration": True,
    "tts": True,
}


# ===== 脚手架 =====


def _test_settings(**overrides) -> Settings:
    kwargs = dict(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        llm_provider="none",
        agent_allow_mock_providers=True,
        magicclass_enabled=True,
        magicclass_base_url=INTERNAL,
        magicclass_embed_origin=PUBLIC,
    )
    kwargs.update(overrides)
    return Settings(**kwargs)


def _production_settings(**overrides) -> Settings:
    """满足 production 强约束的最小集合，用于验证生产专属校验。"""
    kwargs = dict(
        app_env="production",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=False,
        agent_allow_mock_providers=False,
        jwt_secret="x" * 48,
        edu_session_store="encrypted_sqlite",
        edu_session_encryption_key=base64.b64encode(b"k" * 32).decode(),
        edu_session_encryption_key_id="test-key",
        llm_provider="none",
        magicclass_enabled=True,
        magicclass_base_url=INTERNAL,
        magicclass_embed_origin=PUBLIC,
    )
    kwargs.update(overrides)
    return Settings(**kwargs)


def _contract_handler(
    recorder: List[httpx.Request],
    *,
    version: str = "1.0.1",
    capabilities: Dict[str, bool] | None = None,
    health_payload: Dict[str, Any] | None = None,
    health_status: int = 200,
    access_payload: Dict[str, Any] | None = None,
    access_status: int = 200,
    probe_status: int = 404,
    probe_payload: Dict[str, Any] | None = None,
    submit_response: httpx.Response | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    """模拟真实 magic class 的三个探针端点。"""

    def handler(request: httpx.Request) -> httpx.Response:
        recorder.append(request)
        path = request.url.path
        if path.endswith("/api/access-code/status"):
            body = access_payload
            if body is None:
                body = {"success": True, "enabled": False, "authenticated": False}
            return httpx.Response(access_status, json=body)
        if path.endswith("/api/health"):
            body = health_payload
            if body is None:
                body = {
                    "success": True,
                    "status": "ok",
                    "version": version,
                    "capabilities": FULL_CAPS if capabilities is None else capabilities,
                }
            return httpx.Response(health_status, json=body)
        if path.startswith("/api/generate-classroom/"):
            if probe_payload is not None or probe_status != 404:
                body = probe_payload
                if body is None:
                    body = {
                        "success": False,
                        "errorCode": "INVALID_REQUEST",
                        "error": "Classroom generation job not found",
                    }
                return httpx.Response(probe_status, json=body)
            return httpx.Response(
                404,
                json={
                    "success": False,
                    "errorCode": "INVALID_REQUEST",
                    "error": "Classroom generation job not found",
                },
            )
        if request.method == "POST" and path.endswith("/api/generate-classroom"):
            if submit_response is not None:
                return submit_response
            return httpx.Response(202, json={"success": True, "jobId": "job_1"})
        return httpx.Response(
            404,
            json={"success": False, "errorCode": "INVALID_REQUEST", "error": "not found"},
        )

    return handler


def _client(handler, **overrides) -> MagicClassClient:
    settings = _test_settings(**overrides)
    return MagicClassClient(
        base_url=settings.magicclass_base_url,
        timeout_seconds=5.0,
        probe_timeout_seconds=settings.magicclass_health_timeout_seconds,
        origin=settings.magicclass_origin,
        transport=httpx.MockTransport(handler),
        access_code=settings.magicclass_access_code,
    )


def _service(tmp_path, handler, **overrides) -> MagicClassClassroomService:
    settings = _test_settings(**overrides)
    store = MagicClassResultStore(tmp_path / "rooms")
    client = _client(handler, **overrides)
    return MagicClassClassroomService(settings, store, client=client)


# ===== A. 版本范围工具 =====


def test_parse_semver_handles_prerelease_and_rejects_junk():
    assert parse_semver("1.2.3") == (1, 2, 3)
    assert parse_semver("1.0.1-rc.1") == (1, 0, 1)
    assert parse_semver("1.0.1+build.9") == (1, 0, 1)
    assert parse_semver(" 2.0.0 ") == (2, 0, 0)
    for junk in ("", "v1.0.0", "1.0", "abc", None, 1.0):
        assert parse_semver(junk) is None


def test_version_spec_rejects_invalid_syntax_at_config_time():
    with pytest.raises(ValueError):
        parse_version_spec("1.0.0")
    with pytest.raises(ValueError):
        parse_version_spec("")
    with pytest.raises(ValueError):
        parse_version_spec("~1.0.0")
    assert parse_version_spec(DEFAULT_ALLOWED_VERSIONS) == (
        (">=", (1, 0, 0)),
        ("<", (2, 0, 0)),
    )


def test_version_satisfies_returns_none_when_undecidable():
    assert version_satisfies("1.0.1", DEFAULT_ALLOWED_VERSIONS) is True
    assert version_satisfies("1.9.9", DEFAULT_ALLOWED_VERSIONS) is True
    assert version_satisfies("2.0.0", DEFAULT_ALLOWED_VERSIONS) is False
    assert version_satisfies("0.9.0", DEFAULT_ALLOWED_VERSIONS) is False
    # 无法判定 ≠ 不兼容
    assert version_satisfies("0.1.0-dev", ">=2.0.0") is False
    assert version_satisfies("", DEFAULT_ALLOWED_VERSIONS) is None
    assert version_satisfies("unknown", DEFAULT_ALLOWED_VERSIONS) is None


# ===== B. 配置校验：公开 Origin 与内部地址分离 =====


def test_embed_origin_accepts_distinct_public_origin():
    s = _test_settings()
    assert s.magicclass_embed_origin == PUBLIC
    assert s.magicclass_origin == INTERNAL


def test_embed_origin_rejects_credentials_query_fragment_and_path():
    for bad in (
        "https://user:pw@classroom.example.com",
        "https://classroom.example.com/?x=1",
        "https://classroom.example.com/#frag",
        "https://classroom.example.com/magicclass",
        "ftp://classroom.example.com",
        "classroom.example.com",
    ):
        with pytest.raises(ValueError):
            _test_settings(magicclass_embed_origin=bad)


def test_embed_origin_rejects_unspecified_and_link_local_in_any_env():
    for bad in ("http://0.0.0.0:3000", "http://169.254.169.254", "http://[::]"):
        with pytest.raises(ValueError):
            _test_settings(magicclass_embed_origin=bad)
        with pytest.raises(ValueError):
            _production_settings(magicclass_embed_origin=bad)


def test_embed_origin_rejects_internal_address_in_production():
    for bad in (
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://10.0.0.5",
        "http://192.168.1.10",
        "http://magicclass.internal",
    ):
        with pytest.raises(ValueError):
            _production_settings(magicclass_embed_origin=bad)


def test_embed_origin_allows_loopback_in_development():
    s = _test_settings(magicclass_embed_origin="http://127.0.0.1:3000")
    assert s.magicclass_embed_origin == "http://127.0.0.1:3000"


def test_embed_origin_must_be_https_in_production():
    with pytest.raises(ValueError):
        _production_settings(magicclass_embed_origin="http://classroom.example.com")


def test_allowed_versions_spec_validated_on_startup():
    with pytest.raises(ValueError):
        _test_settings(magicclass_allowed_versions="not-a-range")
    assert _test_settings(magicclass_allowed_versions=">=1.0.0 <2.0.0").magicclass_allowed_versions


def test_new_magicclass_limits_are_validated():
    with pytest.raises(ValueError):
        _test_settings(magicclass_health_timeout_seconds=0)
    with pytest.raises(ValueError):
        _test_settings(magicclass_probe_ttl_seconds=-1)
    with pytest.raises(ValueError):
        _test_settings(magicclass_poll_interval_ms=10)
    with pytest.raises(ValueError):
        _test_settings(magicclass_poll_max_seconds=1)


def test_external_3d_defaults_available_and_can_be_disabled():
    assert _test_settings().magicclass_external_3d_available is True
    assert _test_settings(magicclass_external_3d_available=False).magicclass_external_3d_available is False


# ===== C. 契约指纹 =====


def test_probe_passes_against_real_magicclass_contract(tmp_path):
    rec: List[httpx.Request] = []
    client = _client(_contract_handler(rec))
    import asyncio

    probe = asyncio.run(client.probe())
    assert probe.ok is True
    assert probe.checks == {"health": True, "access_code": True, "generate_classroom": True}
    assert probe.version == "1.0.1"
    assert probe.capabilities == FULL_CAPS
    assert probe.unreachable is False


def test_probe_never_creates_a_generation_job(tmp_path):
    """契约指纹必须是零成本只读：不得 POST /api/generate-classroom。"""
    rec: List[httpx.Request] = []
    client = _client(_contract_handler(rec))
    import asyncio

    asyncio.run(client.probe())
    assert rec, "探针应当真的访问了目标服务"
    posts = [r for r in rec if r.method == "POST"]
    assert posts == [], f"探针不允许产生写请求: {[str(r.url) for r in posts]}"
    assert {r.method for r in rec} == {"GET"}


def test_probe_health_without_success_flag_is_incompatible(tmp_path):
    rec: List[httpx.Request] = []
    handler = _contract_handler(
        rec, health_payload={"status": "ok", "version": "1.0.1", "capabilities": FULL_CAPS}
    )
    import asyncio

    probe = asyncio.run(_client(handler).probe())
    assert probe.ok is False
    assert probe.checks["health"] is False
    assert probe.failed_check == "health"


def test_probe_health_without_capabilities_object_is_incompatible(tmp_path):
    rec: List[httpx.Request] = []
    handler = _contract_handler(
        rec, health_payload={"success": True, "status": "ok", "version": "1.0.1"}
    )
    import asyncio

    probe = asyncio.run(_client(handler).probe())
    assert probe.ok is False
    assert probe.failed_check == "health"


def test_probe_missing_generate_classroom_family_is_incompatible(tmp_path):
    """目标服务的作业族不存在（例如返回 200）时必须判不兼容，而不是当作可用。"""
    rec: List[httpx.Request] = []
    handler = _contract_handler(rec, probe_status=200, probe_payload={"success": True})
    import asyncio

    probe = asyncio.run(_client(handler).probe())
    assert probe.ok is False
    assert probe.checks["generate_classroom"] is False
    assert probe.failed_check == "generate_classroom"


def test_probe_wrong_error_code_is_incompatible(tmp_path):
    rec: List[httpx.Request] = []
    handler = _contract_handler(
        rec,
        probe_status=404,
        probe_payload={"success": False, "errorCode": "SOMETHING_ELSE", "error": "nope"},
    )
    import asyncio

    probe = asyncio.run(_client(handler).probe())
    assert probe.ok is False
    assert probe.failed_check == "generate_classroom"


def test_probe_access_code_status_must_expose_boolean_enabled(tmp_path):
    rec: List[httpx.Request] = []
    handler = _contract_handler(rec, access_payload={"success": True})
    import asyncio

    probe = asyncio.run(_client(handler).probe())
    assert probe.ok is False
    assert probe.failed_check == "access_code"


def test_probe_maps_network_failure_to_unreachable_not_incompatible(tmp_path):
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    import asyncio

    probe = asyncio.run(_client(boom).probe())
    assert probe.ok is False
    assert probe.unreachable is True
    assert probe.reason


def test_probe_fails_closed_when_access_code_required_but_unset(tmp_path):
    rec: List[httpx.Request] = []
    handler = _contract_handler(
        rec, access_payload={"success": True, "enabled": True, "authenticated": False}
    )
    import asyncio

    probe = asyncio.run(_client(handler).probe())
    assert probe.ok is False
    assert probe.access_code_required is True
    assert probe.authenticated is False


# ===== D. status 五态契约 =====


def test_status_exposes_public_embed_origin_never_internal(tmp_path):
    rec: List[httpx.Request] = []
    import asyncio

    status = asyncio.run(_service(tmp_path, _contract_handler(rec)).status())
    assert status["configured"] is True
    assert status["available"] is True
    assert status["enabled"] is True
    assert status["embed_origin"] == PUBLIC
    assert INTERNAL not in str(status["embed_origin"])
    assert status["compatibility"] == "compatible"
    assert status["incompatible"] is False


def test_status_embed_origin_is_null_when_not_configured(tmp_path):
    import asyncio

    service = _service(
        tmp_path,
        _contract_handler([]),
        magicclass_enabled=False,
        magicclass_embed_origin="",
    )
    status = asyncio.run(service.status())
    assert status["configured"] is False
    assert status["enabled"] is False
    assert status["embed_origin"] is None
    assert status["browser_embed_available"] is False


def test_status_unavailable_when_service_unreachable(tmp_path):
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    import asyncio

    status = asyncio.run(_service(tmp_path, boom).status())
    assert status["configured"] is True
    assert status["available"] is False
    assert status["unavailable"] is True
    assert status["enabled"] is False
    assert status["reason"]


def test_status_reports_incompatible_distinct_from_unavailable(tmp_path):
    rec: List[httpx.Request] = []
    handler = _contract_handler(rec, health_payload={"success": True, "status": "weird"})
    import asyncio

    status = asyncio.run(_service(tmp_path, handler).status())
    assert status["compatibility"] == "incompatible"
    assert status["incompatible"] is True
    assert status["available"] is False
    assert status["unavailable"] is False
    assert status["enabled"] is False


def test_version_out_of_range_is_recorded_but_never_fatal(tmp_path):
    """版本越界只告警。

    magicclass 的 Docker 镜像不经过 npm 脚本启动，`npm_package_version` 取不到，
    `/api/health` 会回落成硬编码的 `0.1.0` —— 合法但错误的 semver。
    若按版本范围硬性拒绝，真实部署会被误判为不兼容，功能直接不可用。
    因此兼容性只由契约指纹决定，版本越界写入 version_out_of_range 供运维排查。
    """
    rec: List[httpx.Request] = []
    handler = _contract_handler(rec, version="2.5.0")
    import asyncio

    status = asyncio.run(_service(tmp_path, handler).status())
    assert status["version"] == "2.5.0"
    assert status["version_out_of_range"] is True
    assert status["incompatible"] is False
    assert status["available"] is True
    assert status["enabled"] is True
    assert status["compatibility"] == "compatible"
    assert status["compatibility_reason"]


def test_status_version_alone_does_not_decide_compatibility(tmp_path):
    """Docker 回落值 0.1.0：可解析但越界 —— 仍必须按契约指纹放行。"""
    rec: List[httpx.Request] = []
    handler = _contract_handler(rec, version="0.1.0")
    import asyncio

    status = asyncio.run(_service(tmp_path, handler).status())
    assert status["version"] == "0.1.0"
    assert status["version_source"] == "reported"
    assert status["version_out_of_range"] is True
    assert status["compatibility"] == "compatible"
    assert status["incompatible"] is False
    assert status["available"] is True


def test_status_version_source_unknown_when_not_semver(tmp_path):
    rec: List[httpx.Request] = []
    handler = _contract_handler(rec, version="")
    import asyncio

    status = asyncio.run(_service(tmp_path, handler).status())
    assert status["version_source"] == "unknown"
    assert status["version_out_of_range"] is False
    assert status["incompatible"] is False
    assert status["available"] is True


def test_status_version_source_is_reported_when_version_parsable(tmp_path):
    rec: List[httpx.Request] = []
    import asyncio

    status = asyncio.run(_service(tmp_path, _contract_handler(rec, version="1.0.1")).status())
    assert status["version_source"] == "reported"


def test_status_degraded_when_optional_capabilities_missing(tmp_path):
    rec: List[httpx.Request] = []
    handler = _contract_handler(
        rec, capabilities={"webSearch": True, "imageGeneration": False, "videoGeneration": True, "tts": False}
    )
    import asyncio

    status = asyncio.run(_service(tmp_path, handler).status())
    assert status["available"] is True
    assert status["degraded"] is True
    assert set(status["unavailable_capabilities"]) == {"imageGeneration", "tts"}


def test_status_not_degraded_when_all_capabilities_present(tmp_path):
    rec: List[httpx.Request] = []
    import asyncio

    status = asyncio.run(_service(tmp_path, _contract_handler(rec)).status())
    assert status["degraded"] is False
    assert status["unavailable_capabilities"] == []


def test_operator_switches_and_health_intersect(tmp_path):
    """运维开关只能收紧，不能放开服务端未启用的能力。"""
    rec: List[httpx.Request] = []
    handler = _contract_handler(
        rec, capabilities={"webSearch": False, "imageGeneration": True, "videoGeneration": True, "tts": True}
    )
    import asyncio

    status = asyncio.run(
        _service(tmp_path, handler, magicclass_enable_image_generation=False).status()
    )
    assert status["capabilities"]["imageGeneration"] is False  # 运维关闭
    assert status["capabilities"]["webSearch"] is False  # 服务端未启用
    assert status["capabilities"]["tts"] is True


def test_status_probe_is_cached_within_ttl(tmp_path):
    rec: List[httpx.Request] = []
    service = _service(tmp_path, _contract_handler(rec))
    import asyncio

    async def twice():
        await service.status()
        first = len(rec)
        await service.status()
        return first, len(rec)

    first, second = asyncio.run(twice())
    assert first > 0
    assert second == first, "TTL 内不应重复探测目标服务"


def test_status_probe_cache_expires(tmp_path):
    rec: List[httpx.Request] = []
    service = _service(tmp_path, _contract_handler(rec), magicclass_probe_ttl_seconds=0)
    import asyncio

    async def twice():
        await service.status()
        first = len(rec)
        await service.status()
        return first, len(rec)

    first, second = asyncio.run(twice())
    assert second > first, "TTL=0 时必须重新探测"


def test_health_never_reported_available_from_config_alone(tmp_path):
    """配置非空但服务返回 500 —— 不得因为配置存在就报告可用。"""
    rec: List[httpx.Request] = []
    handler = _contract_handler(rec, health_status=500, health_payload={"success": False})
    import asyncio

    status = asyncio.run(_service(tmp_path, handler).status())
    assert status["configured"] is True
    assert status["available"] is False
    assert status["enabled"] is False


# ===== E. URL 校验：scheme + host + port =====


def _url_client() -> MagicClassClient:
    return MagicClassClient(base_url=INTERNAL, origin="https://classroom.example.com:8443")


def test_classroom_url_requires_exact_scheme_host_port():
    client = _url_client()
    ok = client._validate_classroom_url(
        "https://classroom.example.com:8443/classroom/room_1", "room_1"
    )
    assert ok == "https://classroom.example.com:8443/classroom/room_1"
    for bad in (
        "https://classroom.example.com/classroom/room_1",  # 端口不同
        "http://classroom.example.com:8443/classroom/room_1",  # scheme 不同
        "https://classroom.example.com:84430/classroom/room_1",  # 前缀混淆
        "https://evil.example.com:8443/classroom/room_1",
        "https://classroom.example.com:8443/classroom/room_1?x=1",
        "https://classroom.example.com:8443/classroom/room_1#f",
        "https://classroom.example.com:8443/classroom/room_1/../room_2",
        "javascript:alert(1)",
        "data:text/html,<script>1</script>",
        "file:///etc/passwd",
        "https://classroom.example.com:8443/classroom/room_2",
    ):
        with pytest.raises(MagicClassInvalidOrigin):
            client._validate_classroom_url(bad, "room_1")


def test_classroom_url_rejects_credentials_in_url():
    client = _url_client()
    with pytest.raises(MagicClassInvalidOrigin):
        client._validate_classroom_url(
            "https://u:p@classroom.example.com:8443/classroom/room_1", "room_1"
        )


def test_classroom_url_passes_none_through():
    assert _url_client()._validate_classroom_url(None, None) is None
