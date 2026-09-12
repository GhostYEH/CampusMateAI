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
from ..repositories.study_goal_repository import StudyGoalRepository
from ..repositories.study_checkin_repository import StudyCheckinRepository
from ..repositories.chaoxing_repository import ChaoxingRepository
from ..repositories.notice_repository import NoticeRepository
from ..repositories.university_repository import UniversityRepository
from ..repositories.community_repository import CommunityRepository
from ..repositories.home_banner_repository import HomeBannerRepository
from ..repositories.academic_repository import AcademicRepository
from ..repositories.notice_automation_repository import NoticeAutomationRepository
from ..repositories.course_content_repository import CourseContentRepository
from ..repositories.edu_data_repository import EduDataRepository
from ..repositories.edu_repository import EduRepository
from ..repositories.learner_event_repository import LearnerEventRepository
from ..repositories.learner_state_repository import LearnerStateRepository
from ..repositories.learning_plan_repository import LearningPlanRepository
from ..repositories.model_shadow_repository import ModelShadowRepository
from ..repositories.c_knowledge_repository import KnowledgeRepository
from ..repositories.learner_control_repository import LearnerControlRepository
from ..repositories.qr_auth_repository import (
    QrLoginSessionRepository,
    TrustedDeviceRepository,
)
from ..services.knowledge_ingestion_service import KnowledgeIngestionService
from ..services.learner_event_service import LearnerEventService
from ..services.learner_state_service import LearnerStateProjectionService
from ..services.c_knowledge_service import KnowledgeService
from ..services.learner_control_service import LearnerControlService
from ..services.learner_model_source_policy import LearnerModelSourcePolicy
from ..services.learning_planner_service import LearningPlannerService
from ..services.learning_agent_tools import LearningAgentToolRegistry
from ..services.model_capability_registry import ModelCapabilityRegistry
from ..services.model_shadow_runner import ModelShadowRunner
from ..services.llm.base import LLMClient
from ..services.llm.fallback import build_llm_client
from ..services.llm.openai_compatible import OpenAICompatibleClient
from ..services.notice_extraction_service import NoticeExtractionService
from ..services.rag_service import RagService
from ..services.retrieval_service import RetrievalService
from ..services.task_breakdown_service import TaskBreakdownService
from ..services.tts import MiMoTtsClient
from ..services.edu import EduConnectorService, SchoolRegistry, SystemDetector, SessionManager
from ..services.edu.encrypted_session_store import EncryptedSqliteEduSessionStore


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
    model_shadow_runner: ModelShadowRunner
    tts: Optional[MiMoTtsClient]
    # 多角色仓库
    user_repository: UserRepository
    refresh_token_repository: RefreshTokenRepository
    course_repository: CourseRepository
    class_group_repository: ClassGroupRepository
    enrollment_repository: EnrollmentRepository
    announcement_repository: AnnouncementRepository
    assignment_repository: AssignmentRepository
    submission_repository: SubmissionRepository
    # 个人待办仓库(学生从通知抽取生成的任务)
    personal_task_repository: PersonalTaskRepository
    # 个人中心仓库(用户私有文件 / 跨模块收藏)
    personal_file_repository: PersonalFileRepository
    favorite_repository: FavoriteRepository
    # 学习陪伴
    study_session_repository: StudySessionRepository
    study_goal_repository: StudyGoalRepository
    study_checkin_repository: StudyCheckinRepository
    chaoxing_repository: ChaoxingRepository
    notice_repository: NoticeRepository
    university_repository: UniversityRepository
    community_repository: CommunityRepository
    home_banner_repository: HomeBannerRepository
    academic_repository: AcademicRepository
    notice_automation_repository: NoticeAutomationRepository
    course_content_repository: CourseContentRepository
    task_breakdown_service: TaskBreakdownService
    learner_event_repository: LearnerEventRepository
    learner_event_service: LearnerEventService
    learner_state_repository: LearnerStateRepository
    learner_state_service: LearnerStateProjectionService
    knowledge_repository: KnowledgeRepository
    knowledge_service: KnowledgeService
    learning_plan_repository: LearningPlanRepository
    learning_planner_service: LearningPlannerService
    learning_agent_tools: LearningAgentToolRegistry
    learner_control_repository: LearnerControlRepository
    learner_control_service: LearnerControlService
    learner_model_source_policy: LearnerModelSourcePolicy
    # QR 扫码登录与可信设备
    qr_login_session_repository: QrLoginSessionRepository
    trusted_device_repository: TrustedDeviceRepository
    # EduConnector
    edu_repository: EduRepository
    edu_connector: EduConnectorService
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
    candidate_llm = None
    if settings.campusmate_lm_available:
        candidate_llm = OpenAICompatibleClient(
            base_url=settings.campusmate_lm_base_url,
            api_key=settings.campusmate_lm_api_key,
            model=settings.campusmate_lm_model_name,
            timeout=settings.campusmate_lm_timeout_ms / 1000,
        )
    model_shadow_runner = ModelShadowRunner(
        registry=ModelCapabilityRegistry(), candidate_llm=candidate_llm,
        enabled=settings.campusmate_lm_enabled, sample_rate=settings.campusmate_lm_shadow_sample_rate,
        concurrency_limit=settings.campusmate_lm_concurrency_limit, timeout_ms=settings.campusmate_lm_timeout_ms,
        max_tokens=settings.campusmate_lm_max_tokens, temperature=settings.campusmate_lm_temperature,
        seed=settings.campusmate_lm_seed, circuit_breaker_threshold=settings.campusmate_lm_circuit_breaker_threshold,
        circuit_breaker_cooldown_seconds=settings.campusmate_lm_circuit_breaker_cooldown_seconds,
        repository=ModelShadowRepository(db, retention_days=settings.campusmate_lm_data_retention_days),
    )
    tts = (
        MiMoTtsClient(
            base_url=settings.mimo_base_url,
            api_key=settings.mimo_api_key,
            model=settings.mimo_tts_model,
            voice=settings.mimo_tts_voice,
            timeout=float(settings.mimo_tts_timeout_seconds),
        )
        if settings.mimo_tts_available
        else None
    )
    notice = NoticeExtractionService(llm, settings)
    rag = RagService(retrieval, llm, settings, repo)
    assignment_repo = AssignmentRepository(db)
    course_repo = CourseRepository(db)
    personal_task_repo = PersonalTaskRepository(db)
    personal_file_repo = PersonalFileRepository(db)
    favorite_repo = FavoriteRepository(db)
    # StudySessionRepository 注入 PersonalTaskRepository 用于校验 related_task_id
    study_session_repo = StudySessionRepository(db, personal_task_repo=personal_task_repo)
    study_goal_repo = StudyGoalRepository(db)
    study_checkin_repo = StudyCheckinRepository(db)
    # TaskBreakdownService 只解析 PersonalTask(不再接受 Assignment ID)
    task_breakdown = TaskBreakdownService(
        personal_task_repo=personal_task_repo,
        retrieval=retrieval,
        llm=llm,
        settings=settings,
    )
    course_content_repository = CourseContentRepository(db)
    home_banner_repository = HomeBannerRepository(db)
    home_banner_repository.seed_defaults()
    learner_event_repository = LearnerEventRepository(db)
    learner_event_service = LearnerEventService(
        learner_event_repository,
        study_session_repository=study_session_repo,
        personal_task_repository=personal_task_repo,
        course_repository=course_repo,
        notice_repository=NoticeRepository(db),
        course_content_repository=course_content_repository,
    )
    learner_state_repository = LearnerStateRepository(db)
    learner_control_repository = LearnerControlRepository(db)
    learner_state_service = LearnerStateProjectionService(learner_state_repository, control_repository=learner_control_repository)
    knowledge_repository = KnowledgeRepository(db)
    knowledge_service = KnowledgeService(
        knowledge_repository, learner_event_repository, learner_state_repository
    )
    knowledge_service.seed_c_taxonomy()
    learning_plan_repository = LearningPlanRepository(db)
    learning_planner_service = LearningPlannerService(
        repository=learning_plan_repository, state_service=learner_state_service,
        state_repository=learner_state_repository, knowledge_service=knowledge_service,
        knowledge_repository=knowledge_repository, task_repository=personal_task_repo,
        content_repository=course_content_repository, llm=llm,
    )

    learner_control_service = LearnerControlService(
        repository=learner_control_repository,
        state_repository=learner_state_repository,
        shadow_repository=ModelShadowRepository(db, retention_days=settings.campusmate_lm_data_retention_days),
    )
    learner_model_source_policy = LearnerModelSourcePolicy(control_repository=learner_control_repository)
    # EduConnector
    edu_repo = EduRepository(db)
    edu_data_repo = EduDataRepository(db)
    school_registry = SchoolRegistry(university_repo=UniversityRepository(db), edu_repo=edu_repo)
    system_detector = SystemDetector(registry=school_registry)
    if settings.effective_edu_session_store == "encrypted_sqlite":
        session_manager = EncryptedSqliteEduSessionStore(
            db=db,
            encryption_key_base64=settings.edu_session_encryption_key,
            key_id=settings.edu_session_encryption_key_id,
            session_ttl_seconds=settings.edu_session_ttl_seconds,
        )
    else:
        session_manager = SessionManager(
            session_ttl_seconds=settings.edu_session_ttl_seconds
        )
    edu_connector = EduConnectorService(
        settings=settings,
        registry=school_registry,
        detector=system_detector,
        session_manager=session_manager,
        edu_repo=edu_repo,
        edu_data_repo=edu_data_repo,
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
        model_shadow_runner=model_shadow_runner,
        tts=tts,
        user_repository=UserRepository(db),
        refresh_token_repository=RefreshTokenRepository(db),
        course_repository=course_repo,
        class_group_repository=ClassGroupRepository(db),
        enrollment_repository=EnrollmentRepository(db),
        announcement_repository=AnnouncementRepository(db),
        assignment_repository=assignment_repo,
        submission_repository=SubmissionRepository(db),
        personal_task_repository=personal_task_repo,
        personal_file_repository=personal_file_repo,
        favorite_repository=favorite_repo,
        study_session_repository=study_session_repo,
        study_goal_repository=study_goal_repo,
        study_checkin_repository=study_checkin_repo,
        chaoxing_repository=ChaoxingRepository(db),
        notice_repository=NoticeRepository(db),
        university_repository=UniversityRepository(db),
        community_repository=CommunityRepository(db),
        home_banner_repository=home_banner_repository,
        academic_repository=AcademicRepository(db),
        notice_automation_repository=NoticeAutomationRepository(db),
        course_content_repository=CourseContentRepository(db),
        task_breakdown_service=task_breakdown,
        learner_event_repository=learner_event_repository,
        learner_event_service=learner_event_service,
        learner_state_repository=learner_state_repository,
        learner_state_service=learner_state_service,
        knowledge_repository=knowledge_repository,
        knowledge_service=knowledge_service,
        learning_plan_repository=learning_plan_repository,
        learning_planner_service=learning_planner_service,
        learning_agent_tools=LearningAgentToolRegistry(None),
        learner_control_repository=learner_control_repository,
        learner_control_service=learner_control_service,
        learner_model_source_policy=learner_model_source_policy,
        qr_login_session_repository=QrLoginSessionRepository(db),
        trusted_device_repository=TrustedDeviceRepository(db),
        edu_repository=edu_repo,
        edu_connector=edu_connector,
    )
    container.learning_agent_tools.container = container
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
