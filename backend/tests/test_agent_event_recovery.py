"""事件恢复测试 —— SSE 以持久化事件为真源,按游标准确续传。

锁定四条不变量:
1. `Last-Event-ID` 通过 `(run_id, event_id)` 索引直接定位,不扫描历史事件列表;
2. 无效或跨 Run 的游标返回 `409 AGENT_CURSOR_INVALID`,而不是静默从头推流;
3. 非终态 Run 不会因为"空闲 N 次"或"若干秒无业务事件"被断流;
4. 终态事件发送完毕后才关闭,客户端不会漏掉最后一条。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import agent_runtime as route_module
from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.services.container import reset_container_for_tests


@pytest.fixture
def env():
    container = reset_container_for_tests(
        Settings(
            app_env="test",
            database_url="sqlite:///:memory:",
            auto_seed_demo_users=False,
            auto_import_demo=False,
            llm_provider="none",
        )
    )
    user = container.user_repository.create_user(
        username="recovery_student", password_hash=hash_password("Demo123456"), role="student"
    )
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "recovery_student", "password": "Demo123456"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return container, client, headers, user.id


def _new_run(container, user_id, *, status="QUEUED"):
    repo = container.agent_runtime_repository
    job_id = repo.create_job(user_id=user_id, job_kind="final_review")
    run_id = repo.create_run(job_id=job_id, user_id=user_id)
    if status != "QUEUED":
        repo.update_run(run_id, status=status, phase="IDLE", finished_at="t")
    return repo, run_id


class TestCursorResolution:
    def test_resume_uses_index_not_full_scan(self, env, monkeypatch):
        """续传必须按 sequence 增量取,不能把历史事件整表捞出来比对。"""
        container, client, headers, user_id = env
        repo, run_id = _new_run(container, user_id)
        eid1, seq1 = repo.append_event(
            run_id=run_id, type="RUN_STARTED", status="RUNNING", phase="IDLE"
        )
        repo.append_event(run_id=run_id, type="MODEL_COMPLETED", status="SUCCEEDED", phase="IDLE")
        repo.update_run(run_id, status="SUCCEEDED", phase="IDLE", finished_at="t")

        calls: list[dict] = []
        original = AgentRuntimeRepository.list_events

        def counting(self, run_id_, after_sequence=0, limit=100):
            calls.append({"after_sequence": after_sequence, "limit": limit})
            return original(self, run_id_, after_sequence, limit)

        monkeypatch.setattr(AgentRuntimeRepository, "list_events", counting)
        resp = client.get(
            f"/api/v1/agent-runs/{run_id}/events/stream",
            headers={**headers, "Last-Event-ID": eid1},
        )
        assert resp.status_code == 200
        assert calls, "应当发生一次增量查询"
        assert all(call["limit"] != 10000 for call in calls), "不得再扫描历史事件列表"
        assert calls[0]["after_sequence"] == seq1, "必须直接定位到游标对应的 sequence"

    def test_unknown_cursor_returns_409(self, env):
        container, client, headers, user_id = env
        _, run_id = _new_run(container, user_id)
        resp = client.get(
            f"/api/v1/agent-runs/{run_id}/events/stream",
            headers={**headers, "Last-Event-ID": "evt_missing"},
        )
        assert resp.status_code == 409
        assert resp.json()["code"] == "AGENT_CURSOR_INVALID"

    def test_cursor_from_other_run_returns_409(self, env):
        container, client, headers, user_id = env
        repo, run_id = _new_run(container, user_id)
        _, other_run_id = _new_run(container, user_id)
        foreign_event_id, _ = repo.append_event(
            run_id=other_run_id, type="RUN_STARTED", status="RUNNING", phase="IDLE"
        )
        resp = client.get(
            f"/api/v1/agent-runs/{run_id}/events/stream",
            headers={**headers, "Last-Event-ID": foreign_event_id},
        )
        assert resp.status_code == 409
        assert resp.json()["code"] == "AGENT_CURSOR_INVALID"


class _FakeRequest:
    """最小 Request 替身:只提供 SSE 用到的断线检查,并可控地切换断线状态。"""

    def __init__(self) -> None:
        self.disconnected = False

    async def is_disconnected(self) -> bool:
        return self.disconnected


async def _start_stream(container, request, run_id, last_event_id=None):
    """直接驱动路由返回的 StreamingResponse,避免测试客户端对无限流的限制。"""
    user = container.user_repository.get_user_by_username("recovery_student")
    response = await route_module.stream_events(
        run_id=run_id, request=request, user=user,
        container=container, last_event_id=last_event_id,
    )
    return response.body_iterator


class TestStreamLifecycle:
    def test_terminal_event_is_delivered_before_close(self, env):
        container, client, headers, user_id = env
        repo, run_id = _new_run(container, user_id)
        repo.append_event(run_id=run_id, type="RUN_STARTED", status="RUNNING", phase="IDLE")
        repo.append_event(run_id=run_id, type="RUN_COMPLETED", status="SUCCEEDED", phase="IDLE")
        repo.update_run(run_id, status="SUCCEEDED", phase="IDLE", finished_at="t")
        resp = client.get(f"/api/v1/agent-runs/{run_id}/events/stream", headers=headers)
        assert resp.status_code == 200
        text = resp.text
        assert "event: RUN_STARTED" in text
        assert "event: RUN_COMPLETED" in text, "终态事件必须在关闭前送达"

    @pytest.mark.asyncio
    async def test_non_terminal_run_never_drops_for_idle(self, env, monkeypatch):
        """QUEUED 运行长时间没有业务事件也必须保持连接(旧的 60 次空闲断流已被移除)。"""
        container, _client, _headers, user_id = env
        _repo, run_id = _new_run(container, user_id, status="QUEUED")
        monkeypatch.setattr(route_module, "_SSE_HEARTBEAT_SECONDS", 0.0)

        idle_iterations = {"count": 0}

        async def instant_wait(self, run_id_, timeout):
            idle_iterations["count"] += 1
            return False

        monkeypatch.setattr(type(container.agent_event_notifier), "wait", instant_wait)

        stream = await _start_stream(container, _FakeRequest(), run_id)
        heartbeats = 0
        for _ in range(200):
            chunk = await stream.__anext__()
            heartbeats += chunk.count(": keep-alive")
            if idle_iterations["count"] > 60:
                break
        await stream.aclose()
        assert heartbeats >= 3, "空闲时应持续发送注释心跳"
        assert idle_iterations["count"] > 60, "连接不得在 60 次空闲后被切断"

    @pytest.mark.asyncio
    async def test_disconnect_does_not_cancel_run(self, env):
        container, _client, _headers, user_id = env
        repo, run_id = _new_run(container, user_id, status="QUEUED")
        request = _FakeRequest()
        stream = await _start_stream(container, request, run_id)
        first = await stream.__anext__()
        assert "RUN_QUEUED" in first
        request.disconnected = True
        with pytest.raises(StopAsyncIteration):
            await stream.__anext__()
        await stream.aclose()
        assert repo.get_run(run_id)["status"] == "QUEUED", "断线不得改变运行状态"


class TestEventNotifier:
    @pytest.mark.asyncio
    async def test_notify_wakes_waiter(self):
        import asyncio

        from app.services.agent_runtime.event_notifier import EventNotifier

        notifier = EventNotifier()
        waiter = asyncio.ensure_future(notifier.wait("run_1", timeout=5))
        await asyncio.sleep(0)  # 让等待协程先注册,再触发通知
        assert notifier.waiters("run_1") == 1
        notifier.notify("run_1")
        assert await waiter is True
        assert notifier.waiters("run_1") == 0

    @pytest.mark.asyncio
    async def test_wait_times_out_without_notification(self):
        from app.services.agent_runtime.event_notifier import EventNotifier

        notifier = EventNotifier()
        assert await notifier.wait("run_1", timeout=0.01) is False
        assert notifier.waiters("run_1") == 0
