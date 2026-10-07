"""magicclass 互动课堂适配层测试。

覆盖：
- 权限：有权限学生生成 / 越权与不存在课程被拒
- requirement 构造：不同模式 / 不向 magicclass 传密钥与认证信息
- 依据 health capabilities 过滤可选功能
- 202 提交 + 轮询成功
- 超时 / 429 / 5xx / 无效 JSON / 任务失败
- 返回 URL Origin 校验
- 幂等提交
- 未配置时安全降级
- 课程上下文包含章节但不泄露隐私
通过 httpx.MockTransport 模拟 magicclass，不伪造真实生成。
"""
from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.magicclass.client import PROBE_JOB_ID, MagicClassClient
from app.services.magicclass.classroom_service import MagicClassClassroomService
from app.services.magicclass.course_context import build_course_context
from app.services.magicclass.requirement_builder import (
    build_input_payload,
    build_requirement,
    validate_mode,
)
from app.services.magicclass.result_store import (
    MagicClassReservation,
    MagicClassResultStore,
    MagicClassSession,
    new_session_id,
)

BASE = "http://127.0.0.1:3000"


def _test_settings(**overrides) -> Settings:
    kwargs = dict(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        llm_provider="none",
        agent_allow_mock_providers=True,
        magicclass_enabled=True,
        magicclass_base_url=BASE,
        # 浏览器公开 Origin 与内部 BASE_URL 分离；测试里用同一地址便于断言
        magicclass_embed_origin=BASE,
    )
    kwargs.update(overrides)
    return Settings(**kwargs)


@pytest.mark.asyncio
async def test_poll_persistence_runs_outside_event_loop_thread():
    import threading

    thread_ids = []

    def record_thread(*args, **kwargs):
        thread_ids.append(threading.get_ident())

    def resolve_missing_job(session, **_kwargs):
        record_thread()
        session.status = "failed"
        session.step = "failed"
        session.progress = 100
        return "closed"

    store = SimpleNamespace(resolve_missing_job_for_poll=resolve_missing_job)
    service = MagicClassClassroomService(settings=_test_settings(), store=store, client=object())
    session = SimpleNamespace(is_terminal=False, job_id=None, user_id="user", course_id="course", session_id="session")
    await service.poll(session)
    assert session.status == "failed"
    assert len(thread_ids) == 1
    assert all(thread_id != threading.get_ident() for thread_id in thread_ids)


def _age_reservation(store, user_id: str, course_id: str, session_id: str, mode: str = "review"):
    old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    reservation = MagicClassReservation(
        session_id=session_id, mode=mode, created_at=old, updated_at=old
    )
    store._write_json_atomic(
        store._reservation_path(user_id, course_id), reservation.to_dict()
    )


def test_stale_queued_session_without_job_id_is_taken_over_and_closed(tmp_path):
    store = MagicClassResultStore(tmp_path)
    service = MagicClassClassroomService(
        settings=_test_settings(magicclass_reservation_ttl_seconds=30),
        store=store,
        client=object(),
    )
    old_id = new_session_id()
    old = MagicClassSession(
        session_id=old_id,
        course_id="course",
        user_id="user",
        mode="review",
        status="queued",
        step="queued",
    )
    store.save(old)
    _age_reservation(store, "user", "course", old_id)

    new_id, reusable = service._acquire(user_id="user", course_id="course", mode="quiz")

    assert new_id != old_id
    assert reusable is None
    abandoned = store.get_session(user_id="user", course_id="course", session_id=old_id)
    assert abandoned.status == "failed"
    assert abandoned.error_code == "SUBMISSION_OUTCOME_UNKNOWN"
    assert store.read_reservation(user_id="user", course_id="course").session_id == new_id


def test_stale_reservation_with_known_job_id_is_reused(tmp_path):
    store = MagicClassResultStore(tmp_path)
    service = MagicClassClassroomService(
        settings=_test_settings(magicclass_reservation_ttl_seconds=30),
        store=store,
        client=object(),
    )
    session_id = new_session_id()
    session = MagicClassSession(
        session_id=session_id,
        course_id="course",
        user_id="user",
        mode="review",
        job_id="upstream_job",
        status="running",
        step="generating_scenes",
    )
    store.save(session)
    _age_reservation(store, "user", "course", session_id)

    acquired_id, reusable = service._acquire(
        user_id="user", course_id="course", mode="quiz"
    )

    assert acquired_id == session_id
    assert reusable.job_id == "upstream_job"
    assert store.read_reservation(user_id="user", course_id="course").session_id == session_id


def test_reservation_job_id_recovers_session_persist_crash_window(tmp_path):
    store = MagicClassResultStore(tmp_path)
    service = MagicClassClassroomService(
        settings=_test_settings(magicclass_reservation_ttl_seconds=30),
        store=store,
        client=object(),
    )
    session_id = new_session_id()
    store.save(
        MagicClassSession(
            session_id=session_id,
            course_id="course",
            user_id="user",
            mode="review",
            status="queued",
            step="queued",
        )
    )
    _age_reservation(store, "user", "course", session_id)
    reservation = store.read_reservation(user_id="user", course_id="course")
    reservation.job_id = "upstream_job"
    store._write_json_atomic(
        store._reservation_path("user", "course"), reservation.to_dict()
    )

    acquired_id, reusable = service._acquire(
        user_id="user", course_id="course", mode="quiz"
    )

    assert acquired_id == session_id
    assert reusable.job_id == "upstream_job"
    assert reusable.status == "queued"


def test_stale_reservation_takeover_is_compare_and_swap(tmp_path):
    store = MagicClassResultStore(tmp_path)
    service = MagicClassClassroomService(
        settings=_test_settings(magicclass_reservation_ttl_seconds=30),
        store=store,
        client=object(),
    )
    old_id = new_session_id()
    _age_reservation(store, "user", "course", old_id)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: service._acquire(
                    user_id="user", course_id="course", mode="review"
                ),
                range(8),
            )
        )

    session_ids = {session_id for session_id, _ in results}
    assert len(session_ids) == 1
    assert sum(reusable is None for _, reusable in results) == 1


@pytest.mark.asyncio
async def test_cancelled_submit_persists_failure_releases_reservation_and_propagates(tmp_path):
    store = MagicClassResultStore(tmp_path)
    client = SimpleNamespace()
    submitted = asyncio.Event()

    async def submit(_payload):
        submitted.set()
        await asyncio.Event().wait()

    client.submit = submit
    service = MagicClassClassroomService(settings=_test_settings(), store=store, client=client)

    async def compatible():
        return client

    async def capabilities(_client):
        return {}

    service._require_compatible_client = compatible
    service._health_capabilities = capabilities
    context = SimpleNamespace(text="course context", material_text="", signals=None)
    task = asyncio.create_task(
        service.generate(
            user_id="user",
            course_id="course",
            context=context,
            mode="review",
        )
    )
    await asyncio.wait_for(submitted.wait(), timeout=2)
    reservation = await asyncio.to_thread(
        store.read_reservation, user_id="user", course_id="course"
    )
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert store.read_reservation(user_id="user", course_id="course") is None
    cancelled = store.get_session(
        user_id="user", course_id="course", session_id=reservation.session_id
    )
    assert cancelled.status == "failed"
    assert cancelled.error_code == "SUBMISSION_CANCELLED"


@pytest.mark.asyncio
async def test_poll_during_active_submit_keeps_lease_and_prevents_duplicate_submit(
    tmp_path,
):
    store = MagicClassResultStore(tmp_path)
    client = SimpleNamespace()
    submitted = asyncio.Event()
    finish_submit = asyncio.Event()
    submit_calls = 0

    async def submit(_payload):
        nonlocal submit_calls
        submit_calls += 1
        submitted.set()
        await finish_submit.wait()
        return SimpleNamespace(job_id="upstream_job", status="queued", step="queued")

    client.submit = submit
    service = MagicClassClassroomService(settings=_test_settings(), store=store, client=client)

    async def compatible():
        return client

    async def capabilities(_client):
        return {}

    service._require_compatible_client = compatible
    service._health_capabilities = capabilities
    context = SimpleNamespace(text="course context", material_text="", signals=None)
    first = asyncio.create_task(
        service.generate(
            user_id="user", course_id="course", context=context, mode="review"
        )
    )
    await asyncio.wait_for(submitted.wait(), timeout=2)
    queued = store.list_sessions(user_id="user", course_id="course")[0]

    polled = await service.poll(queued)
    reused = await service.generate(
        user_id="user", course_id="course", context=context, mode="quiz"
    )

    assert polled.status == "queued"
    assert reused.session_id == queued.session_id
    assert submit_calls == 1
    assert store.read_reservation(user_id="user", course_id="course").session_id == queued.session_id

    finish_submit.set()
    assert (await first).job_id == "upstream_job"


@pytest.mark.asyncio
async def test_poll_backfills_job_id_from_reservation(tmp_path):
    store = MagicClassResultStore(tmp_path)
    service = MagicClassClassroomService(
        settings=_test_settings(), store=store, client=object()
    )
    session_id = new_session_id()
    session = MagicClassSession(
        session_id=session_id,
        course_id="course",
        user_id="user",
        mode="review",
        status="queued",
        step="queued",
    )
    store.save(session)
    assert store.acquire_reservation(
        user_id="user", course_id="course", session_id=session_id, mode="review"
    )
    assert store.update_reservation(
        user_id="user",
        course_id="course",
        session_id=session_id,
        job_id="upstream_job",
    )
    polled_ids = []

    async def poll(job_id):
        polled_ids.append(job_id)
        return SimpleNamespace(
            status="queued",
            step="queued",
            progress=0,
            message="waiting",
            error=None,
            partial=False,
            classroom_id=None,
            scenes_count=0,
        )

    service._require_client = lambda: SimpleNamespace(poll=poll)

    result = await service.poll(session)

    assert polled_ids == ["upstream_job"]
    assert result.job_id == "upstream_job"
    assert store.get_session(
        user_id="user", course_id="course", session_id=session_id
    ).job_id == "upstream_job"


@pytest.mark.asyncio
async def test_cancel_during_known_job_persistence_keeps_job_for_reuse(tmp_path):
    import threading

    store = MagicClassResultStore(tmp_path)
    client = SimpleNamespace()
    save_started = threading.Event()
    allow_save = threading.Event()
    submitted = asyncio.Event()
    submit_calls = 0
    original_save = store.save

    def controlled_save(session):
        if session.job_id:
            save_started.set()
            if not allow_save.wait(timeout=3):
                raise TimeoutError("job session save was not released")
        original_save(session)

    async def submit(_payload):
        nonlocal submit_calls
        submit_calls += 1
        submitted.set()
        return SimpleNamespace(job_id="upstream_job", status="queued", step="queued")

    client.submit = submit
    store.save = controlled_save
    service = MagicClassClassroomService(settings=_test_settings(), store=store, client=client)

    async def compatible():
        return client

    async def capabilities(_client):
        return {}

    service._require_compatible_client = compatible
    service._health_capabilities = capabilities
    context = SimpleNamespace(text="course context", material_text="", signals=None)
    first = asyncio.create_task(
        service.generate(
            user_id="user", course_id="course", context=context, mode="review"
        )
    )
    await asyncio.wait_for(submitted.wait(), timeout=2)
    assert await asyncio.to_thread(save_started.wait, 2)
    first.cancel()
    first.cancel()
    first.cancel()
    first.cancel()
    await asyncio.sleep(0)
    assert not first.done()
    allow_save.set()
    with pytest.raises(asyncio.CancelledError):
        await first

    reservation = store.read_reservation(user_id="user", course_id="course")
    assert reservation.session_id
    assert reservation.job_id == "upstream_job"
    store.save = original_save
    reused = await service.generate(
        user_id="user", course_id="course", context=context, mode="quiz"
    )
    assert reused.job_id == "upstream_job"
    assert submit_calls == 1


@pytest.mark.asyncio
async def test_known_job_persistence_error_does_not_release_for_resubmit(tmp_path):
    store = MagicClassResultStore(tmp_path)
    client = SimpleNamespace()
    submit_calls = 0
    original_save = store.save
    failed_once = False

    def fail_first_job_save(session):
        nonlocal failed_once
        if session.job_id and not failed_once:
            failed_once = True
            raise OSError("disk busy")
        original_save(session)

    async def submit(_payload):
        nonlocal submit_calls
        submit_calls += 1
        return SimpleNamespace(job_id="upstream_job", status="queued", step="queued")

    client.submit = submit
    store.save = fail_first_job_save
    service = MagicClassClassroomService(settings=_test_settings(), store=store, client=client)

    async def compatible():
        return client

    async def capabilities(_client):
        return {}

    service._require_compatible_client = compatible
    service._health_capabilities = capabilities
    context = SimpleNamespace(text="course context", material_text="", signals=None)

    with pytest.raises(OSError, match="disk busy"):
        await service.generate(
            user_id="user", course_id="course", context=context, mode="review"
        )

    store.save = original_save
    reused = await service.generate(
        user_id="user", course_id="course", context=context, mode="quiz"
    )
    assert reused.job_id == "upstream_job"
    assert submit_calls == 1


@pytest.mark.asyncio
async def test_cancelled_cleanup_task_does_not_spin_forever():
    cleanup = asyncio.create_task(asyncio.Event().wait())
    cleanup.cancel()

    await asyncio.wait_for(
        MagicClassClassroomService._wait_for_cleanup(cleanup), timeout=1
    )


@pytest.mark.asyncio
async def test_submit_error_releases_reservation_even_if_failure_save_raises(tmp_path):
    store = MagicClassResultStore(tmp_path)
    client = SimpleNamespace()

    async def submit(_payload):
        raise RuntimeError("upstream unavailable")

    client.submit = submit
    service = MagicClassClassroomService(settings=_test_settings(), store=store, client=client)

    async def compatible():
        return client

    async def capabilities(_client):
        return {}

    service._require_compatible_client = compatible
    service._health_capabilities = capabilities
    original_save = store.save
    failed_session = None

    def fail_closed_session_save(session):
        nonlocal failed_session
        if session.status == "failed":
            failed_session = session
            raise OSError("disk full")
        original_save(session)

    store.save = fail_closed_session_save
    context = SimpleNamespace(text="course context", material_text="", signals=None)

    with pytest.raises(RuntimeError, match="upstream unavailable"):
        await service.generate(
            user_id="user", course_id="course", context=context, mode="review"
        )

    assert failed_session is not None
    assert store.read_reservation(user_id="user", course_id="course") is None


@pytest.mark.asyncio
async def test_submit_heartbeat_keeps_reservation_owned_past_ttl(tmp_path):
    import threading

    store = MagicClassResultStore(tmp_path)
    client = SimpleNamespace()
    submitted = asyncio.Event()
    finish_submit = asyncio.Event()
    wake_heartbeat = asyncio.Event()
    touch_finished = threading.Event()
    update_started = threading.Event()
    allow_update = threading.Event()
    submit_calls = 0
    original_touch = store.touch_reservation
    original_persist = store.persist_submission

    async def sleeper(_delay):
        await wake_heartbeat.wait()
        wake_heartbeat.clear()

    def record_touch(**kwargs):
        renewed = original_touch(**kwargs)
        touch_finished.set()
        return renewed

    def controlled_persist(session, *, job_id):
        update_started.set()
        if not allow_update.wait(timeout=3):
            raise TimeoutError("reservation update was not released")
        return original_persist(session, job_id=job_id)

    async def submit(_payload):
        nonlocal submit_calls
        submit_calls += 1
        submitted.set()
        await finish_submit.wait()
        return SimpleNamespace(job_id="upstream_job", status="queued", step="queued")

    client.submit = submit
    store.touch_reservation = record_touch
    store.persist_submission = controlled_persist
    service = MagicClassClassroomService(
        settings=_test_settings(magicclass_reservation_ttl_seconds=30),
        store=store,
        client=client,
        sleeper=sleeper,
    )

    async def compatible():
        return client

    async def capabilities(_client):
        return {}

    service._require_compatible_client = compatible
    service._health_capabilities = capabilities
    context = SimpleNamespace(text="course context", material_text="", signals=None)
    first_task = asyncio.create_task(
        service.generate(
            user_id="user", course_id="course", context=context, mode="review"
        )
    )
    await asyncio.wait_for(submitted.wait(), timeout=2)
    reservation = await asyncio.to_thread(
        store.read_reservation, user_id="user", course_id="course"
    )
    _age_reservation(store, "user", "course", reservation.session_id)

    # Drive the injected heartbeat without waiting for the configured 10s interval.
    wake_heartbeat.set()
    assert await asyncio.to_thread(touch_finished.wait, 2)
    renewed = await asyncio.to_thread(
        store.read_reservation, user_id="user", course_id="course"
    )
    assert not store.reservation_is_stale(renewed, 30)

    reused = await service.generate(
        user_id="user", course_id="course", context=context, mode="quiz"
    )
    assert reused.session_id == reservation.session_id
    assert reused.mode == "review"
    assert submit_calls == 1

    # Hold the success persistence step after submit returns. The heartbeat
    # must remain active until the reservation has its upstream job id.
    finish_submit.set()
    assert await asyncio.to_thread(update_started.wait, 2)
    touch_finished.clear()
    _age_reservation(store, "user", "course", reservation.session_id)
    wake_heartbeat.set()
    assert await asyncio.to_thread(touch_finished.wait, 2)
    renewed_during_persist = await asyncio.to_thread(
        store.read_reservation, user_id="user", course_id="course"
    )
    assert not store.reservation_is_stale(renewed_during_persist, 30)

    allow_update.set()
    result = await first_task
    assert result.job_id == "upstream_job"
    assert submit_calls == 1


@pytest.mark.asyncio
async def test_repeated_cancellation_waits_for_save_and_reservation_release(tmp_path):
    import threading

    store = MagicClassResultStore(tmp_path)
    client = SimpleNamespace()
    submitted = asyncio.Event()
    save_started = threading.Event()
    allow_save = threading.Event()
    released = threading.Event()
    original_save = store.save
    original_release = store.release_reservation

    def controlled_save(session):
        if session.status == "failed":
            save_started.set()
            if not allow_save.wait(timeout=3):
                raise TimeoutError("controlled save was not released")
        original_save(session)

    def record_release(**kwargs):
        original_release(**kwargs)
        released.set()

    async def submit(_payload):
        submitted.set()
        await asyncio.Event().wait()

    client.submit = submit
    store.save = controlled_save
    store.release_reservation = record_release
    service = MagicClassClassroomService(settings=_test_settings(), store=store, client=client)

    async def compatible():
        return client

    async def capabilities(_client):
        return {}

    service._require_compatible_client = compatible
    service._health_capabilities = capabilities
    context = SimpleNamespace(text="course context", material_text="", signals=None)
    task = asyncio.create_task(
        service.generate(
            user_id="user", course_id="course", context=context, mode="review"
        )
    )
    await asyncio.wait_for(submitted.wait(), timeout=2)
    task.cancel()
    assert await asyncio.to_thread(save_started.wait, 2)

    task.cancel()
    task.cancel()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done(), "后续取消不得跳过仍在运行的清理任务"
    allow_save.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert await asyncio.to_thread(released.wait, 2)
    assert store.read_reservation(user_id="user", course_id="course") is None


@pytest.mark.asyncio
async def test_cancelled_initial_save_leaves_reservation_recoverable_after_ttl(tmp_path):
    import threading

    store = MagicClassResultStore(tmp_path)
    original_save = store.save
    save_started = threading.Event()
    allow_save = threading.Event()
    save_finished = threading.Event()

    def controlled_initial_save(session):
        save_started.set()
        if not allow_save.wait(timeout=3):
            raise TimeoutError("controlled initial save was not released")
        original_save(session)
        save_finished.set()

    store.save = controlled_initial_save
    service = MagicClassClassroomService(settings=_test_settings(), store=store, client=object())

    async def compatible():
        return service._client

    service._require_compatible_client = compatible
    context = SimpleNamespace(text="course context", material_text="", signals=None)
    task = asyncio.create_task(
        service.generate(
            user_id="user", course_id="course", context=context, mode="review"
        )
    )
    assert await asyncio.to_thread(save_started.wait, 2)
    reservation = await asyncio.to_thread(
        store.read_reservation, user_id="user", course_id="course"
    )
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    allow_save.set()
    assert await asyncio.to_thread(save_finished.wait, 2)
    _age_reservation(store, "user", "course", reservation.session_id)
    store.save = original_save
    new_id, reusable = service._acquire(
        user_id="user", course_id="course", mode="quiz"
    )
    assert new_id != reservation.session_id
    assert reusable is None
    abandoned = store.get_session(
        user_id="user", course_id="course", session_id=reservation.session_id
    )
    assert abandoned.status == "failed"
    assert abandoned.error_code == "SUBMISSION_OUTCOME_UNKNOWN"


@pytest.mark.asyncio
def probe_not_found_response() -> httpx.Response:
    """契约指纹 P3 的真实期望：格式合法但不存在的 jobId → 404 INVALID_REQUEST。"""
    return httpx.Response(
        404,
        json={
            "success": False,
            "errorCode": "INVALID_REQUEST",
            "error": "Classroom generation job not found",
        },
    )


def is_probe_request(request: httpx.Request) -> bool:
    """只匹配契约指纹探针（用固定的探针 jobId），不要误伤真实轮询。"""
    return request.method == "GET" and request.url.path.endswith(
        f"/api/generate-classroom/{PROBE_JOB_ID}"
    )


def _transport(handler):
    return httpx.MockTransport(handler)


def _client_with(handler) -> MagicClassClient:
    return MagicClassClient(
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

    from app.services.magicclass.errors import MagicClassUnavailable

    with pytest.raises(MagicClassUnavailable):
        asyncio.run(client.poll("job_abc"))


@pytest.mark.parametrize("status", [429, 500, 502])
def test_http_error_status_mapping(status):
    def handler(request):
        return httpx.Response(status, json={"success": False})

    client = _client_with(handler)
    import asyncio

    from app.services.magicclass import errors

    expected = (
        errors.MagicClassRateLimited if status == 429 else errors.MagicClassServerError
    )
    with pytest.raises(expected):
        asyncio.run(client.submit({"requirement": "r"}))


def test_invalid_json_maps_to_protocol_error():
    def handler(request):
        return httpx.Response(200, text="<html>not json</html>")

    client = _client_with(handler)
    import asyncio

    from app.services.magicclass.errors import MagicClassProtocolError

    with pytest.raises(MagicClassProtocolError):
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
    # 客户端只做内部 Origin 校验；该字段是**内部**值，绝不进入领域层/响应
    assert result.upstream_classroom_url == f"{BASE}/classroom/room_1"
    assert result.scenes_count == 6


@pytest.mark.parametrize(
    "result",
    [
        None,
        "not-an-object",
        {},
        {"classroomId": "room_1"},
        {"url": f"{BASE}/classroom/room_1"},
    ],
)
def test_poll_rejects_succeeded_without_complete_classroom_result(result):
    """捕获把缺少 classroomId/url 的上游假成功保存为已完成的回归。"""

    def handler(request):
        return httpx.Response(
            200,
            json={
                "success": True,
                "status": "succeeded",
                "step": "completed",
                "progress": 100,
                "done": True,
                "result": result,
            },
        )

    import asyncio

    from app.services.magicclass.errors import MagicClassProtocolError

    with pytest.raises(MagicClassProtocolError):
        asyncio.run(_client_with(handler).poll("job_abc"))


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

    from app.services.magicclass.errors import MagicClassInvalidOrigin

    with pytest.raises(MagicClassInvalidOrigin):
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

    from app.services.magicclass.errors import MagicClassInvalidOrigin

    with pytest.raises(MagicClassInvalidOrigin):
        asyncio.run(client.poll("job_abc"))


# ===== 未启用安全降级 =====


def test_status_safe_degrade_when_not_configured():
    client = TestClient(create_app())
    container = reset_container_for_tests(_test_settings(magicclass_enabled=False))
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
    assert gen.json()["code"] == "MAGICCLASS_NOT_ENABLED"


# ===== 路由：权限 + 202 提交 + 轮询成功 =====


def _setup_routes(tmp_path, handler, **settings_overrides):
    container = reset_container_for_tests(
        _test_settings(**settings_overrides)
    )
    seed_demo_data(container, force=True)
    # 课堂会话/预占是磁盘状态，必须落在每个用例独立的临时目录，
    # 否则会写进仓库 data/ 并在多次运行之间互相污染。
    container.magicclass_result_store = MagicClassResultStore(tmp_path / "magicclass_classrooms")
    container.magicclass_classroom_service = MagicClassClassroomService(
        container.settings, container.magicclass_result_store
    )
    # 注入带 MockTransport 的客户端，避免真实联调
    container.magicclass_classroom_service._client = _client_with(handler)
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
        if request.url.path.endswith("/api/access-code/status"):
            return httpx.Response(
                200, json={"success": True, "enabled": False, "authenticated": False}
            )
        if request.url.path.endswith("/api/health"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "status": "ok",
                    "capabilities": {"webSearch": False, "tts": True},
                },
            )
        if is_probe_request(request):
            return probe_not_found_response()
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


def test_generate_returns_202_then_poll_succeeds(tmp_path):
    calls = []
    _, client, headers, cid = _setup_routes(tmp_path, _success_handler(calls))
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
    # 旧值 practice 归一化到规范意图 quiz（阶段 2 / 决策 D2）
    assert session["mode"] == "quiz"
    assert session["requested_mode"] == "quiz"

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


def test_generate_rebinds_submit_only_to_configured_payload(tmp_path):
    calls = []
    _, client, headers, cid = _setup_routes(tmp_path, _success_handler(calls))
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


def test_nonexistent_course_rejected(tmp_path):
    _, client, headers, _ = _setup_routes(tmp_path, _success_handler([]))
    resp = client.get("/api/v1/courses/no_such_course/interactive-classroom/status", headers=headers)
    assert resp.status_code in (404, 403)


def test_task_failure_surfaces_retryable_state(tmp_path):
    def handler(request: httpx.Request):
        if request.url.path.endswith("/api/access-code/status"):
            return httpx.Response(
                200, json={"success": True, "enabled": False, "authenticated": False}
            )
        if request.url.path.endswith("/api/health"):
            return httpx.Response(
                200, json={"success": True, "status": "ok", "capabilities": {}}
            )
        if is_probe_request(request):
            return probe_not_found_response()
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

    _, client, headers, cid = _setup_routes(tmp_path, handler)
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


def test_course_context_includes_chapters_but_not_credentials(tmp_path):
    container, client, headers, _ = _setup_routes(tmp_path, _success_handler([]))
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


def test_magicclass_content_never_serves_as_official_fact():
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
