"""Daily Agenda 服务(§8.1)。

从 plan version 生成当日议程,并将近期 item 物化为 idempotent personal_tasks。
只物化当前和近期 item,完整计划留在 daily-agenda 行。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from ...repositories.final_review_repository import FinalReviewRepository
from ...repositories.personal_task_repository import PersonalTaskRepository


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


class AgendaService:
    """每日议程生成与物化。"""

    def __init__(
        self,
        *,
        final_review_repo: FinalReviewRepository,
        personal_task_repo: PersonalTaskRepository,
    ) -> None:
        self._repo = final_review_repo
        self._task_repo = personal_task_repo

    def generate_today(
        self,
        *,
        campaign_id: str,
        plan_version: int,
        user_id: str,
    ) -> dict[str, Any]:
        """生成今日议程。若已存在则返回已有议程(幂等)。

        会将今日 item 物化为 personal_tasks(幂等,通过 source_notice_id 去重)。
        """
        plan_row = self._repo.get_plan_version(campaign_id, plan_version, user_id=user_id)
        if not plan_row:
            raise ValueError("plan version 不存在或无权访问")

        plan = json.loads(plan_row.plan_json)
        today = _today()

        # 幂等:已存在则返回
        existing = self._repo.get_agenda_by_date(campaign_id, plan_version, today, user_id=user_id)
        if existing:
            items = self._repo.list_items(existing.agenda_id, user_id=user_id)
            return self._agenda_to_dict(existing, items)

        # 从 plan 中找到今日的 day
        today_day = self._find_day(plan, today)
        items_data = today_day.get("items", []) if today_day else []
        total_minutes = today_day.get("minutes", 0) if today_day else 0

        # 创建 agenda
        agenda = self._repo.create_agenda(
            campaign_id=campaign_id,
            plan_version=plan_version,
            user_id=user_id,
            agenda_date=today,
            total_minutes=total_minutes,
        )

        # 创建 items 并物化 personal_tasks
        created_items = []
        for idx, item_data in enumerate(items_data):
            title = str(item_data.get("title", "复习"))
            course_name = item_data.get("course_name")
            scheduled_minutes = int(item_data.get("minutes", 0))

            # 物化为 personal_task(幂等:source_notice_id = agenda_id + idx)
            task_source_id = f"final_review:{agenda.agenda_id}:{idx}"
            existing_task = self._task_repo.get_task_by_source_notice_id(
                task_source_id, user_id=user_id
            )
            if existing_task:
                personal_task_id = existing_task.id
            else:
                try:
                    task = self._task_repo.create_task(
                        user_id=user_id,
                        title=title,
                        source_name="final_review",
                        source_text=f"期末复习:{title}",
                        source_notice_id=task_source_id,
                        source="final_review",
                        external_id=task_source_id,
                        priority="medium",
                    )
                    personal_task_id = task.id
                except Exception:
                    personal_task_id = None

            item = self._repo.create_item(
                agenda_id=agenda.agenda_id,
                campaign_id=campaign_id,
                user_id=user_id,
                title=title,
                course_name=course_name,
                scheduled_minutes=scheduled_minutes,
                sort_order=idx,
                personal_task_id=personal_task_id,
            )
            created_items.append(item)

        return self._agenda_to_dict(agenda, created_items)

    def complete_item(
        self,
        *,
        item_id: str,
        user_id: str,
        difficulty: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """完成 agenda item。同步标记 personal_task 为 completed。"""
        item = self._repo.get_item(item_id, user_id=user_id)
        if not item:
            return None
        if item.status != "pending":
            return self._item_to_dict(item)

        updated = self._repo.complete_item(
            item_id, user_id=user_id, difficulty=difficulty, feedback=feedback
        )
        if not updated:
            return None

        # 同步 personal_task
        if updated.personal_task_id:
            try:
                self._task_repo.complete(updated.personal_task_id, user_id=user_id)
            except Exception:
                pass

        return self._item_to_dict(updated)

    def record_checkin(
        self,
        *,
        campaign_id: str,
        user_id: str,
        report_date: str,
        completed_item_ids: list[str],
        insufficient_time: bool = False,
        difficulty_notes: Optional[str] = None,
    ) -> int:
        """记录每日签到/晚间反馈。返回 evidence 计数。"""
        evidence_count = 0
        for item_id in completed_item_ids:
            item = self._repo.get_item(item_id, user_id=user_id)
            if item and item.status == "pending":
                self._repo.complete_item(item_id, user_id=user_id)
                evidence_count += 1
        # insufficient_time / difficulty_notes 作为 evidence 存在 proposal 分析中
        if insufficient_time or difficulty_notes:
            evidence_count += 1
        campaign = self._repo.get_campaign(campaign_id, user_id=user_id)
        self._repo.upsert_checkin_evidence(
            campaign_id=campaign_id,
            plan_version=campaign.active_version if campaign else None,
            user_id=user_id,
            report_date=report_date,
            completed_item_ids=completed_item_ids,
            insufficient_time=insufficient_time,
            difficulty_notes=difficulty_notes,
        )
        return evidence_count

    def _find_day(self, plan: dict, target_date: str) -> Optional[dict]:
        """从 plan 中找到指定日期的 day。"""
        days = plan.get("days", [])
        for day in days:
            if day.get("date") == target_date:
                return day
        return None

    def _agenda_to_dict(self, agenda, items) -> dict[str, Any]:
        return {
            "agenda_id": agenda.agenda_id,
            "campaign_id": agenda.campaign_id,
            "plan_version": agenda.plan_version,
            "agenda_date": agenda.agenda_date,
            "total_minutes": agenda.total_minutes,
            "items": [self._item_to_dict(it) for it in items],
        }

    def _item_to_dict(self, item) -> dict[str, Any]:
        return {
            "item_id": item.item_id,
            "title": item.title,
            "course_name": item.course_name,
            "scheduled_minutes": item.scheduled_minutes,
            "sort_order": item.sort_order,
            "status": item.status,
            "personal_task_id": item.personal_task_id,
            "difficulty": item.difficulty,
        }


__all__ = ["AgendaService"]
