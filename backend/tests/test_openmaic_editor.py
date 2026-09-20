"""FastAPI 网关的编辑器边界测试。

编辑器是唯一"客户端和服务端同时持有一份文档"的面，所以这里重点验证网关自己
必须负责的事：命令列表不能变成整份 PUT、重试必须有幂等键、并发必须靠 If-Match、
命令被拒时 `code`/`path` 要能原样传给编辑器用于定位那一行。受管服务本身的命令
语义由 `openmaic-service/tests/editor.test.mjs` 覆盖。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.routes import openmaic_editor, openmaic_workspaces
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
        self.default = (200, {})

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
    app.dependency_overrides[openmaic_editor._client] = lambda: client
    app.dependency_overrides[openmaic_workspaces._client] = lambda: client
    http = TestClient(app)
    login = http.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    courses = http.get("/api/v1/courses", headers=headers).json()["items"]
    return container, transport, http, headers, courses[0]["id"]


def _stage_payload(course_id: str, **overrides):
    payload = {
        "id": "stg_1",
        "workspace_id": "ws_1",
        "course_id": course_id,
        "title": "第一课",
        "revision": 2,
        "dsl_version": "0.3.0",
        "created_at": "2026-01-01T00:00:00.000Z",
        "updated_at": "2026-01-01T00:00:00.000Z",
        "document": {"dslVersion": "0.3.0", "stage": {"id": "stg_1", "name": "第一课"}, "scenes": []},
        "applied_commands": 1,
        "migrated": False,
    }
    payload.update(overrides)
    return payload


def _commands_path(course_id: str) -> str:
    return f"/api/v1/courses/{course_id}/workspaces/ws_1/stages/stg_1/commands"


def _claims(call):
    return decode_service_assertion(call["headers"]["X-CampusMate-Service-Assertion"], secret=SECRET)


def test_applying_commands_forwards_a_command_list_not_a_document():
    _, transport, http, headers, course_id = _setup([])
    transport.script.append((200, _stage_payload(course_id)))
    response = http.post(
        _commands_path(course_id),
        json={"commands": [{"type": "scene.create", "sceneType": "slide", "title": "开场"}]},
        headers={**headers, "If-Match": "1", "Idempotency-Key": "edit-1"},
    )
    assert response.status_code == 200
    call = transport.calls[0]
    assert call["url"] == f"{SERVICE_URL}/internal/courses/{course_id}/workspaces/ws_1/stages/stg_1/commands"
    assert call["json"] == {"commands": [{"type": "scene.create", "sceneType": "slide", "title": "开场"}]}
    assert "document" not in call["json"], "编辑器不得把整份文档当请求体"
    assert call["headers"]["If-Match"] == "1"
    assert call["headers"]["Idempotency-Key"] == "edit-1"

    claims = _claims(call)
    # 编辑器只借 stage 作用域：拿到断言也改不了工作台本身的元数据。
    assert claims["scope"] == ["stage:read", "stage:write"]
    assert response.json()["applied_commands"] == 1


def test_element_move_keeps_the_stage_command_gateway_contract():
    _, transport, http, headers, course_id = _setup([])
    transport.script.append((200, _stage_payload(course_id, revision=3, applied_commands=1)))
    command = {
        "type": "slide.element.move",
        "sceneId": "scn_slide",
        "elementId": "el_title",
        "left": 142.5,
        "top": 88.25,
    }
    response = http.post(
        _commands_path(course_id),
        json={"commands": [command]},
        headers={**headers, "If-Match": "2", "Idempotency-Key": "move-1"},
    )
    assert response.status_code == 200
    assert transport.calls[0]["json"] == {"commands": [command]}
    assert "document" not in transport.calls[0]["json"]
    assert transport.calls[0]["headers"]["If-Match"] == "2"
    assert transport.calls[0]["headers"]["Idempotency-Key"] == "move-1"
    assert _claims(transport.calls[0])["scope"] == ["stage:read", "stage:write"]


def test_the_editor_edit_requires_if_match_and_an_idempotency_key():
    _, transport, http, headers, course_id = _setup([])

    no_match = http.post(
        _commands_path(course_id),
        json={"commands": [{"type": "scene.create", "sceneType": "slide"}]},
        headers={**headers, "Idempotency-Key": "edit-1"},
    )
    assert no_match.status_code == 400

    wildcard = http.post(
        _commands_path(course_id),
        json={"commands": [{"type": "scene.create", "sceneType": "slide"}]},
        headers={**headers, "If-Match": "*", "Idempotency-Key": "edit-1"},
    )
    assert wildcard.status_code == 400

    no_key = http.post(
        _commands_path(course_id),
        json={"commands": [{"type": "scene.create", "sceneType": "slide"}]},
        headers={**headers, "If-Match": "1"},
    )
    assert no_key.status_code == 400

    assert transport.calls == [], "拒绝必须发生在调用上游之前"


def test_an_empty_or_oversized_command_list_is_refused_locally():
    _, transport, http, headers, course_id = _setup([])

    empty = http.post(
        _commands_path(course_id),
        json={"commands": []},
        headers={**headers, "If-Match": "1", "Idempotency-Key": "edit-1"},
    )
    assert empty.status_code == 422, "空列表由 pydantic 的 min_length 拦下"

    oversized = http.post(
        _commands_path(course_id),
        json={"commands": [{"type": "scene.create", "sceneType": "slide"}] * 51},
        headers={**headers, "If-Match": "1", "Idempotency-Key": "edit-1"},
    )
    assert oversized.status_code == 422

    assert transport.calls == []


def test_a_rejected_command_keeps_its_code_and_path_for_the_editor():
    _, transport, http, headers, course_id = _setup([])
    transport.script.append((
        422,
        {
            "error": "command_rejected",
            "code": "interactive_content_required",
            "path": "commands[0].content",
            "message": "新建 interactive 场景必须提供 html 或 url",
        },
    ))
    response = http.post(
        _commands_path(course_id),
        json={"commands": [{"type": "scene.create", "sceneType": "interactive"}]},
        headers={**headers, "If-Match": "1", "Idempotency-Key": "edit-1"},
    )
    assert response.status_code == 422
    details = response.json()["details"]
    assert details["service_error"] == "command_rejected"
    assert details["path"] == "commands[0].content"
    assert SERVICE_URL not in response.text
    assert SECRET not in response.text


def test_a_stale_revision_is_a_conflict_the_editor_can_act_on():
    _, transport, http, headers, course_id = _setup([])
    transport.script.append((412, {"error": "revision_mismatch"}))
    response = http.post(
        _commands_path(course_id),
        json={"commands": [{"type": "scene.create", "sceneType": "slide"}]},
        headers={**headers, "If-Match": "1", "Idempotency-Key": "edit-1"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "OPENMAIC_REVISION_CONFLICT"


def test_the_outline_and_a_single_scene_are_read_through_the_gateway():
    _, transport, http, headers, course_id = _setup([])
    transport.script.append((
        200,
        {
            "stage_id": "stg_1",
            "workspace_id": "ws_1",
            "title": "第一课",
            "revision": 3,
            "dsl_version": "0.3.0",
            "scenes": [
                {"id": "scn_1", "type": "slide", "title": "开场", "order": 0, "actions": 1, "updated_at": 5},
            ],
        },
    ))
    transport.script.append((200, {"id": "scn_1", "type": "slide", "title": "开场", "order": 0, "content": {"type": "slide", "canvas": {}}}))

    outline = http.get(f"/api/v1/courses/{course_id}/workspaces/ws_1/stages/stg_1/outline", headers=headers)
    assert outline.status_code == 200
    body = outline.json()
    assert body["scenes"][0]["id"] == "scn_1"
    assert "content" not in body["scenes"][0], "目录不得下发场景正文"
    assert _claims(transport.calls[0])["scope"] == ["stage:read"]

    scene = http.get(
        f"/api/v1/courses/{course_id}/workspaces/ws_1/stages/stg_1/scenes/scn_1", headers=headers
    )
    assert scene.status_code == 200
    assert scene.json()["content"]["type"] == "slide"


def test_the_editor_answers_503_without_calling_the_service_when_the_switch_is_off():
    _, transport, http, headers, course_id = _setup([], openmaic_fusion_enabled=False)
    response = http.get(
        f"/api/v1/courses/{course_id}/workspaces/ws_1/stages/stg_1/outline", headers=headers
    )
    assert response.status_code == 503
    assert transport.calls == []


def test_an_unknown_course_is_refused_before_the_editor_calls_the_service():
    _, transport, http, headers, _ = _setup([])
    response = http.get(
        "/api/v1/courses/course-does-not-exist/workspaces/ws_1/stages/stg_1/outline",
        headers=headers,
    )
    assert response.status_code == 404
    assert transport.calls == []


def test_the_playback_plan_passes_the_resume_scene_and_keeps_the_sandbox_decision():
    _, transport, http, headers, course_id = _setup([])
    transport.script.append((
        200,
        {
            "stage_id": "stg_1",
            "workspace_id": "ws_1",
            "title": "第一课",
            "revision": 4,
            "dsl_version": "0.3.0",
            "start_index": 1,
            "scenes": [
                {
                    "id": "scn_1",
                    "type": "slide",
                    "title": "开场",
                    "order": 0,
                    "render": {"kind": "native"},
                    "steps": [{"action_id": "a1", "type": "speech", "mode": "sync"}],
                    "dropped_actions": [],
                    "whiteboards": 0,
                    "multi_agent": False,
                },
                {
                    "id": "scn_2",
                    "type": "interactive",
                    "title": "三维",
                    "order": 1,
                    "render": {"kind": "unsupported", "widget_type": "visualization3d", "reason": "widget_requires_external_cdn"},
                    "steps": [],
                    "dropped_actions": [],
                    "whiteboards": 0,
                    "multi_agent": False,
                },
            ],
            "degraded": [{"scene_id": "scn_2", "reason": "widget_requires_external_cdn"}],
        },
    ))
    response = http.get(
        f"/api/v1/courses/{course_id}/workspaces/ws_1/stages/stg_1/playback",
        params={"scene_id": "scn_2"},
        headers=headers,
    )
    assert response.status_code == 200
    call = transport.calls[0]
    assert call["params"] == {"scene_id": "scn_2"}
    assert _claims(call)["scope"] == ["stage:read"]

    body = response.json()
    assert body["start_index"] == 1
    assert body["scenes"][1]["render"]["kind"] == "unsupported"
    assert body["degraded"][0]["reason"] == "widget_requires_external_cdn"
    # 沙箱决定只由服务端给出：网关不做二次加工，也不放大权限。
    assert "allow-same-origin" not in response.text
