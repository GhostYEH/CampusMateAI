from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..models.personal_task import PersonalTaskRow
from ..models.study import StudySessionRow
from ..repositories.learner_event_repository import LearnerEventRepository
from ..schemas.learner_event import EvidenceReference, LearnerEventAppendResult, LearnerEventCreate


class LearnerEventService:
    def __init__(self, repository: LearnerEventRepository) -> None:
        self._repository = repository

    @property
    def repository(self) -> LearnerEventRepository:
        return self._repository

    def record_event(
        self, *, user_id: str, event: LearnerEventCreate
    ) -> LearnerEventAppendResult:
        return self._repository.append_idempotent(user_id=user_id, event=event)

    def record_study_session_finished(
        self, session: StudySessionRow
    ) -> Optional[LearnerEventAppendResult]:
        if session.status != "completed":
            return None
        if not session.ended_at:
            return None
        if session.duration_seconds < 0:
            return None
        try:
            occurred_at = datetime.fromisoformat(session.ended_at)
        except ValueError:
            return None
        payload: dict = {
            "mode": session.mode,
            "experience_mode": session.experience_mode,
            "planned_duration_seconds": session.planned_duration_seconds,
            "pause_seconds": session.pause_seconds,
        }
        if session.related_task_id:
            payload["related_task_id"] = session.related_task_id
        event = LearnerEventCreate(
            source="study",
            event_type="study_session_finished",
            occurred_at=occurred_at,
            subject_type="study_session",
            subject_id=session.id,
            outcome="completed",
            duration_seconds=session.duration_seconds,
            evidence_reference=EvidenceReference(
                kind="row", table="study_sessions", row_id=session.id
            ),
            data_quality="verified",
            consent_scope="core_learning_record",
            dedupe_key=f"study:study_session_finished:{session.id}",
            payload=payload,
        )
        return self.record_event(user_id=session.user_id, event=event)

    def record_personal_task_completed(
        self, task: PersonalTaskRow
    ) -> Optional[LearnerEventAppendResult]:
        if task.status != "completed":
            return None
        if not task.completed_at:
            return None
        if task.deleted_at:
            return None
        try:
            occurred_at = datetime.fromisoformat(task.completed_at)
        except ValueError:
            return None
        event = LearnerEventCreate(
            source="personal_task",
            event_type="task_completed",
            occurred_at=occurred_at,
            course_id=task.course_id,
            subject_type="personal_task",
            subject_id=task.id,
            external_ref=task.external_id,
            outcome="completed",
            evidence_reference=EvidenceReference(
                kind="row",
                table="personal_tasks",
                row_id=task.id,
                external_id=task.external_id,
            ),
            data_quality="verified",
            consent_scope="core_learning_record",
            dedupe_key=f"personal_task:task_completed:{task.id}:{task.completed_at}",
            payload={
                "priority": task.priority,
                "importance": task.importance,
                "source": task.source,
                "has_deadline": task.deadline is not None,
            },
        )
        return self.record_event(user_id=task.user_id, event=event)

    def list_events(
        self,
        *,
        user_id: str,
        source: Optional[str] = None,
        event_type: Optional[str] = None,
        course_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ):
        return self._repository.list_for_user(
            user_id=user_id,
            source=source,
            event_type=event_type,
            course_id=course_id,
            since=since,
            until=until,
            page=page,
            page_size=page_size,
        )

    def delete_user_events(self, *, user_id: str) -> int:
        return self._repository.delete_for_user(user_id=user_id)


__all__ = ["LearnerEventService"]
