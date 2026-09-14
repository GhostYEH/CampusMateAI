"""期末复习测试共用辅助。

路由只负责创建命令(激活计划版本 / 应用调整提案),真正的领域写操作由
`AgentWorker` 经 `ToolInvocationGateway` 执行。测试里没有常驻 worker,
因此必须显式驱动它把队列排空,否则断言会看到"命令已入队但尚未生效"的中间态。
"""
from __future__ import annotations

import asyncio


def drain_worker(container, *, max_rounds: int = 20) -> None:
    """反复调用 `AgentWorker.run_once()`,直到队列为空或达到轮数上限。"""

    async def _run() -> None:
        for _ in range(max_rounds):
            report = await container.agent_worker.run_once()
            if report.action in {"idle", "skipped"}:
                return

    asyncio.run(_run())


__all__ = ["drain_worker"]
