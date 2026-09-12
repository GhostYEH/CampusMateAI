"""Agent 事件存储 —— 单调序列 + append_event。

事件表是事务性 event 表 + 轻量 outbox,不是 Kafka。
业务状态与对应事件在同一数据库事务中提交。
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