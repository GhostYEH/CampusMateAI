from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class StudentGoalRow:
    goal_id: str
    user_id: str
    category: str
    status: str
    target_date: Optional[str]
    archived_at: Optional[str]
    progress_percent: float
    milestone_count: int
    created_at: str
    updated_at: str
    idempotency_key: Optional[str]

    @classmethod
    def from_row(cls, row) -> "StudentGoalRow":
        return cls(
            goal_id=row["goal_id"],
            user_id=row["user_id"],
            category=row["category"],
            status=row["status"],
            target_date=row["target_date"],
            archived_at=row["archived_at"],
            progress_percent=float(row["progress_percent"]),
            milestone_count=int(row["milestone_count"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            idempotency_key=row["idempotency_key"],
        )


@dataclass(frozen=True)
class StudentGoalProgressRow:
    progress_id: str
    goal_id: str
    user_id: str
    progress_percent: float
    milestone_reached: Optional[str]
    occurred_at: str
    idempotency_key: Optional[str]
    created_at: str

    @classmethod
    def from_row(cls, row) -> "StudentGoalProgressRow":
        return cls(
            progress_id=row["progress_id"],
            goal_id=row["goal_id"],
            user_id=row["user_id"],
            progress_percent=float(row["progress_percent"]),
            milestone_reached=row["milestone_reached"],
            occurred_at=row["occurred_at"],
            idempotency_key=row["idempotency_key"],
            created_at=row["created_at"],
        )