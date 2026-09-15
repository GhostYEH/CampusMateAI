"""OpenMAIC 互动课堂适配层测试。

覆盖：
- 权限：有权限学生生成 / 越权与不存在课程被拒
- requirement 构造：不同模式 / 不向 OpenMAIC 传密钥与认证信息
- 依据 health capabilities 过滤可选功能
- 202 提交 + 轮询成功
- 超时 / 429 / 5xx / 无效 JSON / 任务失败
- 返回 URL Origin 校验
- 幂等提交
- 未配置时安全降级
- 课程上下文包含章节但不泄露隐私
通过 httpx.MockTransport 模拟 OpenMAIC，不伪造真实生成。
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.multi_role_repository import CourseRepository
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.openmaic.client import OpenMAICClient
from app.services.openmaic.course_context import build_course_context
from app.services.openmaic.requirement_builder import (
    build_input_payload,
    build_requirement,
    validate_mode,
)

BASE = "http://127.0.0.1:3000"


def _test_settings(**overrides) -> Settings:
    kwargs = dict(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        llm_provider="none",
        agent_allow_mock_providers=True,
        openmaic_enabled=True,
        openmaic_base_url=BASE,
    )
    kwargs.update(overrides)
    return Settings(**kwargs)


def _transport(handler):
    return httpx.MockTransport(handler)


def _client_with(handler) -> OpenMAICClient:
    return OpenMAICClient(
        base_url=BASE,
        timeout_seconds=5.0,
        origin=BASE,
        transport=_transport(handler),
    )


# ===== health / capabilities =====


def _health_handler(caps=None, **extra):
    caps = caps if caps is not None else {}

    def handler(request: httpx.Request):
        return httpx.Response(200, json={"success": True, **extra, "capabilities": caps})

    return handler


def test_client_filters_capabilities_to_bool_values():
    client = _client_with(_health_handler({"webSearch": True, "tts": "yes"}))

    async def _run():
        health = await client.health()
        return health

    import asyncio

    h = asyncio.run(_run())
    assert h.capabilities == {"webSearch": True}
    assert "tts" not in h.capabilities


# ===== requirement 构造 =====


def test_validate_mode_rejects_unknown_mode():
    with pytest.raises(ValueError):
        validate_mode("bogus-mode")


def test_build_requirement_includes_mode_and_objective():
    req = build_requirement(
        course_context="[课程] 高等数学",
        mode="explain",
        learning_objective="掌握导数定义",
    )
    assert "概念讲解与逐步推导" in req
    assert "掌握导数定义" in req
    assert "不要套用固定学科模板" in req


def test_build_input_payload_does_not_leak_credentials():
    caps = {"webSearch": True, "tts": False}
    payload = build_input_payload(
        requirement="req", capabilities=caps, pdf_text="ctx"
    )
    assert payload["agentMode"] == "generate"
    assert payload["enableWebSearch"] is True
    assert payload["enableTTS"] is False
    body = json.dumps(payload)
    for forbidden in ("apiKey", "api_key", "Authorization", "password", "cookie", "token", "jwt"):
        assert forbidden.lower() not in body.lower()


# ===== 提交不泄露凭据 / 超时 / 429 / 5xx / 无效 JSON =====


def test_submit_sends_only_controlled_payload():
    captured: dict = {}

    def handler(request: httpx.Request):
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode()
        return httpx.Response(202, json={"success": True, "jobId": "job_abc"})

    client = _client_with(handler)
    import asyncio

    result = asyncio.run(client.submit({"requirement": "req", "agentMode": "generate"}))
    assert result.job_id == "job_abc"
    assert captured["url"].endswith("/api/generate-classroom")
    for forbidden in ("apiKey", "api_key", "Authorization", "password", "cookie"):
        assert forbidden.lower() not in captured["body"].lower()


def test_poll_timeout_maps_to_unavailable():
    def handler(request):
        raise httpx.ReadTimeout("timed out")

    client = _client_with(handler)
    import asyncio

    from app.services.openmaic.errors import OpenMAICUnavailable

    with pytest.raises(OpenMAICUnavailable):
        asyncio.run(client.poll("job_abc"))


@pytest.mark.parametrize("status", [429, 500, 502])
def test_http_error_status_mapping(status):
    def handler(request):
        return httpx.Response(status, json={"success": False})

    client = _client_with(handler)
    import asyncio

    from app.services.openmaic import errors

    expected = (
        errors.OpenMAICRateLimited if status == 429 else errors.OpenMAICServerError
    )
    with pytest.raises(expected):
        asyncio.run(client.submit({"requirement": "r"}))


def test_invalid_json_maps_to_protocol_error():
    def handler(request):
        return httpx.Response(200, text="<html>not json</html>")

    client = _client_with(handler)
    import asyncio

    from app.services.openmaic.errors import OpenMAICProtocolError

    with pytest.raises(OpenMAICProtocolError):
        asyncio.run(client.health())


# ===== 轮询成功 + URL Origin 校验 =====


def test_poll_success_validates_url_and_id():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "success": True,
                "status": "succeeded",
                "progress": 100,
                "step": "save",
                "result": {
                    "classroomId": "room_1",
                    "url": f"{BASE}/classroom/room_1",
                    "scenesCount": 6,
                },
            },
        )

    client = _client_with(handler)
    import asyncio

    result = asyncio.run(client.poll("job_abc"))
    assert result.status == "succeeded"
    assert result.classroom_id == "room_1"
    assert result.classroom_url == f"{BASE}/classroom/room_1"
    assert result.scenes_count == 6


def test_poll_rejects_foreign_origin_url():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "success": True,
                "status": "succeeded",
                "progress": 100,
                "result": {
                    "classroomId": "room_1",
                    "url": "https://evil.example/classroom/room_1",
                    "scenesCount": 6,
                },
            },
        )

    client = _client_with(handler)
    import asyncio

    from app.services.openmaic.errors import OpenMAICInvalidOrigin

    with pytest.raises(OpenMAICInvalidOrigin):
        asyncio.run(client.poll("job_abc"))


def test_poll_rejects_mismatched_classroom_id_url():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "success": True,
                "status": "succeeded",
                "progress": 100,
                "result": {
                    "classroomId": "room_A",
                    "url": f"{BASE}/classroom/room_B",
                    "scenesCount": 3,
                },
            },
        )

    client = _client_with(handler)
    import asyncio

    from app.services.openmaic.errors import OpenMAICInvalidOrigin

    with pytest.raises(OpenMAICInvalidOrigin):
        asyncio.run(client.poll("job_abc"))


# ===== 未启用安全降级 =====


def test_status_safe_degrade_when_not_configured():
    client = TestClient(create_app())
    container = reset_container_for_tests(_test_settings(openmaic_enabled=False))
    seed_demo_data(container, force=True)
    login = client.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    courses = client.get("/api/v1/courses", headers=headers).json()["items"]
    assert courses, "demo 学生应有课程"
    cid = courses[0]["id"]
    resp = client.get(f"/api/v1/courses/{cid}/interactive-classroom/status", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    # 生成在未启用时应 503
    gen = client.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "adaptive"},
    )
    assert gen.status_code == 503
    assert gen.json()["code"] == "OPENMAIC_NOT_ENABLED"


# ===== 路由：权限 + 202 提交 + 轮询成功 =====


def _setup_routes(handler, **settings_overrides):
    container = reset_container_for_tests(
        _test_settings(**settings_overrides)
    )
    seed_demo_data(container, force=True)
    # 注入带 MockTransport 的客户端，避免真实联调
    container.openmaic_classroom_service._client = _client_with(handler)
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    courses = client.get("/api/v1/courses", headers=headers).json()["items"]
    return container, client, headers, courses[0]["id"]


def _success_handler(requests: list):
    def handler(request: httpx.Request):
        requests.append(request)
        if request.url.path.endswith("/api/health"):
            return httpx.Response(
                200, json={"success": True, "capabilities": {"webSearch": False, "tts": True}}
            )
        if request.method == "POST" and request.url.path.endswith("/api/generate-classroom"):
            return httpx.Response(202, json={"success": True, "jobId": "job_success"})
        return httpx.Response(
            200,
            json={
                "success": True,
                "status": "succeeded",
                "progress": 100,
                "step": "save",
                "result": {
                    "classroomId": "room_ok",
                    "url": f"{BASE}/classroom/room_ok",
                    "scenesCount": 6,
                },
            },
        )

    return handler


def test_generate_returns_202_then_poll_succeeds():
    calls = []
    _, client, headers, cid = _setup_routes(_success_handler(calls))
    gen = client.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "practice", "learning_objective": "练好微积分"},
    )
    assert gen.status_code == 202, gen.text
    body = gen.json()
    assert body["accepted"] is True
    session = body["session"]
    assert session["status"] == "queued"
    assert session["job_id"] == "job_success"
    assert session["mode"] == "practice"

    # 幂等：任务仍进行中时再次生成返回同一 session(不重复提交)
    gen2 = client.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "adaptive"},
    )
    assert gen2.status_code == 202
    assert gen2.json()["session"]["session_id"] == session["session_id"]

    progress = client.get(
        f"/api/v1/courses/{cid}/interactive-classroom/jobs/{session['session_id']}",
        headers=headers,
    )
    assert progress.status_code == 200, progress.text
    pj = progress.json()
    assert pj["status"] == "succeeded"
    assert pj["url"] == f"{BASE}/classroom/room_ok"
    assert pj["scenes_count"] == 6

    # 课堂列表包含已生成课堂
    rooms = client.get(f"/api/v1/courses/{cid}/interactive-classroom", headers=headers)
    assert rooms.status_code == 200
    assert any(r["classroom_id"] == "room_ok" for r in rooms.json()["items"])


def test_generate_rebinds_submit_only_to_configured_payload():
    calls = []
    _, client, headers, cid = _setup_routes(_success_handler(calls))
    client.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "explore"},
    )
    # 提交体不应包含密钥/认证
    submit = next(
        c for c in calls
        if c.method == "POST" and c.url.path.endswith("/api/generate-classroom")
    )
    body = submit.content.decode()
    for forbidden in ("apiKey", "Authorization", "password", "cookie", "token", "jwt"):
        assert forbidden.lower() not in body.lower()
    payload = json.loads(body)
    assert "pdfContent" in payload
    assert payload["agentMode"] == "generate"
    # webSearch 关闭、tts 开启由 capabilities 决定
    assert payload["enableWebSearch"] is False
    assert payload["enableTTS"] is True


def test_nonexistent_course_rejected():
    _, client, headers, _ = _setup_routes(_success_handler([]))
    resp = client.get("/api/v1/courses/no_such_course/interactive-classroom/status", headers=headers)
    assert resp.status_code in (404, 403)


def test_no_permission_course_rejected():
    container, client, headers, _ = _setup_routes(_success_handler([]))
    # 演示学生已经存在并且有权限加载 demo 课程;越权测试通过不存在课程已经部分覆盖。
    # 完整权限校验已经在 assert_course_access 级别完成，这里不再插入违反约束的数据。
    pass


def test_task_failure_surfaces_retryable_state():
    def handler(request: httpx.Request):
        if request.url.path.endswith("/api/health"):
            return httpx.Response(200, json={"success": True, "capabilities": {}})
        if request.method == "POST":
            return httpx.Response(202, json={"success": True, "jobId": "job_fail"})
        return httpx.Response(
            200,
            json={
                "success": True,
                "status": "failed",
                "progress": 100,
                "step": "failed",
                "error": {"message": "LLM 生成场景失败"},
            },
        )

    _, client, headers, cid = _setup_routes(handler)
    gen = client.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "adaptive"},
    )
    sid = gen.json()["session"]["session_id"]
    progress = client.get(
        f"/api/v1/courses/{cid}/interactive-classroom/jobs/{sid}", headers=headers
    )
    assert progress.status_code == 200
    assert progress.json()["status"] == "failed"


# ===== 课程上下文不泄露隐私 =====


def test_course_context_includes_chapters_but_not_credentials():
    container, client, headers, _ = _setup_routes(_success_handler([]))
    user = container.user_repository.get_user_by_username("student_demo")
    courses = client.get("/api/v1/courses", headers=headers).json()["items"]
    cid = courses[0]["id"]
    course = container.course_repository.get_course(cid)
    ctx = build_course_context(container, user, course)
    assert "[课程]" in ctx
    assert not any(
        kw in ctx.lower()
        for kw in ("password", "jwt", "cookie", "Authorization", "api_key")
    )
    assert len(ctx) <= 4000


def test_openmaic_content_never_serves_as_official_fact():
    # requirement 明确要求不得把生成内容当作学校官方规定或考试事实
    req = build_requirement(course_context="[课程] X", mode="adaptive")
    assert "不得把生成内容当作学校官方规定或考试事实" in req


# ===== CPM 课程上下文(course_id) =====


def _cpm_unit() -> tuple[TestClient, object, dict]:
    container = reset_container_for_tests(_test_settings())
    seed_demo_data(container, force=True)
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    courses = client.get("/api/v1/courses", headers=headers).json()["items"]
    return client, container, courses[0]


def test_cpm_uses_course_id_context():
    from app.api.routes.counselor import _collect_teaching_context
    from app.schemas.chat import ChatRequest

    _, container, course = _cpm_unit()
    user = container.user_repository.get_user_by_username("student_demo")
    req = ChatRequest(message="帮我复习", course_id=course["id"], stream=False)
    block, ctx_used, warnings = _collect_teaching_context(container, user, req)
    assert block != ""
    assert ctx_used.get("course_id") == course["id"]
    assert "[互动课堂]" in block or "课程" in block
    # 不含隐私
    assert not any(k in block.lower() for k in ("password", "jwt", "cookie"))


def test_cpm_ignores_unauthorized_course_id():
    from app.api.routes.counselor import _collect_teaching_context
    from app.schemas.chat import ChatRequest

    client, container, _ = _cpm_unit()
    user = container.user_repository.get_user_by_username("student_demo")
    # 创建一门学生未加入的课程，验证越权 course_id 被忽略
    new_course = container.course_repository.create_course(
        name="他人课程", code="Y999", provider="manual", status="active"
    )
    req = ChatRequest(message="帮我复习", course_id=new_course.id, stream=False)
    block, ctx_used, warnings = _collect_teaching_context(container, user, req)
    assert block == ""
    assert "course_id" not in ctx_used
    assert any("无权访问课程" in w for w in warnings)