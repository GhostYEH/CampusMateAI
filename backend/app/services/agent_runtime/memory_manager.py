"""MemoryManager —— 显式记忆管理(§5.2)。

只允许 CONFIRMED_PREFERENCE / CONFIRMED_STUDY_GOAL / CONFIRMED_CONSTRAINT / USER_APPROVED_SUMMARY。
不存储完整对话、完整作业答案、原始通知内容、心理推断或摄像头数据。
用户可查看、撤销、清除记忆。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ...repositories.agent_runtime_repository import AgentRuntimeRepository


ALLOWED_KINDS = {
    "CONFIRMED_PREFERENCE",
    "CONFIRMED_STUDY_GOAL",
    "CONFIRMED_CONSTRAINT",
    "USER_APPROVED_SUMMARY",
}


class MemoryManager:
    """显式记忆管理器。"""

    def __init__(self, repository: AgentRuntimeRepository) -> None:
        self._repo = repository

    def record(
        self,
        *,
        user_id: str,
        kind: str,
        content_summary: str,
        sensitivity: str = "low",
        confirmed: bool = False,
        model_may_consume: bool = False,
        provenance: Optional[str] = None,
        valid_until: Optional[str] = None,
    ) -> str:
        """记录一条记忆。kind 必须在允许列表内。"""
        if kind not in ALLOWED_KINDS:
            raise ValueError(f"不允许的记忆类型: {kind}")
        if len(content_summary) > 512:
            raise ValueError("content_summary 过长(>512)")
        return self._repo.save_memory(
            user_id=user_id,
            kind=kind,
            content_summary=content_summary,
            sensitivity=sensitivity,
            confirmed=confirmed,
            model_may_consume=model_may_consume and confirmed,
            provenance=provenance,
            valid_until=valid_until,
        )

    def withdraw(self, *, user_id: str, memory_id: str) -> dict | None:
        """撤销记忆。撤销后 model_may_consume=False。"""
        if not self._repo.withdraw_memory(memory_id, user_id):
            return None
        return self._repo.get_memory(memory_id, user_id)

    def list_for_user(self, user_id: str) -> list[dict]:
        """列出用户所有记忆。"""
        return self._repo.list_memories(user_id)

    def consumable_for_model(self, user_id: str) -> list[dict]:
        """返回模型可消费的记忆(已确认 + 未撤销 + model_may_consume)。"""
        now = datetime.now(timezone.utc)
        result = []
        for memory in self._repo.list_memories(user_id):
            if memory["model_may_consume"] != 1 or memory["withdrawn"] != 0 or memory["confirmed"] != 1:
                continue
            valid_until = memory.get("valid_until")
            if valid_until:
                try:
                    expires = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
                    if expires.tzinfo is not None and expires <= now:
                        continue
                except ValueError:
                    # Invalid expiry is treated conservatively: do not expose it to the model.
                    continue
            result.append(memory)
        return result


__all__ = ["MemoryManager", "ALLOWED_KINDS"]
