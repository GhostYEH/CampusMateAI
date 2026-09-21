"""FastAPI 网关的 workspace/stage 边界测试。

网关是浏览器唯一能到受管服务的门，所以这里重点验证它**自己**要负责的四件事：
身份不由客户端指定、重试必须显式、上游状态被翻译成浏览器能处理的状态、
内部地址与断言永不外泄。受管服务本身由 `magicclass-service/tests/workspace.test.mjs`
覆盖，这里用替身隔离。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import magicclass_fusion, magicclass_workspaces
from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.magicclass.fusion_client import MagicClassFusionClient
from app.services.magicclass.fusion_errors import FusionUnavailable
from app.services.magicclass.service_assertion import decode_service_assertion

SECRET = "gateway-secret"
SERVICE_URL = "http://magicclass.internal:4010"


class _RecordingTransport:
    """替身：记录上游请求，按脚本回放响应。"""

    def __init__(self, script=None):
        self.calls = []
        self.script = list(script or [])
        self.default = (200, {"items": [], "next_cursor": None})

    def _next(self):
        return self.script.pop(0) if self.script else self.default

    async def get(self, url, *, headers=None, timeout=None, params=None):
        self.calls.append({"method": "GET", "url": url, "headers": headers or {}, "params": params})
        return _Response(*self._next())

    async def request(self, method, url, *, headers=None, timeout=None, json=None):
        self.calls.append(
            {"method": method, "url": url, "headers": headers or {}, "json": json}
        )
        return _Response(*self._next())


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _test_settings(**overrides) -> Settings:
    kwargs = dict(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        llm_provider="none",
        agent_allow_mock_providers=True,
        magicclass_fusion_enabled=True,
        magicclass_service_url=SERVICE_URL,
        magicclass_internal_secret=SECRET,
    )
    kwargs.update(overrides)
    return Settings(**kwargs)


def _setup(script=None, **settings_overrides):
    container = reset_container_for_tests(_test_settings(**settings_overrides))
    seed_demo_data(container, force=True)
    transport = _RecordingTransport(script)
    client = MagicClassFusionClient(
        base_url=container.settings.magicclass_service_url,
        secret=container.settings.magicclass_internal_secret,
        transport=transport,
    )
    app = create_app()
    app.dependency_overrides[magicclass_workspaces._client] = lambda: client
    http = TestClient(app)
    login = http.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    courses = http.get("/api/v1/courses", headers=headers).json()["items"]
    return container, transport, http, headers, courses[0]["id"]


def _workspace_payload(**overrides):
    payload = {
        "id": "ws_1",
        "course_id": "course-1",
        "name": "期末复习",
        "description": "",
        "revision": 1,
        "created_at": "2026-01-01T00:00:00.000Z",
        "updated_at": "2026-01-01T00:00:00.000Z",
    }
    payload.update(overrides)
    return payload


def test_fusion_status_route_exposes_workspace_only_when_container_enables_it():
    container, transport, http, headers, _ = _setup([
        (200, {"status": "ready", "capabilities": ["workspace"]}),
    ])
    client = MagicClassFusionClient(
        base_url=container.settings.magicclass_service_url,
        secret=container.settings.magicclass_internal_secret,
        transport=transport,
    )
    http.app.dependency_overrides[magicclass_fusion._client] = lambda: client

    response = http.get("/api/v1/magicclass/fusion/status", headers=headers)

    assert response.status_code == 200
    assert response.json()["state"] == "ready"
    assert response.json()["capabilities"] == ["workspace"]
    assert len(transport.calls) == 1


def test_fusion_status_route_stays_disabled_without_contacting_service():
    container, transport, http, headers, _ = _setup(magicclass_fusion_enabled=False)
    client = MagicClassFusionClient(
        base_url=container.settings.magicclass_service_url,
        secret=container.settings.magicclass_internal_secret,
        transport=transport,
    )
    http.app.dependency_overrides[magicclass_fusion._client] = lambda: client

    response = http.get("/api/v1/magicclass/fusion/status", headers=headers)

    assert response.status_code == 200
    assert response.json()["state"] == "disabled"
    assert response.json()["capabilities"] == []
    assert transport.calls == []


# ===== 正常路径 =====


def test_create_forwards_name_and_a_scoped_assertion():
    container, transport, http, headers, course_id = _setup([
        (201, _workspace_payload()),
    ])

    response = http.post(
        f"/api/v1/courses/{course_id}/workspaces",
        json={"name": "期末复习"},
        headers={**headers, "Idempotency-Key": "key-1"},
    )

    assert response.status_code == 201
    assert response.json()["id"] == "ws_1"
    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["json"] == {"name": "期末复习", "description": ""}
    assert call["headers"]["Idempotency-Key"] == "key-1"

    claims = decode_service_assertion(
        call["headers"]["X-CampusMate-Service-Assertion"], secret=SECRET
    )
    assert claims["course_id"] == course_id
    assert claims["scope"] == ["workspace:read", "workspace:write"]
    # 归属来自服务端身份，不由请求体指定
    assert claims["sub"]


def test_reads_use_the_read_scope_and_the_path_course():
    _, transport, http, headers, course_id = _setup()

    http.get(f"/api/v1/courses/{course_id}/workspaces", headers=headers)

    call = transport.calls[0]
    claims = decode_service_assertion(
        call["headers"]["X-CampusMate-Service-Assertion"], secret=SECRET
    )
    assert claims["scope"] == ["workspace:read"]
    assert call["url"] == f"{SERVICE_URL}/internal/courses/{course_id}/workspaces"


def test_update_and_delete_send_if_match_as_a_revision():
    _, transport, http, headers, course_id = _setup([
        (200, _workspace_payload(revision=2)),
        (200, {"deleted": True}),
    ])

    patched = http.patch(
        f"/api/v1/courses/{course_id}/workspaces/ws_1",
        json={"name": "新名字"},
        headers={**headers, "If-Match": '"1"'},
    )
    assert patched.status_code == 200
    assert patched.json()["revision"] == 2
    assert transport.calls[0]["headers"]["If-Match"] == "1"

    deleted = http.delete(
        f"/api/v1/courses/{course_id}/workspaces/ws_1",
        headers={**headers, "If-Match": "2"},
    )
    assert deleted.status_code == 200
    assert transport.calls[1]["headers"]["If-Match"] == "2"


def test_a_stage_list_omits_the_document_but_a_single_fetch_returns_it():
    _, transport, http, headers, course_id = _setup([
        (200, {"items": [{"id": "stg_1", "workspace_id": "ws_1", "course_id": "c",
                          "title": "第一节", "revision": 1, "dsl_version": "0.3.0",
                          "created_at": "", "updated_at": ""}], "next_cursor": None}),
        (200, {"id": "stg_1", "workspace_id": "ws_1", "course_id": "c", "title": "第一节",
               "revision": 1, "dsl_version": "0.3.0", "created_at": "", "updated_at": "",
               "document": {"dslVersion": "0.3.0", "stage": {"id": "s"}, "scenes": []}}),
    ])

    listing = http.get(
        f"/api/v1/courses/{course_id}/workspaces/ws_1/stages", headers=headers
    )
    assert listing.status_code == 200
    assert "document" not in listing.json()["items"][0]

    single = http.get(
        f"/api/v1/courses/{course_id}/workspaces/ws_1/stages/stg_1", headers=headers
    )
    assert single.status_code == 200
    assert single.json()["document"]["dslVersion"] == "0.3.0"


# ===== 重试安全：两个头都必须显式 =====


def test_a_create_without_an_idempotency_key_is_refused_before_calling_upstream():
    _, transport, http, headers, course_id = _setup()

    response = http.post(
        f"/api/v1/courses/{course_id}/workspaces", json={"name": "x"}, headers=headers
    )

    assert response.status_code == 400
    assert response.json()["code"] == "MAGICCLASS_INVALID_REQUEST"
    assert transport.calls == [], "拒绝必须发生在调用上游之前"


def test_a_conditional_write_without_if_match_is_refused():
    _, transport, http, headers, course_id = _setup()

    patched = http.patch(
        f"/api/v1/courses/{course_id}/workspaces/ws_1", json={"name": "x"}, headers=headers
    )
    assert patched.status_code == 400
    assert "If-Match" in patched.json()["message"]

    deleted = http.delete(f"/api/v1/courses/{course_id}/workspaces/ws_1", headers=headers)
    assert deleted.status_code == 400

    replaced = http.put(
        f"/api/v1/courses/{course_id}/workspaces/ws_1/stages/stg_1",
        json={"document": {}},
        headers=headers,
    )
    assert replaced.status_code == 400

    assert transport.calls == []


def test_if_match_star_is_refused_because_it_is_the_lost_update():
    _, transport, http, headers, course_id = _setup()

    response = http.patch(
        f"/api/v1/courses/{course_id}/workspaces/ws_1",
        json={"name": "x"},
        headers={**headers, "If-Match": "*"},
    )

    assert response.status_code == 400
    assert transport.calls == []


def test_a_patch_with_no_fields_is_refused():
    _, transport, http, headers, course_id = _setup()

    response = http.patch(
        f"/api/v1/courses/{course_id}/workspaces/ws_1",
        json={},
        headers={**headers, "If-Match": "1"},
    )

    assert response.status_code == 400
    assert transport.calls == []


# ===== 上游状态翻译 =====


def test_a_service_412_becomes_a_409_for_the_browser():
    _, _, http, headers, course_id = _setup([(412, {"error": "revision_mismatch"})])

    response = http.patch(
        f"/api/v1/courses/{course_id}/workspaces/ws_1",
        json={"name": "x"},
        headers={**headers, "If-Match": "1"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "MAGICCLASS_REVISION_CONFLICT"


def test_a_service_idempotency_conflict_is_reported_as_its_own_code():
    _, _, http, headers, course_id = _setup([
        (409, {"error": "idempotency_conflict"})
    ])

    response = http.post(
        f"/api/v1/courses/{course_id}/workspaces",
        json={"name": "x"},
        headers={**headers, "Idempotency-Key": "reused"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "MAGICCLASS_IDEMPOTENCY_CONFLICT"


def test_a_service_404_stays_a_404_without_confirming_existence():
    _, _, http, headers, course_id = _setup([(404, {"error": "not_found"})])

    response = http.get(
        f"/api/v1/courses/{course_id}/workspaces/ws_missing", headers=headers
    )

    assert response.status_code == 404
    assert response.json()["code"] == "MAGICCLASS_WORKSPACE_NOT_FOUND"
    assert "ws_missing" not in response.text


def test_a_rejected_document_carries_the_issues_but_not_the_service_body():
    _, _, http, headers, course_id = _setup([
        (422, {
            "error": "document_rejected",
            "message": "dsl: 文档校验失败（1 项）",
            "issues": [{"code": "scene_type_invalid", "path": "scenes[0].type", "message": "无效"}],
            "internal_hint": "should not be relayed",
        })
    ])

    response = http.post(
        f"/api/v1/courses/{course_id}/workspaces/ws_1/stages",
        json={"title": "t", "document": {"stage": {"id": "s"}, "scenes": []}},
        headers={**headers, "Idempotency-Key": "k"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "MAGICCLASS_DOCUMENT_REJECTED"
    assert body["details"]["issues"][0]["code"] == "scene_type_invalid"
    assert "internal_hint" not in response.text


def test_an_oversize_document_reports_the_named_limit():
    _, _, http, headers, course_id = _setup([
        (422, {"error": "document_rejected", "message": "too big", "limit": "maxDocumentBytes"})
    ])

    response = http.post(
        f"/api/v1/courses/{course_id}/workspaces/ws_1/stages",
        json={"title": "t", "document": {}},
        headers={**headers, "Idempotency-Key": "k"},
    )

    assert response.status_code == 422
    assert response.json()["details"]["limit"] == "maxDocumentBytes"


def test_an_assertion_the_service_rejects_is_reported_as_unavailable_not_as_a_client_error():
    for status in (401, 403):
        _, _, http, headers, course_id = _setup([(status, {"error": "unauthorized"})])
        response = http.get(
            f"/api/v1/courses/{course_id}/workspaces", headers=headers
        )
        assert response.status_code == 503, status
        assert response.json()["code"] == "MAGICCLASS_FUSION_UNAVAILABLE", status


def test_a_transport_failure_never_leaks_the_internal_address():
    class _Broken(_RecordingTransport):
        async def get(self, url, *, headers=None, timeout=None, params=None):
            raise RuntimeError(f"cannot reach {url}")

    container = reset_container_for_tests(_test_settings())
    seed_demo_data(container, force=True)
    client = MagicClassFusionClient(
        base_url=container.settings.magicclass_service_url,
        secret=container.settings.magicclass_internal_secret,
        transport=_Broken(),
    )
    app = create_app()
    app.dependency_overrides[magicclass_workspaces._client] = lambda: client
    http = TestClient(app)
    login = http.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    course_id = http.get("/api/v1/courses", headers=headers).json()["items"][0]["id"]

    response = http.get(f"/api/v1/courses/{course_id}/workspaces", headers=headers)

    assert response.status_code == 503
    assert SERVICE_URL not in response.text
    assert SECRET not in response.text
    assert "magicclass.internal" not in response.text


# ===== 开关与权限 =====


def test_the_routes_answer_unavailable_when_the_fusion_switch_is_off():
    _, transport, http, headers, course_id = _setup([], magicclass_fusion_enabled=False)

    response = http.get(f"/api/v1/courses/{course_id}/workspaces", headers=headers)

    # 空列表会被读成"你没有工作台"——服务关掉是另一个答案
    assert response.status_code == 503
    assert response.json()["code"] == "MAGICCLASS_FUSION_UNAVAILABLE"
    assert transport.calls == []


def test_a_course_the_student_cannot_see_is_refused_before_calling_upstream():
    container, transport, http, headers, _ = _setup()
    other_owner = container.user_repository.get_user_by_username("student_demo_01")
    other = container.course_repository.create_course(
        name="别人的课程", code="OTHER-1", owner_user_id=other_owner.id, provider="chaoxing"
    )

    response = http.get(f"/api/v1/courses/{other.id}/workspaces", headers=headers)

    assert response.status_code in (403, 404)
    assert transport.calls == []


def test_an_anonymous_request_is_rejected():
    _, transport, http, _, course_id = _setup()
    assert http.get(f"/api/v1/courses/{course_id}/workspaces").status_code == 401
    assert transport.calls == []


def test_the_limit_is_clamped_by_the_schema():
    _, transport, http, headers, course_id = _setup()

    assert http.get(
        f"/api/v1/courses/{course_id}/workspaces?limit=5000", headers=headers
    ).status_code == 422
    assert http.get(
        f"/api/v1/courses/{course_id}/workspaces?limit=0", headers=headers
    ).status_code == 422
    assert transport.calls == []


def test_pagination_passes_the_opaque_cursor_through_unchanged():
    _, transport, http, headers, course_id = _setup([
        (200, {"items": [], "next_cursor": "next-page-token"})
    ])

    response = http.get(
        f"/api/v1/courses/{course_id}/workspaces?limit=5&cursor=abc", headers=headers
    )

    assert response.status_code == 200
    assert transport.calls[0]["params"] == {"limit": 5, "cursor": "abc"}
    assert response.json()["next_cursor"] == "next-page-token"


def test_the_stage_create_forwards_the_document_verbatim():
    document = {
        "dslVersion": "0.3.0",
        "stage": {"id": "stage-1", "name": "演示", "createdAt": 1, "updatedAt": 2},
        "scenes": [],
    }
    _, transport, http, headers, course_id = _setup([
        (201, {"id": "stg_1", "workspace_id": "ws_1", "course_id": "c", "title": "第一节",
               "revision": 1, "dsl_version": "0.3.0", "created_at": "", "updated_at": "",
               "document": document})
    ])

    response = http.post(
        f"/api/v1/courses/{course_id}/workspaces/ws_1/stages",
        json={"title": "第一节", "document": document},
        headers={**headers, "Idempotency-Key": "k"},
    )

    assert response.status_code == 201
    # 网关不改写文档：校验与迁移是受管服务的职责，网关只做身份与重试
    assert transport.calls[0]["json"]["document"] == document


def test_an_omitted_document_is_not_invented_by_the_gateway():
    _, transport, http, headers, course_id = _setup([
        (201, {"id": "stg_1", "workspace_id": "ws_1", "course_id": "c", "title": "空",
               "revision": 1, "dsl_version": "0.3.0", "created_at": "", "updated_at": "",
               "document": {"scenes": []}})
    ])

    http.post(
        f"/api/v1/courses/{course_id}/workspaces/ws_1/stages",
        json={"title": "空"},
        headers={**headers, "Idempotency-Key": "k"},
    )

    assert "document" not in transport.calls[0]["json"], "空 stage 的构造属于服务端"


def test_each_request_gets_a_fresh_single_use_assertion():
    _, transport, http, headers, course_id = _setup()

    http.get(f"/api/v1/courses/{course_id}/workspaces", headers=headers)
    http.get(f"/api/v1/courses/{course_id}/workspaces", headers=headers)

    def jti_of(call):
        return decode_service_assertion(
            call["headers"]["X-CampusMate-Service-Assertion"], secret=SECRET
        )["jti"]

    assert jti_of(transport.calls[0]) != jti_of(transport.calls[1]), (
        "断言单次使用，两次请求不能复用同一个 jti"
    )


# ===== 失败原因映射（浏览器据此说哪句话）=====
#
# 这些 503 的 HTTP 状态码相同，但"下一步"完全不同：没启用要改部署、连不上可以
# 重试、服务自身依赖没就绪要等。所以网关必须把稳定 reason 带出去，否则界面只能
# 对三种处境说同一句话。


def _reason(response) -> str:
    return (response.json().get("details") or {}).get("reason")


def test_the_fusion_switch_off_reports_a_permanent_reason():
    _, transport, http, headers, course_id = _setup([], magicclass_fusion_enabled=False)

    response = http.get(f"/api/v1/courses/{course_id}/workspaces", headers=headers)

    assert response.status_code == 503
    assert _reason(response) == "fusion_disabled"
    assert transport.calls == [], "开关关着就不该去连服务"


def test_a_missing_internal_secret_is_refused_at_startup_not_at_request_time():
    """密钥缺失是**启动期**错误，不是运行期 503。

    网关在 fusion 打开时校验配置，缺密钥/地址直接拒绝启动。因此"请求时才发现没配
    好"这条路径在应用里不可达——把它做成 503 只会让部署错误伪装成临时故障。
    """
    import pytest
    from pydantic import ValidationError

    with pytest.raises((ValidationError, ValueError)):
        _test_settings(magicclass_internal_secret="")


def test_a_service_url_with_a_path_is_refused_at_startup():
    import pytest
    from pydantic import ValidationError

    with pytest.raises((ValidationError, ValueError)):
        _test_settings(magicclass_service_url=f"{SERVICE_URL}/internal")


async def test_a_client_constructed_without_configuration_reports_unconfigured():
    """纵深防御：绕过 Settings 直接构造的客户端也必须 fail-closed。"""
    transport = _RecordingTransport()
    client = MagicClassFusionClient(base_url="", secret="", transport=transport)

    with pytest.raises(FusionUnavailable) as excinfo:
        await client.list_workspaces(user_id="u1", course_id="c1")

    assert excinfo.value.details == {"reason": "service_unconfigured"}
    assert transport.calls == [], "没配好就不该发出任何出站请求"


async def test_the_status_route_reports_unconfigured_without_contacting_anyone():
    transport = _RecordingTransport()
    client = MagicClassFusionClient(base_url="", secret="", transport=transport)

    status = await client.status(user_id="u1")

    assert status.state.value == "unavailable"
    assert status.reason == "service_unconfigured"
    assert status.capabilities == []
    assert transport.calls == []


def test_an_unreachable_node_service_is_reported_as_retryable():
    class _Broken(_RecordingTransport):
        async def get(self, url, *, headers=None, timeout=None, params=None):
            raise RuntimeError(f"cannot reach {url}")

    container = reset_container_for_tests(_test_settings())
    seed_demo_data(container, force=True)
    client = MagicClassFusionClient(
        base_url=container.settings.magicclass_service_url,
        secret=container.settings.magicclass_internal_secret,
        transport=_Broken(),
    )
    app = create_app()
    app.dependency_overrides[magicclass_workspaces._client] = lambda: client
    http = TestClient(app)
    login = http.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    course_id = http.get("/api/v1/courses", headers=headers).json()["items"][0]["id"]

    response = http.get(f"/api/v1/courses/{course_id}/workspaces", headers=headers)

    assert response.status_code == 503
    assert _reason(response) == "service_unreachable"
    assert SERVICE_URL not in response.text and SECRET not in response.text


def test_a_node_503_is_reported_as_a_dependency_problem_not_a_dead_end():
    _, _, http, headers, course_id = _setup(
        [(503, {"error": "dependency_unavailable", "message": "database not ready"})]
    )

    response = http.get(f"/api/v1/courses/{course_id}/workspaces", headers=headers)

    assert response.status_code == 503
    assert _reason(response) == "dependency_unavailable"
    assert "database not ready" not in response.text, "上游正文不原样转发"


def test_a_node_503_from_a_missing_provider_keeps_its_own_reason():
    _, _, http, headers, course_id = _setup(
        [(503, {"error": "provider_unavailable", "message": "tts provider is unavailable"})]
    )

    response = http.get(f"/api/v1/courses/{course_id}/workspaces", headers=headers)

    assert response.status_code == 503
    assert _reason(response) == "provider_unavailable"


def test_an_unexpected_upstream_status_is_not_dressed_up_as_retryable():
    _, _, http, headers, course_id = _setup([(418, {"error": "teapot"})])

    response = http.get(f"/api/v1/courses/{course_id}/workspaces", headers=headers)

    assert response.status_code == 503
    assert _reason(response) == "unexpected_response"
