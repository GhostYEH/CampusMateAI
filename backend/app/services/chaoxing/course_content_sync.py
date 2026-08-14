from __future__ import annotations

from datetime import datetime, timezone

from ...repositories.course_content_repository import CourseContentRepository
from .ChaoxingClient import ChaoxingClient


class ChaoxingCourseContentSyncService:
    SECTION_KINDS = {
        "chapters": {"chapter", "document", "video", "audio", "image", "link", "quiz", "material"},
        "materials": {"document", "video", "audio", "image", "link", "material"},
        "exams": {"exam"},
        "discussions": {"discussion"},
        "assignments": {"assignment"},
        "notices": {"notice"},
    }

    def __init__(self, container) -> None:
        self.container = container
        self.repository: CourseContentRepository = container.course_content_repository

    async def sync_course(self, *, user_id: str, course_id: str) -> dict:
        course = self.container.course_repository.get_course(course_id)
        if course is None or course.provider != "chaoxing" or course.teacher_id != user_id:
            raise ValueError("course_not_found")
        credentials = self.container.chaoxing_repository.get_credentials(user_id)
        if not credentials:
            raise ValueError("chaoxing_credentials_not_found")
        client = ChaoxingClient(cookies=credentials)
        context = {
            "course_id": (course.external_id or "").split("_", 1)[0],
            "clazz_id": course.remote_class_id or ((course.external_id or "_").split("_", 1) + [""])[1],
            "cpi": course.remote_cpi,
        }
        fetchers = {
            "chapters": client.get_course_chapters,
            "materials": client.get_course_materials,
            "exams": client.get_course_exams,
            "discussions": client.get_course_discussions,
            "assignments": client.get_course_assignments,
            "notices": client.get_course_notices,
        }
        section_results = {}
        try:
            for section, fetcher in fetchers.items():
                result = await fetcher(context)
                items = result.get("items") or []
                status = result.get("status") or "failed"
                if status in {"complete", "partial"}:
                    keys: set[tuple[str, str]] = set()
                    for item in items:
                        external_id = str(item.get("external_id") or "")
                        kind = str(item.get("kind") or "")
                        if not external_id or not kind:
                            continue
                        keys.add((kind, external_id))
                        self.repository.upsert_item(
                            user_id=user_id, course_id=course_id, kind=kind,
                            external_id=external_id, title=item.get("title") or "无标题",
                            **{key: value for key, value in item.items()
                               if key not in {"kind", "external_id", "title"}},
                        )
                    if status == "complete":
                        self.repository.mark_section_stale_except(
                            user_id=user_id, course_id=course_id,
                            kinds=self.SECTION_KINDS[section], external_keys=keys,
                        )
                error = result.get("error")
                self.repository.upsert_section_status(
                    user_id=user_id, course_id=course_id, section=section,
                    status=status, item_count=len(items), error_code=error,
                    error_message=error,
                )
                section_results[section] = {"status": status, "item_count": len(items), "error": error}
        finally:
            await client.client.aclose()
        return {
            "course_id": course_id,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "sections": section_results,
        }
