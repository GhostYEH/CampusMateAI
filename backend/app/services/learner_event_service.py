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
        edu_data_repository=None,
        edu_repository=None,
        source_policy=None,
    ) -> None:
        self._repository = repository
        self._study_session_repository = study_session_repository
        self._personal_task_repository = personal_task_repository
        self._course_repository = course_repository
        self._notice_repository = notice_repository
        self._course_content_repository = course_content_repository
        self._edu_data_repository = edu_data_repository
        self._edu_repository = edu_repository
        self._source_policy = source_policy

    @property
    def repository(self) -> LearnerEventRepository:
        return self._repository

    def _is_source_skipped(self, *, user_id: str, source: str) -> bool:
        if self._source_policy is None:
            return False
        return self._source_policy.should_skip_learner_event(user_id=user_id, source=source)

    def record_event(
        self, *, user_id: str, event: LearnerEventCreate
    ) -> LearnerEventAppendResult:
        return self._repository.append_idempotent(user_id=user_id, event=event)

    def record_intervention_event(
        self, *, user_id: str, event_type: str, intervention_id: str, goal_id: str,
        occurred_at: datetime, evaluation_id: str | None = None, decision_id: str | None = None,
        outcome: str = "updated", evidence_refs: list[str] | None = None,
    ) -> LearnerEventAppendResult:
        """Append a bounded, idempotent adaptive-loop event.

        These events are audit signals only; state projection filters an event
        carrying the current evaluation id from that evaluation's comparison.
        """
        payload = {"intervention_id": intervention_id, "goal_id": goal_id,
                   "evaluation_id": evaluation_id, "decision_id": decision_id,
                   "evidence_refs": sorted(set(evidence_refs or []))}
        return self.record_event(user_id=user_id, event=LearnerEventCreate(
            source="adaptive_intervention", event_type=event_type, occurred_at=occurred_at,
            subject_type="adaptive_intervention", subject_id=intervention_id,
            outcome=outcome, evidence_reference=EvidenceReference(
                kind="adaptive_intervention", table="adaptive_interventions", row_id=intervention_id,
            ), data_quality="partial" if event_type == "intervention_feedback_received" else "verified",
            consent_scope="core_learning_record",
            source_version="adaptive-loop-v1",
            dedupe_key=f"adaptive:{event_type}:{intervention_id}:{evaluation_id or decision_id or 'none'}",
            payload=payload,
        ))

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
        if self._is_source_skipped(user_id=course.owner_user_id, source="chaoxing"):
            return None
        occurred_at = self._parse_aware_datetime(course.last_synced_at)
        if occurred_at is None:
            return None
        # Deliberately hash only stable structured fields. Course/teacher/school/class
        # names and URLs are free text and therefore neither revision inputs nor event
        # payload data; sync-time changes to them do not create new evidence revisions.
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
        if self._is_source_skipped(user_id=task.user_id, source="chaoxing"):
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
        if self._is_source_skipped(user_id=task.user_id, source="chaoxing"):
            return None
        # 学习通回传的真实提交时间优先于"同步时发现已完成"的时间戳，
        # 否则晚同步会把完成时间整体推后，污染 execution_consistency 等状态。
        remote_submitted = getattr(task, "remote_submitted_at", None)
        occurred_at = self._parse_aware_datetime(
            remote_submitted or observed_at or task.last_synced_at or task.completed_at
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
            data_quality="verified" if remote_submitted else "partial",
            consent_scope="connected_learning_platform",
            dedupe_key=f"chaoxing:assignment_submitted:{task.id}",
            payload={
                "platform": "chaoxing",
                "observation": "completed_status",
                "observed_at": occurred_at.isoformat(),
                "submitted_at_source": "remote" if remote_submitted else "sync_observed",
            },
        )
        return self.record_event(user_id=task.user_id, event=event)

    def record_chaoxing_notice_synced(
        self, notice: NoticeRow
    ) -> Optional[LearnerEventAppendResult]:
        if notice.source != "chaoxing":
            return None
        if self._is_source_skipped(user_id=notice.user_id, source="chaoxing"):
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
        if self._is_source_skipped(user_id=item.user_id, source="chaoxing"):
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

    @staticmethod
    def _controlled_semester_key(semester: Optional[str]) -> Optional[str]:
        if not semester:
            return None
        return hashlib.sha256(f"sem:{semester}".encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _score_band(score: Optional[str]) -> Optional[str]:
        # 0 分是有效成绩(0_59 段)，只有缺失或空值才不产出分段。
        if score is None or str(score).strip() == "":
            return None
        try:
            numeric = float(score)
        except (TypeError, ValueError):
            return "non_numeric"
        if numeric >= 90:
            return "90_100"
        if numeric >= 80:
            return "80_89"
        if numeric >= 70:
            return "70_79"
        if numeric >= 60:
            return "60_69"
        return "0_59"

    @staticmethod
    def _exam_time_bucket(starts_at: Optional[str]) -> Optional[str]:
        if not starts_at:
            return "unknown"
        try:
            exam_dt = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return "unknown"
        if exam_dt.tzinfo is None:
            exam_dt = exam_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta_days = (exam_dt - now).days
        if delta_days < 0:
            return "past"
        if delta_days <= 7:
            return "within_7d"
        if delta_days <= 30:
            return "within_30d"
        return "beyond_30d"

    @classmethod
    def exam_time_bucket(cls, starts_at: Optional[str]) -> Optional[str]:
        """公开的时间分桶入口，供学习通等同步侧复用同一套分桶口径。"""
        return cls._exam_time_bucket(starts_at)

    def record_edu_schedule_synced(
        self,
        *,
        user_id: str,
        binding_id: str,
        semester: Optional[str],
        scheduled_item_count: int,
        observed_at: datetime,
        sync_batch_id: str,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="edu"):
            return None
        sem_key = self._controlled_semester_key(semester)
        revision = self._revision_hash(
            {
                "binding_id": binding_id,
                "semester_key": sem_key,
                "scheduled_item_count": scheduled_item_count,
                "sync_batch_id": sync_batch_id,
            }
        )
        event = LearnerEventCreate(
            source="edu",
            event_type="edu_schedule_synced",
            occurred_at=observed_at,
            subject_type="edu_schedule",
            subject_id=sync_batch_id,
            outcome="synced",
            evidence_reference=EvidenceReference(
                kind="row", table="edu_schedule_items", row_id=sync_batch_id
            ),
            data_quality=data_quality,
            consent_scope="connected_learning_platform",
            source_version=revision,
            dedupe_key=f"edu:edu_schedule_synced:{binding_id}:{sem_key or 'none'}:{revision}",
            payload={
                "semester_key": sem_key,
                "scheduled_item_count": scheduled_item_count,
                "data_quality": data_quality,
            },
        )
        return self.record_event(user_id=user_id, event=event)

    def record_edu_grade_observed(
        self,
        *,
        user_id: str,
        binding_id: str,
        semester: Optional[str],
        course_code: Optional[str],
        credit_value: Optional[float],
        score: Optional[str],
        assessment_category: Optional[str],
        grade_id: str,
        observed_at: datetime,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="edu"):
            return None
        sem_key = self._controlled_semester_key(semester)
        score_band = self._score_band(score)
        revision = self._revision_hash(
            {
                "binding_id": binding_id,
                "semester_key": sem_key,
                "course_code": course_code,
                "credit_value": credit_value,
                "score_band": score_band,
                "assessment_category": assessment_category,
            }
        )
        event = LearnerEventCreate(
            source="edu",
            event_type="edu_grade_observed",
            occurred_at=observed_at,
            subject_type="edu_grade",
            subject_id=grade_id,
            external_ref=course_code,
            outcome="observed_completed",
            evidence_reference=EvidenceReference(
                kind="row", table="edu_grades", row_id=grade_id
            ),
            data_quality=data_quality,
            consent_scope="connected_learning_platform",
            source_version=revision,
            dedupe_key=f"edu:edu_grade_observed:{grade_id}:{revision}",
            payload={
                "semester_key": sem_key,
                "course_id": course_code,
                "assessment_category": assessment_category,
                "normalized_score_band": score_band,
                "credit_value": credit_value,
                "data_quality": data_quality,
            },
        )
        return self.record_event(user_id=user_id, event=event)

    def record_edu_exam_discovered(
        self,
        *,
        user_id: str,
        binding_id: str,
        semester: Optional[str],
        course_code: Optional[str],
        exam_id: str,
        starts_at: Optional[str],
        observed_at: datetime,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="edu"):
            return None
        sem_key = self._controlled_semester_key(semester)
        time_bucket = self._exam_time_bucket(starts_at)
        revision = self._revision_hash(
            {
                "binding_id": binding_id,
                "semester_key": sem_key,
                "course_code": course_code,
                "exam_time_bucket": time_bucket,
            }
        )
        event = LearnerEventCreate(
            source="edu",
            event_type="edu_exam_discovered",
            occurred_at=observed_at,
            subject_type="edu_exam",
            subject_id=exam_id,
            external_ref=course_code,
            outcome="discovered",
            evidence_reference=EvidenceReference(
                kind="row", table="edu_exam_items", row_id=exam_id
            ),
            data_quality=data_quality,
            consent_scope="connected_learning_platform",
            source_version=revision,
            dedupe_key=f"edu:edu_exam_discovered:{exam_id}:{revision}",
            payload={
                "semester_key": sem_key,
                "course_id": course_code,
                "exam_time_bucket": time_bucket,
                "data_quality": data_quality,
            },
        )
        return self.record_event(user_id=user_id, event=event)

    def record_self_report_submitted(
        self,
        *,
        user_id: str,
        report_id: str,
        report_kind: str,
        occurred_at: datetime,
        duration_minutes: Optional[int] = None,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="self_report"):
            return None
        revision = self._revision_hash(
            {"report_id": report_id, "report_kind": report_kind}
        )
        payload: dict[str, Any] = {
            "report_kind": report_kind,
            "data_quality": data_quality,
        }
        if duration_minutes is not None:
            payload["duration_minutes"] = duration_minutes
        event = LearnerEventCreate(
            source="self_report",
            event_type="self_report_submitted",
            occurred_at=occurred_at,
            subject_type="self_report",
            subject_id=report_id,
            outcome="completed",
            evidence_reference=EvidenceReference(
                kind="row", table="study_sessions", row_id=report_id
            ),
            data_quality=data_quality,
            consent_scope="core_learning_record",
            source_version=revision,
            dedupe_key=f"self_report:self_report_submitted:{report_id}:{revision}",
            payload=payload,
        )
        return self.record_event(user_id=user_id, event=event)

    def record_ai_learning_feedback_recorded(
        self,
        *,
        user_id: str,
        feedback_id: str,
        feedback_kind: str,
        course_id: Optional[str] = None,
        occurred_at: datetime,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="ai_learning_feedback"):
            return None
        revision = self._revision_hash(
            {"feedback_id": feedback_id, "feedback_kind": feedback_kind}
        )
        event = LearnerEventCreate(
            source="ai_learning_feedback",
            event_type="ai_learning_feedback_recorded",
            occurred_at=occurred_at,
            course_id=course_id,
            subject_type="ai_learning_feedback",
            subject_id=feedback_id,
            outcome="observed_completed",
            evidence_reference=EvidenceReference(
                kind="row", table="learning_plan_feedback", row_id=feedback_id
            ),
            data_quality=data_quality,
            consent_scope="core_learning_record",
            source_version=revision,
            dedupe_key=f"ai_learning_feedback:ai_learning_feedback_recorded:{feedback_id}:{revision}",
            payload={
                "feedback_kind": feedback_kind,
                "data_quality": data_quality,
            },
        )
        return self.record_event(user_id=user_id, event=event)


    def record_chaoxing_assignment_graded(
        self,
        *,
        user_id: str,
        task_id: str,
        course_id: Optional[str],
        score_band: Optional[str] = None,
        observed_at: Any = None,
        score: Optional[float] = None,
        score_max: Optional[float] = None,
    ) -> Optional[LearnerEventAppendResult]:
        """记录一次作业评分。

        调用方可以直接给出 `score_band`，也可以只给 `score`(可带 `score_max`)，
        由本方法归一化成分段，避免每个调用方重复实现分段规则。
        """
        if self._is_source_skipped(user_id=user_id, source="chaoxing"):
            return None
        band = score_band or self._score_band(score)
        occurred_at = self._parse_aware_datetime(observed_at)
        if occurred_at is None:
            return None
        revision = self._revision_hash(
            {"task_id": task_id, "score_band": band}
        )
        event = LearnerEventCreate(
            source="chaoxing",
            event_type="assignment_graded",
            occurred_at=observed_at,
            course_id=course_id,
            subject_type="personal_task",
            subject_id=task_id,
            outcome="observed_completed",
            evidence_reference=EvidenceReference(
                kind="row", table="personal_tasks", row_id=task_id
            ),
            data_quality="partial",
            consent_scope="connected_learning_platform",
            source_version=revision,
            dedupe_key=f"chaoxing:assignment_graded:{task_id}:{revision}",
            payload={
                "normalized_score_band": band,
                "score": score,
                "score_max": score_max,
                "data_quality": "partial",
            },
        )
        return self.record_event(user_id=user_id, event=event)

    def record_chaoxing_discussion_participated(
        self,
        *,
        user_id: str,
        discussion_id: str,
        course_id: Optional[str],
        observed_at: datetime,
    ) -> Optional[LearnerEventAppendResult]:
        """记录一次本人参与讨论。

        暂未接线: ChaoxingClient.get_course_discussions 只返回讨论主题列表
        (creatername / replycount / lastreplytime)，没有"本人是否发帖或回复"的标识，
        也没有保存学习通账号身份可供比对。在拿到身份字段前调用本方法会造出
        "参与"假事实，因此保持只有测试覆盖。
        """
        if self._is_source_skipped(user_id=user_id, source="chaoxing"):
            return None
        revision = self._revision_hash({"discussion_id": discussion_id})
        event = LearnerEventCreate(
            source="chaoxing",
            event_type="discussion_participated",
            occurred_at=observed_at,
            course_id=course_id,
            subject_type="discussion",
            subject_id=discussion_id,
            outcome="observed_completed",
            evidence_reference=EvidenceReference(
                kind="row", table="chaoxing_discussions", row_id=discussion_id
            ),
            data_quality="partial",
            consent_scope="connected_learning_platform",
            source_version=revision,
            dedupe_key=f"chaoxing:discussion_participated:{discussion_id}:{revision}",
            payload={"data_quality": "partial"},
        )
        return self.record_event(user_id=user_id, event=event)

    def record_chaoxing_exam_discovered(
        self,
        *,
        user_id: str,
        exam_id: str,
        course_id: Optional[str],
        exam_time_bucket: str,
        observed_at: datetime,
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="chaoxing"):
            return None
        revision = self._revision_hash(
            {"exam_id": exam_id, "exam_time_bucket": exam_time_bucket}
        )
        event = LearnerEventCreate(
            source="chaoxing",
            event_type="exam_discovered",
            occurred_at=observed_at,
            course_id=course_id,
            subject_type="exam",
            subject_id=exam_id,
            outcome="discovered",
            evidence_reference=EvidenceReference(
                kind="row", table="chaoxing_exams", row_id=exam_id
            ),
            data_quality="partial",
            consent_scope="connected_learning_platform",
            source_version=revision,
            dedupe_key=f"chaoxing:exam_discovered:{exam_id}:{revision}",
            payload={
                "exam_time_bucket": exam_time_bucket,
                "data_quality": "partial",
            },
        )
        return self.record_event(user_id=user_id, event=event)

    def record_chaoxing_knowledge_graph_synced(
        self,
        *,
        user_id: str,
        graph_id: str,
        course_id: Optional[str],
        knowledge_point_count: int,
        own_mastery_rate: Optional[float] = None,
        observed_at: Any = None,
    ) -> Optional[LearnerEventAppendResult]:
        """记录一次课程知识图谱同步(知识点体系 + 掌握率)。

        这是外部数据源观测(课程/学校发布的知识点 + 平台统计)，不是平台自造推断，
        因此与被删除的 C 语言学习系统知识点能力无关。
        """
        if self._is_source_skipped(user_id=user_id, source="chaoxing"):
            return None
        occurred_at = self._parse_aware_datetime(observed_at)
        if occurred_at is None:
            return None
        revision = self._revision_hash({
            "graph_id": graph_id,
            "knowledge_point_count": knowledge_point_count,
            "own_mastery_rate": own_mastery_rate,
        })
        event = LearnerEventCreate(
            source="chaoxing",
            event_type="knowledge_graph_synced",
            occurred_at=occurred_at,
            course_id=course_id,
            subject_type="knowledge_graph",
            subject_id=graph_id,
            outcome="synced",
            evidence_reference=EvidenceReference(
                kind="row", table="chaoxing_knowledge_graphs", row_id=graph_id
            ),
            data_quality="partial",
            consent_scope="connected_learning_platform",
            source_version=revision,
            dedupe_key=f"chaoxing:knowledge_graph_synced:{graph_id}:{revision}",
            payload={
                "knowledge_point_count": knowledge_point_count,
                "own_mastery_rate": own_mastery_rate,
                "data_quality": "partial",
            },
        )
        return self.record_event(user_id=user_id, event=event)

    def record_campus_schedule_synced(
        self,
        *,
        user_id: str,
        item_count: int,
        occurred_at: datetime,
        sync_batch_id: str,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="campus"):
            return None
        revision = self._revision_hash({"sync_batch_id": sync_batch_id, "item_count": item_count})
        event = LearnerEventCreate(
            source="campus",
            event_type="campus_schedule_synced",
            occurred_at=occurred_at,
            subject_type="campus_schedule",
            subject_id=sync_batch_id,
            outcome="synced",
            evidence_reference=EvidenceReference(
                kind="row", table="campus_schedule_items", row_id=sync_batch_id
            ),
            data_quality=data_quality,
            consent_scope="core_learning_record",
            source_version=revision,
            dedupe_key=f"campus:campus_schedule_synced:{sync_batch_id}:{revision}",
            payload={"source_kind": "campus", "item_count": item_count, "data_quality": data_quality},
        )
        return self.record_event(user_id=user_id, event=event)

    def record_exam_updated(
        self,
        *,
        user_id: str,
        exam_id: str,
        exam_time_bucket: str,
        occurred_at: datetime,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="campus"):
            return None
        revision = self._revision_hash({"exam_id": exam_id, "exam_time_bucket": exam_time_bucket})
        event = LearnerEventCreate(
            source="campus",
            event_type="exam_updated",
            occurred_at=occurred_at,
            subject_type="exam",
            subject_id=exam_id,
            outcome="updated",
            evidence_reference=EvidenceReference(kind="row", table="exams", row_id=exam_id),
            data_quality=data_quality,
            consent_scope="core_learning_record",
            source_version=revision,
            dedupe_key=f"campus:exam_updated:{exam_id}:{revision}",
            payload={"exam_time_bucket": exam_time_bucket, "data_quality": data_quality},
        )
        return self.record_event(user_id=user_id, event=event)

    def record_academic_progress_synced(
        self,
        *,
        user_id: str,
        binding_id: str,
        occurred_at: datetime,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="campus"):
            return None
        revision = self._revision_hash({"binding_id": binding_id})
        event = LearnerEventCreate(
            source="campus",
            event_type="academic_progress_synced",
            occurred_at=occurred_at,
            subject_type="academic_progress",
            subject_id=binding_id,
            outcome="synced",
            evidence_reference=EvidenceReference(
                kind="row", table="academic_progress", row_id=binding_id
            ),
            data_quality=data_quality,
            consent_scope="core_learning_record",
            source_version=revision,
            dedupe_key=f"campus:academic_progress_synced:{binding_id}:{revision}",
            payload={"data_quality": data_quality},
        )
        return self.record_event(user_id=user_id, event=event)

    def record_campus_notice_synced(
        self,
        *,
        user_id: str,
        notice_id: str,
        occurred_at: datetime,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="campus"):
            return None
        revision = self._revision_hash({"notice_id": notice_id})
        event = LearnerEventCreate(
            source="campus",
            event_type="campus_notice_synced",
            occurred_at=occurred_at,
            subject_type="campus_notice",
            subject_id=notice_id,
            outcome="synced",
            evidence_reference=EvidenceReference(
                kind="row", table="campus_notices", row_id=notice_id
            ),
            data_quality=data_quality,
            consent_scope="core_learning_record",
            source_version=revision,
            dedupe_key=f"campus:campus_notice_synced:{notice_id}:{revision}",
            payload={"source_kind": "campus", "data_quality": data_quality},
        )
        return self.record_event(user_id=user_id, event=event)

    def record_campus_task_created(
        self,
        *,
        user_id: str,
        task_id: str,
        has_deadline: bool,
        occurred_at: datetime,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="campus"):
            return None
        revision = self._revision_hash({"task_id": task_id, "has_deadline": has_deadline})
        event = LearnerEventCreate(
            source="campus",
            event_type="campus_task_created",
            occurred_at=occurred_at,
            subject_type="campus_task",
            subject_id=task_id,
            outcome="discovered",
            evidence_reference=EvidenceReference(
                kind="row", table="campus_tasks", row_id=task_id
            ),
            data_quality=data_quality,
            consent_scope="core_learning_record",
            source_version=revision,
            dedupe_key=f"campus:campus_task_created:{task_id}:{revision}",
            payload={"has_deadline": has_deadline, "data_quality": data_quality},
        )
        return self.record_event(user_id=user_id, event=event)

    def record_campus_task_completed(
        self,
        *,
        user_id: str,
        task_id: str,
        occurred_at: datetime,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="campus"):
            return None
        revision = self._revision_hash({"task_id": task_id})
        event = LearnerEventCreate(
            source="campus",
            event_type="campus_task_completed",
            occurred_at=occurred_at,
            subject_type="campus_task",
            subject_id=task_id,
            outcome="completed",
            evidence_reference=EvidenceReference(
                kind="row", table="campus_tasks", row_id=task_id
            ),
            data_quality=data_quality,
            consent_scope="core_learning_record",
            source_version=revision,
            dedupe_key=f"campus:campus_task_completed:{task_id}:{revision}",
            payload={"data_quality": data_quality},
        )
        return self.record_event(user_id=user_id, event=event)

    def record_personal_goal_created(
        self,
        *,
        user_id: str,
        goal_id: str,
        category: str,
        has_target_date: bool,
        milestone_count: int,
        occurred_at: datetime,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="personal_growth"):
            return None
        revision = self._revision_hash(
            {"goal_id": goal_id, "category": category, "milestone_count": milestone_count}
        )
        event = LearnerEventCreate(
            source="personal_growth",
            event_type="personal_goal_created",
            occurred_at=occurred_at,
            subject_type="student_goal",
            subject_id=goal_id,
            outcome="discovered",
            evidence_reference=EvidenceReference(
                kind="row", table="student_goals", row_id=goal_id
            ),
            data_quality=data_quality,
            consent_scope="core_learning_record",
            source_version=revision,
            dedupe_key=f"personal_growth:personal_goal_created:{goal_id}:{revision}",
            payload={
                "category": category,
                "has_target_date": has_target_date,
                "milestone_count": milestone_count,
            },
        )
        return self.record_event(user_id=user_id, event=event)

    def record_personal_goal_updated(
        self,
        *,
        user_id: str,
        goal_id: str,
        category: str,
        has_target_date: bool,
        milestone_count: int,
        occurred_at: datetime,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="personal_growth"):
            return None
        revision = self._revision_hash(
            {"goal_id": goal_id, "category": category, "milestone_count": milestone_count}
        )
        event = LearnerEventCreate(
            source="personal_growth",
            event_type="personal_goal_updated",
            occurred_at=occurred_at,
            subject_type="student_goal",
            subject_id=goal_id,
            outcome="updated",
            evidence_reference=EvidenceReference(
                kind="row", table="student_goals", row_id=goal_id
            ),
            data_quality=data_quality,
            consent_scope="core_learning_record",
            source_version=revision,
            dedupe_key=f"personal_growth:personal_goal_updated:{goal_id}:{revision}",
            payload={
                "category": category,
                "has_target_date": has_target_date,
                "milestone_count": milestone_count,
            },
        )
        return self.record_event(user_id=user_id, event=event)

    def record_goal_progress_reported(
        self,
        *,
        user_id: str,
        goal_id: str,
        progress_percent: float,
        has_milestone: bool,
        occurred_at: datetime,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="personal_growth"):
            return None
        revision = self._revision_hash(
            {"goal_id": goal_id, "progress_percent": progress_percent, "has_milestone": has_milestone}
        )
        event = LearnerEventCreate(
            source="personal_growth",
            event_type="goal_progress_reported",
            occurred_at=occurred_at,
            subject_type="student_goal",
            subject_id=goal_id,
            outcome="reported",
            evidence_reference=EvidenceReference(
                kind="row", table="student_goal_progress", row_id=goal_id
            ),
            data_quality=data_quality,
            consent_scope="core_learning_record",
            source_version=revision,
            dedupe_key=f"personal_growth:goal_progress_reported:{goal_id}:{revision}",
            payload={
                "progress_percent": progress_percent,
                "has_milestone": has_milestone,
            },
        )
        return self.record_event(user_id=user_id, event=event)

    def record_preference_updated(
        self,
        *,
        user_id: str,
        preference_kind: str,
        occurred_at: datetime,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="campus"):
            return None
        revision = self._revision_hash({"preference_kind": preference_kind})
        event = LearnerEventCreate(
            source="campus",
            event_type="preference_updated",
            occurred_at=occurred_at,
            subject_type="preference",
            subject_id=preference_kind,
            outcome="updated",
            evidence_reference=EvidenceReference(
                kind="row", table="preferences", row_id=preference_kind
            ),
            data_quality=data_quality,
            consent_scope="core_learning_record",
            source_version=revision,
            dedupe_key=f"campus:preference_updated:{preference_kind}:{revision}",
            payload={"preference_kind": preference_kind},
        )
        return self.record_event(user_id=user_id, event=event)

    def record_data_source_paused(
        self,
        *,
        user_id: str,
        source_name: str,
        occurred_at: datetime,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="campus"):
            return None
        revision = self._revision_hash({"source_name": source_name})
        event = LearnerEventCreate(
            source="campus",
            event_type="data_source_paused",
            occurred_at=occurred_at,
            subject_type="data_source",
            subject_id=source_name,
            outcome="paused",
            evidence_reference=EvidenceReference(
                kind="row", table="data_source_controls", row_id=source_name
            ),
            data_quality=data_quality,
            consent_scope="core_learning_record",
            source_version=revision,
            dedupe_key=f"campus:data_source_paused:{source_name}:{revision}",
            payload={"source_name": source_name},
        )
        return self.record_event(user_id=user_id, event=event)

    def record_data_source_resumed(
        self,
        *,
        user_id: str,
        source_name: str,
        occurred_at: datetime,
        data_quality: str = "verified",
    ) -> Optional[LearnerEventAppendResult]:
        if self._is_source_skipped(user_id=user_id, source="campus"):
            return None
        revision = self._revision_hash({"source_name": source_name})
        event = LearnerEventCreate(
            source="campus",
            event_type="data_source_resumed",
            occurred_at=occurred_at,
            subject_type="data_source",
            subject_id=source_name,
            outcome="resumed",
            evidence_reference=EvidenceReference(
                kind="row", table="data_source_controls", row_id=source_name
            ),
            data_quality=data_quality,
            consent_scope="core_learning_record",
            source_version=revision,
            dedupe_key=f"campus:data_source_resumed:{source_name}:{revision}",
            payload={"source_name": source_name},
        )
        return self.record_event(user_id=user_id, event=event)

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

        self._backfill_repository(
            repository=self._course_repository,
            query_method="list_chaoxing_for_event_backfill",
            recorder=self.record_chaoxing_course_synced,
            user_id=user_id,
            batch_size=batch_size,
            subject_type="course",
            result=result,
        )
        self._backfill_chaoxing_tasks(
            user_id=user_id,
            batch_size=batch_size,
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

    def backfill_edu_learning_events(
        self,
        *,
        user_id: Optional[str] = None,
        batch_size: int = 100,
    ) -> dict[str, int]:
        """从已持久化的教务数据幂等补写 Learner Events。"""
        if batch_size < 1 or batch_size > 100:
            raise ValueError("batch_size must stay within 1..100")
        if self._edu_data_repository is None or self._edu_repository is None:
            raise RuntimeError("edu learning event backfill repositories are not configured")
        result = {
            "scanned": 0,
            "created": 0,
            "reused": 0,
            "skipped": 0,
            "failed": 0,
        }
        self._backfill_edu_schedules(user_id=user_id, batch_size=batch_size, result=result)
        self._backfill_edu_grades(user_id=user_id, batch_size=batch_size, result=result)
        self._backfill_edu_exams(user_id=user_id, batch_size=batch_size, result=result)
        return result

    def _backfill_edu_schedules(
        self, *, user_id: Optional[str], batch_size: int, result: dict[str, int]
    ) -> None:
        if user_id is None:
            return
        binding = self._edu_repository.get_binding_by_user(user_id)
        if binding is None:
            return
        semesters = self._edu_data_repository.list_semesters_with_schedule(user_id)
        now = datetime.now(timezone.utc)
        for semester in semesters:
            items = self._edu_data_repository.list_schedule_items(
                user_id=user_id, semester=semester, include_stale=False
            )
            if not items:
                continue
            result["scanned"] += 1
            try:
                append_result = self.record_edu_schedule_synced(
                    user_id=user_id,
                    binding_id=binding.id,
                    semester=semester,
                    scheduled_item_count=len(items),
                    observed_at=now,
                    sync_batch_id=f"backfill:{semester}",
                )
            except Exception as exc:
                result["failed"] += 1
                logger.warning(
                    "learner_event_backfill_failed subject_type=edu_schedule subject_id={} exception_type={}",
                    semester,
                    type(exc).__name__,
                )
            else:
                if append_result is None:
                    result["skipped"] += 1
                elif append_result.created:
                    result["created"] += 1
                else:
                    result["reused"] += 1

    def _backfill_edu_grades(
        self, *, user_id: Optional[str], batch_size: int, result: dict[str, int]
    ) -> None:
        if user_id is None:
            return
        binding = self._edu_repository.get_binding_by_user(user_id)
        if binding is None:
            return
        semesters = self._edu_data_repository.list_semesters_with_grades(user_id)
        now = datetime.now(timezone.utc)
        for semester in semesters:
            items = self._edu_data_repository.list_grade_items(
                user_id=user_id, semester=semester, include_stale=False
            )
            for item in items:
                result["scanned"] += 1
                try:
                    append_result = self.record_edu_grade_observed(
                        user_id=user_id,
                        binding_id=binding.id,
                        semester=semester,
                        course_code=item.course_code,
                        credit_value=item.credit,
                        score=item.score,
                        assessment_category=item.category,
                        grade_id=item.id,
                        observed_at=now,
                    )
                except Exception as exc:
                    result["failed"] += 1
                    logger.warning(
                        "learner_event_backfill_failed subject_type=edu_grade subject_id={} exception_type={}",
                        item.id,
                        type(exc).__name__,
                    )
                else:
                    if append_result is None:
                        result["skipped"] += 1
                    elif append_result.created:
                        result["created"] += 1
                    else:
                        result["reused"] += 1

    def _backfill_edu_exams(
        self, *, user_id: Optional[str], batch_size: int, result: dict[str, int]
    ) -> None:
        if user_id is None:
            return
        binding = self._edu_repository.get_binding_by_user(user_id)
        if binding is None:
            return
        semesters = self._edu_data_repository.list_semesters_with_exams(user_id)
        now = datetime.now(timezone.utc)
        for semester in semesters:
            items = self._edu_data_repository.list_exam_items(
                user_id=user_id, semester=semester, include_stale=False
            )
            for item in items:
                result["scanned"] += 1
                try:
                    append_result = self.record_edu_exam_discovered(
                        user_id=user_id,
                        binding_id=binding.id,
                        semester=semester,
                        course_code=item.course_code,
                        exam_id=item.id,
                        starts_at=item.starts_at,
                        observed_at=now,
                    )
                except Exception as exc:
                    result["failed"] += 1
                    logger.warning(
                        "learner_event_backfill_failed subject_type=edu_exam subject_id={} exception_type={}",
                        item.id,
                        type(exc).__name__,
                    )
                else:
                    if append_result is None:
                        result["skipped"] += 1
                    elif append_result.created:
                        result["created"] += 1
                    else:
                        result["reused"] += 1

    def _backfill_chaoxing_tasks(
        self, *, user_id: Optional[str], batch_size: int, result: dict[str, int]
    ) -> None:
        """Backfill the two assignment observations independently.

        A discovery append failure must not suppress the independent completed-status
        observation; accounting is per event so a partial retry is visible.
        """
        page = 1
        while True:
            rows, _ = self._personal_task_repository.list_chaoxing_for_event_backfill(
                user_id=user_id, page=page, page_size=batch_size
            )
            if not rows:
                return
            for task in rows:
                result["scanned"] += 1
                try:
                    discovered = self.record_chaoxing_assignment_discovered(task)
                except Exception as exc:
                    result["failed"] += 1
                    logger.warning(
                        "learner_event_backfill_failed subject_type=personal_task subject_id=%s event_type=assignment_discovered exception_type=%s",
                        task.id,
                        type(exc).__name__,
                    )
                else:
                    if discovered is None:
                        result["skipped"] += 1
                    elif discovered.created:
                        result["created"] += 1
                    else:
                        result["reused"] += 1

                if task.status != "completed":
                    continue
                try:
                    submitted = self.record_chaoxing_assignment_submitted(task)
                except Exception as exc:
                    result["failed"] += 1
                    logger.warning(
                        "learner_event_backfill_failed subject_type=personal_task subject_id=%s event_type=assignment_submitted exception_type=%s",
                        task.id,
                        type(exc).__name__,
                    )
                else:
                    if submitted is None:
                        result["skipped"] += 1
                    elif submitted.created:
                        result["created"] += 1
                    else:
                        result["reused"] += 1
            if len(rows) < batch_size:
                return
            page += 1

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
