"""知识库相关 schema。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """文档元数据(上传时可选，自动推断时为空)。"""
    title: Optional[str] = None
    source_department: Optional[str] = None
    source_type: Optional[str] = None
    published_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    version: Optional[str] = None
    applicable_students: Optional[str] = None
    is_official: bool = False


class DocumentSummary(BaseModel):
    document_id: str
    title: str
    source_department: Optional[str] = None
    source_type: Optional[str] = None
    original_filename: Optional[str] = None
    content_hash: str
    published_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    version: Optional[str] = None
    applicable_students: Optional[str] = None
    is_official: bool
    is_expired: bool
    is_demo: bool = False
    file_size: Optional[int] = None
    file_ext: Optional[str] = None
    imported_at: datetime


class KnowledgeStatus(BaseModel):
    document_count: int
    chunk_count: int
    last_updated: Optional[datetime] = None
    index_status: str = Field(..., description="ready|empty|error")
    retrieval_method: str = Field(..., description="bm25|vector|hybrid")
    is_available: bool
    knowledge_base_path: str
    # 知识库类型: demo(仿真) / user(用户导入) / hybrid(混合) / empty(空)
    knowledge_base_type: str = Field(
        ..., description="demo|user|hybrid|empty"
    )
    demo_document_count: int = 0
    user_document_count: int = 0
    # LLM 与问答模式
    llm_available: bool = False
    qa_mode: str = Field(
        "no_knowledge",
        description="retrieval_summary|llm_rag|no_knowledge",
    )


class RebuildResponse(BaseModel):
    success: bool
    document_count: int
    chunk_count: int
    message: str


class DeleteResponse(BaseModel):
    success: bool
    document_id: str


class RestoreDemoResponse(BaseModel):
    """恢复演示资料响应。"""
    success: bool
    restored_count: int
    total_demo_count: int
    message: str


class DataManagementResponse(BaseModel):
    """数据清理操作响应。"""
    success: bool
    action: str = Field(..., description="执行的清理动作")
    affected_count: int = 0
    message: str


__all__ = [
    "DocumentMetadata",
    "DocumentSummary",
    "KnowledgeStatus",
    "RebuildResponse",
    "DeleteResponse",
    "RestoreDemoResponse",
    "DataManagementResponse",
]
