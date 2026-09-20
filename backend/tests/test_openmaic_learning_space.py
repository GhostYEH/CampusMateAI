"""导航栏「学习空间」的可见性路由。

学习空间不绑定课程：入口在导航栏里，任何登录用户都可能点。它读的是与课程级
互动课堂**同一份**服务状态，所以这一份测试主要钉三件事：

1. 它必须要求登录 —— 一个不绑定课程的路由最容易顺手做成匿名可读；
2. 下发给浏览器的只有公开 Origin，内部地址（`OPENMAIC_BASE_URL`）不得出现在响应里；
3. 它与课程级路由**不分叉**：同一份配置下两侧的 `embed_origin` / `enabled` 必须一致，
   否则会出现"课程里能用、导航栏说没启用"这种无法解释的分歧。
"""
from __future__ import annotations

import json
from typing import Callable, Dict, List, Tuple

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import ServiceContainer, reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.openmaic.classroom_service import OpenMAICClassroomService
from app.services.openmaic.client import PROBE_JOB_ID, OpenMAICClient
from app.services.openmaic.result_store import OpenMAICResultStore

INTERNAL = "http://openmaic:3000"
PUBLIC = "https://classroom.example.edu"
STATUS_PATH = "/api/v1/openmaic/learning-space/status"


def _settings(**overrides) -> Settings:
    kwargs = dict(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        llm_provider="none",
        agent_allow_mock_providers=True,
        openmaic_enabled=True,
        openmaic_base_url=INTERNAL,
        openmaic_embed_origin=PUBLIC,
    )
    kwargs.update(overrides)
    return Settings(**kwargs)


def _handler(recorder: List[httpx.Request]) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        recorder.append(request)
        path = request.url.path
        if path.endswith("/api/access-code/status"):
            return httpx.Response(
                200, json={"success": True, "enabled": False, "authenticated": False}
            )
        if path.endswith("/api/health"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "status": "ok",
                    "version": "1.0.3",
                    "capabilities": {
                        "webSearch": True,
                        "imageGeneration": True,
                        "videoGeneration": True,
                        "tts": True,
                    },
                },
            )
        if path.endswith(f"/api/generate-classroom/{PROBE_JOB_ID}"):
            return httpx.Response(
                404,
                json={
                    "success": False,
                    "errorCode": "INVALID_REQUEST",
                    "error": "Classroom generation job not found",
                },
            )
        return httpx.Response(200, json={"success": True})

    return handler


def _bootstrap(tmp_path, **overrides) -> Tuple[ServiceContainer, TestClient, Dict[str, str]]:
    settings = _settings(**overrides)
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    store = OpenMAICResultStore(tmp_path / "openmaic_classrooms")
    client = OpenMAICClient(
        base_url=settings.openmaic_base_url,
        timeout_seconds=5.0,
        origin=settings.openmaic_origin,
        transport=httpx.MockTransport(_handler([])),
        access_code=settings.openmaic_access_code,
    )
    container.openmaic_result_store = store
    container.openmaic_classroom_service = OpenMAICClassroomService(settings, store, client=client)
    tc = TestClient(create_app())
    login = tc.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    assert login.status_code == 200, login.text
    return container, tc, {"Authorization": f"Bearer {login.json()['access_token']}"}


# ===== 鉴权 =====


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer not-a-token"}])
def test_status_requires_login(tmp_path, headers):
    _, tc, _ = _bootstrap(tmp_path)
    resp = tc.get(STATUS_PATH, headers=headers)
    assert resp.status_code in (401, 403), resp.text


# ===== 已配置 =====


def test_status_is_readable_without_a_course(tmp_path):
    _, tc, headers = _bootstrap(tmp_path)
    resp = tc.get(STATUS_PATH, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is True
    assert body["configured"] is True
    assert body["available"] is True
    assert body["reason"] is None


def test_status_only_hands_the_public_origin_to_the_browser(tmp_path):
    """内部地址绝不能出现在响应里 —— 这个路由是导航栏用的，浏览器直接读它。"""
    _, tc, headers = _bootstrap(tmp_path)
    resp = tc.get(STATUS_PATH, headers=headers)
    body = resp.json()
    assert body["embed_origin"] == PUBLIC
    assert body["browser_embed_available"] is True
    assert INTERNAL not in json.dumps(body, ensure_ascii=False)


def test_status_does_not_leak_internal_address_even_when_probe_fails(tmp_path):
    """上游连不上时也不得退回内部地址兜底。"""

    def failing(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/health"):
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(404, json={"success": False})

    settings = _settings()
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    store = OpenMAICResultStore(tmp_path / "openmaic_classrooms")
    container.openmaic_result_store = store
    container.openmaic_classroom_service = OpenMAICClassroomService(
        settings,
        store,
        client=OpenMAICClient(
            base_url=settings.openmaic_base_url,
            timeout_seconds=5.0,
            origin=settings.openmaic_origin,
            transport=httpx.MockTransport(failing),
            access_code=settings.openmaic_access_code,
        ),
    )
    tc = TestClient(create_app())
    login = tc.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = tc.get(STATUS_PATH, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is False
    assert body["unavailable"] is True
    assert body["embed_origin"] == PUBLIC, "公开 Origin 是静态配置，不随探测结果消失"
    assert INTERNAL not in json.dumps(body, ensure_ascii=False)


# ===== 未配置 =====


def test_status_is_honest_when_not_configured(tmp_path):
    _, tc, headers = _bootstrap(tmp_path, openmaic_enabled=False)
    resp = tc.get(STATUS_PATH, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is False
    assert body["configured"] is False
    assert body["embed_origin"] is None
    assert body["browser_embed_available"] is False
    # reason 原样透传服务状态的措辞，不在导航路由里改成"学习空间…"：
    # 未启用时服务状态一定有 reason，改写分支永远不会执行（见路由 docstring）。
    assert body["reason"]


def test_status_fails_closed_when_public_origin_is_missing(tmp_path):
    """只配了内部地址、没配公开 Origin：页面必须无从内嵌。"""
    _, tc, headers = _bootstrap(tmp_path, openmaic_embed_origin="")
    resp = tc.get(STATUS_PATH, headers=headers)
    body = resp.json()
    assert body["enabled"] is True
    assert body["embed_origin"] is None
    assert body["browser_embed_available"] is False
    assert body["browser_embed_reason"]
    assert INTERNAL not in json.dumps(body, ensure_ascii=False)


# ===== 与课程级路由不分叉 =====


def test_agrees_with_the_course_scoped_route(tmp_path):
    _, tc, headers = _bootstrap(tmp_path)
    courses = tc.get("/api/v1/courses", headers=headers).json()["items"]
    assert courses, "演示数据应至少给出一门课程"

    nav = tc.get(STATUS_PATH, headers=headers).json()
    course = tc.get(
        f"/api/v1/courses/{courses[0]['id']}/interactive-classroom/status", headers=headers
    ).json()

    for field in ("enabled", "configured", "available", "embed_origin", "browser_embed_available"):
        assert nav[field] == course[field], f"{field} 在导航栏与课程级路由上必须一致"


def test_course_scoped_route_still_checks_course_access(tmp_path):
    """导航栏路由不校验课程，课程级路由必须继续校验 —— 别把两者改成同一个。"""
    _, tc, headers = _bootstrap(tmp_path)
    resp = tc.get(
        "/api/v1/courses/no_such_course/interactive-classroom/status", headers=headers
    )
    assert resp.status_code in (403, 404), resp.text
