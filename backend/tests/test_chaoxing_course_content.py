from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.database.sqlite_db import Database
from app.repositories.course_content_repository import CourseContentRepository
from app.repositories.multi_role_repository import CourseRepository
from app.services.chaoxing.ChaoxingClient import ChaoxingClient, ChaoxingParser
from app.services.chaoxing.resource_proxy import ChaoxingResourceProxy, CourseResourceProxyError


@pytest.fixture
def db() -> Database:
    database = Database(None)
    with database.transaction() as conn:
        for user_id in ("user1", "user2"):
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, user_id, "hash", "now", "now"),
            )
    yield database
    database.dispose()


def _course(db: Database, user_id: str, external_id: str):
    return CourseRepository(db).create_course(
        name="离散数学",
        teacher_id=user_id,
        provider="chaoxing",
        external_id=external_id,
        status="active",
    )


def test_course_content_schema_and_indexes_are_created(db: Database):
    with db.query() as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        indexes = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }

    assert {"course_content_items", "course_sync_sections", "course_resource_cache"} <= tables
    assert "idx_course_content_lookup" in indexes
    assert "idx_course_sync_sections_course" in indexes


def test_course_content_upsert_is_idempotent_and_isolated_by_user(db: Database):
    first_course = _course(db, "user1", "11_22")
    second_course = _course(db, "user2", "11_22")
    repository = CourseContentRepository(db)

    first = repository.upsert_item(
        user_id="user1",
        course_id=first_course.id,
        kind="chapter",
        external_id="chapter-1",
        title="第一章",
        position=1,
    )
    updated = repository.upsert_item(
        user_id="user1",
        course_id=first_course.id,
        kind="chapter",
        external_id="chapter-1",
        title="第一章（更新）",
        position=2,
    )
    other_user = repository.upsert_item(
        user_id="user2",
        course_id=second_course.id,
        kind="chapter",
        external_id="chapter-1",
        title="另一账号的第一章",
        position=1,
    )

    assert updated.id == first.id
    assert updated.title == "第一章（更新）"
    assert updated.position == 2
    assert other_user.id != first.id
    assert repository.count_items(user_id="user1", course_id=first_course.id) == 1
    assert repository.count_items(user_id="user2", course_id=second_course.id) == 1


def test_course_sync_section_upsert_distinguishes_empty_from_failure(db: Database):
    course = _course(db, "user1", "11_22")
    repository = CourseContentRepository(db)

    complete = repository.upsert_section_status(
        user_id="user1",
        course_id=course.id,
        section="materials",
        status="complete",
        item_count=0,
    )
    failed = repository.upsert_section_status(
        user_id="user1",
        course_id=course.id,
        section="discussions",
        status="failed",
        item_count=3,
        error_code="structure_changed",
        error_message="学习通页面结构发生变化",
    )

    assert complete.status == "complete"
    assert complete.item_count == 0
    assert complete.error_code is None
    assert failed.status == "failed"
    assert failed.item_count == 3
    assert failed.error_code == "structure_changed"


def test_course_remote_context_round_trips(db: Database):
    repository = CourseRepository(db)
    course = repository.create_course(
        name="程序设计实践",
        teacher_id="user1",
        remote_teacher_name="米老师",
        provider="chaoxing",
        external_id="33_44",
        remote_class_id="44",
        remote_cpi="55",
        remote_school_name="示例大学",
        remote_class_name="程序设计一班",
        remote_student_count=77,
        cover_url="https://p.ananas.chaoxing.com/star3/example.jpg",
        starts_at="2026-03-01T00:00:00+00:00",
        ends_at="2026-07-01T00:00:00+00:00",
        status="active",
    )

    assert course.remote_class_id == "44"
    assert course.remote_cpi == "55"
    assert course.remote_school_name == "示例大学"
    assert course.remote_class_name == "程序设计一班"
    assert course.remote_student_count == 77
    assert course.cover_url.endswith("example.jpg")


def test_course_content_unique_constraint_matches_repository_contract(db: Database):
    course = _course(db, "user1", "11_22")
    repository = CourseContentRepository(db)
    repository.upsert_item(
        user_id="user1",
        course_id=course.id,
        kind="document",
        external_id="file-1",
        title="讲义.pdf",
    )

    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute(
                """INSERT INTO course_content_items
                   (id, user_id, course_id, provider, external_id, kind, title,
                    position, depth, status, is_stale, created_at, updated_at)
                   VALUES (?, ?, ?, 'chaoxing', ?, ?, ?, 0, 0, 'unknown', 0, 'now', 'now')""",
                ("duplicate", "user1", course.id, "file-1", "document", "重复"),
            )


def test_cache_pruning_returns_oldest_entries_until_under_limit(db: Database):
    course = _course(db, "user1", "11_22")
    repository = CourseContentRepository(db)
    first = repository.upsert_item(user_id="user1", course_id=course.id, kind="document", external_id="f1", title="一.pdf")
    second = repository.upsert_item(user_id="user1", course_id=course.id, kind="document", external_id="f2", title="二.pdf")
    repository.upsert_cache(item_id=first.id, user_id="user1", course_id=course.id, relative_path="aa/first", content_hash="a", mime_type="application/pdf", file_size=60)
    repository.upsert_cache(item_id=second.id, user_id="user1", course_id=course.id, relative_path="bb/second", content_hash="b", mime_type="application/pdf", file_size=60)
    with db.transaction() as conn:
        conn.execute("UPDATE course_resource_cache SET last_accessed_at='2026-01-01' WHERE item_id=?", (first.id,))

    removed = repository.prune_cache(max_bytes=100)

    assert removed == ["aa/first"]
    assert repository.get_cache(item_id=first.id, user_id="user1") is None
    assert repository.get_cache(item_id=second.id, user_id="user1") is not None


def test_invalid_cache_record_can_be_removed_for_safe_refetch(db: Database):
    course = _course(db, "user1", "11_22")
    repository = CourseContentRepository(db)
    item = repository.upsert_item(
        user_id="user1", course_id=course.id, kind="document",
        external_id="bad-cache", title="资料.docx",
    )
    repository.upsert_cache(
        item_id=item.id, user_id="user1", course_id=course.id,
        relative_path="bad/response", content_hash="bad",
        mime_type="application/json", file_size=88,
    )

    removed = repository.delete_cache(item_id=item.id, user_id="user1")

    assert removed == "bad/response"
    assert repository.get_cache(item_id=item.id, user_id="user1") is None


def test_course_content_routes_are_registered():
    from app.main import app
    registered = {(method, route.path) for route in app.routes for method in route.methods or set()}
    assert ("GET", "/api/v1/courses/{course_id}/content-summary") in registered
    assert ("GET", "/api/v1/courses/{course_id}/content") in registered
    assert ("POST", "/api/v1/courses/{course_id}/sync") in registered
    assert ("GET", "/api/v1/courses/{course_id}/resources/{item_id}/download") in registered


def test_proxy_accepts_signed_cldisk_download_but_rejects_plain_http():
    signed = "https://d0.cldisk.com/download/object?at_=1&ak_=2&ad_=3"
    assert ChaoxingResourceProxy.validate_url(signed) == signed
    with pytest.raises(CourseResourceProxyError):
        ChaoxingResourceProxy.validate_url(signed.replace("https://", "http://"))


def test_course_parser_preserves_remote_context():
    courses = ChaoxingParser.parse_courses_json({
        "channelList": [{
            "content": {
                "id": 22,
                "cpi": 55,
                "name": "程序设计一班",
                "studentcount": 77,
                "beginDate": "2026-03-01 08:00",
                "endDate": "2026-07-01 18:00",
                "course": {"data": [{
                    "id": 11,
                    "name": "程序设计实践",
                    "teacherfactor": "米老师",
                    "schools": "示例大学",
                    "imageurl": "https://p.ananas.chaoxing.com/star3/example.jpg",
                }]},
            }
        }]
    })

    assert courses[0] | {} == {
        "name": "程序设计实践",
        "link": "https://mooc2-ans.chaoxing.com/mycourse/stu?courseid=11&clazzid=22",
        "course_id": "11",
        "clazz_id": "22",
        "external_id": "11_22",
        "teacher_name": "米老师",
        "cpi": "55",
        "school_name": "示例大学",
        "class_name": "程序设计一班",
        "student_count": 77,
        "cover_url": "https://p.ananas.chaoxing.com/star3/example.jpg",
        "starts_at": "2026-03-01 08:00",
        "ends_at": "2026-07-01 18:00",
    }


def test_chapter_parser_builds_tree_and_attachment_metadata():
    result = ChaoxingParser.parse_course_chapters({
        "data": [{
            "id": 22,
            "course": {"data": [{
                "id": 11,
                "knowledge": {"data": [
                    {"id": 101, "name": "第一章", "indexOrder": 1, "parentnodeid": 0, "layer": 1, "jobcount": 2},
                    {
                        "id": 102,
                        "name": "1.1 基础",
                        "indexOrder": 2,
                        "parentnodeid": 101,
                        "layer": 2,
                        "attachment": {"data": [
                            {"id": 501, "type": "video", "objectid": "video-object", "extension": "mp4"},
                            {"id": 502, "type": "document", "objectid": "doc-object", "extension": "pdf"},
                        ]},
                    },
                ]},
            }]},
        }]
    }, course_id="11", clazz_id="22", cpi="55")

    assert [(item["external_id"], item["parent_external_id"], item["depth"]) for item in result["chapters"]] == [
        ("101", None, 0), ("102", "101", 1)
    ]
    assert [(item["kind"], item["remote_object_id"], item["parent_external_id"]) for item in result["resources"]] == [
        ("video", "video-object", "102"), ("document", "doc-object", "102")
    ]


def test_card_parser_extracts_real_video_and_document_metadata():
    html = '''<script>mArg = {"attachments":[
      {"aid":1001,"type":"video","objectId":"video-object","property":{"name":"第一讲.mp4","size":123,"type":".mp4"}},
      {"aid":1002,"type":"document","property":{"objectid":"doc-object","name":"实验讲义.pdf","size":456,"type":".pdf"}},
      {"aid":1003,"type":"vote","property":{"title":"课堂投票"}}
    ]};</script>'''

    items = ChaoxingParser.parse_chapter_card_resources(html, chapter_id="101", card_url="https://mooc1.chaoxing.com/mooc-ans/knowledge/cards")

    assert [(item["kind"], item["title"], item["remote_object_id"]) for item in items] == [
        ("video", "第一讲.mp4", "video-object"),
        ("document", "实验讲义.pdf", "doc-object"),
        ("quiz", "课堂投票", None),
    ]
    assert all(item["parent_external_id"] == "101" for item in items)


@pytest.mark.asyncio
async def test_get_course_chapters_uses_mobile_read_only_request():
    response = MagicMock(status_code=200)
    response.raise_for_status = MagicMock()
    response.json.return_value = {"data": []}
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response) as request:
        result = await ChaoxingClient().get_course_chapters({
            "course_id": "11", "clazz_id": "22", "cpi": "55"
        })

    assert result["status"] == "complete"
    assert result["items"] == []
    _, kwargs = request.call_args
    assert kwargs["params"]["id"] == "22"
    assert kwargs["params"]["personid"] == "55"
    assert kwargs["params"]["view"] == "json"
    assert "knowledge.fields" in kwargs["params"]["fields"]
    assert "ChaoXingStudy" in kwargs["headers"]["User-Agent"]


@pytest.mark.asyncio
async def test_course_assignments_only_include_matching_course_and_class():
    client = ChaoxingClient()
    client.get_all_assignments = AsyncMock(return_value=[
        {"external_id": "w1", "title": "未完成作业", "course_id": "11", "clazz_id": "22", "status": "pending", "deadline": "2026-08-20", "link": "https://mooc2-ans.chaoxing.com/work/view?workId=w1"},
        {"external_id": "w2", "title": "其他班作业", "course_id": "11", "clazz_id": "99", "status": "pending"},
        {"external_id": "w3", "title": "已完成作业", "course_id": "11", "clazz_id": "22", "status": "completed"},
    ])

    result = await client.get_course_assignments({"course_id": "11", "clazz_id": "22"})

    assert result["status"] == "complete"
    assert [(item["external_id"], item["status"]) for item in result["items"]] == [
        ("w1", "pending"), ("w3", "completed")
    ]
    assert all(item["kind"] == "assignment" for item in result["items"])


@pytest.mark.asyncio
async def test_course_notices_match_course_and_keep_unscoped_account_notices_out():
    client = ChaoxingClient()
    client.get_all_notices = AsyncMock(return_value=[
        {"external_id": "n1", "title": "本课程通知", "course_id": "11", "clazz_id": "22", "creator_name": "王老师", "published_at": "2026-08-13"},
        {"external_id": "n2", "title": "全校通知", "course_id": None, "clazz_id": None},
        {"external_id": "n3", "title": "其他课程通知", "course_id": "33", "clazz_id": "44"},
    ])

    result = await client.get_course_notices({"course_id": "11", "clazz_id": "22"})

    assert result["status"] == "complete"
    assert [item["external_id"] for item in result["items"]] == ["n1"]
    assert result["items"][0]["author_name"] == "王老师"
    assert result["items"][0]["kind"] == "notice"
