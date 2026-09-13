from __future__ import annotations

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
