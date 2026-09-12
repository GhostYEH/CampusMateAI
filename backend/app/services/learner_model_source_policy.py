"""Phase 6.1-4: 学习模型数据源策略。

统一、轻量的数据源控制策略，避免路由直接查询数据库，也避免 service 间循环依赖。

语义：
- 暂停数据源只停止该来源进入"学生世界模型派生链路"。
- 不得阻止学习会话完成、任务完成、Chaoxing 同步、教务同步、练习作答等核心业务正常保存。
- 事件/状态投影失败或被暂停，不得回滚核心业务。
- 被暂停后，不再为该来源创建新的 learner event、shadow run 或主动建议输入。
- 已有历史证据保留，状态显示 PARTIAL/STALE 和固定 warning。
- 恢复后只允许新数据进入。
- MODEL_SHADOW 暂停后不能创建真实或固定 fixture 的 shadow run。
- PROACTIVE_SUGGESTIONS 暂停后不能自动生成建议。
"""
from __future__ import annotations

from typing import Optional


class LearnerModelSourcePolicy:
    """学习模型数据源策略。"""

    def __init__(self, control_repository) -> None:
        self._repo = control_repository

    def is_source_paused(self, *, user_id: str, source_key: str) -> bool:
        """检查指定数据源是否被暂停。"""
        return self._repo.is_source_paused(user_id=user_id, source_key=source_key)

    def should_skip_learner_event(self, *, user_id: str, source: str) -> bool:
        """检查是否应跳过为该来源创建新的 learner event。

        核心业务事件（study session finish, task complete, practice attempt）
        不受数据源控制影响，始终保存。只有派生 learner event 才检查。
        """
        source_map = {
            "chaoxing": "CHAOXING",
            "edu": "EDU",
            "practice": "PRACTICE",
            "code_analysis": "PRACTICE",
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
        return self.is_source_paused(user_id=user_id, source_key="PROACTIVE_SUGGESTIONS")

    def get_paused_sources(self, *, user_id: str) -> set[str]:
        """返回当前用户所有被暂停的数据源。"""
        controls = self._repo.list_source_controls(user_id=user_id)
        return {
            c.source_key for c in controls
            if c.status in ("PAUSED", "DISCONNECTED", "DELETE_REQUESTED")
        }

    def get_projection_warning(self, *, user_id: str) -> Optional[str]:
        """如果有数据源被暂停，返回固定 warning code。"""
        paused = self.get_paused_sources(user_id=user_id)
        if paused:
            return "learner_data_source_paused"
        return None


__all__ = ["LearnerModelSourcePolicy"]