from __future__ import annotations

import asyncio
import threading

import pytest

from app.services.agent_runtime.worker import AgentWorker


@pytest.mark.asyncio
async def test_worker_heartbeat_database_wait_does_not_block_event_loop():
    call_started = threading.Event()
    release_call = threading.Event()

    class SlowRepository:
        def renew_run_lease(self, *args, **kwargs):
            call_started.set()
            if not release_call.wait(timeout=5):
                raise TimeoutError("lease renewal was not released")

    worker = AgentWorker(
        SlowRepository(), object(), worker_id="worker-test",
        lease_seconds=1, heartbeat_seconds=0.01,
    )
    heartbeat = asyncio.create_task(worker._heartbeat("run-test"))
    safety_release = threading.Timer(3, release_call.set)
    safety_release.start()
    try:
        assert await asyncio.to_thread(call_started.wait, 2)
        loop_progress = asyncio.Event()
        asyncio.get_running_loop().call_soon(loop_progress.set)
        await asyncio.wait_for(loop_progress.wait(), timeout=1)
    finally:
        release_call.set()
        heartbeat.cancel()
        with pytest.raises(asyncio.CancelledError):
            await heartbeat
        safety_release.cancel()
