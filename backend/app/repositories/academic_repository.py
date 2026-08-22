from __future__ import annotations

from typing import Optional
from ..database.sqlite_db import Database


class AcademicRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_for_user(self, user_id: str) -> Optional[dict]:
        with self.db.query() as conn:
            row = conn.execute("SELECT * FROM academic_bindings WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None

    def delete_for_user(self, user_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM academic_bindings WHERE user_id=?", (user_id,))

