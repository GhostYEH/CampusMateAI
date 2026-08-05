"""服务容器 — 全局单例，FastAPI 启动时初始化。

集中管理各 service 的依赖关系，避免在每个路由里重复构造。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..core.config import Settings, get_settings
from ..database.sqlite_db import Database, init_db
from ..repositories.document_repository import DocumentRepository
from ..repositories.multi_role_repository import (
    AnnouncementRepository,
    AssignmentRepository,
    CampusActivityRepository,
    ClassGroupRepository,
    CourseRepository,
    EnrollmentRepository,
    RefreshTokenRepository,
    SubmissionRepository,
    UserRepository,
)
from ..repositories.personal_task_repository import PersonalTaskRepository
from ..repositories.personal_hub_repository import (
    FavoriteRepository,
    PersonalFileRepository,
)
from ..repositories.study_session_repository import StudySessionRepository
from ..services.knowledge_ingestion_service import KnowledgeIngestionService
from ..services.llm.base import LLMClient
from ..services.llm.fallback import build_llm_client
from ..services.notice_extraction_service import NoticeExtractionService
from ..services.rag_service import RagService
from ..services.retrieval_service import RetrievalService
from ..services.task_breakdown_service import TaskBreakdownService


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
    campus_activity_repository: CampusActivityRepository
    assignment_repository: AssignmentRepository
    submission_repository: SubmissionRepository
    # 个人待办仓库(学生从通知抽取生成的任务)
    personal_task_repository: PersonalTaskRepository
    # 个人中心仓库(用户私有文件 / 跨模块收藏)
    personal_file_repository: PersonalFileRepository
    favorite_repository: FavoriteRepository
    # 学习陪伴
    study_session_repository: StudySessionRepository
    task_breakdown_service: TaskBreakdownService
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

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
    assignment_repo = AssignmentRepository(db)
    personal_task_repo = PersonalTaskRepository(db)
    personal_file_repo = PersonalFileRepository(db)
    favorite_repo = FavoriteRepository(db)
    # StudySessionRepository 注入 PersonalTaskRepository 用于校验 related_task_id
    study_session_repo = StudySessionRepository(db, personal_task_repo=personal_task_repo)
    # TaskBreakdownService 只解析 PersonalTask(不再接受 Assignment ID)
    task_breakdown = TaskBreakdownService(
        personal_task_repo=personal_task_repo,
        retrieval=retrieval,
        llm=llm,
        settings=settings,
    )
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
        campus_activity_repository=CampusActivityRepository(db),
        assignment_repository=assignment_repo,
        submission_repository=SubmissionRepository(db),
        personal_task_repository=personal_task_repo,
        personal_file_repository=personal_file_repo,
        favorite_repository=favorite_repo,
        study_session_repository=study_session_repo,
        task_breakdown_service=task_breakdown,
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
