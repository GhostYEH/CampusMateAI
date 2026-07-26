"""服务容器 — 全局单例，FastAPI 启动时初始化。

集中管理各 service 的依赖关系，避免在每个路由里重复构造。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..core.config import Settings, get_settings
from ..database.sqlite_db import Database, init_db
from ..repositories.document_repository import DocumentRepository
from ..services.knowledge_ingestion_service import KnowledgeIngestionService
from ..services.llm.base import LLMClient
from ..services.llm.fallback import build_llm_client
from ..services.notice_extraction_service import NoticeExtractionService
from ..services.rag_service import RagService
from ..services.retrieval_service import RetrievalService


@dataclass
class ServiceContainer:
    settings: Settings
    db: Database
    document_repository: DocumentRepository
    retrieval: RetrievalService
    knowledge_ingestion: KnowledgeIngestionService
    notice_extraction: NoticeExtractionService
    rag: RagService
    llm: Optional[LLMClient]

    def ensure_index(self) -> int:
        """确保索引就绪(若 stale 则重建)。返回 chunk 数。"""
        return self.retrieval.rebuild()


_container: Optional[ServiceContainer] = None


def build_container(settings: Optional[Settings] = None) -> ServiceContainer:
    """构造 ServiceContainer 并执行启动初始化。"""
    global _container
    s = settings or get_settings()
    db = init_db(s)
    repo = DocumentRepository(db)
    retrieval = RetrievalService(repo)
    ingestion = KnowledgeIngestionService(repo, retrieval, s)
    llm = build_llm_client(s)
    notice = NoticeExtractionService(llm, s)
    rag = RagService(retrieval, llm, s, repo)
    container = ServiceContainer(
        settings=s,
        db=db,
        document_repository=repo,
        retrieval=retrieval,
        knowledge_ingestion=ingestion,
        notice_extraction=notice,
        rag=rag,
        llm=llm,
    )
    # 启动时重建索引(从已持久化的 chunks 重建 BM25)
    try:
        retrieval.rebuild()
    except Exception:
        pass
    _container = container
    return container


def get_container() -> ServiceContainer:
    if _container is None:
        build_container()
    return _container  # type: ignore[return-value]


def reset_container_for_tests(settings: Optional[Settings] = None) -> ServiceContainer:
    """测试专用：重置 container 与 DB 单例。"""
    global _container
    from ..database.sqlite_db import reset_db_for_tests

    reset_db_for_tests()
    s = settings or get_settings()
    db = reset_db_for_tests()
    repo = DocumentRepository(db)
    retrieval = RetrievalService(repo)
    ingestion = KnowledgeIngestionService(repo, retrieval, s)
    llm = None  # 测试默认不接 LLM
    notice = NoticeExtractionService(llm, s)
    rag = RagService(retrieval, llm, s, repo)
    container = ServiceContainer(
        settings=s,
        db=db,
        document_repository=repo,
        retrieval=retrieval,
        knowledge_ingestion=ingestion,
        notice_extraction=notice,
        rag=rag,
        llm=llm,
    )
    _container = container
    return container


__all__ = ["ServiceContainer", "build_container", "get_container", "reset_container_for_tests"]
