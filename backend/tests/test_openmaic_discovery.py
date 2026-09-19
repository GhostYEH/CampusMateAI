"""FastAPI 网关的文件夹 / 站内搜索边界测试。

网关是浏览器唯一能到受管服务的门。和工作台一样,它自己必须负责:身份不由客户端
指定、重试必须显式、上游状态被翻译成浏览器能处理的状态、内部地址与断言永不外泄。
额外的两条只对发现功能成立:

- ``folder_id`` / ``parent_id`` 必须区分"没传"与"传了 null"(取消归档 / 移到根层);
- 空关键词必须在**调用上游之前**被拒,否则"没输入"会退化成"返回全部内容"。

受管服务本身的权限与分页由 ``openmaic-service/tests/discovery.test.mjs`` 覆盖。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.routes import openmaic_discovery, openmaic_workspaces
from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.openmaic.fusion_client import OpenMAICFusionClient
from app.services.openmaic.service_assertion import decode_service_assertion

SECRET = "gateway-secret"
SERVICE_URL = "http://openmaic.internal:4010"


class _RecordingTransport:
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
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "json": json})
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
        openmaic_fusion_enabled=True,
        openmaic_service_url=SERVICE_URL,
        openmaic_internal_secret=SECRET,
    )
    kwargs.update(overrides)
    return Settings(**kwargs)


def _setup(script=None, **settings_overrides):
    container = reset_container_for_tests(_test_settings(**settings_overrides))
    seed_demo_data(container, force=True)
    transport = _RecordingTransport(script)
    client = OpenMAICFusionClient(
        base_url=container.settings.openmaic_service_url,
        secret=container.settings.openmaic_internal_secret,
        transport=transport,
    )
    app = create_app()
    # Both routers mint their own client dependency; the filing tests exercise the
    # workspace route, so overriding only the discovery one would hit the network.
    app.dependency_overrides[openmaic_discovery._client] = lambda: client
    app.dependency_overrides[openmaic_workspaces._client] = lambda: client
    http = TestClient(app)
    login = http.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    courses = http.get("/api/v1/courses", headers=headers).json()["items"]
    return container, transport, http, headers, courses[0]["id"]


def _folder_payload(**overrides):
    payload = {
        "id": "fd_1",
        "course_id": "course-1",
        "parent_id": None,
        "name": "第一章",
        "revision": 1,
        "created_at": "2026-01-01T00:00:00.000Z",
        "updated_at": "2026-01-01T00:00:00.000Z",
        "workspace_count": 0,
    }
    payload.update(overrides)
    return payload


def _claims(call):
    return decode_service_assertion(call["headers"]["X-CampusMate-Service-Assertion"], secret=SECRET)


# ===== 开关 =====


def test_folder_routes_answer_503_without_calling_the_service_when_the_switch_is_off():
    _, transport, http, headers, course_id = _setup(
        [], openmaic_fusion_enabled=False
    )
    response = http.get(f"/api/v1/courses/{course_id}/folders", headers=headers)
    assert response.status_code == 503
    assert transport.calls == [], "关闭状态下不得触碰受管服务"


def test_search_answers_503_without_calling_the_service_when_the_switch_is_off():
    _, transport, http, headers, course_id = _setup(
        [], openmaic_fusion_enabled=False
    )
    response = http.get(f"/api/v1/courses/{course_id}/search?q=线性代数", headers=headers)
    assert response.status_code == 503
    assert transport.calls == []


# ===== 身份与归属 =====


def test_creating_a_folder_mints_a_folder_scope_assertion_for_the_jwt_subject():
    _, transport, http, headers, course_id = _setup([])
    transport.script.append((201, _folder_payload(course_id=course_id)))
    response = http.post(
        f"/api/v1/courses/{course_id}/folders",
        json={"name": "第一章"},
        headers={**headers, "Idempotency-Key": "folder-key-1"},
    )
    assert response.status_code == 201
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"] == f"{SERVICE_URL}/internal/courses/{course_id}/folders"
    assert call["headers"]["Idempotency-Key"] == "folder-key-1"

    claims = _claims(call)
    assert claims["course_id"] == course_id
    assert "folder:write" in claims["scope"]
    assert "workspace:write" not in claims["scope"], "发现功能不得借用工作台写权限"
    # 请求体里没有任何用户标识：归属只来自 JWT。
    assert "user_id" not in call["json"]


def test_search_uses_a_read_only_search_scope():
    _, transport, http, headers, course_id = _setup([
        (200, {"items": [], "next_cursor": None}),
    ])
    response = http.get(f"/api/v1/courses/{course_id}/search?q=复习", headers=headers)
    assert response.status_code == 200
    claims = _claims(transport.calls[0])
    assert claims["scope"] == ["search:read"]
    assert transport.calls[0]["params"]["q"] == "复习"


def test_an_unknown_course_is_refused_before_the_service_is_called():
    _, transport, http, headers, _ = _setup([])
    response = http.get("/api/v1/courses/course-does-not-exist/folders", headers=headers)
    assert response.status_code == 404
    assert transport.calls == []


# ===== 重试与并发 =====


def test_a_folder_create_without_an_idempotency_key_is_refused_locally():
    _, transport, http, headers, course_id = _setup([])
    response = http.post(
        f"/api/v1/courses/{course_id}/folders", json={"name": "第一章"}, headers=headers
    )
    assert response.status_code == 400
    assert transport.calls == [], "拒绝必须发生在调用上游之前"


def test_renaming_a_folder_requires_if_match_and_maps_412_to_409():
    _, transport, http, headers, course_id = _setup([])
    transport.script.extend([
        (412, {"error": "revision_mismatch"}),
        (200, _folder_payload(course_id=course_id, name="新名字", revision=2)),
    ])
    folder_url = f"/api/v1/courses/{course_id}/folders/fd_1"

    missing = http.patch(folder_url, json={"name": "新名字"}, headers=headers)
    assert missing.status_code == 400
    assert transport.calls == []

    wildcard = http.patch(
        folder_url, json={"name": "新名字"}, headers={**headers, "If-Match": "*"}
    )
    assert wildcard.status_code == 400
    assert transport.calls == []

    conflict = http.patch(
        folder_url, json={"name": "新名字"}, headers={**headers, "If-Match": "9"}
    )
    assert conflict.status_code == 409
    assert transport.calls[0]["headers"]["If-Match"] == "9"

    ok = http.patch(
        folder_url, json={"name": "新名字"}, headers={**headers, "If-Match": "1"}
    )
    assert ok.status_code == 200
    assert ok.json()["revision"] == 2


def test_moving_a_folder_to_the_root_sends_an_explicit_null_but_a_rename_omits_it():
    _, transport, http, headers, course_id = _setup([])
    transport.script.extend([
        (200, _folder_payload(course_id=course_id, revision=2)),
        (200, _folder_payload(course_id=course_id, revision=3)),
    ])
    folder_url = f"/api/v1/courses/{course_id}/folders/fd_1"

    moved = http.patch(
        folder_url, json={"parent_id": None}, headers={**headers, "If-Match": "1"}
    )
    assert moved.status_code == 200
    assert "parent_id" in transport.calls[0]["json"]
    assert transport.calls[0]["json"]["parent_id"] is None

    renamed = http.patch(folder_url, json={"name": "只改名"}, headers={**headers, "If-Match": "2"})
    assert renamed.status_code == 200
    assert "parent_id" not in transport.calls[1]["json"], "未提供该字段时不得隐式移动"


# ===== 搜索输入 =====


def test_a_blank_search_query_is_refused_before_the_service_is_called():
    _, transport, http, headers, course_id = _setup([])
    for suffix in ("", "?q=", "?q=%20%20"):
        response = http.get(f"/api/v1/courses/{course_id}/search{suffix}", headers=headers)
        assert response.status_code == 400, suffix
    assert transport.calls == []


def test_an_overlong_search_query_is_refused_locally():
    _, transport, http, headers, course_id = _setup([])
    response = http.get(
        f"/api/v1/courses/{course_id}/search", params={"q": "a" * 201}, headers=headers
    )
    assert response.status_code == 400
    assert transport.calls == []


def test_search_returns_the_server_generated_deep_link_without_leaking_internals():
    _, transport, http, headers, course_id = _setup([])
    transport.script.append(
        (
            200,
            {
                "items": [
                    {
                        "kind": "stage",
                        "workspace_id": "ws_1",
                        "stage_id": "stg_1",
                        "title": "线性代数第一讲",
                        "snippet": "",
                        "folder_id": "fd_1",
                        "updated_at": "2026-01-01T00:00:00.000Z",
                        "path": f"/courses/{course_id}?tab=mentoring&workspace=ws_1&stage=stg_1",
                    }
                ],
                "next_cursor": None,
            },
        )
    )
    response = http.get(f"/api/v1/courses/{course_id}/search?q=线性代数", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "线性代数"
    assert body["items"][0]["path"] == (
        f"/courses/{course_id}?tab=mentoring&workspace=ws_1&stage=stg_1"
    )
    assert SERVICE_URL not in response.text
    assert SECRET not in response.text


def test_a_foreign_folder_is_reported_as_not_found_without_confirming_it_exists():
    _, transport, http, headers, course_id = _setup([
        (404, {"error": "not_found"}),
    ])
    response = http.get(f"/api/v1/courses/{course_id}/folders/fd_foreign", headers=headers)
    assert response.status_code == 404
    assert SERVICE_URL not in response.text
    assert SECRET not in response.text


# ===== 工作台归档 =====


def test_a_workspace_can_be_filed_into_a_folder_and_reads_back_its_folder_id():
    _, transport, http, headers, course_id = _setup([])
    transport.script.append(
        (
            201,
            {
                "id": "ws_1",
                "course_id": course_id,
                "name": "线性代数复习",
                "description": "",
                "folder_id": "fd_1",
                "revision": 1,
                "created_at": "2026-01-01T00:00:00.000Z",
                "updated_at": "2026-01-01T00:00:00.000Z",
            },
        )
    )
    response = http.post(
        f"/api/v1/courses/{course_id}/workspaces",
        json={"name": "线性代数复习", "folder_id": "fd_1"},
        headers={**headers, "Idempotency-Key": "ws-key-1"},
    )
    assert response.status_code == 201
    assert response.json()["folder_id"] == "fd_1"
    assert transport.calls[0]["json"]["folder_id"] == "fd_1"


def test_unfiling_a_workspace_sends_an_explicit_null():
    _, transport, http, headers, course_id = _setup([])
    transport.script.append(
        (
            200,
            {
                "id": "ws_1",
                "course_id": course_id,
                "name": "线性代数复习",
                "description": "",
                "folder_id": None,
                "revision": 2,
                "created_at": "2026-01-01T00:00:00.000Z",
                "updated_at": "2026-01-01T00:00:00.000Z",
            },
        )
    )
    response = http.patch(
        f"/api/v1/courses/{course_id}/workspaces/ws_1",
        json={"folder_id": None},
        headers={**headers, "If-Match": "1"},
    )
    assert response.status_code == 200
    assert "folder_id" in transport.calls[0]["json"]
    assert transport.calls[0]["json"]["folder_id"] is None
    assert response.json()["folder_id"] is None


def test_a_workspace_update_that_changes_nothing_is_refused_locally():
    _, transport, http, headers, course_id = _setup([])
    response = http.patch(
        f"/api/v1/courses/{course_id}/workspaces/ws_1",
        json={},
        headers={**headers, "If-Match": "1"},
    )
    assert response.status_code == 400
    assert transport.calls == []
