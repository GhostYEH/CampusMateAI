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
        owner_user_id=user_id,
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
        owner_user_id="user1",
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
    registered = {(method, route.path) for route in app.routes for method in (getattr(route, "methods", None) or set())}
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

    result = ChaoxingParser.parse_chapter_card_resources(html, chapter_id="101", card_url="https://mooc1.chaoxing.com/mooc-ans/knowledge/cards")
    items = result["items"]

    assert [(item["kind"], item["title"], item["remote_object_id"]) for item in items] == [
        ("video", "第一讲.mp4", "video-object"),
        ("document", "实验讲义.pdf", "doc-object"),
        ("poll", "课堂投票", None),
    ]
    assert all(item["parent_external_id"] == "101" for item in items)
    assert result["status"] == "complete"


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


def test_chapter_signature_detects_resource_replacement():
    """P1: 附件替换但数量不变时 signature 必须变化。"""
    from app.services.chaoxing.course_content_sync import ChaoxingCourseContentSyncService

    chapter = {"external_id": "101", "title": "第一章", "status": "unknown",
               "metadata": {"job_count": 1, "raw_status": 0}}
    items_a = [{"kind": "video", "external_id": "501", "parent_external_id": "101", "remote_object_id": "obj-a"}]
    items_b = [{"kind": "video", "external_id": "502", "parent_external_id": "101", "remote_object_id": "obj-b"}]

    fp_a = ChaoxingCourseContentSyncService._resource_fingerprint(items_a, "101")
    fp_b = ChaoxingCourseContentSyncService._resource_fingerprint(items_b, "101")
    sig_a = ChaoxingCourseContentSyncService._chapter_signature(chapter, 1, fp_a)
    sig_b = ChaoxingCourseContentSyncService._chapter_signature(chapter, 1, fp_b)

    assert sig_a != sig_b, "替换附件后 signature 必须不同"

    fp_same = ChaoxingCourseContentSyncService._resource_fingerprint(items_a, "101")
    sig_same = ChaoxingCourseContentSyncService._chapter_signature(chapter, 1, fp_same)
    assert sig_a == sig_same, "相同附件 signature 必须一致"


def test_chapter_card_parser_returns_structure_changed_for_login_page():
    """登录页面被当作课程页时必须返回 structure_changed 而非 empty。"""
    html = '<div class="knowledge-card"><form>用户登录</form></div>'
    result = ChaoxingParser.parse_chapter_card_resources(
        html, chapter_id="101", card_url="https://mooc1.chaoxing.com/card"
    )
    assert result["status"] == "structure_changed"
    assert result["error"] == "marg_not_found"


def test_chapter_card_parser_returns_empty_for_genuine_empty_page():
    """真正没有资源的页面返回 empty。"""
    html = "<html><body>本章无内容</body></html>"
    result = ChaoxingParser.parse_chapter_card_resources(
        html, chapter_id="101", card_url="https://mooc1.chaoxing.com/card"
    )
    assert result["status"] == "empty"
    assert result["error"] is None


def test_chapter_card_parser_returns_structure_changed_for_bad_json():
    """mArg JSON 格式损坏返回 structure_changed。"""
    html = '<script>mArg = {broken json};</script>'
    result = ChaoxingParser.parse_chapter_card_resources(
        html, chapter_id="101", card_url="https://mooc1.chaoxing.com/card"
    )
    assert result["status"] == "structure_changed"
    assert result["error"] == "marg_parse_failed"


def test_resource_proxy_rejects_non_chaoxing_host():
    """SSRF: 非 Chaoxing 域名必须被拒绝。"""
    from app.services.chaoxing.resource_proxy import ChaoxingResourceProxy, CourseResourceProxyError

    for url in [
        "https://127.0.0.1/secret",
        "https://localhost/admin",
        "https://169.254.169.254/latest/meta-data",
        "http://chaoxing.com/course",
        "ftp://chaoxing.com/file",
    ]:
        try:
            ChaoxingResourceProxy.validate_url(url)
            assert False, f"URL 应被拒绝: {url}"
        except CourseResourceProxyError as e:
            assert e.code == "resource_host_not_allowed"


def test_resource_proxy_allows_chaoxing_subdomain():
    """Chaoxing 子域名应被允许。"""
    from app.services.chaoxing.resource_proxy import ChaoxingResourceProxy

    for url in [
        "https://ananas.chaoxing.com/file/123",
        "https://d0.ananas.chaoxing.com/file/456",
        "https://mooc1-api.chaoxing.com/gas/clazz",
    ]:
        assert ChaoxingResourceProxy.validate_url(url) == url


@pytest.mark.asyncio
async def test_stream_file_passes_follow_redirects_to_send_not_build_request():
    """P1: follow_redirects 必须传给 send()，不能传给 build_request()。

    httpx 0.28.1 的 AsyncClient.build_request() 不接受 follow_redirects
    参数；传错会在发送前触发 TypeError，导致视频/音频流式代理 500。
    """
    item = MagicMock()
    item.source_url = "https://ananas.chaoxing.com/file/123"
    item.remote_object_id = None
    item.title = "video.mp4"
    item.id = "item1"
    item.user_id = "user1"

    build_request_calls: list[dict] = []
    send_calls: list[dict] = []

    response_mock = MagicMock()
    response_mock.status_code = 200
    response_mock.headers = {"content-type": "video/mp4", "content-length": "4"}
    response_mock.aclose = AsyncMock()

    def fake_build_request(*args, **kwargs):
        build_request_calls.append(kwargs)
        return MagicMock()

    async def fake_send(*args, **kwargs):
        send_calls.append(kwargs)
        return response_mock

    with patch("httpx.AsyncClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.build_request = fake_build_request
        mock_instance.send = fake_send
        mock_instance.aclose = AsyncMock()

        proxy = ChaoxingResourceProxy(
            settings=MagicMock(),
            repository=MagicMock(),
            credentials={},
        )
        await proxy.stream_file(item=item, range_header=None)

    assert build_request_calls, "build_request 应被调用"
    assert send_calls, "send 应被调用"
    for kwargs in build_request_calls:
        assert "follow_redirects" not in kwargs, "build_request 不应接受 follow_redirects"
    for kwargs in send_calls:
        assert kwargs.get("stream") is True, "send 必须传 stream=True"
        assert kwargs.get("follow_redirects") is False, "send 必须传 follow_redirects=False"


@pytest.mark.asyncio
async def test_unchanged_chapter_preserves_existing_materials_not_stale(db: Database):
    """P1/P2: signature 未变的 chapter 跳过 card 请求后，
    已有 materials 不应被 mark_section_stale_except 误标为 stale。
    """
    from app.services.chaoxing.course_content_sync import ChaoxingCourseContentSyncService

    course = _course(db, "user1", "11_22")
    repo = CourseContentRepository(db)

    chapter_dict = {
        "kind": "chapter", "external_id": "ch1", "title": "第一章",
        "status": "unknown", "metadata": {"job_count": 0, "raw_status": 0},
    }
    fp = ChaoxingCourseContentSyncService._resource_fingerprint([chapter_dict], "ch1")
    sig = ChaoxingCourseContentSyncService._chapter_signature(chapter_dict, 0, fp)

    repo.upsert_item(
        user_id="user1", course_id=course.id, kind="chapter",
        external_id="ch1", title="第一章",
        metadata={"sync_signature": sig, "job_count": 0, "raw_status": 0},
    )
    repo.upsert_item(
        user_id="user1", course_id=course.id, kind="document",
        external_id="doc1", title="讲义.pdf",
        parent_external_id="ch1",
    )

    container = MagicMock()
    container.course_repository.get_course.return_value = course
    container.chaoxing_repository.get_credentials.return_value = {"cookie": "val"}
    container.course_content_repository = repo

    mock_client = MagicMock()
    mock_client.client = MagicMock()
    mock_client.client.aclose = AsyncMock()
    mock_client.get_course_chapters = AsyncMock(return_value={
        "status": "complete", "items": [chapter_dict], "error": None,
    })
    mock_client.get_course_materials = AsyncMock(return_value={
        "status": "complete", "items": [], "error": None,
    })
    mock_client.get_course_exams = AsyncMock(return_value={
        "status": "complete", "items": [], "error": None,
    })
    mock_client.get_course_discussions = AsyncMock(return_value={
        "status": "complete", "items": [], "error": None,
    })

    with patch("app.services.chaoxing.course_content_sync.ChaoxingClient", return_value=mock_client):
        service = ChaoxingCourseContentSyncService(container)
        await service.sync_course(user_id="user1", course_id=course.id, depth="deep")

    items = repo.list_items(user_id="user1", course_id=course.id, kind="document", include_stale=True)
    assert len(items) == 1
    assert not items[0].is_stale, "unchanged chapter 的已有 material 不应被标记 stale"


@pytest.mark.asyncio
async def test_chapter_with_job_count_not_skipped_for_card_only_detection(db: Database):
    """P2: job_count > 0 的 chapter 即使 signature 匹配也不应跳过 card 请求，
    否则 card-only 内容（test/work/vote）的变化无法被检测。
    """
    from app.services.chaoxing.course_content_sync import ChaoxingCourseContentSyncService

    course = _course(db, "user1", "11_22")
    repo = CourseContentRepository(db)

    chapter_dict = {
        "kind": "chapter", "external_id": "ch1", "title": "第一章",
        "status": "unknown", "metadata": {"job_count": 2, "raw_status": 0},
    }
    fp = ChaoxingCourseContentSyncService._resource_fingerprint([chapter_dict], "ch1")
    sig = ChaoxingCourseContentSyncService._chapter_signature(chapter_dict, 0, fp)

    repo.upsert_item(
        user_id="user1", course_id=course.id, kind="chapter",
        external_id="ch1", title="第一章",
        metadata={"sync_signature": sig, "job_count": 2, "raw_status": 0},
    )

    container = MagicMock()
    container.course_repository.get_course.return_value = course
    container.chaoxing_repository.get_credentials.return_value = {"cookie": "val"}
    container.course_content_repository = repo

    mock_client = MagicMock()
    mock_client.client = MagicMock()
    mock_client.client.aclose = AsyncMock()
    mock_client.get_course_chapters = AsyncMock(return_value={
        "status": "complete", "items": [chapter_dict], "error": None,
    })
    mock_client.get_course_materials = AsyncMock(return_value={
        "status": "complete", "items": [], "error": None,
    })
    mock_client.get_course_exams = AsyncMock(return_value={
        "status": "complete", "items": [], "error": None,
    })
    mock_client.get_course_discussions = AsyncMock(return_value={
        "status": "complete", "items": [], "error": None,
    })

    with patch("app.services.chaoxing.course_content_sync.ChaoxingClient", return_value=mock_client):
        service = ChaoxingCourseContentSyncService(container)
        await service.sync_course(user_id="user1", course_id=course.id, depth="deep")

    _, kwargs = mock_client.get_course_materials.call_args
    skip_ids = kwargs.get("unchanged_chapter_ids") or set()
    assert "ch1" not in skip_ids, "job_count > 0 的 chapter 不应被跳过"
