"""服务容器 — 全局单例，FastAPI 启动时初始化。

集中管理各 service 的依赖关系，避免在每个路由里重复构造。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..core.config import Settings, get_settings
from ..database.sqlite_db import Database, init_db
from ..repositories.document_repository import DocumentRepository
from ..repositories.multi_role_repository import (
    AnnouncementRepository,
    AssignmentRepository,
    ClassGroupRepository,
    CourseRepository,
    EnrollmentRepository,
    RefreshTokenRepository,
    SubmissionRepository,
    UserRepository,
)
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
    # 多角色仓库
    user_repository: UserRepository
    refresh_token_repository: RefreshTokenRepository
    course_repository: CourseRepository
    class_group_repository: ClassGroupRepository
    enrollment_repository: EnrollmentRepository
    announcement_repository: AnnouncementRepository
    assignment_repository: AssignmentRepository
    submission_repository: SubmissionRepository

    def ensure_index(self) -> int:
        """确保索引就绪(若 stale 则重建)。返回 chunk 数。"""
        return self.retrieval.rebuild()


_container: Optional[ServiceContainer] = None


def _build_container_inner(settings: Settings, db: Database) -> ServiceContainer:
    repo = DocumentRepository(db)
    retrieval = RetrievalService(repo)
    ingestion = KnowledgeIngestionService(repo, retrieval, settings)
    llm = build_llm_client(settings)
    notice = NoticeExtractionService(llm, settings)
    rag = RagService(retrieval, llm, settings, repo)
    container = ServiceContainer(
        settings=settings,
        db=db,
        document_repository=repo,
        retrieval=retrieval,
        knowledge_ingestion=ingestion,
        notice_extraction=notice,
        rag=rag,
        llm=llm,
        user_repository=UserRepository(db),
        refresh_token_repository=RefreshTokenRepository(db),
        course_repository=CourseRepository(db),
        class_group_repository=ClassGroupRepository(db),
        enrollment_repository=EnrollmentRepository(db),
        announcement_repository=AnnouncementRepository(db),
        assignment_repository=AssignmentRepository(db),
        submission_repository=SubmissionRepository(db),
    )
    # 启动时重建索引(从已持久化的 chunks 重建 BM25)
    try:
        retrieval.rebuild()
    except Exception:
        pass
    return container


def build_container(settings: Optional[Settings] = None) -> ServiceContainer:
    """构造 ServiceContainer 并执行启动初始化。"""
    global _container
    s = settings or get_settings()
    db = init_db(s)
    container = _build_container_inner(s, db)
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

    s = settings or get_settings()
    db = reset_db_for_tests()
    container = _build_container_inner(s, db)
    _container = container
    return container


__all__ = ["ServiceContainer", "build_container", "get_container", "reset_container_for_tests"]
