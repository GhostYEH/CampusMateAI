from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..core.logging import logger
from ..models.personal_task import PersonalTaskRow
from ..models.study import StudySessionRow
from ..repositories.learner_event_repository import LearnerEventRepository
from ..schemas.learner_event import EvidenceReference, LearnerEventAppendResult, LearnerEventCreate


class LearnerEventService:
    def __init__(
        self,
        repository: LearnerEventRepository,
        *,
        study_session_repository=None,
        personal_task_repository=None,
    ) -> None:
        self._repository = repository
        self._study_session_repository = study_session_repository
        self._personal_task_repository = personal_task_repository

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

    def backfill_core_learning_events(
        self,
        *,
        user_id: Optional[str] = None,
        batch_size: int = 100,
    ) -> dict[str, int]:
        """从已完成的核心业务记录幂等补写 Learner Events。

        业务 Repository 在容器中注入，避免引入新的容器或数据库实例。
        ``user_id=None`` 只允许明确的管理回填调用，两个查询方法也有专门命名。
        """
        if batch_size < 1 or batch_size > 100:
            raise ValueError("batch_size must stay within 1..100")
        if self._study_session_repository is None or self._personal_task_repository is None:
            raise RuntimeError("core learning event backfill repositories are not configured")
        result = {
            "scanned": 0,
            "created": 0,
            "reused": 0,
            "skipped": 0,
            "failed": 0,
        }
        self._backfill_repository(
            repository=self._study_session_repository,
            recorder=self.record_study_session_finished,
            user_id=user_id,
            batch_size=batch_size,
            subject_type="study_session",
            result=result,
        )
        self._backfill_repository(
            repository=self._personal_task_repository,
            recorder=self.record_personal_task_completed,
            user_id=user_id,
            batch_size=batch_size,
            subject_type="personal_task",
            result=result,
        )
        return result

    def _backfill_repository(
        self,
        *,
        repository,
        recorder,
        user_id: Optional[str],
        batch_size: int,
        subject_type: str,
        result: dict[str, int],
    ) -> None:
        page = 1
        while True:
            rows, _ = repository.list_completed_for_event_backfill(
                user_id=user_id,
                page=page,
                page_size=batch_size,
            )
            if not rows:
                return
            for row in rows:
                result["scanned"] += 1
                try:
                    append_result = recorder(row)
                except Exception as exc:
                    result["failed"] += 1
                    logger.warning(
                        "learner_event_backfill_failed subject_type={} subject_id={} exception_type={}",
                        subject_type,
                        row.id,
                        type(exc).__name__,
                    )
                    continue
                if append_result is None:
                    result["skipped"] += 1
                elif append_result.created:
                    result["created"] += 1
                else:
                    result["reused"] += 1
            if len(rows) < batch_size:
                return
            page += 1


__all__ = ["LearnerEventService"]
