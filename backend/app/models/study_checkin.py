from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StudyCheckinRow:
    id: str
    user_id: str
    date: str
    scene: str
    mood: str | None
    created_at: str

    @classmethod
    def from_row(cls, row) -> "StudyCheckinRow":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            date=row["date_key"],
            scene=row["scene"],
            mood=row["mood"],
            created_at=row["created_at"],
        )
