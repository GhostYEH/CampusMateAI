"""同进程事件通知器 —— 让 SSE 不必靠忙轮询发现新事件。

语义边界:
- **只优化延迟,不保证投递**:事件真源始终是持久化的 `agent_events`。
  通知丢失时 SSE 退化为短周期(默认 1 秒)数据库轮询,跨进程写入也由此兼容。
- **不做跨进程广播**:多副本部署靠轮询兜底,不引入 Redis/额外基础设施。
- 心跳由 SSE 层负责,本模块不写入任何数据库记录。
"""
from __future__ import annotations

import asyncio


def _resolve(future: "asyncio.Future[bool]") -> None:
    if not future.done():
        future.set_result(True)


class EventNotifier:
    """按 `run_id` 聚合的等待/唤醒原语。"""

    def __init__(self) -> None:
        self._waiters: dict[str, set["asyncio.Future[bool]"]] = {}

    def notify(self, run_id: str) -> None:
        """唤醒所有等待该 Run 的流。可在任意线程调用;失败不影响持久化真源。"""
        waiters = self._waiters.get(run_id)
        if not waiters:
            return
        for future in list(waiters):
            if future.done():
                continue
            try:
                future.get_loop().call_soon_threadsafe(_resolve, future)
            except (RuntimeError, AttributeError):
                try:
                    _resolve(future)
                except (RuntimeError, asyncio.InvalidStateError):
                    pass

    async def wait(self, run_id: str, timeout: float) -> bool:
        """等待该 Run 的新事件;超时返回 False,由调用方回落到数据库查询。"""
        if timeout <= 0:
            return False
        loop = asyncio.get_running_loop()
        future: "asyncio.Future[bool]" = loop.create_future()
        self._waiters.setdefault(run_id, set()).add(future)
        try:
            await asyncio.wait_for(future, timeout)
            return True
        except (asyncio.TimeoutError, TimeoutError):
            return False
        finally:
            bucket = self._waiters.get(run_id)
            if bucket is not None:
                bucket.discard(future)
                if not bucket:
                    self._waiters.pop(run_id, None)

    def waiters(self, run_id: str) -> int:
        return len(self._waiters.get(run_id, ()))


__all__ = ["EventNotifier"]
