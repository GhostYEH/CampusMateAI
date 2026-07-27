"""学习陪伴 — 数据行模型(StudySessionRow / StudyBreakRow)。

仅承载从数据库读取的原始字段,不包含业务逻辑。
状态机校验由 StudySessionRepository 与路由层共同完成。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class StudyBreakRow:
    id: str
    session_id: str
    started_at: str
    ended_at: Optional[str]
    reason: Optional[str]
    created_at: str

    @classmethod
    def from_row(cls, row) -> "StudyBreakRow":
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            reason=row["reason"],
            created_at=row["created_at"],
        )

    @property
    def is_open(self) -> bool:
        return self.ended_at is None


@dataclass
class StudySessionRow:
    id: str
    user_id: str
    goal: Optional[str]
    related_task_id: Optional[str]
    started_at: str
    paused_at: Optional[str]
    ended_at: Optional[str]
    duration_seconds: int
    pause_seconds: int
    status: str  # active | paused | completed
    self_report: Optional[str]
    self_report_tags: List[str] = field(default_factory=list)
    expression_signal: Optional[Any] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "StudySessionRow":
        tags_raw = row["self_report_tags"]
        tags: List[str] = []
        if tags_raw:
            try:
                parsed = json.loads(tags_raw)
                if isinstance(parsed, list):
                    tags = [str(t) for t in parsed]
            except (ValueError, TypeError):
                tags = []
        # expression_signal: 尝试解析为 JSON 对象(dict/list),失败则保留原字符串
        signal_raw = row["expression_signal"]
        signal: Optional[object] = None
        if signal_raw:
            try:
                signal = json.loads(signal_raw)
            except (ValueError, TypeError):
                signal = signal_raw  # 保留原始字符串
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            goal=row["goal"],
            related_task_id=row["related_task_id"],
            started_at=row["started_at"],
            paused_at=row["paused_at"],
            ended_at=row["ended_at"],
            duration_seconds=int(row["duration_seconds"] or 0),
            pause_seconds=int(row["pause_seconds"] or 0),
            status=row["status"],
            self_report=row["self_report"],
            self_report_tags=tags,
            expression_signal=signal,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


__all__ = ["StudySessionRow", "StudyBreakRow"]
