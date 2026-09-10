from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..core.exceptions import AppException
from ..database.sqlite_db import Database
from ..models.learner_event import LearnerEventRow
from ..schemas.learner_event import LearnerEventAppendResult, LearnerEventCreate

_COLUMNS = (
    "event_id,user_id,occurred_at,received_at,source,event_type,course_id,"
    "subject_type,subject_id,external_ref,outcome,duration_seconds,"
    "evidence_reference_json,data_quality,consent_scope,source_version,"
    "dedupe_key,payload_json,created_at"
)

_IDENTITY_FIELDS = ("source", "event_type", "subject_type", "subject_id")


class LearnerEventConflict(AppException):
    code = "LEARNER_EVENT_CONFLICT"
    http_status = 409
    message = "事件幂等键冲突"


class LearnerEventRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _dump(value: dict | None) -> Optional[str]:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _identity(event: LearnerEventCreate) -> tuple:
        return (
            event.source,
            event.event_type,
            event.subject_type,
            event.subject_id,
            event.evidence_reference.model_dump(),
        )

    @staticmethod
    def _identity_of(row: LearnerEventRow) -> tuple:
        return (
            row.source,
            row.event_type,
            row.subject_type,
            row.subject_id,
            dict(row.evidence_reference or {}),
        )

    def append_idempotent(
        self, *, user_id: str, event: LearnerEventCreate
    ) -> LearnerEventAppendResult:
        now = self._now_iso()
        event_id = f"leevt_{uuid.uuid4().hex[:16]}"
        occurred_at = event.occurred_at.astimezone(timezone.utc).isoformat()
        try:
            with self._db.transaction() as conn:
                conn.execute(
                    f"INSERT INTO learner_events ({_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        event_id,
                        user_id,
                        occurred_at,
                        now,
                        event.source,
                        event.event_type,
                        event.course_id,
                        event.subject_type,
                        event.subject_id,
                        event.external_ref,
                        event.outcome,
                        event.duration_seconds,
                        self._dump(event.evidence_reference.model_dump()),
                        event.data_quality,
                        event.consent_scope,
                        event.source_version,
                        event.dedupe_key,
                        self._dump(dict(event.payload or {})) if event.payload else None,
                        now,
                    ),
                )
        except sqlite3.IntegrityError:
            existing = self.get_by_dedupe(user_id=user_id, dedupe_key=event.dedupe_key)
            if existing is None:
                raise
            if self._identity_of(existing) != self._identity(event):
                raise LearnerEventConflict("同一幂等键对应不同事件身份")
            return LearnerEventAppendResult(event_id=existing.event_id, created=False)
        return LearnerEventAppendResult(event_id=event_id, created=True)

    def get_by_dedupe(self, *, user_id: str, dedupe_key: str) -> Optional[LearnerEventRow]:
        with self._db.query() as conn:
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM learner_events WHERE user_id=? AND dedupe_key=?",
                (user_id, dedupe_key),
            ).fetchone()
        return LearnerEventRow.from_row(row) if row else None

    def get_event(self, *, user_id: str, event_id: str) -> Optional[LearnerEventRow]:
        with self._db.query() as conn:
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM learner_events WHERE user_id=? AND event_id=?",
                (user_id, event_id),
            ).fetchone()
        return LearnerEventRow.from_row(row) if row else None

    def list_for_user(
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
    ) -> tuple[list[LearnerEventRow], int]:
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must stay within 1..100")
        if since is not None and until is not None and since > until:
            raise ValueError("since must not exceed until")
        conditions = ["user_id=?"]
        params: list = [user_id]
        if source is not None:
            conditions.append("source=?")
            params.append(source)
        if event_type is not None:
            conditions.append("event_type=?")
            params.append(event_type)
        if course_id is not None:
            conditions.append("course_id=?")
            params.append(course_id)
        if since is not None:
            conditions.append("occurred_at>=?")
            params.append(since.astimezone(timezone.utc).isoformat())
        if until is not None:
            conditions.append("occurred_at<=?")
            params.append(until.astimezone(timezone.utc).isoformat())
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            total = int(
                conn.execute(
                    f"SELECT COUNT(*) AS n FROM learner_events{where}", params
                ).fetchone()["n"]
            )
            rows = conn.execute(
                f"SELECT {_COLUMNS} FROM learner_events{where} "
                "ORDER BY occurred_at DESC, created_at DESC, event_id DESC "
                "LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()
        return [LearnerEventRow.from_row(row) for row in rows], total

    def delete_for_user(self, *, user_id: str) -> int:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM learner_events WHERE user_id=?", (user_id,)
            )
            return int(cursor.rowcount or 0)


__all__ = ["LearnerEventConflict", "LearnerEventRepository"]
