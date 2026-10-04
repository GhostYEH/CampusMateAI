"""Wire isolated sync fixtures the same way as the production container."""
from app.core.config import Settings
from app.repositories.notice_repository import NoticeRepository
from app.repositories.personal_task_repository import PersonalTaskRepository
from app.services.chaoxing.sync_service import ChaoxingSyncDependencies, ChaoxingSyncService
from app.services.notice_extraction_service import NoticeExtractionService


def wire_sync_service(container):
    if not hasattr(container, "personal_task_repository"):
        container.personal_task_repository = PersonalTaskRepository(container.db)
    if not hasattr(container, "notice_repository"):
        container.notice_repository = NoticeRepository(container.db)
    if not hasattr(container, "notice_extraction"):
        container.notice_extraction = NoticeExtractionService(None, Settings(llm_provider="none"))
    container.chaoxing_sync_service = ChaoxingSyncService(ChaoxingSyncDependencies(
        course_repository=container.course_repository,
        personal_task_repository=container.personal_task_repository,
        chaoxing_repository=container.chaoxing_repository,
        notice_repository=container.notice_repository,
        notice_extraction=container.notice_extraction,
        learner_event_service=getattr(container, "learner_event_service", None),
    ))
    return container
