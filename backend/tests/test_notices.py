from app.api.routes.notices import list_notices
from app.database.sqlite_db import Database
from app.models.multi_role import UserRow
from app.repositories.notice_repository import NoticeRepository


def test_list_notices_exposes_only_current_users_chaoxing_notice():
    db = Database(None)
    try:
        with db.transaction() as conn:
            for user_id in ("user1", "user2"):
                conn.execute(
                    "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (user_id, user_id, "hash", "now", "now"),
                )
        notice_repo = NoticeRepository(db)
        notice_repo.create_or_update_notice(
            user_id="user1",
            source="chaoxing",
            external_id="same",
            title="用户一通知",
            source_url="https://example.test/1",
            published_at="1783209663000",
        )
        notice_repo.create_or_update_notice(
            user_id="user2",
            source="chaoxing",
            external_id="same",
            title="用户二通知",
            source_url="https://example.test/2",
        )

        class EmptyEnrollmentRepository:
            def list_user_classes(self, user_id):
                return []

        class EmptyAnnouncementRepository:
            def list_announcements(self, class_id, status, page, page_size):
                return [], 0

        container = type(
            "Container",
            (),
            {
                "notice_repository": notice_repo,
                "enrollment_repository": EmptyEnrollmentRepository(),
                "announcement_repository": EmptyAnnouncementRepository(),
                "class_group_repository": object(),
                "course_repository": object(),
            },
        )()
        user = UserRow(id="user1", username="user1", password_hash="hash", role="student")

        result = list_notices(
            unread_only=False, page=1, page_size=50, user=user, container=container
        )

        assert [item.title for item in result.items] == ["用户一通知"]
        assert result.items[0].kind == "unified"
        assert result.items[0].source_url == "https://example.test/1"
        assert result.items[0].time == "2026-07-05T00:01:03+00:00"
    finally:
        db.dispose()
