from __future__ import annotations

from typing import Callable

from ...models.agent_runtime import AgentRunRow
from ...repositories.agent_runtime_repository import AgentRuntimeRepository


class RunManager:
    def __init__(self, repository: AgentRuntimeRepository) -> None:
        self._repository = repository

    def mark_incomplete_runs_for_recovery(self) -> list[AgentRunRow]:
        recovered: list[AgentRunRow] = []
        for run in self._repository.list_incomplete_runs():
            recovered.append(
                self._repository.update_run(
                    run_id=run.id, status="RUNNING", phase="RECOVERY_CHECKING", current_role=run.current_role
                )
            )
        return recovered

    def classify_incomplete_runs(self, resumable: Callable[[AgentRunRow], bool]) -> dict[str, list[AgentRunRow]]:
        """启动恢复分类。

        只有能被证明可恢复的运行才保留原状，等待执行器真正被调度后再进入 `RECOVERY_CHECKING`；
        无法证明可恢复的旧运行直接标记 `FAILED`，避免出现「看起来在恢复、实际无人接管」的假状态。
        """
        pending: list[AgentRunRow] = []
        failed: list[AgentRunRow] = []
        for run in self._repository.list_incomplete_runs():
            try:
                proof = bool(resumable(run))
            except Exception:
                proof = False
            if proof:
                self._repository.append_event(
                    run_id=run.id, event_type="RUN_RECOVERY_PENDING",
                    summary="该运行可在执行器接管后恢复，等待下一次调度",
                )
                pending.append(run)
                continue
            failed.append(self._repository.update_run(
                run_id=run.id, status="FAILED", phase="IDLE", current_role=run.current_role
            ))
            self._repository.append_event(
                run_id=run.id, event_type="RUN_FAILED", summary="无法证明可恢复，启动时已终止"
            )
        return {"pending": pending, "failed": failed}
