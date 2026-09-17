"""Run 状态机与安全恢复。

状态转换严格校验,非法转换抛 AgentRuntimeError。
所有伴随状态变化的事件都由 `AgentRuntimeRepository` 的原子方法写入,
保证 `agent_runs.status` 与 `agent_events` 在同一事务提交。
重启后不会盲目重放中断的执行；无法安全恢复的执行 run 会明确失败。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from ...core.exceptions import AgentRuntimeError
from ...repositories.agent_runtime_repository import AgentRuntimeRepository
from .cancellation import ensure_run_active
from .event_store import AgentEventStore


# 合法状态转换(§5.6)
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "QUEUED": {"RUNNING", "PAUSED", "CANCELLED", "FAILED"},
    "RUNNING": {"AWAITING_APPROVAL", "PAUSED", "SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"},
        # 审批通过后，原 Run 必须能被 Worker 重新领取 —— 否则批准了也永远不会执行，
    # 客户端就只剩下"再建一个新 Job 并带上旧 approval"这条错误路径。
    "AWAITING_APPROVAL": {"QUEUED", "RUNNING", "SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"},
    "PAUSED": {"RUNNING", "CANCELLED"},
    "SUCCEEDED": set(),  # 终态
    "PARTIAL": {"CANCELLED"},  # 可取消
    "FAILED": set(),  # 终态
    "CANCELLED": set(),  # 终态
}

_TERMINAL_STATES = {"SUCCEEDED", "FAILED", "CANCELLED"}


class RunManager:
    """Run 状态机与恢复。"""

    def __init__(
        self,
        repository: AgentRuntimeRepository,
        event_store: Optional[AgentEventStore] = None,
    ) -> None:
        self._repo = repository
        self._events = event_store or AgentEventStore(repository)

    @staticmethod
    def validate_transition(from_status: str, to_status: str) -> None:
        if from_status == to_status:
            return
        allowed = _VALID_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise AgentRuntimeError(
                f"非法状态转换: {from_status} -> {to_status}",
                code="AGENT_INVALID_STATE",
                http_status=409,
            )

    @staticmethod
    def is_terminal(status: str) -> bool:
        return status in _TERMINAL_STATES

    def assert_active(self, run_id: str) -> dict:
        """模型/工具边界处的取消检查点:已取消或终态则抛异常。"""
        return ensure_run_active(self._repo, run_id)

    def sweep_stale_runs(self, *, older_than_minutes: int = 120) -> int:
        """兜底清理长期停留在非终态的 run(进程崩溃/网络中断后不会永久挂着)。

        进程崩溃后不会有人再来推进这些 run,由调用方(启动时或定时任务)扫描。
        这里只置终态并留错误原因,不做任何业务回滚。
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
        ).isoformat()
        swept = 0
        for run in self._repo.list_stale_runs(older_than_iso=cutoff):
            try:
                self.transition(
                    run["run_id"],
                    "FAILED",
                    phase="IDLE",
                    error_code="AGENT_INVALID_STATE",
                    error_message=f"run 超过 {older_than_minutes} 分钟未推进,已由兜底清理置为失败",
                    event_type="RUN_FAILED",
                    event_summary="运行超时未推进,已由兜底清理终止",
                )
            except AgentRuntimeError:
                # 并发下已被其它路径收尾:跳过即可,不视为错误。
                continue
            swept += 1
        return swept

    def transition(
        self,
        run_id: str,
        to_status: str,
        *,
        phase: Optional[str] = None,
        risk_level: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        event_type: Optional[str] = None,
        event_status: Optional[str] = None,
        event_phase: Optional[str] = None,
        event_role: Optional[str] = None,
        event_summary: Optional[str] = None,
        event_progress: Optional[dict] = None,
    ) -> dict:
        """执行状态转换。校验合法性后,把状态与事件在同一事务写入。"""
        run = self._repo.get_run(run_id)
        if not run:
            raise AgentRuntimeError(
                "Run 不存在", code="AGENT_RUN_NOT_FOUND", http_status=404
            )
        if self.is_terminal(run["status"]) and to_status != run["status"]:
            raise AgentRuntimeError(
                f"Run 已终态({run['status']}),不能再转换",
                code="AGENT_INVALID_STATE",
                http_status=409,
            )
        self.validate_transition(run["status"], to_status)
        return self._repo.transition_run_with_event(
            run_id,
            to_status,
            expected_statuses=[run["status"]],
            phase=phase,
            risk_level=risk_level,
            error_code=error_code,
            error_message=error_message,
            event_type=event_type,
            event_status=event_status,
            event_phase=event_phase,
            event_role=event_role,
            event_summary=event_summary,
            event_progress=event_progress,
        )

    def cancel(self, run_id: str, reason: Optional[str] = None) -> dict:
        """取消 run。已完成内部动作保留记录,仅阻止未来工作。"""
        run = self._repo.get_run(run_id)
        if not run:
            raise AgentRuntimeError(
                "Run 不存在", code="AGENT_RUN_NOT_FOUND", http_status=404
            )
        if self.is_terminal(run["status"]):
            if run["status"] == "CANCELLED":
                return run
            raise AgentRuntimeError(
                f"Run 已终态({run['status']}),无法取消",
                code="AGENT_RUN_CANCELLED",
                http_status=409,
            )
        return self.transition(
            run_id,
            "CANCELLED",
            phase="IDLE",
            error_message=reason,
            event_type="RUN_CANCELLED",
            event_summary=reason or "运行已取消",
        )

    def pause(self, run_id: str, reason: Optional[str] = None) -> dict:
        """暂停可协作中断的 Run；审批等待态不被伪装成暂停。"""
        run = self._repo.get_run(run_id)
        if not run:
            raise AgentRuntimeError("Run 不存在", code="AGENT_RUN_NOT_FOUND", http_status=404)
        if run["status"] == "PAUSED":
            return run
        if run["status"] not in {"QUEUED", "RUNNING"}:
            raise AgentRuntimeError(
                f"Run 当前状态({run['status']})不可暂停",
                code="AGENT_INVALID_STATE", http_status=409,
            )
        return self.transition(
            run_id, "PAUSED", phase="IDLE", error_message=reason,
            event_type="RUN_PAUSED", event_summary=reason or "运行已暂停",
        )

    def resume(self, run_id: str) -> dict:
        """仅从 PAUSED 恢复到 RUNNING。"""
        run = self._repo.get_run(run_id)
        if not run:
            raise AgentRuntimeError("Run 不存在", code="AGENT_RUN_NOT_FOUND", http_status=404)
        if run["status"] != "PAUSED":
            if run["status"] == "RUNNING":
                return run
            raise AgentRuntimeError(
                f"Run 当前状态({run['status']})不可恢复",
                code="AGENT_INVALID_STATE", http_status=409,
            )
        return self.transition(
            run_id, "RUNNING", phase="WAITING_FOR_TOOL",
            event_type="RUN_RESUMED", event_summary="运行已恢复",
        )

    def retry(
        self,
        run_id: str,
        *,
        idempotency_key: Optional[str] = None,
        handler_code: Optional[str] = None,
        handler_version: Optional[str] = None,
    ) -> dict:
        """为失败/部分/取消的 Run 创建新的可追踪 Run，不重放旧 Run。"""
        run = self._repo.get_run(run_id)
        if not run:
            raise AgentRuntimeError("Run 不存在", code="AGENT_RUN_NOT_FOUND", http_status=404)
        if run["status"] not in {"FAILED", "PARTIAL", "CANCELLED"}:
            raise AgentRuntimeError(
                f"Run 当前状态({run['status']})不可重试",
                code="AGENT_INVALID_STATE", http_status=409,
            )
        key = idempotency_key or f"retry:{run_id}"
        existing = self._repo.find_run_by_idempotency(run["user_id"], key)
        if existing:
            return existing
        new_run_id = self._repo.create_run(
            job_id=run["job_id"], user_id=run["user_id"],
            request_id=run.get("request_id"), idempotency_key=key, retry_of=run_id,
            handler_code=handler_code or run.get("handler_code"),
            handler_version=handler_version or run.get("handler_version"),
        )
        return self._repo.get_run(new_run_id) or {}

    def recover_incomplete_runs(self) -> list[dict]:
        """兼容旧调用方；恢复工作已由带租约的 AgentWorker 接管。

        旧的“启动时把所有 RUNNING 标记 FAILED”会丢失安全 checkpoint，且会
        破坏至少一次投递语义，因此这里不再修改任何运行记录。
        """
        return []


__all__ = ["RunManager"]
