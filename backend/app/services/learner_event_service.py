from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from ..core.logging import logger
from ..models.multi_role import CourseRow, NoticeRow
from ..models.personal_task import PersonalTaskRow
from ..models.study import StudySessionRow
from ..repositories.course_content_repository import CourseContentItemRow
from ..repositories.learner_event_repository import LearnerEventRepository
from ..schemas.learner_event import EvidenceReference, LearnerEventAppendResult, LearnerEventCreate


class LearnerEventService:
    def __init__(
        self,
        repository: LearnerEventRepository,
        *,
        study_session_repository=None,
        personal_task_repository=None,
        course_repository=None,
        notice_repository=None,
        course_content_repository=None,
    ) -> None:
        self._repository = repository
        self._study_session_repository = study_session_repository
        self._personal_task_repository = personal_task_repository
        self._course_repository = course_repository
        self._notice_repository = notice_repository
        self._course_content_repository = course_content_repository

    @property
    def repository(self) -> LearnerEventRepository:
        return self._repository

    def record_event(
        self, *, user_id: str, event: LearnerEventCreate
    ) -> LearnerEventAppendResult:
        return self._repository.append_idempotent(user_id=user_id, event=event)

    @staticmethod
    def _parse_aware_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            candidate = value
        elif value:
            try:
                candidate = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        if candidate.tzinfo is None:
            return None
        return candidate.astimezone(timezone.utc)

    @staticmethod
    def _revision_hash(value: dict[str, Any]) -> str:
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def project_safely(
        self,
        *,
        action: str,
        subject_type: str,
        subject_id: str,
        callback: Callable[[], Any],
    ) -> Any:
        """投影失败时保留业务同步结果，只输出不含输入内容的安全日志。"""
        try:
            return callback()
        except Exception as exc:
            logger.warning(
                "learner_event_append_failed action={} subject_type={} subject_id={} exception_type={}",
                action,
                subject_type,
                subject_id,
                type(exc).__name__,
            )
            return None

    def record_chaoxing_course_synced(
        self, course: CourseRow
    ) -> Optional[LearnerEventAppendResult]:
        if course.provider != "chaoxing" or not course.owner_user_id:
            return None
        occurred_at = self._parse_aware_datetime(course.last_synced_at)
        if occurred_at is None:
            return None
        revision = self._revision_hash(
            {
                "external_id": course.external_id,
                "remote_class_id": course.remote_class_id,
                "remote_cpi": course.remote_cpi,
                "remote_student_count": course.remote_student_count,
                "starts_at": course.starts_at,
                "ends_at": course.ends_at,
                "status": course.status,
            }
        )
        event = LearnerEventCreate(
            source="chaoxing",
            event_type="course_synced",
            occurred_at=occurred_at,
            course_id=course.id,
            subject_type="course",
            subject_id=course.id,
            external_ref=course.external_id,
            outcome="synced",
            evidence_reference=EvidenceReference(
                kind="row", table="courses", row_id=course.id, external_id=course.external_id
            ),
            data_quality="verified",
            consent_scope="connected_learning_platform",
            source_version=revision,
            dedupe_key=f"chaoxing:course_synced:{course.id}:{revision}",
            payload={"platform": "chaoxing", "revision": revision},
        )
        return self.record_event(user_id=course.owner_user_id, event=event)

    def record_chaoxing_assignment_discovered(
        self, task: PersonalTaskRow
    ) -> Optional[LearnerEventAppendResult]:
        if task.source != "chaoxing":
            return None
        occurred_at = self._parse_aware_datetime(task.created_at)
        if occurred_at is None:
            return None
        event = LearnerEventCreate(
            source="chaoxing",
            event_type="assignment_discovered",
            occurred_at=occurred_at,
            course_id=task.course_id,
            subject_type="personal_task",
            subject_id=task.id,
            external_ref=task.external_id,
            outcome="discovered",
            evidence_reference=EvidenceReference(
                kind="row", table="personal_tasks", row_id=task.id, external_id=task.external_id
            ),
            data_quality="verified",
            consent_scope="connected_learning_platform",
            dedupe_key=f"chaoxing:assignment_discovered:{task.id}",
            payload={
                "platform": "chaoxing",
                "observation": "first_persisted",
                "initial_status": task.status,
                "has_deadline": task.deadline is not None,
            },
        )
        return self.record_event(user_id=task.user_id, event=event)

    def record_chaoxing_assignment_submitted(
        self, task: PersonalTaskRow, *, observed_at: Any = None
    ) -> Optional[LearnerEventAppendResult]:
        if task.source != "chaoxing" or task.status != "completed":
            return None
        occurred_at = self._parse_aware_datetime(
            observed_at or task.last_synced_at or task.completed_at
        )
        if occurred_at is None:
            return None
        event = LearnerEventCreate(
            source="chaoxing",
            event_type="assignment_submitted",
            occurred_at=occurred_at,
            course_id=task.course_id,
            subject_type="personal_task",
            subject_id=task.id,
            external_ref=task.external_id,
            outcome="observed_completed",
            evidence_reference=EvidenceReference(
                kind="row", table="personal_tasks", row_id=task.id, external_id=task.external_id
            ),
            data_quality="partial",
            consent_scope="connected_learning_platform",
            dedupe_key=f"chaoxing:assignment_submitted:{task.id}",
            payload={
                "platform": "chaoxing",
                "observation": "completed_status",
                "observed_at": occurred_at.isoformat(),
            },
        )
        return self.record_event(user_id=task.user_id, event=event)

    def record_chaoxing_notice_synced(
        self, notice: NoticeRow
    ) -> Optional[LearnerEventAppendResult]:
        if notice.source != "chaoxing":
            return None
        occurred_at = self._parse_aware_datetime(notice.last_synced_at)
        if occurred_at is None:
            return None
        revision = self._revision_hash(
            {
                "external_id": notice.external_id,
                "course_id": notice.course_id,
                "published_at": notice.published_at,
                "title": notice.title,
                "content": notice.content,
            }
        )
        event = LearnerEventCreate(
            source="chaoxing",
            event_type="notice_synced",
            occurred_at=occurred_at,
            course_id=notice.course_id,
            subject_type="notice",
            subject_id=notice.id,
            external_ref=notice.external_id,
            outcome="synced",
            evidence_reference=EvidenceReference(
                kind="row", table="notices", row_id=notice.id, external_id=notice.external_id
            ),
            data_quality="verified",
            consent_scope="connected_learning_platform",
            source_version=revision,
            dedupe_key=f"chaoxing:notice_synced:{notice.id}:{revision}",
            payload={"platform": "chaoxing", "revision": revision},
        )
        return self.record_event(user_id=notice.user_id, event=event)

    def record_chaoxing_chapter_completed(
        self, item: CourseContentItemRow, *, section_status: str
    ) -> Optional[LearnerEventAppendResult]:
        if (
            item.provider != "chaoxing"
            or item.kind != "chapter"
            or item.status != "completed"
            or item.is_stale
            or section_status != "complete"
        ):
            return None
        occurred_at = self._parse_aware_datetime(item.last_synced_at)
        if occurred_at is None:
            return None
        event = LearnerEventCreate(
            source="chaoxing",
            event_type="chapter_completed",
            occurred_at=occurred_at,
            course_id=item.course_id,
            subject_type="chapter",
            subject_id=item.id,
            external_ref=item.external_id,
            outcome="observed_completed",
            evidence_reference=EvidenceReference(
                kind="row", table="course_content_items", row_id=item.id, external_id=item.external_id
            ),
            data_quality="partial",
            consent_scope="connected_learning_platform",
            dedupe_key=f"chaoxing:chapter_completed:{item.course_id}:{item.id}",
            payload={
                "platform": "chaoxing",
                "observation": "platform_completed",
                "section_status": section_status,
                "is_stale": False,
            },
        )
        return self.record_event(user_id=item.user_id, event=event)

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
            query_kwargs={"exclude_source": "chaoxing"},
        )
        return result

    def backfill_chaoxing_learning_events(
        self,
        *,
        user_id: Optional[str] = None,
        batch_size: int = 100,
    ) -> dict[str, int]:
        """从已持久化的学习通记录幂等补写外部学习证据。"""
        if batch_size < 1 or batch_size > 100:
            raise ValueError("batch_size must stay within 1..100")
        repositories = (
            self._course_repository,
            self._personal_task_repository,
            self._notice_repository,
            self._course_content_repository,
        )
        if any(repository is None for repository in repositories):
            raise RuntimeError("chaoxing learning event backfill repositories are not configured")
        result = {
            "scanned": 0,
            "created": 0,
            "reused": 0,
            "skipped": 0,
            "failed": 0,
        }

        def record_task_events(task: PersonalTaskRow) -> list[Optional[LearnerEventAppendResult]]:
            events = [self.record_chaoxing_assignment_discovered(task)]
            if task.status == "completed":
                events.append(self.record_chaoxing_assignment_submitted(task))
            return events

        self._backfill_repository(
            repository=self._course_repository,
            query_method="list_chaoxing_for_event_backfill",
            recorder=self.record_chaoxing_course_synced,
            user_id=user_id,
            batch_size=batch_size,
            subject_type="course",
            result=result,
        )
        self._backfill_repository(
            repository=self._personal_task_repository,
            query_method="list_chaoxing_for_event_backfill",
            recorder=record_task_events,
            user_id=user_id,
            batch_size=batch_size,
            subject_type="personal_task",
            result=result,
        )
        self._backfill_repository(
            repository=self._notice_repository,
            query_method="list_chaoxing_for_event_backfill",
            recorder=self.record_chaoxing_notice_synced,
            user_id=user_id,
            batch_size=batch_size,
            subject_type="notice",
            result=result,
        )
        self._backfill_repository(
            repository=self._course_content_repository,
            query_method="list_completed_chapters_for_event_backfill",
            recorder=lambda item: self.record_chaoxing_chapter_completed(
                item, section_status="complete"
            ),
            user_id=user_id,
            batch_size=batch_size,
            subject_type="chapter",
            result=result,
        )
        return result

    def _backfill_repository(
        self,
        *,
        repository,
        query_method: str = "list_completed_for_event_backfill",
        recorder,
        user_id: Optional[str],
        batch_size: int,
        subject_type: str,
        result: dict[str, int],
        query_kwargs: Optional[dict[str, Any]] = None,
    ) -> None:
        page = 1
        while True:
            rows, _ = getattr(repository, query_method)(
                user_id=user_id,
                page=page,
                page_size=batch_size,
                **(query_kwargs or {}),
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
                if isinstance(append_result, list):
                    append_results = [item for item in append_result if item is not None]
                    if not append_results:
                        result["skipped"] += 1
                        continue
                    for item in append_results:
                        if item.created:
                            result["created"] += 1
                        else:
                            result["reused"] += 1
                elif append_result is None:
                    result["skipped"] += 1
                elif append_result.created:
                    result["created"] += 1
                else:
                    result["reused"] += 1
            if len(rows) < batch_size:
                return
            page += 1


__all__ = ["LearnerEventService"]
