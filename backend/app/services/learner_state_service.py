from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from ..models.learner_state import ProjectionRunRow, StateSnapshotRow
from ..repositories.learner_state_repository import LearnerStateRepository

ESTIMATOR_VERSION = "deterministic-observed-v1"
_SHORT_TTL = timedelta(minutes=5)
_CHAOXING_TTL = timedelta(hours=24)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("as_of must carry timezone")
    return value.astimezone(timezone.utc)


def _digest(inputs: dict[str, Any]) -> str:
    raw = json.dumps(inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _confidence(quality: str) -> float:
    return {"verified": 1.0, "partial": 0.6, "stale": 0.25, "unavailable": 0.0}[quality]


@dataclass(frozen=True)
class ComputedSnapshot:
    snapshot_id: str
    run_id: str
    scope_type: str
    scope_id: str
    state_type: str
    value: dict[str, Any]
    confidence: float
    data_quality: str
    observed_from: str | None
    observed_through: str | None
    valid_until: str | None
    computed_at: str


@dataclass(frozen=True)
class ProjectionResult:
    run_id: str
    user_id: str
    as_of: str
    computed_at: str
    estimator_version: str
    input_digest: str
    snapshots: list[ComputedSnapshot]
    warnings: list[str]


class LearnerStateProjectionService:
    """Deterministic, full-user projection over events plus authoritative rows."""

    def __init__(self, repository: LearnerStateRepository) -> None:
        self.repository = repository

    def project_user(
        self, user_id: str, *, as_of: datetime, trigger: str = "read"
    ) -> ProjectionResult:
        as_of = _require_utc(as_of)
        current = self.repository.get_current_run(user_id=user_id)
        try:
            inputs = self.repository.collect_inputs(user_id=user_id)
            input_digest = _digest(inputs)
            if current and current.estimator_version == ESTIMATOR_VERSION and current.input_digest == input_digest:
                existing = self._result_from_current(current, as_of=as_of)
                # A run is keyed by its explicit as_of. If a source is already stale at
                # that as_of, recomputing cannot make the same historical observation
                # fresh; reuse the deterministic stale result until as_of advances.
                if existing is not None and _parse(current.as_of) == as_of:
                    return existing
            result, snapshot_rows, evidence = self._compute(
                user_id=user_id,
                inputs=inputs,
                as_of=as_of,
                input_digest=input_digest,
                trigger=trigger,
            )
            self.repository.save_projection(
                run={
                    "run_id": result.run_id,
                    "user_id": user_id,
                    "as_of": result.as_of,
                    "computed_at": result.computed_at,
                    "estimator_version": ESTIMATOR_VERSION,
                    "input_digest": input_digest,
                    "trigger": trigger,
                    "warnings": result.warnings,
                },
                snapshots=[self._to_dict(row) for row in snapshot_rows],
                evidence=evidence,
            )
            return result
        except Exception:
            if current is not None:
                return self._stale_result(current, as_of=as_of)
            return self._unavailable_result(user_id=user_id, as_of=as_of)

    def _result_from_current(self, run: ProjectionRunRow, *, as_of: datetime) -> ProjectionResult | None:
        rows = self.repository.list_all_current_snapshots(user_id=run.user_id)
        if not rows:
            return None
        return ProjectionResult(
            run_id=run.run_id,
            user_id=run.user_id,
            as_of=run.as_of,
            computed_at=run.computed_at,
            estimator_version=run.estimator_version,
            input_digest=run.input_digest,
            snapshots=[self._computed(row) for row in rows],
            warnings=run.warnings,
        )

    @staticmethod
    def _computed(row: StateSnapshotRow) -> ComputedSnapshot:
        return ComputedSnapshot(
            snapshot_id=row.snapshot_id, run_id=row.run_id, scope_type=row.scope_type,
            scope_id=row.scope_id, state_type=row.state_type, value=row.value,
            confidence=row.confidence, data_quality=row.data_quality,
            observed_from=row.observed_from, observed_through=row.observed_through,
            valid_until=row.valid_until, computed_at=row.computed_at,
        )

    @staticmethod
    def _to_dict(row: ComputedSnapshot) -> dict[str, Any]:
        return row.__dict__.copy()

    def _compute(
        self, *, user_id: str, inputs: dict[str, Any], as_of: datetime,
        input_digest: str, trigger: str,
    ) -> tuple[ProjectionResult, list[ComputedSnapshot], list[dict[str, Any]]]:
        computed_at = _iso(as_of)
        run_id = f"lrun_{uuid.uuid4().hex[:16]}"
        rows: list[ComputedSnapshot] = []
        evidence: list[dict[str, Any]] = []

        def add(
            *, scope_type: str, scope_id: str, state_type: str, value: dict[str, Any],
            quality: str, observed_from: datetime | None, observed_through: datetime | None,
            valid_until: datetime | None, sources: list[dict[str, Any]],
        ) -> None:
            snapshot = ComputedSnapshot(
                snapshot_id=f"lsnap_{uuid.uuid4().hex[:16]}", run_id=run_id,
                scope_type=scope_type, scope_id=scope_id, state_type=state_type,
                value=value, confidence=_confidence(quality), data_quality=quality,
                observed_from=_iso(observed_from) if observed_from else None,
                observed_through=_iso(observed_through) if observed_through else None,
                valid_until=_iso(valid_until) if valid_until else None,
                computed_at=computed_at,
            )
            rows.append(snapshot)
            for source in sources[:100]:
                evidence.append({
                    "evidence_id": f"lev_{uuid.uuid4().hex[:16]}",
                    "snapshot_id": snapshot.snapshot_id,
                    "evidence_kind": source["evidence_kind"],
                    "event_id": source.get("event_id"),
                    "source_type": source["source_type"],
                    "source_id": source["source_id"],
                    "role": source.get("role", "SUPPORTS"),
                    "quality": source.get("quality", quality),
                })

        events = inputs["events"]
        sessions = inputs["sessions"]
        tasks = inputs["tasks"]
        content = inputs["content"]
        sections = inputs["sections"]

        activity_value, activity_quality, activity_sources, activity_last = self._activity(
            events, sessions, tasks, as_of, user_id
        )
        add(
            scope_type="USER", scope_id=user_id, state_type="observed_learning_activity",
            value=activity_value, quality=activity_quality, observed_from=as_of - timedelta(days=30),
            observed_through=activity_last or as_of, valid_until=as_of + _SHORT_TTL,
            sources=activity_sources,
        )

        workload_value, workload_quality, workload_sources = self._workload(tasks, as_of, user_id)
        add(
            scope_type="USER", scope_id=user_id, state_type="task_workload",
            value=workload_value, quality=workload_quality, observed_from=None,
            observed_through=as_of, valid_until=as_of + _SHORT_TTL, sources=workload_sources,
        )

        for task in tasks:
            if task.get("deleted_at") or task.get("status") == "deleted":
                continue
            bucket, quality = self._deadline_bucket(task.get("deadline"), as_of)
            deadline_sources = [{
                "evidence_kind": "SOURCE_ROW", "source_type": "personal_task",
                "source_id": task["id"], "role": "SUPPORTS", "quality": quality,
            }]
            add(
                scope_type="TASK", scope_id=task["id"], state_type="deadline_exposure",
                value={"bucket": bucket}, quality=quality, observed_from=None,
                observed_through=as_of, valid_until=self._deadline_valid_until(bucket, as_of),
                sources=deadline_sources,
            )

        course_ids = {
            str(item["course_id"]) for item in content if item.get("course_id")
        }
        course_ids.update(str(event["course_id"]) for event in events if event.get("course_id"))
        for course_id in sorted(course_ids):
            value, quality, sources, last = self._course_participation(
                course_id, events, content, sections, as_of
            )
            add(
                scope_type="COURSE", scope_id=course_id, state_type="course_participation",
                value=value, quality=quality, observed_from=None, observed_through=last or as_of,
                valid_until=as_of + _CHAOXING_TTL, sources=sources,
            )

        for source_id in ("core_learning_record", "chaoxing"):
            value, quality, sources, observed, valid_until = self._source_health(
                source_id, inputs, as_of
            )
            add(
                scope_type="SOURCE", scope_id=source_id, state_type="data_source_health",
                value=value, quality=quality, observed_from=observed, observed_through=observed,
                valid_until=valid_until, sources=sources,
            )

        result = ProjectionResult(
            run_id=run_id, user_id=user_id, as_of=computed_at, computed_at=computed_at,
            estimator_version=ESTIMATOR_VERSION, input_digest=input_digest,
            snapshots=rows, warnings=[],
        )
        return result, rows, evidence

    @staticmethod
    def _event_sources(events: list[dict[str, Any]], *, event_types: set[str] | None = None, subject_ids: set[str] | None = None) -> list[dict[str, Any]]:
        result = []
        for event in events:
            if event_types and event.get("event_type") not in event_types:
                continue
            if subject_ids and event.get("subject_id") not in subject_ids:
                continue
            result.append({
                "evidence_kind": "EVENT", "event_id": event["event_id"],
                "source_type": event.get("source") or "unknown",
                "source_id": event.get("subject_id") or event["event_id"],
                "role": "SUPPORTS", "quality": event.get("data_quality") or "partial",
            })
        return result

    def _activity(self, events, sessions, tasks, as_of, user_id):
        start7, start30 = as_of - timedelta(days=7), as_of - timedelta(days=30)
        session_times: dict[str, tuple[datetime, int]] = {}
        for row in sessions:
            ended = _parse(row.get("ended_at"))
            if row.get("status") == "completed" and ended and ended <= as_of:
                session_times[row["id"]] = (ended, int(row.get("duration_seconds") or 0))
        event_times = {
            event["subject_id"]: _parse(event.get("occurred_at"))
            for event in events if event.get("event_type") == "study_session_finished" and event.get("subject_id")
        }
        for subject_id, when in event_times.items():
            if subject_id not in session_times and when and when <= as_of:
                session_times[subject_id] = (when, 0)
        task_times: dict[str, datetime] = {}
        for row in tasks:
            when = _parse(row.get("completed_at"))
            if row.get("status") == "completed" and when and when <= as_of and not row.get("deleted_at"):
                task_times[row["id"]] = when
        for event in events:
            if event.get("event_type") not in {"task_completed", "assignment_submitted"}:
                continue
            when = _parse(event.get("occurred_at"))
            if event.get("subject_id") and when and when <= as_of:
                task_times.setdefault(event["subject_id"], when)
        def count_since(mapping, since):
            return sum(1 for value in mapping.values() if (value[0] if isinstance(value, tuple) else value) >= since)
        def seconds_since(since):
            return sum(seconds for when, seconds in session_times.values() if when >= since)
        last_values = [when for when, _ in session_times.values()] + list(task_times.values())
        last = max(last_values) if last_values else None
        sources = self._event_sources(events, event_types={"study_session_finished", "task_completed", "assignment_submitted"})
        sources += [{
            "evidence_kind": "SOURCE_ROW", "source_type": "study_sessions", "source_id": row["id"],
            "role": "SUPPORTS", "quality": "verified",
        } for row in sessions if row.get("id") in session_times]
        if not sources:
            sources = [{"evidence_kind": "SYNC_STATUS", "source_type": "core_learning_record", "source_id": user_id, "role": "LIMITS", "quality": "partial"}]
        return {
            "observed_sessions_7d": count_since(session_times, start7),
            "observed_sessions_30d": count_since(session_times, start30),
            "observed_study_seconds_7d": seconds_since(start7),
            "observed_study_seconds_30d": seconds_since(start30),
            "observed_completed_tasks_7d": count_since(task_times, start7),
            "observed_completed_tasks_30d": count_since(task_times, start30),
            "last_observed_activity_at": _iso(last) if last else None,
        }, "verified" if sessions or tasks else "partial", sources, last

    def _workload(self, tasks, as_of, user_id):
        pending = [row for row in tasks if row.get("status") == "pending" and not row.get("deleted_at")]
        result = {"known_pending": len(pending), "known_overdue": 0, "known_due_24h": 0,
                  "known_due_7d": 0, "known_without_deadline": 0, "unknown_deadline": 0}
        sources = []
        for task in pending:
            bucket, quality = self._deadline_bucket(task.get("deadline"), as_of)
            key = {"OVERDUE": "known_overdue", "DUE_24H": "known_due_24h", "DUE_7D": "known_due_7d"}.get(bucket)
            if key:
                result[key] += 1
            elif bucket == "NO_DEADLINE":
                result["known_without_deadline"] += 1
            else:
                result["unknown_deadline"] += 1
            sources.append({"evidence_kind": "SOURCE_ROW", "source_type": "personal_task", "source_id": task["id"], "role": "SUPPORTS", "quality": quality})
        if not sources:
            sources = [{"evidence_kind": "SYNC_STATUS", "source_type": "core_learning_record", "source_id": user_id, "role": "SUPPORTS", "quality": "verified"}]
        quality = "verified" if all(item.get("deadline") is None or _parse(item.get("deadline")) for item in pending) else "partial"
        return result, quality, sources

    @staticmethod
    def _deadline_bucket(deadline, as_of):
        if deadline is None:
            return "NO_DEADLINE", "verified"
        parsed = _parse(deadline)
        if parsed is None:
            return "UNKNOWN", "partial"
        if parsed < as_of:
            return "OVERDUE", "verified"
        if parsed <= as_of + timedelta(hours=24):
            return "DUE_24H", "verified"
        if parsed <= as_of + timedelta(days=7):
            return "DUE_7D", "verified"
        return "LATER", "verified"

    @staticmethod
    def _deadline_valid_until(bucket, as_of):
        boundaries = {
            "OVERDUE": as_of + _SHORT_TTL,
            "DUE_24H": as_of + timedelta(hours=24),
            "DUE_7D": as_of + timedelta(days=7),
            "LATER": as_of + _SHORT_TTL,
            "NO_DEADLINE": as_of + _SHORT_TTL,
            "UNKNOWN": as_of + _SHORT_TTL,
        }
        return boundaries[bucket]

    def _course_participation(self, course_id, events, content, sections, as_of):
        good_sections = {
            row["course_id"] for row in sections
            if str(row.get("course_id")) == course_id and row.get("section") == "chapters" and row.get("status") == "complete"
        }
        fresh_chapters = {
            row["id"] for row in content
            if str(row.get("course_id")) == course_id and row.get("kind") == "chapter"
            and row.get("status") == "completed" and not row.get("is_stale") and course_id in good_sections
        }
        stale_chapter_ids = {
            row["id"] for row in content
            if str(row.get("course_id")) == course_id and row.get("kind") == "chapter" and row.get("is_stale")
        }
        chapter_events = [
            event for event in events
            if event.get("course_id") == course_id
            and event.get("event_type") == "chapter_completed"
            and course_id in good_sections
            and event.get("subject_id") not in stale_chapter_ids
        ]
        assignment_discovered = {event.get("subject_id") for event in events if event.get("course_id") == course_id and event.get("event_type") == "assignment_discovered"}
        assignment_completed = {event.get("subject_id") for event in events if event.get("course_id") == course_id and event.get("event_type") == "assignment_submitted"}
        last_values = [_parse(event.get("occurred_at")) for event in events if event.get("course_id") == course_id]
        last_values = [item for item in last_values if item and item <= as_of]
        last = max(last_values) if last_values else None
        sources = self._event_sources(events, subject_ids=None)
        sources = [item for item, event in zip(sources, events) if event.get("course_id") == course_id]
        sources += [{"evidence_kind": "SOURCE_ROW", "source_type": "course_content_items", "source_id": item, "role": "SUPPORTS", "quality": "verified"} for item in fresh_chapters]
        if not good_sections:
            sources.append({"evidence_kind": "SYNC_STATUS", "source_type": "course_sync_sections", "source_id": course_id, "role": "LIMITS", "quality": "partial"})
        if not sources:
            sources = [{"evidence_kind": "SYNC_STATUS", "source_type": "course_sync_sections", "source_id": course_id, "role": "LIMITS", "quality": "partial"}]
        quality = "verified" if good_sections else "partial"
        return {
            "observed_chapters_completed": len(fresh_chapters | {event.get("subject_id") for event in chapter_events}),
            "observed_assignments_discovered": len({item for item in assignment_discovered if item}),
            "observed_assignments_completed": len({item for item in assignment_completed if item}),
            "last_observed_course_activity_at": _iso(last) if last else None,
            "evidence_quality": quality,
        }, quality, sources, last

    def _source_health(self, source_id, inputs, as_of):
        if source_id == "core_learning_record":
            core_events = [item for item in inputs["events"] if item.get("source") in {"study", "personal_task"}]
            event_subjects = {item.get("subject_id") for item in core_events}
            observations = [_parse(item.get("occurred_at")) for item in core_events]
            authority_rows = []
            authority_rows.extend(
                _parse(item.get("ended_at")) for item in inputs["sessions"]
                if item.get("status") == "completed"
            )
            authority_rows.extend(
                _parse(item.get("completed_at")) for item in inputs["tasks"]
                if item.get("status") == "completed" and not item.get("deleted_at")
            )
            observations.extend(authority_rows)
            observations = [item for item in observations if item and item <= as_of]
            observed = max(observations) if observations else None
            if observed is None:
                return {"status": "UNAVAILABLE", "last_successful_observation_at": None, "valid_until": None, "warning_codes": ["no_observation"]}, "unavailable", [{"evidence_kind": "SYNC_STATUS", "source_type": source_id, "source_id": source_id, "role": "INVALIDATES", "quality": "unavailable"}], None, None
            valid_until = observed + _CHAOXING_TTL
            missing_event = any(
                row.get("id") not in event_subjects
                for row in inputs["sessions"] + inputs["tasks"]
                if (row.get("status") == "completed" and not row.get("deleted_at"))
            )
            if valid_until < as_of:
                return {"status": "STALE", "last_successful_observation_at": _iso(observed), "valid_until": _iso(valid_until), "warning_codes": ["freshness_expired"]}, "stale", self._event_sources(inputs["events"], event_types={"study_session_finished", "task_completed"}) or [{"evidence_kind": "SYNC_STATUS", "source_type": source_id, "source_id": source_id, "role": "LIMITS", "quality": "stale"}], observed, valid_until
            if missing_event or not core_events:
                return {"status": "PARTIAL", "last_successful_observation_at": _iso(observed), "valid_until": _iso(valid_until), "warning_codes": ["event_gap"]}, "partial", self._event_sources(inputs["events"], event_types={"study_session_finished", "task_completed"}) or [{"evidence_kind": "SYNC_STATUS", "source_type": source_id, "source_id": source_id, "role": "LIMITS", "quality": "partial"}], observed, valid_until
            return {"status": "FRESH", "last_successful_observation_at": _iso(observed), "valid_until": _iso(valid_until), "warning_codes": []}, "verified", self._event_sources(inputs["events"], event_types={"study_session_finished", "task_completed"}) or [{"evidence_kind": "SYNC_STATUS", "source_type": source_id, "source_id": source_id, "role": "SUPPORTS", "quality": "verified"}], observed, valid_until
        observations = []
        for group in (inputs["courses"], inputs["tasks"], inputs["sections"]):
            observations.extend(_parse(item.get("last_synced_at")) for item in group)
        observations = [item for item in observations if item and item <= as_of]
        observed = max(observations) if observations else None
        warnings = []
        credentials = inputs.get("chaoxing_credentials_updated_at")
        if not credentials:
            return {"status": "UNAVAILABLE", "last_successful_observation_at": None, "valid_until": None, "warning_codes": ["disconnected"]}, "unavailable", [{"evidence_kind": "SYNC_STATUS", "source_type": "chaoxing", "source_id": source_id, "role": "INVALIDATES", "quality": "unavailable"}], None, None
        if any(item.get("status") in {"failed", "partial"} for item in inputs["sections"]):
            warnings.append("section_sync_incomplete")
        if observed is None:
            return {"status": "UNAVAILABLE", "last_successful_observation_at": None, "valid_until": None, "warning_codes": ["no_successful_sync"]}, "unavailable", [{"evidence_kind": "SYNC_STATUS", "source_type": "chaoxing", "source_id": source_id, "role": "LIMITS", "quality": "unavailable"}], None, None
        valid_until = observed + _CHAOXING_TTL
        stale = valid_until < as_of
        status = "STALE" if stale else ("PARTIAL" if warnings else "FRESH")
        quality = "stale" if stale else ("partial" if warnings else "verified")
        if stale:
            warnings.append("freshness_expired")
        return {"status": status, "last_successful_observation_at": _iso(observed), "valid_until": _iso(valid_until), "warning_codes": warnings}, quality, [{"evidence_kind": "SYNC_STATUS", "source_type": "chaoxing", "source_id": source_id, "role": "LIMITS" if warnings else "SUPPORTS", "quality": quality}], observed, valid_until

    def _stale_result(self, run: ProjectionRunRow, *, as_of: datetime) -> ProjectionResult:
        rows = self.repository.list_all_current_snapshots(user_id=run.user_id)
        stale_rows = []
        for row in rows:
            value = dict(row.value)
            if row.state_type == "data_source_health":
                if value.get("last_successful_observation_at") is not None:
                    value["status"] = "STALE"
                value.setdefault("warning_codes", []).append("projection_failed")
            stale_rows.append(ComputedSnapshot(
                snapshot_id=row.snapshot_id, run_id=row.run_id, scope_type=row.scope_type,
                scope_id=row.scope_id, state_type=row.state_type, value=value,
                confidence=min(row.confidence, 0.25), data_quality="stale",
                observed_from=row.observed_from, observed_through=row.observed_through,
                valid_until=row.valid_until, computed_at=row.computed_at,
            ))
        return ProjectionResult(run_id=run.run_id, user_id=run.user_id, as_of=run.as_of,
                                computed_at=run.computed_at, estimator_version=run.estimator_version,
                                input_digest=run.input_digest, snapshots=stale_rows,
                                warnings=[*run.warnings, "projection_failed"])

    @staticmethod
    def _unavailable_result(*, user_id: str, as_of: datetime) -> ProjectionResult:
        computed = _iso(as_of)
        snapshots = []
        for source_id in ("core_learning_record", "chaoxing"):
            snapshots.append(ComputedSnapshot(
                snapshot_id=f"unavailable_{source_id}", run_id="", scope_type="SOURCE",
                scope_id=source_id, state_type="data_source_health",
                value={"status": "UNAVAILABLE", "last_successful_observation_at": None, "valid_until": None, "warning_codes": ["projection_failed"]},
                confidence=0.0, data_quality="unavailable", observed_from=None,
                observed_through=None, valid_until=None, computed_at=computed,
            ))
        return ProjectionResult(run_id="", user_id=user_id, as_of=computed, computed_at=computed,
                                estimator_version=ESTIMATOR_VERSION, input_digest="",
                                snapshots=snapshots, warnings=["projection_failed"])


__all__ = ["ESTIMATOR_VERSION", "ComputedSnapshot", "LearnerStateProjectionService", "ProjectionResult"]
