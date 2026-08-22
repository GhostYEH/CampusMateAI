from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from ..database.sqlite_db import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


@dataclass
class CourseContentItemRow:
    id: str
    user_id: str
    course_id: str
    provider: str
    external_id: str
    kind: str
    title: str
    parent_external_id: Optional[str] = None
    description: Optional[str] = None
    author_name: Optional[str] = None
    position: int = 0
    depth: int = 0
    status: str = "unknown"
    starts_at: Optional[str] = None
    deadline: Optional[str] = None
    published_at: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    remote_object_id: Optional[str] = None
    source_url: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    is_stale: bool = False
    last_synced_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "CourseContentItemRow":
        data = dict(row)
        raw_metadata = data.pop("metadata_json", None)
        data["metadata"] = json.loads(raw_metadata) if raw_metadata else None
        data["is_stale"] = bool(data["is_stale"])
        return cls(**data)


@dataclass
class CourseSyncSectionRow:
    user_id: str
    course_id: str
    section: str
    status: str
    item_count: int
    last_synced_at: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "CourseSyncSectionRow":
        return cls(**dict(row))


class CourseContentRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def upsert_item(self, *, user_id: str, course_id: str, kind: str,
                    external_id: str, title: str, provider: str = "chaoxing",
                    **fields) -> CourseContentItemRow:
        now = _now()
        allowed = {
            "parent_external_id", "description", "author_name", "position", "depth",
            "status", "starts_at", "deadline", "published_at", "mime_type", "file_size",
            "remote_object_id", "source_url", "last_synced_at", "is_stale",
        }
        values = {key: fields.get(key) for key in allowed}
        values["position"] = values["position"] or 0
        values["depth"] = values["depth"] or 0
        values["status"] = values["status"] or "unknown"
        values["is_stale"] = int(bool(values["is_stale"]))
        metadata_json = json.dumps(fields.get("metadata"), ensure_ascii=False) if fields.get("metadata") is not None else None
        with self._db.transaction() as conn:
            existing = conn.execute(
                "SELECT id, created_at FROM course_content_items WHERE user_id=? AND provider=? AND course_id=? AND kind=? AND external_id=?",
                (user_id, provider, course_id, kind, external_id),
            ).fetchone()
            item_id = existing["id"] if existing else _id("cci")
            created_at = existing["created_at"] if existing else now
            conn.execute(
                """INSERT OR REPLACE INTO course_content_items
                   (id,user_id,course_id,provider,external_id,parent_external_id,kind,title,
                    description,author_name,position,depth,status,starts_at,deadline,published_at,
                    mime_type,file_size,remote_object_id,source_url,metadata_json,is_stale,
                    last_synced_at,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (item_id,user_id,course_id,provider,external_id,values["parent_external_id"],kind,title,
                 values["description"],values["author_name"],values["position"],values["depth"],
                 values["status"],values["starts_at"],values["deadline"],values["published_at"],
                 values["mime_type"],values["file_size"],values["remote_object_id"],values["source_url"],
                 metadata_json,values["is_stale"],values["last_synced_at"] or now,created_at,now),
            )
        return self.get_item(item_id, user_id=user_id)  # type: ignore[return-value]

    def get_item(self, item_id: str, *, user_id: str) -> Optional[CourseContentItemRow]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM course_content_items WHERE id=? AND user_id=?", (item_id, user_id)
            ).fetchone()
        return CourseContentItemRow.from_row(row) if row else None

    def list_items(self, *, user_id: str, course_id: str, kind: Optional[str] = None,
                   include_stale: bool = False, page: int = 1,
                   page_size: int = 100) -> list[CourseContentItemRow]:
        conditions = ["user_id=?", "course_id=?"]
        params: list[Any] = [user_id, course_id]
        if kind:
            conditions.append("kind=?")
            params.append(kind)
        if not include_stale:
            conditions.append("is_stale=0")
        with self._db.query() as conn:
            rows = conn.execute(
                f"SELECT * FROM course_content_items WHERE {' AND '.join(conditions)} ORDER BY position, created_at LIMIT ? OFFSET ?",
                params + [page_size, (page - 1) * page_size],
            ).fetchall()
        return [CourseContentItemRow.from_row(row) for row in rows]

    def count_items(self, *, user_id: str, course_id: str, kind: Optional[str] = None) -> int:
        conditions = ["user_id=?", "course_id=?", "is_stale=0"]
        params: list[Any] = [user_id, course_id]
        if kind:
            conditions.append("kind=?")
            params.append(kind)
        with self._db.query() as conn:
            return int(conn.execute(
                f"SELECT COUNT(*) AS n FROM course_content_items WHERE {' AND '.join(conditions)}", params
            ).fetchone()["n"])

    def upsert_section_status(self, *, user_id: str, course_id: str, section: str,
                              status: str, item_count: int, error_code: Optional[str] = None,
                              error_message: Optional[str] = None) -> CourseSyncSectionRow:
        now = _now()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO course_sync_sections
                   (user_id,course_id,section,status,item_count,last_synced_at,error_code,error_message)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(user_id,course_id,section) DO UPDATE SET
                     status=excluded.status,item_count=excluded.item_count,
                     last_synced_at=excluded.last_synced_at,error_code=excluded.error_code,
                     error_message=excluded.error_message""",
                (user_id,course_id,section,status,item_count,now,error_code,error_message),
            )
            row = conn.execute(
                "SELECT * FROM course_sync_sections WHERE user_id=? AND course_id=? AND section=?",
                (user_id,course_id,section),
            ).fetchone()
        return CourseSyncSectionRow.from_row(row)

    def list_section_statuses(self, *, user_id: str, course_id: str) -> list[CourseSyncSectionRow]:
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT * FROM course_sync_sections WHERE user_id=? AND course_id=? ORDER BY section",
                (user_id,course_id),
            ).fetchall()
        return [CourseSyncSectionRow.from_row(row) for row in rows]

    def mark_section_stale_except(self, *, user_id: str, course_id: str,
                                  kinds: set[str], external_keys: set[tuple[str, str]]) -> None:
        if not kinds:
            return
        placeholders = ",".join("?" for _ in kinds)
        with self._db.transaction() as conn:
            conn.execute(
                f"UPDATE course_content_items SET is_stale=1 WHERE user_id=? AND course_id=? AND kind IN ({placeholders})",
                [user_id, course_id, *sorted(kinds)],
            )
            for kind, external_id in external_keys:
                conn.execute(
                    "UPDATE course_content_items SET is_stale=0 WHERE user_id=? AND course_id=? AND kind=? AND external_id=?",
                    (user_id, course_id, kind, external_id),
                )

    def get_cache(self, *, item_id: str, user_id: str) -> Optional[dict]:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM course_resource_cache WHERE item_id=? AND user_id=?",
                (item_id, user_id),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE course_resource_cache SET last_accessed_at=? WHERE item_id=? AND user_id=?",
                    (_now(), item_id, user_id),
                )
        return dict(row) if row else None

    def delete_cache(self, *, item_id: str, user_id: str) -> Optional[str]:
        """Remove one cache record and return its relative file path."""
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT relative_path FROM course_resource_cache WHERE item_id=? AND user_id=?",
                (item_id, user_id),
            ).fetchone()
            conn.execute(
                "DELETE FROM course_resource_cache WHERE item_id=? AND user_id=?",
                (item_id, user_id),
            )
        return str(row["relative_path"]) if row else None

    def prune_cache(self, *, max_bytes: int) -> list[str]:
        """Delete LRU cache records until recorded bytes fit the configured ceiling."""
        removed: list[str] = []
        with self._db.transaction() as conn:
            rows = conn.execute(
                "SELECT item_id,user_id,relative_path,file_size FROM course_resource_cache ORDER BY last_accessed_at ASC"
            ).fetchall()
            total = sum(int(row["file_size"] or 0) for row in rows)
            for row in rows:
                if total <= max_bytes:
                    break
                conn.execute(
                    "DELETE FROM course_resource_cache WHERE item_id=? AND user_id=?",
                    (row["item_id"], row["user_id"]),
                )
                total -= int(row["file_size"] or 0)
                removed.append(str(row["relative_path"]))
        return removed

    def upsert_cache(self, *, item_id: str, user_id: str, course_id: str,
                     relative_path: str, content_hash: str, mime_type: Optional[str],
                     file_size: int, expires_at: Optional[str] = None) -> dict:
        now = _now()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO course_resource_cache
                   (item_id,user_id,course_id,relative_path,content_hash,mime_type,file_size,cached_at,last_accessed_at,expires_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(item_id,user_id) DO UPDATE SET
                     relative_path=excluded.relative_path,content_hash=excluded.content_hash,
                     mime_type=excluded.mime_type,file_size=excluded.file_size,
                     cached_at=excluded.cached_at,last_accessed_at=excluded.last_accessed_at,
                     expires_at=excluded.expires_at""",
                (item_id,user_id,course_id,relative_path,content_hash,mime_type,file_size,now,now,expires_at),
            )
        return self.get_cache(item_id=item_id, user_id=user_id) or {}
