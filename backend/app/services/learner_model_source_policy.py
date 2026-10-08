"""Phase 6.1-4: 学习模型数据源策略。

统一、轻量的数据源控制策略，避免路由直接查询数据库，也避免 service 间循环依赖。

语义：
- 暂停数据源只停止该来源进入"学生世界模型派生链路"。
- 不得阻止学习会话完成、任务完成、Chaoxing 同步和教务同步等核心业务正常保存。
- 事件/状态投影失败或被暂停，不得回滚核心业务。
- 被暂停后，不再为该来源创建新的 learner event、shadow run 或主动建议输入。
- 已有历史证据保留，状态显示 PARTIAL/STALE 和固定 warning。
- 恢复后只允许新数据进入。
- MODEL_SHADOW 暂停后不能创建真实或固定 fixture 的 shadow run。
- PROACTIVE_SUGGESTIONS 暂停后不能自动生成建议。
"""

from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone


def filter_paused_inputs(inputs: dict, cutoffs: dict[str, str]) -> dict:
    """Retain only verifiably pre-pause facts; never mutate business records."""
    result = dict(inputs)
    source_keys = {
        "chaoxing": "CHAOXING",
        "edu": "EDU",
        "academic": "EDU",
        "core_study": "CORE_STUDY",
        "study": "CORE_STUDY",
        "study_session": "CORE_STUDY",
        "personal_task": "PERSONAL_TASK",
        "manual": "PERSONAL_TASK",
        "personal": "PERSONAL_TASK",
    }

    def before(row, source, fields):
        cutoff = cutoffs.get(source)
        if not cutoff:
            return True

        def parse(value):
            try:
                parsed = (
                    value
                    if isinstance(value, datetime)
                    else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                )
                return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
            except (ValueError, TypeError):
                return None

        boundary = parse(cutoff)
        times = [parse(row.get(field)) for field in fields if row.get(field)]
        return bool(
            boundary and times and all(t is not None and t <= boundary for t in times)
        )

    specs = {
        "tasks": ("PERSONAL_TASK", ("created_at", "updated_at", "completed_at")),
        "sessions": ("CORE_STUDY", ("started_at", "paused_at", "ended_at")),
        "schedule_items": ("EDU", ("last_seen_at", "last_synced_at")),
        "exam_items": ("EDU", ("last_seen_at", "last_synced_at")),
        "grade_items": ("EDU", ("last_seen_at", "last_synced_at")),
        "chaoxing_exam_items": ("CHAOXING", ("last_synced_at", "updated_at")),
        "chaoxing_grade_items": ("CHAOXING", ("last_synced_at", "updated_at")),
    }
    for key, (default_source, fields) in specs.items():
        result[key] = [
            row
            for row in inputs.get(key, [])
            if before(row, source_keys.get(row.get("source"), default_source), fields)
        ]
    result["events"] = [
        row
        for row in inputs.get("events", [])
        if before(
            row, source_keys.get(row.get("source"), ""), ("occurred_at", "recorded_at")
        )
    ]
    return result


class LearnerModelSourcePolicy:
    """学习模型数据源策略。"""

    def __init__(self, control_repository) -> None:
        self._repo = control_repository

    def is_source_paused(self, *, user_id: str, source_key: str) -> bool:
        """检查指定数据源是否被暂停。"""
        return self._repo.is_source_paused(user_id=user_id, source_key=source_key)

    def should_skip_learner_event(self, *, user_id: str, source: str) -> bool:
        """检查是否应跳过为该来源创建新的 learner event。

        核心业务事件（study session finish, task complete）
        不受数据源控制影响，始终保存。只有派生 learner event 才检查。
        """
        source_map = {
            "chaoxing": "CHAOXING",
            "edu": "EDU",
            "core_study": "CORE_STUDY",
            "personal_task": "PERSONAL_TASK",
        }
        mapped = source_map.get(source, source.upper())
        if mapped not in source_map.values():
            return False
        return self.is_source_paused(user_id=user_id, source_key=mapped)

    def should_skip_shadow_run(self, *, user_id: str) -> bool:
        """检查是否应跳过创建新的 shadow run。"""
        return self.is_source_paused(user_id=user_id, source_key="MODEL_SHADOW")

    def should_skip_proactive_suggestions(self, *, user_id: str) -> bool:
        """检查是否应跳过自动生成建议。"""
        return self.is_source_paused(
            user_id=user_id, source_key="PROACTIVE_SUGGESTIONS"
        )

    def get_paused_sources(self, *, user_id: str) -> set[str]:
        """返回当前用户所有被暂停的数据源。"""
        controls = self._repo.list_source_controls(user_id=user_id)
        return {
            c.source_key
            for c in controls
            if c.status in ("PAUSED", "DISCONNECTED", "DELETE_REQUESTED")
        }

    def get_paused_source_cutoffs(self, *, user_id: str) -> dict[str, str]:
        return {
            row.source_key: row.updated_at.isoformat()
            for row in self._repo.list_source_controls(user_id=user_id)
            if row.status in ("PAUSED", "DISCONNECTED", "DELETE_REQUESTED")
        }

    def get_projection_warning(self, *, user_id: str) -> Optional[str]:
        """如果有数据源被暂停，返回固定 warning code。"""
        paused = self.get_paused_sources(user_id=user_id)
        if paused:
            return "learner_data_source_paused"
        return None


__all__ = ["LearnerModelSourcePolicy"]
