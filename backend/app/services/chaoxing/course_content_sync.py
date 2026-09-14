from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from ...repositories.course_content_repository import CourseContentRepository
from .ChaoxingClient import ChaoxingClient


class ChaoxingCourseContentSyncService:
    SECTION_KINDS = {
        "chapters": {"chapter", "document", "video", "audio", "image", "link", "material"},
        "materials": {"document", "video", "audio", "image", "link", "material", "poll", "live", "task", "quiz"},
        "exams": {"exam_candidate"},
        "discussions": {"discussion"},
        "assignments": {"assignment"},
        "notices": {"notice"},
    }

    FAST_SECTIONS = {"chapters", "assignments", "notices"}
    DEEP_SECTIONS = {"materials", "exams", "discussions"}

    def __init__(self, container) -> None:
        self.container = container
        self.repository: CourseContentRepository = container.course_content_repository

    @staticmethod
    def _chapter_signature(chapter: dict, resource_count: int,
                           resource_fingerprint: str = "") -> str:
        metadata = chapter.get("metadata") or {}
        parts = [
            str(chapter.get("external_id") or ""),
            str(chapter.get("title") or ""),
            str(chapter.get("status") or ""),
            str(metadata.get("job_count") or 0),
            str(metadata.get("raw_status") or ""),
            str(metadata.get("isReview") or ""),
            str(metadata.get("label") or ""),
            str(metadata.get("begintime") or ""),
            str(metadata.get("endtime") or ""),
            str(resource_count),
            resource_fingerprint,
        ]
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    @staticmethod
    def _resource_fingerprint(items: list[dict], chapter_id: str) -> str:
        """Build a sorted fingerprint of resource identifiers for one chapter.

        Includes external_id, kind, and remote_object_id so that replacing
        attachment A with attachment B (same count, different ID) is detected.
        """
        entries: list[str] = []
        for item in items:
            if str(item.get("parent_external_id") or "") != chapter_id:
                continue
            if item.get("kind") == "chapter":
                continue
            entries.append(
                f"{item.get('kind','')}:{item.get('external_id','')}:{item.get('remote_object_id','')}"
            )
        entries.sort()
        return "|".join(entries)

    def _load_existing_chapter_signatures(self, *, user_id: str, course_id: str) -> dict[str, str]:
        items = self.repository.list_items(
            user_id=user_id, course_id=course_id, kind="chapter",
            include_stale=True, page_size=1000,
        )
        signatures: dict[str, str] = {}
        for item in items:
            metadata = item.metadata or {}
            sig = metadata.get("sync_signature")
            if sig:
                signatures[str(item.external_id)] = str(sig)
        return signatures

    @staticmethod
    def _count_resources_per_chapter(items: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            parent = str(item.get("parent_external_id") or "")
            if parent and item.get("kind") != "chapter":
                counts[parent] = counts.get(parent, 0) + 1
        return counts

    def _build_context(self, course) -> dict:
        external_id = course.external_id or ""
        parts = external_id.split("_", 1)
        course_id = parts[0]
        clazz_id = course.remote_class_id or (parts[1] if len(parts) > 1 else "")
        return {
            "course_id": course_id,
            "clazz_id": clazz_id,
            "cpi": course.remote_cpi,
        }

    def _persist_exams(self, *, user_id: str, course_id: str, items: list[dict],
                       course_external_id: str) -> None:
        """把 exam_candidate 落库为结构化 chaoxing_exams 并投射 exam_discovered。

        course_content_items 里的条目只服务前端展示；这里补写结构化考试事实，
        让世界模型能把学习通考试计入 exam_exposure。仅在首次发现或考试时间/分数
        变化时投射事件，避免每次同步重复刷事件。
        """
        repository = getattr(self.container, "chaoxing_repository", None)
        if repository is None or not hasattr(repository, "upsert_exam"):
            return
        event_service = getattr(self.container, "learner_event_service", None)
        seen: set[str] = set()
        for item in items:
            external_id = str(item.get("external_id") or "")
            if not external_id or external_id in seen:
                continue
            seen.add(external_id)
            metadata = item.get("metadata") or {}
            exam_row = repository.upsert_exam(
                user_id=user_id,
                course_id=course_id,
                external_id=f"{course_external_id or course_id}:{external_id}",
                title=str(item.get("title") or "未命名考试"),
                exam_at=metadata.get("exam_at"),
                score=metadata.get("score"),
                score_max=metadata.get("score_max"),
                status="discovered",
                source_url=item.get("source_url"),
            )
            if not (exam_row.get("is_new") or exam_row.get("changed")):
                continue
            if event_service is None or not hasattr(event_service, "project_safely"):
                continue
            bucket = event_service.exam_time_bucket(exam_row.get("exam_at")) or "unknown"
            event_service.project_safely(
                action="exam_discovered",
                subject_type="exam",
                subject_id=exam_row["id"],
                callback=lambda exam_row=exam_row, bucket=bucket: event_service.record_chaoxing_exam_discovered(
                    user_id=user_id,
                    exam_id=exam_row["id"],
                    course_id=course_id,
                    exam_time_bucket=bucket,
                    observed_at=datetime.now(timezone.utc),
                ),
            )

    async def sync_course(self, *, user_id: str, course_id: str,
                          depth: str = "fast", force_refresh: bool = False) -> dict:
        course = self.container.course_repository.get_course(course_id)
        if course is None or course.provider != "chaoxing" or course.owner_user_id != user_id:
            raise ValueError("course_not_found")
        credentials = self.container.chaoxing_repository.get_credentials(user_id)
        if not credentials:
            raise ValueError("chaoxing_credentials_not_found")
        client = ChaoxingClient(cookies=credentials)
        context = self._build_context(course)

        if depth == "fast":
            sections_to_sync = self.FAST_SECTIONS
        elif depth == "deep":
            sections_to_sync = self.DEEP_SECTIONS
        else:
            sections_to_sync = self.FAST_SECTIONS | self.DEEP_SECTIONS

        fetchers = {
            "chapters": client.get_course_chapters,
            "materials": client.get_course_materials,
            "exams": client.get_course_exams,
            "discussions": client.get_course_discussions,
            "assignments": client.get_course_assignments,
            "notices": client.get_course_notices,
        }

        unchanged_chapter_ids: set[str] | None = None
        if "materials" in sections_to_sync and not force_refresh:
            existing_signatures = self._load_existing_chapter_signatures(
                user_id=user_id, course_id=course_id
            )
            chapter_result = await client.get_course_chapters(context)
            if chapter_result["status"] == "complete":
                chapters = [item for item in chapter_result["items"] if item.get("kind") == "chapter"]
                resource_counts = self._count_resources_per_chapter(chapter_result["items"])
                unchanged_chapter_ids = set()
                for chapter in chapters:
                    chapter_id = str(chapter.get("external_id") or "")
                    fp = self._resource_fingerprint(chapter_result["items"], chapter_id)
                    new_sig = self._chapter_signature(chapter, resource_counts.get(chapter_id, 0), fp)
                    if existing_signatures.get(chapter_id) == new_sig:
                        chapter_metadata = chapter.get("metadata") or {}
                        if int(chapter_metadata.get("job_count") or 0) > 0:
                            continue
                        unchanged_chapter_ids.add(chapter_id)

        section_results = {}
        try:
            for section in sections_to_sync:
                fetcher = fetchers[section]
                kwargs: dict = {}
                if section in ("materials", "exams"):
                    kwargs["force_refresh"] = force_refresh
                    kwargs["unchanged_chapter_ids"] = unchanged_chapter_ids
                result = await fetcher(context, **kwargs)
                items = result.get("items") or []
                status = result.get("status") or "failed"
                saved_chapters = []
                if status in {"complete", "partial"}:
                    keys: set[tuple[str, str]] = set()
                    new_resource_counts = (
                        self._count_resources_per_chapter(items) if section == "chapters" else {}
                    )
                    for item in items:
                        external_id = str(item.get("external_id") or "")
                        kind = str(item.get("kind") or "")
                        if not external_id or not kind:
                            continue
                        keys.add((kind, external_id))
                        if section == "chapters" and kind == "chapter":
                            item_metadata = dict(item.get("metadata") or {})
                            fp = self._resource_fingerprint(items, external_id)
                            sig = self._chapter_signature(item, new_resource_counts.get(external_id, 0), fp)
                            item_metadata["sync_signature"] = sig
                            item["metadata"] = item_metadata
                        saved_item = self.repository.upsert_item(
                            user_id=user_id, course_id=course_id, kind=kind,
                            external_id=external_id, title=item.get("title") or "无标题",
                            **{key: value for key, value in item.items()
                               if key not in {"kind", "external_id", "title"}},
                        )
                        if section == "chapters" and kind == "chapter":
                            saved_chapters.append(saved_item)
                    if status == "complete":
                        if unchanged_chapter_ids and section in ("materials", "exams"):
                            existing_items = self.repository.list_items(
                                user_id=user_id, course_id=course_id,
                                include_stale=True, page_size=1000,
                            )
                            section_kinds = self.SECTION_KINDS[section]
                            for existing_item in existing_items:
                                parent = str(existing_item.parent_external_id or "")
                                if parent in unchanged_chapter_ids and existing_item.kind in section_kinds:
                                    keys.add((str(existing_item.kind), str(existing_item.external_id)))
                        self.repository.mark_section_stale_except(
                            user_id=user_id, course_id=course_id,
                            kinds=self.SECTION_KINDS[section], external_keys=keys,
                        )
                if section == "exams" and status in {"complete", "partial"}:
                    self._persist_exams(
                        user_id=user_id, course_id=course_id, items=items,
                        course_external_id=str(course.external_id or ""),
                    )
                error = result.get("error")
                section_row = self.repository.upsert_section_status(
                    user_id=user_id, course_id=course_id, section=section,
                    status=status, item_count=len(items), error_code=error,
                    error_message=error,
                )
                if section == "chapters" and section_row.status == "complete":
                    event_service = getattr(self.container, "learner_event_service", None)
                    project_safely = getattr(event_service, "project_safely", None)
                    if callable(project_safely):
                        for chapter in saved_chapters:
                            project_safely(
                                action="chapter_completed",
                                subject_type="chapter",
                                subject_id=chapter.id,
                                callback=lambda chapter=chapter: event_service.record_chaoxing_chapter_completed(
                                    chapter, section_status=section_row.status
                                ),
                            )
                section_results[section] = {"status": status, "item_count": len(items), "error": error}
        finally:
            await client.client.aclose()
        return {
            "course_id": course_id,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "depth": depth,
            "sections": section_results,
        }
