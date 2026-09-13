from __future__ import annotations

from ...models.agent_runtime import AgentEventRow
from ...repositories.agent_runtime_repository import AgentRuntimeRepository


class AgentEventStore:
    def __init__(self, repository: AgentRuntimeRepository) -> None:
        self._repository = repository

    def append(self, *, run_id: str, event_type: str, summary: str,
               artifact_id: str | None = None, approval_id: str | None = None) -> AgentEventRow:
        return self._repository.append_event(
            run_id=run_id, event_type=event_type, summary=summary,
            artifact_id=artifact_id, approval_id=approval_id,
        )

    def replay(self, *, run_id: str, last_event_id: str | None = None) -> list[AgentEventRow]:
        return self._repository.list_events(run_id=run_id, after_event_id=last_event_id)
