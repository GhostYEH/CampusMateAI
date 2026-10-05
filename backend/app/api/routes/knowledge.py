"""知识库只读列表与状态路由。"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends

from ...schemas.knowledge import DocumentSummary, KnowledgeStatus
from ...services.container import get_container
from ..deps import current_user
from ...models.multi_role import UserRow

router = APIRouter()


def _determine_knowledge_base_type(
    demo_count: int, user_count: int
) -> str:
    """根据演示/用户文档数量判定知识库类型。"""
    if demo_count == 0 and user_count == 0:
        return "empty"
    if demo_count > 0 and user_count == 0:
        return "demo"
    if demo_count == 0 and user_count > 0:
        return "user"
    return "hybrid"


def _determine_qa_mode(
    *, llm_available: bool, is_available: bool
) -> str:
    """根据 LLM 与知识库可用性判定问答模式。"""
    if not is_available:
        return "no_knowledge"
    if llm_available:
        return "llm_rag"
    return "retrieval_summary"


@router.get("/knowledge/status", response_model=KnowledgeStatus)
def knowledge_status() -> KnowledgeStatus:
    """只读状态查询，全部是同步 SQLite 读取；用 def 让 FastAPI 放到线程池执行。"""
    container = get_container()
    last_imported = container.document_repository.latest_imported_at()
    chunk_count = container.retrieval.chunk_count
    doc_count = container.document_repository.count_documents()
    demo_count = container.document_repository.count_demo_documents()
    user_count = container.document_repository.count_user_documents()
    is_available = chunk_count > 0
    kb_type = _determine_knowledge_base_type(demo_count, user_count)
    llm_available = (
        container.llm is not None and container.settings.llm_available
    )
    qa_mode = _determine_qa_mode(
        llm_available=llm_available, is_available=is_available
    )
    return KnowledgeStatus(
        document_count=doc_count,
        chunk_count=chunk_count,
        last_updated=last_imported,
        index_status="ready" if is_available else "empty",
        retrieval_method="bm25",
        is_available=is_available,
        knowledge_base_type=kb_type,
        demo_document_count=demo_count,
        user_document_count=user_count,
        llm_available=llm_available,
        qa_mode=qa_mode,
    )


@router.get("/knowledge/documents", response_model=List[DocumentSummary])
def list_documents(_user: UserRow = Depends(current_user)) -> List[DocumentSummary]:
    """只读文档元数据列表；用 def 避免在事件循环里执行同步 SQLite 读取。"""
    container = get_container()
    docs = container.document_repository.list_documents()
    return [
        DocumentSummary(
            document_id=d.document_id,
            title=d.title,
            source_department=d.source_department,
            source_type=d.source_type,
            original_filename=d.original_filename,
            content_hash=d.content_hash,
            published_at=_parse_dt(d.published_at),
            updated_at=_parse_dt(d.updated_at),
            effective_from=_parse_dt(d.effective_from),
            effective_to=_parse_dt(d.effective_to),
            version=d.version,
            applicable_students=d.applicable_students,
            is_official=d.is_official,
            is_expired=d.is_expired,
            is_demo=d.is_demo,
            file_size=d.file_size,
            file_ext=d.file_ext,
            imported_at=_parse_dt(d.imported_at),
        )
        for d in docs
    ]


def _parse_dt(s: Optional[str]):
    if not s:
        return None
    from datetime import datetime
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
