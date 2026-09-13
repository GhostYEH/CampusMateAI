"""Run 状态机与安全恢复。

状态转换严格校验,非法转换抛 AgentRuntimeError。
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
    "QUEUED": {"RUNNING", "CANCELLED", "FAILED"},
    "RUNNING": {"AWAITING_APPROVAL", "SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"},
    "AWAITING_APPROVAL": {"RUNNING", "SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"},
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
                )
            except AgentRuntimeError:
                # 并发下已被其它路径收尾:跳过即可,不视为错误。
                continue
            self._events.append(
                run_id=run["run_id"],
                type="RUN_FAILED",
                status="FAILED",
                phase="IDLE",
                summary="运行超时未推进,已由兜底清理终止",
            )
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
    ) -> dict:
        """执行状态转换。校验合法性后更新 run。"""
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
        now = datetime.now(timezone.utc).isoformat()
        update_kwargs: dict = {"status": to_status}
        if phase:
            update_kwargs["phase"] = phase
        if risk_level:
            update_kwargs["risk_level"] = risk_level
        if error_code:
            update_kwargs["error_code"] = error_code
        if error_message:
            update_kwargs["error_message"] = error_message
        if to_status == "RUNNING" and not run["started_at"]:
            update_kwargs["started_at"] = now
        if to_status in _TERMINAL_STATES:
            update_kwargs["finished_at"] = now
        self._repo.update_run(run_id, **update_kwargs)
        return self._repo.get_run(run_id)

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
        cancelled = self.transition(
            run_id,
            "CANCELLED",
            phase="IDLE",
            error_message=reason,
        )
        self._events.append(
            run_id=run_id,
            type="RUN_CANCELLED",
            status="CANCELLED",
            phase="IDLE",
            summary=reason or "运行已取消",
        )
        return cancelled

    def recover_incomplete_runs(self) -> list[dict]:
        """终止无法安全恢复的中断执行，并保留持久审批等待态。

        当前 final-review 执行发生在请求内，进程重启后不能安全重放模型或写入。
        ``AWAITING_APPROVAL`` 是持久化的用户等待态，不属于中断执行，保持不变。
        """
        incomplete = self._repo.list_incomplete_runs()
        recovered: list[dict] = []
        for run in incomplete:
            if run["status"] == "AWAITING_APPROVAL":
                continue
            failed = self.transition(
                run["run_id"],
                "FAILED",
                phase="IDLE",
                error_code="AGENT_RECOVERY_UNSUPPORTED",
                error_message="系统重启后无法安全恢复此运行，请重新发起请求。",
            )
            self._events.append(
                run_id=run["run_id"],
                type="RUN_FAILED",
                status="FAILED",
                phase="IDLE",
                summary="系统重启后无法安全恢复，运行已终止",
            )
            recovered.append(failed)
        return recovered


__all__ = ["RunManager"]
