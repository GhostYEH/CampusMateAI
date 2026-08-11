from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StudyGoalRow:
    user_id: str
    target_minutes: int
    updated_at: str

    @classmethod
    def from_row(cls, row) -> "StudyGoalRow":
        return cls(
            user_id=row["user_id"],
            target_minutes=int(row["target_minutes"]),
            updated_at=row["updated_at"],
        )
