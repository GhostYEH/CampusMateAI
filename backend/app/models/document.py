"""数据模型 — 文档与分块。

为后续 ORM 迁移预留：当前用 dataclass 表示行结构，
迁移 PostgreSQL 时可改为 SQLAlchemy 模型。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DocumentRow:
    document_id: str
    title: str
    source_department: Optional[str] = None
    source_type: Optional[str] = None
    original_filename: Optional[str] = None
    content_hash: str = ""
    content_text: str = ""
    raw_text: str = ""
    published_at: Optional[str] = None
    updated_at: Optional[str] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    version: Optional[str] = None
    applicable_students: Optional[str] = None
    is_official: bool = False
    is_expired: bool = False
    is_demo: bool = False
    file_size: Optional[int] = None
    file_ext: Optional[str] = None
    imported_at: str = ""

    @classmethod
    def from_row(cls, row) -> "DocumentRow":
        return cls(
            document_id=row["document_id"],
            title=row["title"],
            source_department=row["source_department"],
            source_type=row["source_type"],
            original_filename=row["original_filename"],
            content_hash=row["content_hash"],
            content_text=row["content_text"],
            raw_text=row["raw_text"],
            published_at=row["published_at"],
            updated_at=row["updated_at"],
            effective_from=row["effective_from"],
            effective_to=row["effective_to"],
            version=row["version"],
            applicable_students=row["applicable_students"],
            is_official=bool(row["is_official"]),
            is_expired=bool(row["is_expired"]),
            is_demo=bool(row["is_demo"]) if "is_demo" in row.keys() else False,
            file_size=row["file_size"],
            file_ext=row["file_ext"],
            imported_at=row["imported_at"],
        )


@dataclass
class ChunkRow:
    chunk_id: str
    document_id: str
    section: Optional[str]
    position: int
    content: str
    page_number: Optional[int] = None
    created_at: str = ""

    @classmethod
    def from_row(cls, row) -> "ChunkRow":
        return cls(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            section=row["section"],
            position=row["position"],
            content=row["content"],
            page_number=row["page_number"],
            created_at=row["created_at"],
        )


@dataclass
class RetrievedChunk:
    """检索结果(带文档元数据)。"""
    chunk: ChunkRow
    document: DocumentRow
    score: float


__all__ = ["DocumentRow", "ChunkRow", "RetrievedChunk"]
