"""Agent artifact 仓储 —— 原子写入 + 所有权校验。

JSON / Markdown 写入受控目录,使用临时文件 + rename 保证原子性。
每次读取/下载重新校验所有权。
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..database.sqlite_db import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class AgentArtifactRepository:
    """agent_artifacts 仓储 + 原子文件写入。"""

    def __init__(self, db: Database, storage_dir: Path) -> None:
        self._db = db
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def _conn(self) -> sqlite3.Connection:
        return self._db._connect()

    def _release(self, conn: sqlite3.Connection) -> None:
        self._db._release(conn)

    def _storage_path(self, artifact_id: str) -> Path:
        return self._storage_dir / f"{artifact_id}.json"

    def create_artifact(
        self,
        *,
        run_id: str,
        user_id: str,
        artifact_type: str,
        content: dict | str,
        mime_type: str = "application/json",
        version: int = 1,
    ) -> str:
        """原子写入 artifact 并记录元数据。返回 artifact_id。"""
        artifact_id = _uuid("art")
        if isinstance(content, (dict, list)):
            text = json.dumps(content, ensure_ascii=False, indent=2)
            mime_type = mime_type or "application/json"
        else:
            text = str(content)
        content_hash = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
        size_bytes = len(text.encode("utf-8"))
        path = self._storage_path(artifact_id)
        # 原子写入:先写临时文件再 rename
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(self._storage_dir), suffix=".tmp", prefix=f"{artifact_id}_"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO agent_artifacts (artifact_id, run_id, user_id, artifact_type, "
                "version, mime_type, size_bytes, content_hash, storage_path, download_url, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    artifact_id,
                    run_id,
                    user_id,
                    artifact_type,
                    version,
                    mime_type,
                    size_bytes,
                    content_hash,
                    str(path),
                    f"/api/v1/agent-artifacts/{artifact_id}",
                    now,
                ),
            )
            conn.commit()
            return artifact_id
        finally:
            self._release(conn)

    def get_artifact(self, artifact_id: str, user_id: str) -> Optional[dict]:
        """读取 artifact 元数据。重新校验所有权。"""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT artifact_id, run_id, user_id, artifact_type, version, mime_type, "
                "size_bytes, content_hash, download_url, created_at, deleted_at "
                "FROM agent_artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
            if not row:
                return None
            data = dict(row)
            if data["user_id"] != user_id:
                return None
            if data["deleted_at"]:
                return None
            return data
        finally:
            self._release(conn)

    def read_content(self, artifact_id: str, user_id: str) -> Optional[str]:
        """读取 artifact 文本内容。重新校验所有权。"""
        meta = self.get_artifact(artifact_id, user_id)
        if not meta:
            return None
        path = self._storage_path(artifact_id)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def list_artifacts_by_run(self, run_id: str, user_id: str) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT artifact_id, run_id, user_id, artifact_type, version, mime_type, "
                "size_bytes, content_hash, download_url, created_at "
                "FROM agent_artifacts WHERE run_id = ? AND user_id = ? AND deleted_at IS NULL "
                "ORDER BY created_at DESC",
                (run_id, user_id),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._release(conn)

    def soft_delete(self, artifact_id: str, user_id: str) -> bool:
        now = _now()
        conn = self._conn()
        try:
            cur = conn.execute(
                "UPDATE agent_artifacts SET deleted_at = ? "
                "WHERE artifact_id = ? AND user_id = ? AND deleted_at IS NULL",
                (now, artifact_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            self._release(conn)


__all__ = ["AgentArtifactRepository"]