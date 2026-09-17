"""Agent 事件存储 —— 单调序列 + append_event。

事件表是事务性 event 表 + 轻量 outbox,不是 Kafka。

**注意**:本模块的 `append()` 只负责"不伴随状态变化"的进度/观测事件。
伴随 `agent_runs.status` 变化的事件必须经过 `AgentRuntimeRepository` 的原子方法
(`transition_run_with_event()` / `complete_run_with_job_output_and_event()` /
`create_job_with_run_and_event()`),由仓储保证状态与事件在同一事务提交。
在本模块里先改状态再 `append()` 会在进程崩溃时留下状态与事件不一致的数据。
"""
from __future__ import annotations

from typing import Optional

from ...repositories.agent_runtime_repository import AgentRuntimeRepository


class AgentEventStore:
    """事件存储封装。"""

    def __init__(self, repository: AgentRuntimeRepository) -> None:
        self._repo = repository

    def append(
        self,
        *,
        run_id: str,
        type: str,
        status: str,
        phase: str,
        role: Optional[str] = None,
        summary: Optional[str] = None,
        progress: Optional[dict] = None,
        artifact_id: Optional[str] = None,
        approval_id: Optional[str] = None,
    ) -> tuple[str, int]:
        """追加事件,返回 (event_id, sequence)。"""
        return self._repo.append_event(
            run_id=run_id,
            type=type,
            status=status,
            phase=phase,
            role=role,
            summary=summary,
            progress=progress,
            artifact_id=artifact_id,
            approval_id=approval_id,
        )

    def list_events(
        self, run_id: str, after_sequence: int = 0, limit: int = 100
    ) -> list[dict]:
        """列出 run 的事件(支持 Last-Event-ID 续传)。"""
        return self._repo.list_events(run_id, after_sequence, limit)


__all__ = ["AgentEventStore"]