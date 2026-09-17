"""学习通全局同步的考试链路、section 失败隔离与只读边界。

覆盖: 考试入口解析与幂等、同名不同外部 ID 不误合并、同一外部 ID 更新不重复插入、
单段失败不丢其它段数据、上游空数据与抓取失败可区分、学习通条目不能在
个人待办接口里被伪造成已完成。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.routes.chaoxing import _status_cache, sync_chaoxing
from app.core.config import Settings
from app.database.sqlite_db import Database
from app.main import create_app
from app.models.multi_role import UserRow
from app.repositories.chaoxing_repository import ChaoxingRepository
from app.repositories.multi_role_repository import CourseRepository
from app.repositories.personal_task_repository import PersonalTaskRepository
from app.services.chaoxing.ChaoxingClient import ChaoxingClient, ChaoxingFetchError
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


@pytest.fixture
def db() -> Database:
    _status_cache.clear()
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


@pytest.fixture
def mock_httpx_client():
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        yield mock_get


class MockContainer:
    def __init__(self, db: Database):
        self.db = db
        self.chaoxing_repository = ChaoxingRepository(db)
        self.course_repository = CourseRepository(db)
        self.personal_task_repository = PersonalTaskRepository(db)


def _user() -> UserRow:
    return UserRow(id="user1", username="test1", password_hash="test",
                   role="student", display_name="test", created_at="", updated_at="")


def _response(text: str, status_code: int = 200):
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.raise_for_status = MagicMock()
    return response


COURSES_HTML = """
    <li class="course">
        <span class="course-name">高等数学</span>
        <a href="/mycourse/stu?courseid=111&clazzid=222">链接</a>
    </li>
"""

COURSE_PAGE_HTML = """
    <html>
        <input name="courseid" value="111" />
        <input name="clazzid" value="222" />
        <a title="作业" data-url="/work">作业</a>
        <input name="workEnc" value="enc" />
    </html>
"""

ASSIGNMENTS_HTML = """
    <html>
        <li class="work-item">
            <div class="work-title">第一次作业</div>
            <div class="work-deadline">2026-09-20</div>
            <a href="/work?workId=99991">去完成</a>
            <span class="status">未交</span>
        </li>
    </html>
"""

EMPTY_NOTICES = "<html></html>"


def _notices_response():
    response = _response(EMPTY_NOTICES)
    response.json.side_effect = Exception("Not JSON")
    return response


def _exam_candidate(external_id: str, title: str, *, exam_at=None, score=None):
    return {
        "kind": "exam_candidate",
        "external_id": external_id,
        "title": title,
        "parent_external_id": "chapter-1",
        "status": "unknown",
        "source_url": "https://mooc1.chaoxing.com/knowledge/cards?knowledgeid=chapter-1",
        "metadata": {
            "candidate_type": "test",
            "course_id": "111",
            "clazz_id": "222",
            **({"exam_at": exam_at} if exam_at else {}),
            **({"score": score, "score_max": 100} if score is not None else {}),
        },
    }


async def _run_sync(db: Database, mock_get, *, candidates):
    container = MockContainer(db)
    container.chaoxing_repository.save_credentials("user1", {"cookie": "A"})
    mock_get.side_effect = [
        _response("", 404),                 # JSON 课程接口不可用 -> 回落 HTML
        _response(COURSES_HTML),
        _response(COURSE_PAGE_HTML),
        _response(ASSIGNMENTS_HTML),
        _response(COURSE_PAGE_HTML),
        _notices_response(),
    ]
    with patch.object(ChaoxingClient, "get_course_exam_candidates",
                      new=AsyncMock(return_value={"status": "complete",
                                                  "items": candidates, "error": None})):
        return await sync_chaoxing(user=_user(), container=container), container


# ---------- 考试链路 ----------

@pytest.mark.asyncio
async def test_global_sync_persists_exams_and_is_idempotent(db, mock_httpx_client):
    candidates = [_exam_candidate("9001", "期中测验", exam_at="2026-09-15T14:00:00+08:00")]
    first, container = await _run_sync(db, mock_httpx_client, candidates=candidates)

    exams = container.chaoxing_repository.list_exams(user_id="user1")
    assert len(exams) == 1
    assert exams[0]["title"] == "期中测验"
    assert exams[0]["exam_at"] == "2026-09-15T14:00:00+08:00"
    assert exams[0]["course_id"] is not None
    assert first["sections"]["exams"]["status"] == "complete"
    assert first["sections"]["exams"]["item_count"] == 1

    # 第二次同步: 同一外部 ID 只更新，不新增。
    second, container = await _run_sync(db, mock_httpx_client, candidates=candidates)
    exams = container.chaoxing_repository.list_exams(user_id="user1")
    assert len(exams) == 1
    assert second["stats"]["exams_created"] == 0


@pytest.mark.asyncio
async def test_same_title_different_external_id_creates_two_exams(db, mock_httpx_client):
    candidates = [
        _exam_candidate("9001", "单元测验"),
        _exam_candidate("9002", "单元测验"),
    ]
    _, container = await _run_sync(db, mock_httpx_client, candidates=candidates)

    exams = container.chaoxing_repository.list_exams(user_id="user1")
    assert len(exams) == 2
    assert {exam["title"] for exam in exams} == {"单元测验"}


@pytest.mark.asyncio
async def test_same_external_id_updates_status_without_duplicate(db, mock_httpx_client):
    _, container = await _run_sync(
        db, mock_httpx_client, candidates=[_exam_candidate("9001", "期中测验")]
    )
    _, container = await _run_sync(
        db, mock_httpx_client,
        candidates=[_exam_candidate("9001", "期中测验（改名）", score=95)],
    )

    exams = container.chaoxing_repository.list_exams(user_id="user1")
    assert len(exams) == 1
    assert exams[0]["title"] == "期中测验（改名）"
    assert exams[0]["score"] == 95


@pytest.mark.asyncio
async def test_exam_candidates_derived_from_chapter_attachments():
    """章节响应里的 work/test 附件就是考试入口；其它类型不得被误当成考试。"""
    client = ChaoxingClient()
    chapters = {
        "status": "complete",
        "error": None,
        "course_meta": {},
        "items": [
            {"kind": "chapter", "external_id": "chapter-1", "title": "第一章",
             "metadata": {"job_count": 2}},
            {"kind": "material", "external_id": "att-doc", "title": "讲义.pdf",
             "parent_external_id": "chapter-1",
             "metadata": {"attachment_type": "document"}},
            {"kind": "material", "external_id": "att-test", "title": "章节测验",
             "parent_external_id": "chapter-1",
             "metadata": {"attachment_type": "test"}},
            {"kind": "material", "external_id": "att-work", "title": "章节作业",
             "parent_external_id": "chapter-1",
             "metadata": {"attachment_type": "work"}},
        ],
    }
    with patch.object(ChaoxingClient, "get_course_chapters",
                      new=AsyncMock(return_value=chapters)):
        result = await client.get_course_exam_candidates(
            {"course_id": "111", "clazz_id": "222", "cpi": "333"}
        )
    await client.client.aclose()

    assert result["status"] == "complete"
    # 只有测验/考试进入考试链路；work(作业) 由作业链路负责，不能重复算成考试。
    assert {item["external_id"] for item in result["items"]} == {"att-test"}
    assert all(item["kind"] == "exam_candidate" for item in result["items"])
    assert all(item["metadata"]["candidate_type"] == "test" for item in result["items"])


@pytest.mark.asyncio
async def test_deep_exam_path_excludes_work_assignments():
    """deep 同步的考试候选同样只收 quiz/test，不收 task/work。"""
    client = ChaoxingClient()
    materials = {
        "status": "complete",
        "error": None,
        "items": [
            {"kind": "quiz", "external_id": "q1", "title": "章节测验",
             "metadata": {"raw_type": "test"}},
            {"kind": "task", "external_id": "w1", "title": "章节作业",
             "metadata": {"raw_type": "work"}},
        ],
    }
    with patch.object(ChaoxingClient, "get_course_materials",
                      new=AsyncMock(return_value=materials)):
        result = await client.get_course_exams({"course_id": "111", "clazz_id": "222"})
    await client.client.aclose()

    assert [item["external_id"] for item in result["items"]] == ["q1"]
    assert result["items"][0]["metadata"]["candidate_type"] == "test"


@pytest.mark.asyncio
async def test_exam_candidates_propagate_chapter_failure():
    client = ChaoxingClient()
    with patch.object(
        ChaoxingClient, "get_course_chapters",
        new=AsyncMock(return_value={"status": "unavailable", "items": [],
                                    "error": "missing_course_context"}),
    ):
        result = await client.get_course_exam_candidates({"course_id": "111"})
    await client.client.aclose()

    assert result["status"] == "unavailable"
    assert result["items"] == []


# ---------- section 失败隔离 ----------

@pytest.mark.asyncio
async def test_assignment_failure_keeps_courses_and_exams(db, mock_httpx_client):
    container = MockContainer(db)
    container.chaoxing_repository.save_credentials("user1", {"cookie": "A"})
    mock_httpx_client.side_effect = [
        _response("", 404),
        _response(COURSES_HTML),
        _response(COURSE_PAGE_HTML),
        _response(COURSE_PAGE_HTML),
        _notices_response(),
    ]
    with patch.object(ChaoxingClient, "get_all_assignments",
                      new=AsyncMock(side_effect=RuntimeError("boom"))), \
         patch.object(ChaoxingClient, "get_course_exam_candidates",
                      new=AsyncMock(return_value={"status": "complete", "items": [
                          _exam_candidate("9001", "期中测验")
                      ], "error": None})):
        result = await sync_chaoxing(user=_user(), container=container)

    # 作业段失败，但课程与考试段照常成功，且明确标记为 failed 而不是"0 条"。
    assert result["sections"]["assignments"]["status"] == "failed"
    assert result["sections"]["assignments"]["error_code"] == "unexpected_error"
    assert result["sections"]["courses"]["status"] == "complete"
    assert result["sections"]["exams"]["status"] == "complete"
    assert result["complete"] is False
    courses, total = container.course_repository.list_courses(owner_user_id="user1")
    assert total == 1
    assert len(container.chaoxing_repository.list_exams(user_id="user1")) == 1


@pytest.mark.asyncio
async def test_upstream_empty_is_complete_not_failed(db, mock_httpx_client):
    """上游真的没有作业时是 complete + 0 条，不能表现成抓取失败。"""
    container = MockContainer(db)
    container.chaoxing_repository.save_credentials("user1", {"cookie": "A"})
    mock_httpx_client.side_effect = [
        _response("", 404),
        _response(COURSES_HTML),
        _response(COURSE_PAGE_HTML),
        _response("<html></html>"),
        _response(COURSE_PAGE_HTML),
        _notices_response(),
    ]
    with patch.object(ChaoxingClient, "get_course_exam_candidates",
                      new=AsyncMock(return_value={"status": "complete",
                                                  "items": [], "error": None})):
        result = await sync_chaoxing(user=_user(), container=container)

    assert result["sections"]["assignments"]["status"] == "complete"
    assert result["sections"]["assignments"]["item_count"] == 0
    assert result["sections"]["exams"]["status"] == "complete"


@pytest.mark.asyncio
async def test_exam_section_partial_when_some_courses_fail(db, mock_httpx_client):
    container = MockContainer(db)
    container.chaoxing_repository.save_credentials("user1", {"cookie": "A"})
    mock_httpx_client.side_effect = [
        _response("", 404),
        _response(COURSES_HTML),
        _response(COURSE_PAGE_HTML),
        _response(ASSIGNMENTS_HTML),
        _response(COURSE_PAGE_HTML),
        _notices_response(),
    ]
    with patch.object(ChaoxingClient, "get_course_exam_candidates",
                      new=AsyncMock(side_effect=RuntimeError("boom"))):
        result = await sync_chaoxing(user=_user(), container=container)

    assert result["sections"]["exams"]["status"] == "failed"
    assert result["sections"]["assignments"]["status"] == "complete"
    assert result["sections"]["courses"]["status"] == "complete"


@pytest.mark.asyncio
async def test_revoked_session_reports_reauth_without_losing_cache(db, mock_httpx_client):
    container = MockContainer(db)
    container.chaoxing_repository.save_credentials("user1", {"cookie": "A"})
    mock_httpx_client.side_effect = [_response("用户登录 请登录", 200)]

    with pytest.raises(Exception) as error:
        await sync_chaoxing(user=_user(), container=container)

    assert getattr(error.value, "status_code", None) == 401
    assert error.value.detail == "reauth_required"


# ---------- 学习通条目只读 ----------

def _student_client() -> tuple[TestClient, object, dict[str, str]]:
    settings = Settings(
        app_env="test", database_url="sqlite:///:memory:",
        auto_seed_demo_users=True, auto_import_demo=False, llm_provider="none",
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/login",
                        json={"username": "student_demo", "password": "Demo123456"})
    assert login.status_code == 200
    return client, container, {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_chaoxing_task_cannot_be_completed_or_edited_via_personal_task_api():
    client, container, headers = _student_client()
    user = client.get("/api/v1/auth/me", headers=headers).json()["user"]
    row = container.personal_task_repository.create_task(
        user_id=user["id"], title="学习通作业", source="chaoxing", external_id="w1",
        deadline="2026-09-20T23:59:59+08:00", source_name="高等数学",
    )

    completed = client.post(f"/api/v1/tasks/{row.id}/complete", headers=headers)
    assert completed.status_code == 409
    assert client.post(f"/api/v1/tasks/{row.id}/restore", headers=headers).status_code == 409
    assert client.patch(f"/api/v1/tasks/{row.id}",
                        headers=headers, json={"title": "改个名"}).status_code == 409

    # 状态没有被本地操作改动，仍然由同步决定。
    unchanged = container.personal_task_repository.get_task(row.id, user_id=user["id"])
    assert unchanged.status == "pending"
    assert unchanged.title == "学习通作业"


def test_ordinary_personal_task_still_completable():
    client, container, headers = _student_client()
    user = client.get("/api/v1/auth/me", headers=headers).json()["user"]
    row = container.personal_task_repository.create_task(
        user_id=user["id"], title="个人待办", source_name="个人安排",
    )

    assert client.post(f"/api/v1/tasks/{row.id}/complete", headers=headers).status_code == 200
    assert client.post(f"/api/v1/tasks/{row.id}/restore", headers=headers).status_code == 200


# ---------- 通知段失败不能伪报成功 ----------

@pytest.mark.asyncio
async def test_notice_failure_is_reported_as_failed_not_complete(db, mock_httpx_client):
    """get_all_notices 抛异常时必须报 failed，而不是 complete + 0 条。"""
    container = MockContainer(db)
    container.chaoxing_repository.save_credentials("user1", {"cookie": "A"})
    mock_httpx_client.side_effect = [
        _response("", 404),
        _response(COURSES_HTML),
        _response(COURSE_PAGE_HTML),
        _response(ASSIGNMENTS_HTML),
        _response(COURSE_PAGE_HTML),
    ]
    with patch.object(ChaoxingClient, "get_course_exam_candidates",
                      new=AsyncMock(return_value={"status": "complete",
                                                  "items": [], "error": None})), \
         patch.object(ChaoxingClient, "get_all_notices",
                      new=AsyncMock(side_effect=RuntimeError("boom"))):
        result = await sync_chaoxing(user=_user(), container=container)

    notices = result["sections"]["notices"]
    assert notices["status"] == "failed"
    assert notices["item_count"] == 0
    assert notices["error_code"] == "unexpected_error:RuntimeError"
    assert notices["error_message"]
    # 其它段照常成功，整体不再被伪报为 complete。
    assert result["sections"]["courses"]["status"] == "complete"
    assert result["sections"]["assignments"]["status"] == "complete"
    assert result["complete"] is False
    assert any("notices" in warning for warning in result["warnings"])


@pytest.mark.asyncio
async def test_notice_fetch_error_code_is_propagated(db, mock_httpx_client):
    """上游明确报错时，error_code 要带出来，而不是退化成 complete。"""
    container = MockContainer(db)
    container.chaoxing_repository.save_credentials("user1", {"cookie": "A"})
    mock_httpx_client.side_effect = [
        _response("", 404),
        _response(COURSES_HTML),
        _response(COURSE_PAGE_HTML),
        _response(ASSIGNMENTS_HTML),
        _response(COURSE_PAGE_HTML),
    ]
    with patch.object(ChaoxingClient, "get_course_exam_candidates",
                      new=AsyncMock(return_value={"status": "complete",
                                                  "items": [], "error": None})), \
         patch.object(ChaoxingClient, "get_all_notices",
                      new=AsyncMock(side_effect=ChaoxingFetchError("http_error_500"))):
        result = await sync_chaoxing(user=_user(), container=container)

    notices = result["sections"]["notices"]
    assert notices["status"] == "failed"
    assert notices["error_code"] == "http_error_500"
    assert result["complete"] is False


@pytest.mark.asyncio
async def test_notice_partial_when_some_courses_fail(db, mock_httpx_client):
    """逐课程抓通知时：部分失败 = partial，全失败 = failed。"""
    container = MockContainer(db)
    container.chaoxing_repository.save_credentials("user1", {"cookie": "A"})
    mock_httpx_client.side_effect = [
        _response("", 404),
        _response(COURSES_HTML),
        _response(COURSE_PAGE_HTML),
        _response(ASSIGNMENTS_HTML),
        _response(COURSE_PAGE_HTML),
    ]
    original = ChaoxingClient.get_all_notices
    del ChaoxingClient.get_all_notices
    try:
        with patch.object(ChaoxingClient, "get_course_exam_candidates",
                          new=AsyncMock(return_value={"status": "complete",
                                                      "items": [], "error": None})), \
             patch.object(ChaoxingClient, "get_notices",
                          new=AsyncMock(side_effect=ChaoxingFetchError("http_error_500"))):
            result = await sync_chaoxing(user=_user(), container=container)
    finally:
        ChaoxingClient.get_all_notices = original

    notices = result["sections"]["notices"]
    assert notices["status"] == "failed"
    assert notices["error_code"] == "http_error_500"
    assert "1/1" in notices["error_message"]


# ---------- 成功来源数不能被条目数代替 ----------

TWO_COURSES_HTML = """
    <li class="course">
        <span class="course-name">高等数学</span>
        <a href="/mycourse/stu?courseid=111&clazzid=222">链接</a>
    </li>
    <li class="course">
        <span class="course-name">线性代数</span>
        <a href="/mycourse/stu?courseid=333&clazzid=444">链接</a>
    </li>
"""


def _url_router(*, courses_html=TWO_COURSES_HTML, work_html=ASSIGNMENTS_HTML):
    """按 URL 分派假响应，不依赖请求顺序（多课程场景下顺序很脆）。"""
    def handler(url, **kwargs):
        target = str(url)
        if "backclazzdata" in target:
            # JSON 课程接口不可用 -> 回落 HTML
            return _response("", 404)
        if "visit/courses/list" in target:
            return _response(courses_html)
        if "work" in target:
            return _response(work_html)
        # 课程页：提供 courseid/clazzid/workEnc 供上下文提取
        return _response(COURSE_PAGE_HTML)
    return handler


async def _run_sync_with(db, mock_get, *, notice_side_effect=None, exam_side_effect=None):
    container = MockContainer(db)
    container.chaoxing_repository.save_credentials("user1", {"cookie": "A"})
    mock_get.side_effect = _url_router()

    original_notices = ChaoxingClient.get_all_notices
    # 走逐课程通知路径（才能构造"一个成功一个失败"）
    del ChaoxingClient.get_all_notices
    try:
        patches = []
        if exam_side_effect is not None:
            patches.append(patch.object(ChaoxingClient, "get_course_exam_candidates",
                                        new=AsyncMock(side_effect=exam_side_effect)))
        else:
            patches.append(patch.object(ChaoxingClient, "get_course_exam_candidates",
                                        new=AsyncMock(return_value={"status": "complete",
                                                                    "items": [], "error": None})))
        if notice_side_effect is not None:
            patches.append(patch.object(ChaoxingClient, "get_notices",
                                        new=AsyncMock(side_effect=notice_side_effect)))
        for item in patches:
            item.start()
        try:
            return await sync_chaoxing(user=_user(), container=container)
        finally:
            for item in patches:
                item.stop()
    finally:
        ChaoxingClient.get_all_notices = original_notices


@pytest.mark.asyncio
async def test_notice_partial_when_one_source_is_empty_and_another_fails(db, mock_httpx_client):
    """一个来源成功但返回 0 条 + 一个来源失败 = partial（不是 failed）。"""
    result = await _run_sync_with(
        db, mock_httpx_client,
        notice_side_effect=[[], ChaoxingFetchError("http_error_500")],
    )

    notices = result["sections"]["notices"]
    assert notices["item_count"] == 0
    assert notices["status"] == "partial", "成功但空的一次抓取不能被当成失败"
    assert notices["error_code"] == "http_error_500"
    assert result["complete"] is False


@pytest.mark.asyncio
async def test_notice_failed_only_when_every_source_fails(db, mock_httpx_client):
    result = await _run_sync_with(
        db, mock_httpx_client,
        notice_side_effect=[ChaoxingFetchError("http_error_500"),
                            ChaoxingFetchError("http_error_500")],
    )

    notices = result["sections"]["notices"]
    assert notices["status"] == "failed"
    assert notices["error_message"] == "2/2 个通知来源抓取失败"


@pytest.mark.asyncio
async def test_notice_complete_when_all_sources_succeed_but_empty(db, mock_httpx_client):
    """全部来源都成功返回空 —— 这是 complete + 0 条，不是 failed。"""
    result = await _run_sync_with(db, mock_httpx_client, notice_side_effect=[[], []])

    notices = result["sections"]["notices"]
    assert notices["status"] == "complete"
    assert notices["item_count"] == 0
    assert notices["error_code"] is None


@pytest.mark.asyncio
async def test_exam_partial_when_one_course_empty_and_another_fails(db, mock_httpx_client):
    """考试链路同理：成功但 0 条 + 另一门失败 = partial，不是 failed。"""
    result = await _run_sync_with(
        db, mock_httpx_client,
        notice_side_effect=[[], []],
        exam_side_effect=[
            {"status": "complete", "items": [], "error": None},
            RuntimeError("boom"),
        ],
    )

    exams = result["sections"]["exams"]
    assert exams["status"] == "partial", "exams_fetched=0 不能推断成全部失败"
    assert exams["item_count"] == 0
    assert exams["error_code"]
    assert "1/2" in exams["error_message"]


@pytest.mark.asyncio
async def test_exam_failed_only_when_every_course_fails(db, mock_httpx_client):
    result = await _run_sync_with(
        db, mock_httpx_client,
        notice_side_effect=[[], []],
        exam_side_effect=[RuntimeError("boom"), RuntimeError("boom")],
    )

    exams = result["sections"]["exams"]
    assert exams["status"] == "failed"
    assert exams["error_message"] == "2/2 门课程的考试入口抓取失败"


@pytest.mark.asyncio
async def test_exam_complete_when_all_courses_succeed_but_empty(db, mock_httpx_client):
    result = await _run_sync_with(
        db, mock_httpx_client,
        notice_side_effect=[[], []],
        exam_side_effect=[
            {"status": "complete", "items": [], "error": None},
            {"status": "complete", "items": [], "error": None},
        ],
    )

    assert result["sections"]["exams"]["status"] == "complete"
    assert result["sections"]["exams"]["item_count"] == 0
