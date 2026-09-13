"""期末复习仓储。

封装 final_review_campaigns / plan_versions / daily_agendas / daily_items /
adjustment_proposals 的 CRUD。初始化时幂等执行 migration。

Plan versions 不可变:本仓储不提供 update_plan_version 方法。
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database.sqlite_db import Database
from ..models.final_review import (
    FinalReviewAdjustmentProposalRow,
    FinalReviewCampaignRow,
    FinalReviewDailyAgendaRow,
    FinalReviewDailyItemRow,
    FinalReviewPlanVersionRow,
)
from .final_review_migration import apply_final_review_migration


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


class FinalReviewRepository:
    """期末复习数据访问。"""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = self._db._connect()
        try:
            apply_final_review_migration(conn)
            conn.commit()
        finally:
            self._db._release(conn)

    def _conn(self) -> sqlite3.Connection:
        return self._db._connect()

    def _release(self, conn: sqlite3.Connection) -> None:
        self._db._release(conn)

    # ===== Campaign =====

    def create_campaign(
        self,
        *,
        user_id: str,
        exam_ids: list[str],
        daily_capacity_minutes: int,
        preferred_periods: Optional[list[str]] = None,
        rest_days: Optional[list[str]] = None,
        intensity: str = "medium",
        idempotency_key: Optional[str] = None,
    ) -> FinalReviewCampaignRow:
        campaign_id = _uuid("frc")
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO final_review_campaigns "
                "(campaign_id, user_id, exam_ids_json, daily_capacity_minutes, "
                "preferred_periods_json, rest_days_json, intensity, status, "
                "idempotency_key, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)",
                (
                    campaign_id,
                    user_id,
                    json.dumps(exam_ids),
                    daily_capacity_minutes,
                    json.dumps(preferred_periods or []),
                    json.dumps(rest_days or []),
                    intensity,
                    idempotency_key,
                    now,
                    now,
                ),
            )
            conn.commit()
            return self._campaign_row(conn, campaign_id)
        finally:
            self._release(conn)

    def find_campaign_by_idempotency(
        self, user_id: str, idempotency_key: str
    ) -> Optional[FinalReviewCampaignRow]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM final_review_campaigns "
                "WHERE user_id = ? AND idempotency_key = ?",
                (user_id, idempotency_key),
            ).fetchone()
            return self._campaign_row_from_dict(row) if row else None
        finally:
            self._release(conn)

    def get_campaign(
        self, campaign_id: str, *, user_id: str
    ) -> Optional[FinalReviewCampaignRow]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM final_review_campaigns "
                "WHERE campaign_id = ? AND user_id = ?",
                (campaign_id, user_id),
            ).fetchone()
            return self._campaign_row_from_dict(row) if row else None
        finally:
            self._release(conn)

    def list_campaigns(
        self, user_id: str, *, limit: int = 50
    ) -> list[FinalReviewCampaignRow]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM final_review_campaigns WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [self._campaign_row_from_dict(r) for r in rows]
        finally:
            self._release(conn)

    def activate_campaign(
        self, campaign_id: str, *, user_id: str, version: int
    ) -> Optional[FinalReviewCampaignRow]:
        now = _now()
        conn = self._conn()
        try:
            cur = conn.execute(
                "UPDATE final_review_campaigns "
                "SET status = 'active', active_version = ?, updated_at = ? "
                "WHERE campaign_id = ? AND user_id = ?",
                (version, now, campaign_id, user_id),
            )
            if cur.rowcount == 0:
                return None
            conn.commit()
            return self._campaign_row(conn, campaign_id)
        finally:
            self._release(conn)

    def archive_campaign(
        self, campaign_id: str, *, user_id: str
    ) -> None:
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE final_review_campaigns SET status = 'archived', updated_at = ? "
                "WHERE campaign_id = ? AND user_id = ?",
                (now, campaign_id, user_id),
            )
            conn.commit()
        finally:
            self._release(conn)

    def _campaign_row(self, conn, campaign_id: str) -> FinalReviewCampaignRow:
        row = conn.execute(
            "SELECT * FROM final_review_campaigns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        return self._campaign_row_from_dict(row)

    def _campaign_row_from_dict(self, row) -> FinalReviewCampaignRow:
        return FinalReviewCampaignRow(
            campaign_id=row["campaign_id"],
            user_id=row["user_id"],
            exam_ids_json=row["exam_ids_json"],
            daily_capacity_minutes=row["daily_capacity_minutes"],
            preferred_periods_json=row["preferred_periods_json"],
            rest_days_json=row["rest_days_json"],
            intensity=row["intensity"],
            status=row["status"],
            active_version=row["active_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            idempotency_key=row["idempotency_key"],
        )

    # ===== Plan version(不可变) =====

    def create_plan_version(
        self,
        *,
        campaign_id: str,
        version: int,
        user_id: str,
        plan: dict,
        source_snapshot_id: Optional[str] = None,
        model_provider: str = "fake",
        route_policy: str = "reasoning_primary",
        risk_level: str = "CONFIRM_REQUIRED",
        approval_id: Optional[str] = None,
        supersedes_version: Optional[int] = None,
    ) -> FinalReviewPlanVersionRow:
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO final_review_plan_versions "
                "(campaign_id, version, user_id, plan_json, source_snapshot_id, "
                "model_provider, route_policy, risk_level, approval_id, "
                "supersedes_version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    campaign_id,
                    version,
                    user_id,
                    json.dumps(plan, ensure_ascii=False),
                    source_snapshot_id,
                    model_provider,
                    route_policy,
                    risk_level,
                    approval_id,
                    supersedes_version,
                    now,
                ),
            )
            conn.commit()
            return self._plan_version_row(conn, campaign_id, version)
        finally:
            self._release(conn)

    def get_plan_version(
        self, campaign_id: str, version: int, *, user_id: str
    ) -> Optional[FinalReviewPlanVersionRow]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM final_review_plan_versions "
                "WHERE campaign_id = ? AND version = ? AND user_id = ?",
                (campaign_id, version, user_id),
            ).fetchone()
            return self._plan_version_row_from_dict(row) if row else None
        finally:
            self._release(conn)

    def list_plan_versions(
        self, campaign_id: str, *, user_id: str
    ) -> list[FinalReviewPlanVersionRow]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM final_review_plan_versions "
                "WHERE campaign_id = ? AND user_id = ? ORDER BY version ASC",
                (campaign_id, user_id),
            ).fetchall()
            return [self._plan_version_row_from_dict(r) for r in rows]
        finally:
            self._release(conn)

    def next_plan_version(self, campaign_id: str) -> int:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS max_v "
                "FROM final_review_plan_versions WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            return int(row["max_v"]) + 1
        finally:
            self._release(conn)

    def _plan_version_row(self, conn, campaign_id: str, version: int) -> FinalReviewPlanVersionRow:
        row = conn.execute(
            "SELECT * FROM final_review_plan_versions "
            "WHERE campaign_id = ? AND version = ?",
            (campaign_id, version),
        ).fetchone()
        return self._plan_version_row_from_dict(row)

    def _plan_version_row_from_dict(self, row) -> FinalReviewPlanVersionRow:
        return FinalReviewPlanVersionRow(
            campaign_id=row["campaign_id"],
            version=row["version"],
            user_id=row["user_id"],
            plan_json=row["plan_json"],
            source_snapshot_id=row["source_snapshot_id"],
            model_provider=row["model_provider"],
            route_policy=row["route_policy"],
            risk_level=row["risk_level"],
            approval_id=row["approval_id"],
            supersedes_version=row["supersedes_version"],
            created_at=row["created_at"],
        )

    # ===== Daily agenda =====

    def create_agenda(
        self,
        *,
        campaign_id: str,
        plan_version: int,
        user_id: str,
        agenda_date: str,
        total_minutes: int = 0,
    ) -> FinalReviewDailyAgendaRow:
        agenda_id = _uuid("fra")
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO final_review_daily_agendas "
                "(agenda_id, campaign_id, plan_version, user_id, agenda_date, "
                "total_minutes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (agenda_id, campaign_id, plan_version, user_id, agenda_date, total_minutes, now),
            )
            conn.commit()
            return FinalReviewDailyAgendaRow(
                agenda_id=agenda_id,
                campaign_id=campaign_id,
                plan_version=plan_version,
                user_id=user_id,
                agenda_date=agenda_date,
                total_minutes=total_minutes,
                created_at=now,
            )
        finally:
            self._release(conn)

    def get_agenda_by_date(
        self, campaign_id: str, plan_version: int, agenda_date: str, *, user_id: str
    ) -> Optional[FinalReviewDailyAgendaRow]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM final_review_daily_agendas "
                "WHERE campaign_id = ? AND plan_version = ? AND agenda_date = ? "
                "AND user_id = ?",
                (campaign_id, plan_version, agenda_date, user_id),
            ).fetchone()
            if not row:
                return None
            return FinalReviewDailyAgendaRow(
                agenda_id=row["agenda_id"],
                campaign_id=row["campaign_id"],
                plan_version=row["plan_version"],
                user_id=row["user_id"],
                agenda_date=row["agenda_date"],
                total_minutes=row["total_minutes"],
                created_at=row["created_at"],
            )
        finally:
            self._release(conn)

    def get_agenda(
        self, agenda_id: str, *, user_id: str
    ) -> Optional[FinalReviewDailyAgendaRow]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM final_review_daily_agendas "
                "WHERE agenda_id = ? AND user_id = ?",
                (agenda_id, user_id),
            ).fetchone()
            if not row:
                return None
            return FinalReviewDailyAgendaRow(
                agenda_id=row["agenda_id"],
                campaign_id=row["campaign_id"],
                plan_version=row["plan_version"],
                user_id=row["user_id"],
                agenda_date=row["agenda_date"],
                total_minutes=row["total_minutes"],
                created_at=row["created_at"],
            )
        finally:
            self._release(conn)

    # ===== Daily items =====

    def create_item(
        self,
        *,
        agenda_id: str,
        campaign_id: str,
        user_id: str,
        title: str,
        course_name: Optional[str] = None,
        scheduled_minutes: int = 0,
        sort_order: int = 0,
        personal_task_id: Optional[str] = None,
    ) -> FinalReviewDailyItemRow:
        item_id = _uuid("fri")
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO final_review_daily_items "
                "(item_id, agenda_id, campaign_id, user_id, title, course_name, "
                "scheduled_minutes, sort_order, status, personal_task_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
                (item_id, agenda_id, campaign_id, user_id, title, course_name,
                 scheduled_minutes, sort_order, personal_task_id),
            )
            conn.commit()
            return self._item_row(conn, item_id)
        finally:
            self._release(conn)

    def list_items(
        self, agenda_id: str, *, user_id: str
    ) -> list[FinalReviewDailyItemRow]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM final_review_daily_items "
                "WHERE agenda_id = ? AND user_id = ? ORDER BY sort_order ASC",
                (agenda_id, user_id),
            ).fetchall()
            return [self._item_row_from_dict(r) for r in rows]
        finally:
            self._release(conn)

    def get_item(
        self, item_id: str, *, user_id: str
    ) -> Optional[FinalReviewDailyItemRow]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM final_review_daily_items "
                "WHERE item_id = ? AND user_id = ?",
                (item_id, user_id),
            ).fetchone()
            return self._item_row_from_dict(row) if row else None
        finally:
            self._release(conn)

    def complete_item(
        self,
        item_id: str,
        *,
        user_id: str,
        difficulty: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> Optional[FinalReviewDailyItemRow]:
        now = _now()
        conn = self._conn()
        try:
            cur = conn.execute(
                "UPDATE final_review_daily_items "
                "SET status = 'completed', completed_at = ?, difficulty = ?, feedback = ? "
                "WHERE item_id = ? AND user_id = ? AND status = 'pending'",
                (now, difficulty, feedback, item_id, user_id),
            )
            if cur.rowcount == 0:
                return None
            conn.commit()
            return self._item_row(conn, item_id)
        finally:
            self._release(conn)

    # ===== Check-in evidence =====

    def upsert_checkin_evidence(
        self,
        *,
        campaign_id: str,
        plan_version: Optional[int],
        user_id: str,
        report_date: str,
        completed_item_ids: list[str],
        insufficient_time: bool,
        difficulty_notes: Optional[str],
    ) -> None:
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO final_review_checkin_evidence "
                "(checkin_id, campaign_id, plan_version, user_id, report_date, "
                "completed_item_ids_json, insufficient_time, difficulty_notes, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(campaign_id, user_id, report_date) DO UPDATE SET "
                "plan_version = excluded.plan_version, "
                "completed_item_ids_json = excluded.completed_item_ids_json, "
                "insufficient_time = excluded.insufficient_time, "
                "difficulty_notes = excluded.difficulty_notes, updated_at = excluded.updated_at",
                (
                    _uuid("frce"), campaign_id, plan_version, user_id, report_date,
                    json.dumps(completed_item_ids, ensure_ascii=False), int(insufficient_time),
                    difficulty_notes, now, now,
                ),
            )
            conn.commit()
        finally:
            self._release(conn)

    def list_checkin_evidence(
        self, campaign_id: str, *, user_id: str, limit: int = 7
    ) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT report_date, plan_version, completed_item_ids_json, insufficient_time, "
                "difficulty_notes FROM final_review_checkin_evidence "
                "WHERE campaign_id = ? AND user_id = ? ORDER BY report_date DESC LIMIT ?",
                (campaign_id, user_id, limit),
            ).fetchall()
            return [
                {
                    "report_date": row["report_date"],
                    "plan_version": row["plan_version"],
                    "completed_item_ids": json.loads(row["completed_item_ids_json"]),
                    "insufficient_time": bool(row["insufficient_time"]),
                    "difficulty_notes": row["difficulty_notes"],
                }
                for row in rows
            ]
        finally:
            self._release(conn)

    def _item_row(self, conn, item_id: str) -> FinalReviewDailyItemRow:
        row = conn.execute(
            "SELECT * FROM final_review_daily_items WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        return self._item_row_from_dict(row)

    def _item_row_from_dict(self, row) -> FinalReviewDailyItemRow:
        return FinalReviewDailyItemRow(
            item_id=row["item_id"],
            agenda_id=row["agenda_id"],
            campaign_id=row["campaign_id"],
            user_id=row["user_id"],
            title=row["title"],
            course_name=row["course_name"],
            scheduled_minutes=row["scheduled_minutes"],
            sort_order=row["sort_order"],
            status=row["status"],
            personal_task_id=row["personal_task_id"],
            completed_at=row["completed_at"],
            difficulty=row["difficulty"],
            feedback=row["feedback"],
        )

    # ===== Adjustment proposal =====

    def create_proposal(
        self,
        *,
        campaign_id: str,
        user_id: str,
        source_version: int,
        proposal: dict,
        risk_level: str,
        model_provider: Optional[str] = None,
        route_policy: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> FinalReviewAdjustmentProposalRow:
        proposal_id = _uuid("frap")
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO final_review_adjustment_proposals "
                "(proposal_id, campaign_id, user_id, source_version, proposal_json, "
                "risk_level, status, model_provider, route_policy, reason, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)",
                (
                    proposal_id,
                    campaign_id,
                    user_id,
                    source_version,
                    json.dumps(proposal, ensure_ascii=False),
                    risk_level,
                    model_provider,
                    route_policy,
                    reason,
                    now,
                ),
            )
            conn.commit()
            return self._proposal_row(conn, proposal_id)
        finally:
            self._release(conn)

    def get_proposal(
        self, proposal_id: str, *, user_id: str
    ) -> Optional[FinalReviewAdjustmentProposalRow]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM final_review_adjustment_proposals "
                "WHERE proposal_id = ? AND user_id = ?",
                (proposal_id, user_id),
            ).fetchone()
            return self._proposal_row_from_dict(row) if row else None
        finally:
            self._release(conn)

    def list_proposals(
        self, campaign_id: str, *, user_id: str
    ) -> list[FinalReviewAdjustmentProposalRow]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM final_review_adjustment_proposals "
                "WHERE campaign_id = ? AND user_id = ? ORDER BY created_at DESC",
                (campaign_id, user_id),
            ).fetchall()
            return [self._proposal_row_from_dict(r) for r in rows]
        finally:
            self._release(conn)

    def resolve_proposal(
        self,
        proposal_id: str,
        *,
        user_id: str,
        status: str,
        approval_id: Optional[str] = None,
        target_version: Optional[int] = None,
    ) -> Optional[FinalReviewAdjustmentProposalRow]:
        now = _now()
        conn = self._conn()
        try:
            cur = conn.execute(
                "UPDATE final_review_adjustment_proposals "
                "SET status = ?, approval_id = ?, target_version = ?, resolved_at = ? "
                "WHERE proposal_id = ? AND user_id = ? AND status = 'pending'",
                (status, approval_id, target_version, now, proposal_id, user_id),
            )
            if cur.rowcount == 0:
                return None
            conn.commit()
            return self._proposal_row(conn, proposal_id)
        finally:
            self._release(conn)

    def attach_approval(
        self,
        proposal_id: str,
        *,
        user_id: str,
        approval_id: str,
    ) -> None:
        """仅附加 approval_id,不改变 status(仍为 pending)。"""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE final_review_adjustment_proposals "
                "SET approval_id = ? WHERE proposal_id = ? AND user_id = ?",
                (approval_id, proposal_id, user_id),
            )
            conn.commit()
        finally:
            self._release(conn)

    def _proposal_row(self, conn, proposal_id: str) -> FinalReviewAdjustmentProposalRow:
        row = conn.execute(
            "SELECT * FROM final_review_adjustment_proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        return self._proposal_row_from_dict(row)

    def _proposal_row_from_dict(self, row) -> FinalReviewAdjustmentProposalRow:
        return FinalReviewAdjustmentProposalRow(
            proposal_id=row["proposal_id"],
            campaign_id=row["campaign_id"],
            user_id=row["user_id"],
            source_version=row["source_version"],
            proposal_json=row["proposal_json"],
            risk_level=row["risk_level"],
            status=row["status"],
            approval_id=row["approval_id"],
            target_version=row["target_version"],
            model_provider=row["model_provider"],
            route_policy=row["route_policy"],
            reason=row["reason"],
            created_at=row["created_at"],
            resolved_at=row["resolved_at"],
        )


__all__ = ["FinalReviewRepository"]
