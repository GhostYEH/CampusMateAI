"""文档仓库 — SQLite 持久化 + 内存索引协同。"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from ..database.sqlite_db import Database
from ..models.document import ChunkRow, DocumentRow
from ..utils.text_utils import chunk_text, extract_sections, extract_title_from_markdown


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class DocumentRepository:
    """文档与分块的持久化访问。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    # ===== 文档 =====

    def add_document(
        self,
        *,
        title: str,
        content_text: str,
        raw_text: str,
        content_hash: Optional[str] = None,
        source_department: Optional[str] = None,
        source_type: Optional[str] = None,
        original_filename: Optional[str] = None,
        published_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        effective_from: Optional[str] = None,
        effective_to: Optional[str] = None,
        version: Optional[str] = None,
        applicable_students: Optional[str] = None,
        is_official: bool = False,
        is_expired: bool = False,
        is_demo: bool = False,
        file_size: Optional[int] = None,
        file_ext: Optional[str] = None,
    ) -> tuple[DocumentRow, bool]:
        """新增文档。返回 (row, created)。若 hash 重复返回 (existing, False)。"""
        if content_hash is None:
            content_hash = compute_content_hash(content_text)
        existing = self.get_document_by_hash(content_hash)
        if existing is not None:
            return existing, False

        doc_id = _new_id("doc")
        imported_at = _now_iso()
        row = DocumentRow(
            document_id=doc_id,
            title=title,
            source_department=source_department,
            source_type=source_type,
            original_filename=original_filename,
            content_hash=content_hash,
            content_text=content_text,
            raw_text=raw_text,
            published_at=published_at,
            updated_at=updated_at,
            effective_from=effective_from,
            effective_to=effective_to,
            version=version,
            applicable_students=applicable_students,
            is_official=is_official,
            is_expired=is_expired,
            is_demo=is_demo,
            file_size=file_size,
            file_ext=file_ext,
            imported_at=imported_at,
        )
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    document_id, title, source_department, source_type,
                    original_filename, content_hash, content_text, raw_text,
                    published_at, updated_at, effective_from, effective_to,
                    version, applicable_students, is_official, is_expired,
                    is_demo, file_size, file_ext, imported_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row.document_id, row.title, row.source_department, row.source_type,
                    row.original_filename, row.content_hash, row.content_text, row.raw_text,
                    row.published_at, row.updated_at, row.effective_from, row.effective_to,
                    row.version, row.applicable_students, int(row.is_official), int(row.is_expired),
                    int(row.is_demo), row.file_size, row.file_ext, row.imported_at,
                ),
            )
        # 同步分块
        self._rebuild_chunks_for_document(row.document_id, content_text)
        return row, True

    def get_document(self, document_id: str) -> Optional[DocumentRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM documents WHERE document_id = ?",
                (document_id,),
            )
            row = cur.fetchone()
            return DocumentRow.from_row(row) if row else None

    def get_document_by_hash(self, content_hash: str) -> Optional[DocumentRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM documents WHERE content_hash = ?",
                (content_hash,),
            )
            row = cur.fetchone()
            return DocumentRow.from_row(row) if row else None

    def list_documents(self) -> List[DocumentRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM documents ORDER BY imported_at DESC"
            )
            rows = cur.fetchall()
            return [DocumentRow.from_row(r) for r in rows]

    def delete_document(self, document_id: str) -> bool:
        with self._db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM documents WHERE document_id = ?",
                (document_id,),
            )
            # 外键 ON DELETE CASCADE 会自动清理 chunks
            return cur.rowcount > 0

    def count_documents(self) -> int:
        with self._db.query() as conn:
            cur = conn.execute("SELECT COUNT(*) AS n FROM documents")
            return int(cur.fetchone()["n"])

    def count_demo_documents(self) -> int:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) AS n FROM documents WHERE is_demo = 1"
            )
            return int(cur.fetchone()["n"])

    def count_user_documents(self) -> int:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) AS n FROM documents WHERE is_demo = 0"
            )
            return int(cur.fetchone()["n"])

    def delete_all_user_documents(self) -> int:
        """删除所有用户导入文档(is_demo=0),保留演示资料。返回删除数量。"""
        with self._db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM documents WHERE is_demo = 0"
            )
            return cur.rowcount

    def delete_all_documents(self) -> int:
        """删除所有文档(包括演示资料)。返回删除数量。"""
        with self._db.transaction() as conn:
            cur = conn.execute("DELETE FROM documents")
            return cur.rowcount

    # ===== 分块 =====

    def _rebuild_chunks_for_document(self, document_id: str, content: str) -> int:
        """为指定文档重新分块(先删后建)。返回新增块数。"""
        # 先删除该文档的旧分块
        with self._db.transaction() as conn:
            conn.execute(
                "DELETE FROM chunks WHERE document_id = ?", (document_id,)
            )
            sections = extract_sections(content)
            created_at = _now_iso()
            position = 0
            for section_title, section_content in sections:
                # 标题不单独成块；段落按字符切分
                pieces = chunk_text(section_content, chunk_size=400, overlap=80)
                if not pieces:
                    pieces = [section_content]
                for piece in pieces:
                    if not piece.strip():
                        continue
                    conn.execute(
                        """
                        INSERT INTO chunks (
                            chunk_id, document_id, section, position,
                            content, page_number, created_at
                        ) VALUES (?,?,?,?,?,?,?)
                        """,
                        (
                            _new_id("chk"), document_id, section_title, position,
                            piece, None, created_at,
                        ),
                    )
                    position += 1
            return position

    def list_chunks(self) -> List[ChunkRow]:
        with self._db.query() as conn:
            cur = conn.execute("SELECT * FROM chunks")
            return [ChunkRow.from_row(r) for r in cur.fetchall()]

    def list_chunks_for_document(self, document_id: str) -> List[ChunkRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM chunks WHERE document_id = ? ORDER BY position",
                (document_id,),
            )
            return [ChunkRow.from_row(r) for r in cur.fetchall()]

    def count_chunks(self) -> int:
        with self._db.query() as conn:
            cur = conn.execute("SELECT COUNT(*) AS n FROM chunks")
            return int(cur.fetchone()["n"])

    def latest_imported_at(self) -> Optional[str]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT imported_at FROM documents ORDER BY imported_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            return row["imported_at"] if row else None

    def infer_title_from_content(self, content: str, fallback_filename: Optional[str]) -> str:
        title = extract_title_from_markdown(content)
        if title:
            return title[:100]
        # 取首行非空内容
        for line in content.splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                return s[:100]
        return fallback_filename or "未命名文档"


__all__ = ["DocumentRepository", "compute_content_hash"]
