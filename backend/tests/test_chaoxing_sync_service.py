"""同步服务脱离 HTTP 容器后仍保留逐条失败隔离、课程关联和重试幂等。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.database.sqlite_db import Database
from app.models.multi_role import UserRow
from app.repositories.chaoxing_repository import ChaoxingRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.notice_repository import NoticeRepository
from app.repositories.personal_task_repository import PersonalTaskRepository
from app.services.chaoxing.sync_service import ChaoxingSyncDependencies, ChaoxingSyncService


class BatchClient:
    async def get_courses(self):
        return True, [{
            "external_id": "course-remote", "course_id": "remote", "name": "测试课程",
            "link": "https://example.invalid/course",
        }]

    async def get_assignments_and_notices(self, link):
        return {"assignments": deepcopy([
            {"title": "无外部编号的作业"},
            {"external_id": "done", "title": "已交作业", "status": "completed", "score": 90, "score_max": 100},
            {"external_id": "pending", "title": "待交作业", "status": "pending"},
        ])}

    async def get_notices(self, link):
        return deepcopy([
            {"title": "无外部编号的通知"},
            {"external_id": "retry", "title": "抽取需要重试", "content": "整理复习清单"},
            {"external_id": "next", "title": "后续正常通知", "content": "准备课堂展示材料"},
        ])


class RetryExtraction:
    def __init__(self):
        self.attempts = []

    async def extract(self, content, **kwargs):
        self.attempts.append(content)
        if content == "整理复习清单" and self.attempts.count(content) == 1:
            raise RuntimeError("temporary extraction failure")
        return SimpleNamespace(actionable=True, task=content, source_text=content,
                               deadline=None, importance="medium")

    def check_duplicate(self, request, *, recent_notices):
        return SimpleNamespace(is_duplicate=False, matches=[])


@pytest.mark.asyncio
async def test_sync_service_continues_items_and_retries_without_duplicate_rows():
    database = Database(None)
    try:
        with database.transaction() as conn:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
                "VALUES ('u', 'u', 'hash', 'now', 'now')"
            )
        sync_repository = ChaoxingRepository(database)
        extraction = RetryExtraction()
        dependencies = ChaoxingSyncDependencies(
            course_repository=CourseRepository(database),
            personal_task_repository=PersonalTaskRepository(database),
            chaoxing_repository=sync_repository,
            sync_repository=sync_repository,
            notice_repository=NoticeRepository(database),
            notice_extraction=extraction,
        )
        service = ChaoxingSyncService(dependencies)
        user = UserRow(id="u", username="u", password_hash="hash", role="student",
                       created_at="now", updated_at="now")
        first = await service.sync(user, {"cookie": "test"}, BatchClient())
        assert first["stats"]["assignments_fetched"] == 3
        assert first["stats"]["assignments_created"] == 2
        assert first["stats"]["notices_fetched"] == 3
        assert first["stats"]["notices_created"] == 2
        with database.query() as conn:
            assert conn.execute("SELECT COUNT(*) FROM personal_tasks").fetchone()[0] == 3
            completed = conn.execute("SELECT status, score FROM personal_tasks WHERE external_id='done'").fetchone()
            assert tuple(completed) == ("completed", 90)
            assert conn.execute("SELECT COUNT(*) FROM notices WHERE external_id='retry'").fetchone()[0] == 1

        second = await service.sync(user, {"cookie": "test"}, BatchClient())
        assert second["stats"]["assignments_created"] == 0
        assert second["stats"]["notices_created"] == 0
        assert second["stats"]["notices_updated"] == 2
        # 已提取的后续通知跳过抽取，失败通知在原记录上补出待办。
        assert extraction.attempts == ["整理复习清单", "准备课堂展示材料", "整理复习清单"]
        with database.query() as conn:
            assert conn.execute("SELECT COUNT(*) FROM personal_tasks").fetchone()[0] == 4
            course_id = conn.execute("SELECT id FROM courses").fetchone()[0]
            assert {row[0] for row in conn.execute("SELECT course_id FROM personal_tasks")} == {course_id}
            assert {row[0] for row in conn.execute("SELECT course_id FROM notices")} == {course_id}
            assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        database.dispose()
