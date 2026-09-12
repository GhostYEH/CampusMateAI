"""ContextSnapshot 构建(§5.1、§8.1)。

从服务端数据构建不可变有界上下文快照:
- 当前用户的考试(student_exams)
- 近期个人任务(personal_tasks)
- 每日容量、偏好、休息日(campaign 配置)

复用 container.agent_context_manager(ContextManager)持久化快照。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from ...repositories.final_review_repository import FinalReviewRepository
from ..agent_runtime.context_manager import ContextManager


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


class ContextSnapshotBuilder:
    """构建期末复习上下文快照。"""

    def __init__(
        self,
        *,
        final_review_repo: FinalReviewRepository,
        context_manager: ContextManager,
        db,
    ) -> None:
        self._repo = final_review_repo
        self._ctx_mgr = context_manager
        self._db = db

    def build(
        self,
        *,
        user_id: str,
        campaign_id: str,
        run_id: Optional[str] = None,
    ) -> tuple[str, dict[str, Any]]:
        """构建并持久化快照。返回 (snapshot_id, facts)。"""
        campaign = self._repo.get_campaign(campaign_id, user_id=user_id)
        if not campaign:
            raise ValueError("campaign 不存在或无权访问")

        exam_ids = json.loads(campaign.exam_ids_json)
        preferred_periods = json.loads(campaign.preferred_periods_json)
        rest_days = json.loads(campaign.rest_days_json)

        # 从 student_exams 读取考试详情
        exams = self._load_exams(user_id, exam_ids)
        # 从 personal_tasks 读取近期未完成任务
        pending_tasks = self._load_pending_tasks(user_id)

        facts: dict[str, Any] = {
            "exams": exams,
            "pending_tasks": pending_tasks,
            "daily_capacity_minutes": campaign.daily_capacity_minutes,
            "preferred_periods": preferred_periods,
            "rest_days": rest_days,
            "intensity": campaign.intensity,
        }

        scope = {
            "user_id": user_id,
            "campaign_id": campaign_id,
            "exam_ids": exam_ids,
        }
        source_refs = [f"student_exams:{eid}" for eid in exam_ids]
        source_refs.append(f"personal_tasks:{user_id}")

        snapshot = self._ctx_mgr.build(
            user_id=user_id,
            run_id=run_id,
            scope=scope,
            facts=facts,
            source_refs=source_refs,
        )
        return snapshot.snapshot_id, facts

    def _load_exams(self, user_id: str, exam_ids: list[str]) -> list[dict]:
        """从 student_exams 表读取考试详情。只返回存在的 exam_id。"""
        if not exam_ids:
            return []
        placeholders = ",".join("?" for _ in exam_ids)
        conn = self._db._connect()
        try:
            rows = conn.execute(
                f"SELECT id, course_name, exam_date, start_time, end_time, "
                f"location, exam_type, notes FROM student_exams "
                f"WHERE user_id = ? AND id IN ({placeholders}) "
                f"ORDER BY exam_date ASC",
                [user_id, *exam_ids],
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error:
            return []
        finally:
            self._db._release(conn)

    def _load_pending_tasks(self, user_id: str) -> list[dict]:
        """读取近期未完成的个人任务(最多 20 条)。"""
        conn = self._db._connect()
        try:
            rows = conn.execute(
                "SELECT id, title, deadline, priority, status, course_id "
                "FROM personal_tasks "
                "WHERE user_id = ? AND status = 'pending' AND deleted_at IS NULL "
                "ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline ASC "
                "LIMIT 20",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error:
            return []
        finally:
            self._db._release(conn)


# 延迟导入避免循环依赖
import sqlite3  # noqa: E402

__all__ = ["ContextSnapshotBuilder"]