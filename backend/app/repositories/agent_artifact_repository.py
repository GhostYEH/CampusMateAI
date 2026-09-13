from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ..database.sqlite_db import Database
from ..models.agent_runtime import AgentArtifactRow


def _artifact(row) -> AgentArtifactRow:
    return AgentArtifactRow(**dict(row))


class AgentArtifactRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, *, user_id: str, run_id: str, artifact_type: str, content_ref: str,
               content_hash: str, version: int, mime_type: str, size_bytes: int) -> AgentArtifactRow:
        artifact_id = f"artifact_{uuid4().hex}"
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO agent_artifacts(id,user_id,run_id,artifact_type,content_ref,content_hash,version,mime_type,size_bytes,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (artifact_id, user_id, run_id, artifact_type, content_ref, content_hash, version, mime_type, size_bytes, now),
            )
            return _artifact(conn.execute("SELECT * FROM agent_artifacts WHERE id=?", (artifact_id,)).fetchone())

    def get(self, *, artifact_id: str, user_id: str) -> AgentArtifactRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM agent_artifacts WHERE id=? AND user_id=? AND deleted_at IS NULL",
                (artifact_id, user_id),
            ).fetchone()
        return _artifact(row) if row else None

    def find(self, *, run_id: str, artifact_type: str, version: int) -> AgentArtifactRow | None:
        """按 UNIQUE(run_id, artifact_type, version) 回读，用于恢复时不重复建 Artifact。"""
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM agent_artifacts WHERE run_id=? AND artifact_type=? AND version=? AND deleted_at IS NULL",
                (run_id, artifact_type, version),
            ).fetchone()
        return _artifact(row) if row else None
