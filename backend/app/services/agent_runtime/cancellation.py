"""运行取消检查点(§5.6)。

取消是协作式的:用户取消只把 run 置为 CANCELLED,已在进行的长任务在下一个
"检查点"自行停下,而不是被强杀。检查点至少覆盖模型调用前与工具执行前,
避免取消后仍继续消耗模型额度或产生新的写操作。

用法:
    ensure_run_active(repository, run_id)   # 边界处调用,已取消则抛 AgentRunCancelled
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.exceptions import AgentRunCancelled, AgentRuntimeError

if TYPE_CHECKING:
    from ...repositories.agent_runtime_repository import AgentRuntimeRepository

_TERMINAL_STATUSES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})


def is_run_cancelled(repository: "AgentRuntimeRepository", run_id: str) -> bool:
    """run 是否已被取消。"""
    run = repository.get_run(run_id)
    return bool(run and run["status"] == "CANCELLED")


def ensure_run_active(repository: "AgentRuntimeRepository", run_id: str) -> dict:
    """确认 run 仍可继续推进;取消或终态时抛异常。

    返回最新 run 记录,便于调用方复用而不再查一次库。
    """
    run = repository.get_run(run_id)
    if not run:
        raise AgentRuntimeError(
            "Run 不存在", code="AGENT_RUN_NOT_FOUND", http_status=404
        )
    status = run["status"]
    if status == "CANCELLED":
        raise AgentRunCancelled(
            "任务已取消,停止后续步骤", code="AGENT_RUN_CANCELLED", http_status=409
        )
    if status in _TERMINAL_STATUSES:
        raise AgentRuntimeError(
            f"Run 已终态({status}),不能再推进",
            code="AGENT_INVALID_STATE",
            http_status=409,
        )
    return run


__all__ = ["ensure_run_active", "is_run_cancelled"]
