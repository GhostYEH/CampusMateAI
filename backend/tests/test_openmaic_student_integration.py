"""OpenMAIC 学生侧集成 —— 行为测试(不是读源码的正则断言)。

覆盖用户要求的 9 项验收：
1. 后端安全返回可信 OpenMAIC Origin(含端口)，未配置时 fail-closed；
2. CPM 课程权限复用统一策略，支持 enrollment 课程与学生自有的学习通导入课程；
3. user_id+course_id 并发生成只提交一次，复用任务返回真实 mode；
4. 仅后端可见的 ACCESS_CODE 认证，凭据不泄露；
5. 真实生成步骤 initializing/researching/generating_outlines/generating_scenes/
   generating_media/generating_tts/persisting/completed 与 queued/running/succeeded/failed、
   updated_at、错误状态同步；
6. status 的 enabled/unavailable 契约；
7. 知识点/知识图谱统计/真实掌握率进入 OpenMAIC 与 CPM 上下文，严格按用户+课程过滤、限长；
8. 每用户每课程最多 20 条历史，只裁剪最早的终态记录。

全部通过 httpx.MockTransport 模拟 OpenMAIC 服务，不伪造真实生成结果。
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Tuple

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.routes.counselor import _collect_teaching_context
from app.core.config import Settings
from app.main import create_app
from app.schemas.chat import ChatRequest
from app.services.container import ServiceContainer, reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.openmaic.classroom_service import PUBLIC_STEPS, OpenMAICClassroomService
from app.services.openmaic.client import (
    GENERATION_STEPS,
    JOB_STATUS_VALUES,
    JOB_STEP_VALUES,
    PROBE_JOB_ID,
    OpenMAICClient,
    normalize_step,
)
from app.services.openmaic.course_context import build_course_context, build_cpm_course_block
from app.services.openmaic import result_store as result_store_module
from app.services.openmaic.result_store import OpenMAICResultStore, OpenMAICSession

BASE = "http://127.0.0.1:3000"


# ===== 脚手架 =====


def _test_settings(**overrides) -> Settings:
    kwargs = dict(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        llm_provider="none",
        agent_allow_mock_providers=True,
        openmaic_enabled=True,
        openmaic_base_url=BASE,
        # 浏览器公开 Origin 与内部 BASE_URL 分离；测试里用同一地址便于断言
        openmaic_embed_origin=BASE,
    )
    kwargs.update(overrides)
    return Settings(**kwargs)


def _probe_not_found() -> httpx.Response:
    """契约指纹 P3 的真实期望：格式合法但不存在的 jobId → 404 INVALID_REQUEST。"""
    return httpx.Response(
        404,
        json={
            "success": False,
            "errorCode": "INVALID_REQUEST",
            "error": "Classroom generation job not found",
        },
    )


def _is_probe(request: httpx.Request) -> bool:
    """只匹配契约指纹探针（用固定的探针 jobId），不要误伤真实轮询。"""
    return request.method == "GET" and request.url.path.endswith(
        f"/api/generate-classroom/{PROBE_JOB_ID}"
    )


def _login(client: TestClient, username: str = "student_demo") -> Dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "Demo123456"}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _bootstrap(
    tmp_path,
    handler: Callable[[httpx.Request], httpx.Response],
    **overrides,
) -> Tuple[ServiceContainer, TestClient, Dict[str, str], OpenMAICResultStore]:
    settings = _test_settings(**overrides)
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    store = OpenMAICResultStore(
        tmp_path / "openmaic_classrooms",
        max_results=settings.openmaic_max_results_per_course,
    )
    client = OpenMAICClient(
        base_url=BASE,
        timeout_seconds=5.0,
        origin=BASE,
        transport=httpx.MockTransport(handler),
        access_code=settings.openmaic_access_code,
    )
    container.openmaic_result_store = store
    container.openmaic_classroom_service = OpenMAICClassroomService(
        settings, store, client=client
    )
    tc = TestClient(create_app())
    return container, tc, _login(tc), store


def _first_course(tc: TestClient, headers: Dict[str, str]) -> str:
    resp = tc.get("/api/v1/courses", headers=headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert items, "demo 学生应有课程"
    return items[0]["id"]


def _student(container: ServiceContainer, username: str = "student_demo"):
    user = container.user_repository.get_user_by_username(username)
    assert user is not None
    return user


def _recording_handler(
    recorder: List[httpx.Request],
    *,
    steps: List[str] | None = None,
    submit_job_id: str = "job_1",
    classroom_id: str = "room_1",
    scenes: int = 4,
):
    """一个可复用的假 OpenMAIC：health / submit / poll 都记录请求。"""
    lock = threading.Lock()
    step_seq = list(steps or [])

    def handler(request: httpx.Request) -> httpx.Response:
        with lock:
            recorder.append(request)
        path = request.url.path
        if path.endswith("/api/access-code/status"):
            return httpx.Response(200, json={"success": True, "enabled": False})
        if path.endswith("/api/health"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "status": "ok",
                    "version": "0.9.9",
                    "capabilities": {"tts": True, "webSearch": False},
                },
            )
        if _is_probe(request):
            return _probe_not_found()
        if request.method == "POST" and path.endswith("/api/generate-classroom"):
            return httpx.Response(202, json={"success": True, "jobId": submit_job_id})
        if step_seq:
            step = step_seq.pop(0)
            if step in ("succeeded", "failed"):
                pass
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "status": "running",
                    "step": step,
                    "progress": 30,
                    "message": f"正在 {step}",
                },
            )
        return httpx.Response(
            200,
            json={
                "success": True,
                "status": "succeeded",
                "step": "completed",
                "progress": 100,
                "done": True,
                "message": "完成",
                "result": {
                    "classroomId": classroom_id,
                    "url": f"{BASE}/classroom/{classroom_id}",
                    "scenesCount": scenes,
                },
            },
        )

    return handler


# ===== 5. 真实生成步骤契约 =====


def test_public_step_contract_matches_real_openmaic():
    assert GENERATION_STEPS == (
        "initializing",
        "researching",
        "generating_outlines",
        "generating_scenes",
        "generating_media",
        "generating_tts",
        "persisting",
        "completed",
    )
    assert JOB_STEP_VALUES == ("queued", "failed", *GENERATION_STEPS)
    assert JOB_STATUS_VALUES == ("queued", "running", "succeeded", "failed")
    # 旧的臆造阶段名不再被接受
    for stale in ("analyzing", "outlining", "generating", "media", "voice", "saving", "done"):
        assert stale not in PUBLIC_STEPS


@pytest.mark.parametrize("step", GENERATION_STEPS)
def test_client_passes_through_each_real_step(step):
    def handler(request):
        return httpx.Response(
            200, json={"success": True, "status": "running", "step": step, "progress": 40}
        )

    client = OpenMAICClient(
        base_url=BASE, origin=BASE, transport=httpx.MockTransport(handler)
    )
    result = asyncio.run(client.poll("job_x"))
    assert result.step == step
    assert result.status == "running"
    assert result.done is False


def test_client_maps_terminal_states_and_error():
    def ok(request):
        return httpx.Response(
            200,
            json={
                "success": True,
                "status": "succeeded",
                "step": "completed",
                "progress": 100,
                "done": True,
                "result": {
                    "classroomId": "r1",
                    "url": f"{BASE}/classroom/r1",
                    "scenesCount": 3,
                },
            },
        )

    succeeded = asyncio.run(
        OpenMAICClient(base_url=BASE, origin=BASE, transport=httpx.MockTransport(ok)).poll("j")
    )
    assert (succeeded.status, succeeded.step, succeeded.done) == ("succeeded", "completed", True)

    def bad(request):
        return httpx.Response(
            200,
            json={
                "success": True,
                "status": "failed",
                "step": "failed",
                "done": True,
                "error": {"message": "场景生成失败"},
            },
        )

    failed = asyncio.run(
        OpenMAICClient(base_url=BASE, origin=BASE, transport=httpx.MockTransport(bad)).poll("j")
    )
    assert (failed.status, failed.step, failed.done) == ("failed", "failed", True)
    assert failed.error == "场景生成失败"


def test_normalize_step_falls_back_without_faking():
    assert normalize_step("generating_tts", "running") == "generating_tts"
    assert normalize_step("", "failed") == "failed"
    assert normalize_step("", "succeeded") == "completed"
    assert normalize_step("bogus", "running") == "initializing"


def test_route_syncs_steps_updated_at_and_terminal_state(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(
        tmp_path,
        _recording_handler(recorder, steps=["initializing", "researching", "generating_scenes"]),
    )
    cid = _first_course(tc, headers)
    gen = tc.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "adaptive"},
    )
    assert gen.status_code == 202, gen.text
    sid = gen.json()["session"]["session_id"]
    # 真实契约：202 提交后任务仍处于 queued
    assert gen.json()["session"]["status"] == "queued"
    assert gen.json()["session"]["step"] == "queued"

    seen_steps = []
    last_updated = gen.json()["session"]["updated_at"]
    for _ in range(3):
        body = tc.get(
            f"/api/v1/courses/{cid}/interactive-classroom/jobs/{sid}", headers=headers
        ).json()
        assert body["status"] == "running"
        seen_steps.append(body["step"])
        assert body["updated_at"] >= last_updated, "每次轮询都必须刷新 updated_at"
        last_updated = body["updated_at"]
    assert seen_steps == ["initializing", "researching", "generating_scenes"]

    done = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/jobs/{sid}", headers=headers
    ).json()
    assert done["status"] == "succeeded"
    assert done["step"] == "completed"
    assert done["progress"] == 100
    assert done["url"] == f"{BASE}/classroom/room_1"
    assert done["scenes_count"] == 4
    assert done["error"] is None


# ===== 6 + 1. status 契约与可信 Origin =====


def test_status_exposes_trusted_origin_with_port(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _recording_handler(recorder))
    cid = _first_course(tc, headers)
    body = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/status", headers=headers
    ).json()
    assert body["enabled"] is True
    assert body["configured"] is True
    assert body["available"] is True
    assert body["unavailable"] is False
    # 必须带端口，客户端才能做完整 origin 精确校验
    assert body["embed_origin"] == "http://127.0.0.1:3000"
    assert body["browser_embed_available"] is True
    assert body["browser_embed_reason"] is None
    assert body["version"] == "0.9.9"


def test_status_contract_when_health_unreachable(tmp_path):
    def handler(request: httpx.Request):
        raise httpx.ConnectError("connection refused", request=request)

    _, tc, headers, _ = _bootstrap(tmp_path, handler)
    cid = _first_course(tc, headers)
    body = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/status", headers=headers
    ).json()
    assert body["enabled"] is False
    assert body["configured"] is True
    assert body["available"] is False
    assert body["unavailable"] is True, "health 不可达必须体现在 unavailable 上"
    assert body["reason"]
    # Origin 仍返回，便于前端在恢复后按精确 origin 打开历史课堂
    assert body["embed_origin"] == BASE


def test_status_contract_when_not_configured(tmp_path):
    _, tc, headers, _ = _bootstrap(
        tmp_path, _recording_handler([]), openmaic_enabled=False
    )
    cid = _first_course(tc, headers)
    body = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/status", headers=headers
    ).json()
    assert body["enabled"] is False
    assert body["configured"] is False
    assert body["unavailable"] is False
    assert body["embed_origin"] is None, "未配置时必须 fail-closed(不下发可信 Origin)"
    gen = tc.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "adaptive"},
    )
    assert gen.status_code == 503
    assert gen.json()["code"] == "OPENMAIC_NOT_ENABLED"


# ===== 4. ACCESS_CODE =====

ACCESS_CODE = "s3cret-access-code"


def _access_code_handler(recorder: List[httpx.Request]) -> Callable:
    lock = threading.Lock()

    def handler(request: httpx.Request) -> httpx.Response:
        with lock:
            recorder.append(request)
        path = request.url.path
        cookie = request.headers.get("cookie", "")
        if path.endswith("/api/access-code/status"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "enabled": True,
                    "authenticated": "openmaic_access=" in cookie,
                },
            )
        if path.endswith("/api/access-code/verify"):
            try:
                payload = json.loads(request.content.decode() or "{}")
            except ValueError:
                payload = {}
            if payload.get("code") != ACCESS_CODE:
                return httpx.Response(
                    401, json={"success": False, "error": "Invalid access code"}
                )
            return httpx.Response(
                200,
                json={"success": True, "valid": True},
                headers={"set-cookie": "openmaic_access=token-abc; Path=/; HttpOnly"},
            )
        # 真实 middleware：除白名单外所有 /api/* 都需要有效 cookie
        if "openmaic_access=token-abc" not in cookie:
            return httpx.Response(
                401,
                json={
                    "success": False,
                    "errorCode": "INVALID_REQUEST",
                    "error": "Access code required",
                },
            )
        if path.endswith("/api/health"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "status": "ok",
                    "version": "1.0.0",
                    "capabilities": {"tts": True},
                },
            )
        if _is_probe(request):
            return _probe_not_found()
        if request.method == "POST" and path.endswith("/api/generate-classroom"):
            return httpx.Response(202, json={"success": True, "jobId": "job_ac"})
        return httpx.Response(
            200,
            json={
                "success": True,
                "status": "succeeded",
                "step": "completed",
                "progress": 100,
                "done": True,
                "result": {
                    "classroomId": "room_ac",
                    "url": f"{BASE}/classroom/room_ac",
                    "scenesCount": 2,
                },
            },
        )

    return handler


def test_access_code_is_verified_and_cookie_is_reused(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(
        tmp_path, _access_code_handler(recorder), openmaic_access_code=ACCESS_CODE
    )
    cid = _first_course(tc, headers)

    status = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/status", headers=headers
    ).json()
    assert status["enabled"] is True, status
    assert status["browser_embed_available"] is False
    assert "访问保护" in status["browser_embed_reason"]
    gen = tc.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "explain"},
    )
    assert gen.status_code == 202, gen.text
    sid = gen.json()["session"]["session_id"]
    job = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/jobs/{sid}", headers=headers
    ).json()
    assert job["status"] == "succeeded"
    assert job["url"] == f"{BASE}/classroom/room_ac"

    verifies = [r for r in recorder if r.url.path.endswith("/api/access-code/verify")]
    assert len(verifies) == 1, "同一客户端只应校验一次访问码"
    assert json.loads(verifies[0].content.decode())["code"] == ACCESS_CODE

    submits = [
        r
        for r in recorder
        if r.method == "POST" and r.url.path.endswith("/api/generate-classroom")
    ]
    assert submits and "openmaic_access=token-abc" in submits[0].headers.get("cookie", "")

    # 凭据绝不进入任何响应体
    for payload in (status, gen.json(), job):
        assert ACCESS_CODE not in json.dumps(payload, ensure_ascii=False)


def test_access_code_required_but_not_configured_fails_closed(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(
        tmp_path, _access_code_handler(recorder), openmaic_access_code=""
    )
    cid = _first_course(tc, headers)
    status = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/status", headers=headers
    ).json()
    assert status["enabled"] is False
    assert status["configured"] is True
    assert status["unavailable"] is True
    gen = tc.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "adaptive"},
    )
    assert gen.status_code == 502
    assert gen.json()["code"] == "OPENMAIC_AUTH_ERROR"
    assert ACCESS_CODE not in json.dumps(gen.json(), ensure_ascii=False)
    # 未拿到访问码时绝不提交生成任务
    assert not [
        r
        for r in recorder
        if r.method == "POST" and r.url.path.endswith("/api/generate-classroom")
    ]


def test_wrong_access_code_is_rejected(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(
        tmp_path, _access_code_handler(recorder), openmaic_access_code="wrong-code"
    )
    cid = _first_course(tc, headers)
    status = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/status", headers=headers
    ).json()
    assert status["enabled"] is False
    assert status["unavailable"] is True


# ===== 3. 并发只提交一次 + 复用返回真实 mode =====


def test_concurrent_generate_submits_exactly_once(tmp_path):
    recorder: List[httpx.Request] = []
    lock = threading.Lock()

    def handler(request: httpx.Request) -> httpx.Response:
        with lock:
            recorder.append(request)
        path = request.url.path
        if path.endswith("/api/access-code/status"):
            return httpx.Response(
                200, json={"success": True, "enabled": False, "authenticated": False}
            )
        if path.endswith("/api/health"):
            return httpx.Response(
                200, json={"success": True, "status": "ok", "capabilities": {}}
            )
        if _is_probe(request):
            return _probe_not_found()
        if request.method == "POST" and path.endswith("/api/generate-classroom"):
            # 拉大窗口，让并发请求真的重叠
            time.sleep(0.2)
            return httpx.Response(202, json={"success": True, "jobId": "job_once"})
        return httpx.Response(
            200,
            json={"success": True, "status": "running", "step": "researching", "progress": 20},
        )

    _, tc, headers, _ = _bootstrap(tmp_path, handler)
    cid = _first_course(tc, headers)
    url = f"/api/v1/courses/{cid}/interactive-classroom/generate"
    # 混入旧值：必须被归一化后接受，不能 4xx
    # 混入旧值：必须被归一化后接受，不能 4xx
    modes = ["adaptive", "explore", "practice", "project", "explain", "adaptive", "explore", "practice"]

    with ThreadPoolExecutor(max_workers=len(modes)) as pool:
        futures = [
            pool.submit(tc.post, url, headers=headers, json={"mode": m}) for m in modes
        ]
        responses = [f.result() for f in futures]

    assert all(r.status_code == 202 for r in responses), [r.text for r in responses]
    submits = [
        r
        for r in recorder
        if r.method == "POST" and r.url.path.endswith("/api/generate-classroom")
    ]
    assert len(submits) == 1, f"并发请求只应提交一次，实际 {len(submits)} 次"

    bodies = [r.json() for r in responses]
    session_ids = {b["session"]["session_id"] for b in bodies}
    assert len(session_ids) == 1, "并发请求必须复用同一个任务"
    # 复用任务时必须返回任务真实 mode，而不是本次请求的 mode
    top_modes = {b["mode"] for b in bodies}
    assert len(top_modes) == 1, f"复用时 mode 必须一致，实际 {top_modes}"
    assert top_modes == {bodies[0]["session"]["mode"]}
    assert top_modes.pop() in {
        "adaptive", "explain", "quiz", "simulation", "visualization",
        "mindmap", "coding", "pbl", "review",
    }


def test_second_generate_after_terminal_starts_new_task(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, store = _bootstrap(tmp_path, _recording_handler(recorder))
    cid = _first_course(tc, headers)
    url = f"/api/v1/courses/{cid}/interactive-classroom/generate"

    first = tc.post(url, headers=headers, json={"mode": "adaptive"}).json()
    sid = first["session"]["session_id"]
    # 完成首个任务
    done = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/jobs/{sid}", headers=headers
    ).json()
    assert done["status"] == "succeeded"

    second = tc.post(url, headers=headers, json={"mode": "project"})
    assert second.status_code == 202
    assert second.json()["session"]["session_id"] != sid
    # 旧值 project 归一化到 pbl
    assert second.json()["mode"] == "pbl"
    submits = [
        r
        for r in recorder
        if r.method == "POST" and r.url.path.endswith("/api/generate-classroom")
    ]
    assert len(submits) == 2, "终态后应允许开启新任务"


def test_stale_reservation_can_be_taken_over(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, store = _bootstrap(
        tmp_path, _recording_handler(recorder), openmaic_reservation_ttl_seconds=30
    )
    cid = _first_course(tc, headers)
    user = _student(container_from(tc))
    # 手工写入一个过期预占(模拟提交者崩溃)
    assert store.acquire_reservation(
        user_id=user.id, course_id=cid, session_id="om_stale", mode="adaptive"
    )
    stale = store.read_reservation(user_id=user.id, course_id=cid)
    assert stale is not None
    stale.updated_at = "2020-01-01T00:00:00+00:00"
    store._write_json_atomic(store._reservation_path(user.id, cid), stale.to_dict())

    resp = tc.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "explore"},
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["session"]["session_id"] != "om_stale"
    # 旧值 explore 归一化到 simulation
    assert resp.json()["mode"] == "simulation"


def test_concurrent_stale_takeover_has_exactly_one_winner(tmp_path, monkeypatch):
    """两个调用都读到同一旧租约时，接管必须具备 compare-and-swap 语义。"""
    store = OpenMAICResultStore(tmp_path / "om")
    assert store.acquire_reservation(
        user_id="u1", course_id="c1", session_id="om_stale", mode="adaptive"
    )
    stale = store.read_reservation(user_id="u1", course_id="c1")
    assert stale is not None
    stale.updated_at = "2020-01-01T00:00:00+00:00"
    store._write_json_atomic(store._reservation_path("u1", "c1"), stale.to_dict())
    service = OpenMAICClassroomService(
        _test_settings(openmaic_reservation_ttl_seconds=30), store, client=None
    )

    # 先让两个接管者都读取同一份旧租约，再强制 B 的 unlink 发生在 A 完成接管后。
    # 旧实现因此稳定地产生两个 winner；具备 CAS 的实现会在 B unlink 前拒绝接管。
    reads_ready = threading.Barrier(2)
    first_takeover_entered = threading.Event()
    first_takeover_finished = threading.Event()
    thread_role = threading.local()
    read_count = 0
    read_lock = threading.Lock()
    original_read = store.read_reservation

    def synchronized_read(*, user_id, course_id):
        nonlocal read_count
        value = original_read(user_id=user_id, course_id=course_id)
        with read_lock:
            read_count += 1
            should_wait = read_count <= 2
        if should_wait:
            reads_ready.wait(timeout=5)
            if getattr(thread_role, "value", None) == "B":
                assert first_takeover_entered.wait(timeout=5)
        return value

    reservation_path = os.fspath(store._reservation_path("u1", "c1"))
    real_unlink = result_store_module.os.unlink

    def ordered_unlink(path, *args, **kwargs):
        if os.fspath(path) != reservation_path:
            return real_unlink(path, *args, **kwargs)
        if getattr(thread_role, "value", None) == "B":
            assert first_takeover_finished.wait(timeout=5)
        else:
            first_takeover_entered.set()
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(store, "read_reservation", synchronized_read)
    monkeypatch.setattr(result_store_module.os, "unlink", ordered_unlink)

    def acquire(role_and_mode):
        role, mode = role_and_mode
        thread_role.value = role
        try:
            return service._acquire(user_id="u1", course_id="c1", mode=mode)
        finally:
            if role == "A":
                first_takeover_finished.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(acquire, (("A", "explain"), ("B", "practice"))))

    winners = [session_id for session_id, reusable in results if reusable is None]
    reused = [reusable for _, reusable in results if reusable is not None]
    assert len(winners) == 1
    assert len(reused) == 1
    assert reused[0].session_id == winners[0]


def container_from(tc: TestClient) -> ServiceContainer:
    from app.services.container import get_container

    return get_container()


# ===== 8. 历史裁剪 =====


def test_history_capped_at_20_pruning_oldest_terminal(tmp_path):
    store = OpenMAICResultStore(tmp_path / "om", max_results=20)
    ids = []
    for i in range(21):
        session = OpenMAICSession(
            session_id=f"om_{i:04d}",
            course_id="c1",
            user_id="u1",
            status="succeeded",
            step="completed",
            progress=100,
            classroom_url=f"{BASE}/classroom/r{i}",
            created_at=f"2026-09-15T00:{i:02d}:00+00:00",
        )
        store.save(session)
        ids.append(session.session_id)

    sessions = store.list_sessions(user_id="u1", course_id="c1")
    assert len(sessions) == 20, f"应裁剪到 20 条，实际 {len(sessions)}"
    remaining = {s.session_id for s in sessions}
    assert "om_0000" not in remaining, "最早的终态记录必须被裁剪"
    assert "om_0020" in remaining, "最新记录必须保留"
    assert remaining == set(ids[1:])
    # 每用户每课程独立计数
    assert store.list_sessions(user_id="u1", course_id="c2") == []
    assert store.list_sessions(user_id="u2", course_id="c1") == []


def test_history_pruning_never_removes_running_records(tmp_path):
    store = OpenMAICResultStore(tmp_path / "om", max_results=3)
    for i in range(3):
        store.save(
            OpenMAICSession(
                session_id=f"om_term_{i}",
                course_id="c1",
                user_id="u1",
                status="succeeded",
                step="completed",
                created_at=f"2026-09-15T00:0{i}:00+00:00",
            )
        )
    store.save(
        OpenMAICSession(
            session_id="om_active",
            course_id="c1",
            user_id="u1",
            status="running",
            step="generating_scenes",
            created_at="2026-09-15T00:09:00+00:00",
        )
    )
    sessions = store.list_sessions(user_id="u1", course_id="c1")
    ids = {s.session_id for s in sessions}
    assert len(sessions) == 3
    assert "om_active" in ids, "进行中的记录永不被裁剪"
    assert "om_term_0" not in ids, "应裁剪最早的终态记录"


# ===== 7. 知识点/掌握率进入上下文 =====


def _seed_knowledge(
    container: ServiceContainer,
    *,
    user_id: str,
    course_id: str,
    names: List[str],
    mastery: float,
    class_rate: float,
    tags: List[str],
) -> None:
    container.chaoxing_repository.upsert_knowledge_graph(
        user_id=user_id,
        course_id=course_id,
        external_course_id="ext-1",
        graph={
            "knowledge_point_count": len(names),
            "own_mastery_rate": mastery,
            "class_mastery_rate": class_rate,
            "own_completion_rate": 80.0,
            "class_completion_rate": 70.0,
            "tags": tags,
        },
        points=[
            {"external_id": f"kp-{i}", "name": name} for i, name in enumerate(names)
        ],
    )


def _own_chaoxing_course(container: ServiceContainer, user):
    return container.course_repository.create_course(
        name="我的学习通课程",
        code="CX-1",
        semester="2026 秋",
        provider="chaoxing",
        owner_user_id=user.id,
        status="active",
    )


def test_openmaic_context_includes_knowledge_and_mastery(tmp_path):
    container, _, _, _ = _bootstrap(tmp_path, _recording_handler([]))
    user = _student(container)
    course = _own_chaoxing_course(container, user)
    _seed_knowledge(
        container,
        user_id=user.id,
        course_id=course.id,
        names=["导数定义", "极限", "连续性"],
        mastery=72.5,
        class_rate=65.0,
        tags=["微积分", "第一章"],
    )
    ctx = build_course_context(container, user, course)
    assert "[知识点与掌握情况]" in ctx
    for name in ("导数定义", "极限", "连续性"):
        assert name in ctx
    assert "我的掌握率:72.5%" in ctx
    assert "班级平均掌握率:65.0%" in ctx
    assert "与班级差:7.5 个百分点" in ctx
    assert "微积分" in ctx
    assert len(ctx) <= 4000
    for forbidden in ("password", "jwt", "cookie", "authorization", "api_key"):
        assert forbidden not in ctx.lower()


def test_cpm_context_includes_knowledge_and_mastery(tmp_path):
    container, _, _, _ = _bootstrap(tmp_path, _recording_handler([]))
    user = _student(container)
    course = _own_chaoxing_course(container, user)
    _seed_knowledge(
        container,
        user_id=user.id,
        course_id=course.id,
        names=["傅里叶变换"],
        mastery=51.0,
        class_rate=60.5,
        tags=["信号"],
    )
    block = build_cpm_course_block(container, user, course)
    assert "[知识点与掌握情况]" in block
    assert "傅里叶变换" in block
    assert "我的掌握率:51.0%" in block
    assert "与班级差:-9.5 个百分点" in block


def test_context_does_not_leak_other_users_knowledge(tmp_path):
    container, _, _, _ = _bootstrap(tmp_path, _recording_handler([]))
    user = _student(container)
    other = _student(container, "student_demo_02")
    course = _own_chaoxing_course(container, user)
    _seed_knowledge(
        container,
        user_id=user.id,
        course_id=course.id,
        names=["我自己的知识点"],
        mastery=70.0,
        class_rate=60.0,
        tags=[],
    )
    # 同一门课程 id、另一个用户的知识点：必须按 user_id 过滤掉
    _seed_knowledge(
        container,
        user_id=other.id,
        course_id=course.id,
        names=["他人私密知识点"],
        mastery=99.0,
        class_rate=10.0,
        tags=[],
    )
    for ctx in (
        build_course_context(container, user, course),
        build_cpm_course_block(container, user, course),
    ):
        assert "我自己的知识点" in ctx
        assert "他人私密知识点" not in ctx
        assert "99.0%" not in ctx


def test_knowledge_context_is_length_limited(tmp_path):
    container, _, _, _ = _bootstrap(tmp_path, _recording_handler([]))
    user = _student(container)
    course = _own_chaoxing_course(container, user)
    _seed_knowledge(
        container,
        user_id=user.id,
        course_id=course.id,
        names=[f"知识点{i:03d}" for i in range(200)],
        mastery=10.0,
        class_rate=20.0,
        tags=[f"标签{i}" for i in range(100)],
    )
    ctx = build_course_context(container, user, course, max_chars=200)
    assert len(ctx) <= 200 + len("\n[已截断]")
    assert ctx.endswith("[已截断]")
    # 默认上限下也不得超长，且知识点条目本身有数量上限
    default_ctx = build_course_context(container, user, course)
    assert len(default_ctx) <= 4000
    assert default_ctx.count("知识点0") <= 20, "知识点条目必须限长"
    block = build_cpm_course_block(container, user, course, max_chars=300)
    assert len(block) <= 300


def test_knowledge_context_absent_when_never_synced(tmp_path):
    container, _, _, _ = _bootstrap(tmp_path, _recording_handler([]))
    user = _student(container)
    course = _own_chaoxing_course(container, user)
    ctx = build_course_context(container, user, course)
    assert "[知识点与掌握情况]" not in ctx, "未同步过不得编造知识点/掌握率"


# ===== 2. CPM 权限复用统一策略 =====


def test_cpm_accepts_own_chaoxing_imported_course(tmp_path):
    container, _, _, _ = _bootstrap(tmp_path, _recording_handler([]))
    user = _student(container)
    course = _own_chaoxing_course(container, user)
    req = ChatRequest(message="帮我复习这门课", course_id=course.id, stream=False)
    block, used, warnings = _collect_teaching_context(container, user, req)
    assert used.get("course_id") == course.id
    assert "我的学习通课程" in block
    assert not any("无权访问" in w for w in warnings)


def test_cpm_rejects_chaoxing_course_owned_by_someone_else(tmp_path):
    container, _, _, _ = _bootstrap(tmp_path, _recording_handler([]))
    user = _student(container)
    other = _student(container, "student_demo_02")
    foreign = container.course_repository.create_course(
        name="别人的学习通课程",
        code="CX-X",
        provider="chaoxing",
        owner_user_id=other.id,
        status="active",
    )
    req = ChatRequest(message="帮我复习", course_id=foreign.id, stream=False)
    block, used, warnings = _collect_teaching_context(container, user, req)
    assert block == ""
    assert "course_id" not in used
    assert any("无权访问" in w for w in warnings)


def test_cpm_still_accepts_enrollment_course(tmp_path):
    container, tc, headers, _ = _bootstrap(tmp_path, _recording_handler([]))
    user = _student(container)
    cid = _first_course(tc, headers)
    req = ChatRequest(message="帮我复习", course_id=cid, stream=False)
    block, used, warnings = _collect_teaching_context(container, user, req)
    assert used.get("course_id") == cid
    assert block != ""
    assert not any("无权访问" in w for w in warnings)


def test_openmaic_route_accepts_own_chaoxing_course(tmp_path):
    container, tc, headers, _ = _bootstrap(tmp_path, _recording_handler([]))
    user = _student(container)
    course = _own_chaoxing_course(container, user)
    resp = tc.get(
        f"/api/v1/courses/{course.id}/interactive-classroom/status", headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["configured"] is True


def test_openmaic_route_rejects_foreign_chaoxing_course(tmp_path):
    container, tc, headers, _ = _bootstrap(tmp_path, _recording_handler([]))
    other = _student(container, "student_demo_02")
    foreign = container.course_repository.create_course(
        name="别人的学习通课程",
        code="CX-Y",
        provider="chaoxing",
        owner_user_id=other.id,
        status="active",
    )
    resp = tc.get(
        f"/api/v1/courses/{foreign.id}/interactive-classroom/status", headers=headers
    )
    assert resp.status_code in (403, 404)


# ===== 1. 课堂 URL 可信性(后端侧) =====


def test_poll_rejects_url_from_same_host_different_port(tmp_path):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "success": True,
                "status": "succeeded",
                "step": "completed",
                "progress": 100,
                "done": True,
                "result": {
                    "classroomId": "room_1",
                    "url": "http://127.0.0.1:30001/classroom/room_1",
                    "scenesCount": 1,
                },
            },
        )

    client = OpenMAICClient(
        base_url=BASE, origin=BASE, transport=httpx.MockTransport(handler)
    )
    from app.services.openmaic.errors import OpenMAICInvalidOrigin

    with pytest.raises(OpenMAICInvalidOrigin):
        asyncio.run(client.poll("job_1"))


def test_history_list_returns_only_trusted_succeeded_classrooms(tmp_path):
    recorder: List[httpx.Request] = []
    container, tc, headers, store = _bootstrap(tmp_path, _recording_handler(recorder))
    cid = _first_course(tc, headers)
    user = _student(container)
    store.save(
        OpenMAICSession(
            session_id="om_ok",
            course_id=cid,
            user_id=user.id,
            status="succeeded",
            step="completed",
            # 公开地址由可信 classroom_id 现场构造；这里显式给出 classroom_id，
            # 否则（旧数据缺标识）后端不会下发任何地址。
            classroom_id="room_ok",
            classroom_url=f"{BASE}/classroom/room_ok",
            mode="explain",
        )
    )
    store.save(
        OpenMAICSession(
            session_id="om_running",
            course_id=cid,
            user_id=user.id,
            status="running",
            step="generating_scenes",
            mode="adaptive",
        )
    )
    body = tc.get(f"/api/v1/courses/{cid}/interactive-classroom", headers=headers).json()
    assert body["enabled"] is True
    urls = [item["url"] for item in body["items"]]
    assert urls == [f"{BASE}/classroom/room_ok"]
    assert body["items"][0]["mode"] == "explain"

