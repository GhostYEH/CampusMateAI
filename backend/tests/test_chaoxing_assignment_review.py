from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.api.routes import chaoxing_assignments
from app.database.sqlite_db import Database
from app.models.multi_role import UserRow
from app.repositories.chaoxing_repository import ChaoxingRepository
from app.services.chaoxing.assignment_content import (
    fetch_assignment_questions,
    parse_assignment_questions,
)
from app.services.chaoxing.assignment_sync import sync_assignment_contents
from app.services.chaoxing.ChaoxingClient import ChaoxingFetchError
from app.services.chaoxing.daily_sync import ChaoxingDailySyncWorker
from app.services.magicclass.fusion_client import MagicClassFusionClient
from test_magicclass_workspaces import _setup

QUESTIONS = [
    {"number": 1, "stem": "当x=2时，x+1是多少？", "options": ["A. 2", "B. 3", "C. 4"]}
]
WORK_URL = "https://mooc1.chaoxing.com/mooc-ans/work/view?workId=1"


@pytest.fixture
def repository():
    db = Database(None)
    with db.transaction() as conn:
        for user_id in ("u", "other"):
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at, updated_at) VALUES (?, ?, 'hash', 'now', 'now')",
                (user_id, user_id),
            )
    yield ChaoxingRepository(db)
    db.dispose()


def test_parser_preserves_option_text_and_math_without_student_answers_or_scripts():
    html = """<div class="questionLi"><h3 class="mark_name">1. <span class="colorShallow">(单选题, 5分)</span>求 x² <img alt="+y²" /></h3>
    <ul class="mark_letter"><li>A. <span>2</span></li><li>B. 3<script>secret()</script></li></ul>
    <textarea>我的答案和个人信息</textarea><div class="check_answer">我的答案 B</div></div>
    <div class="TiMu"><div class="Zy_TItle">判断 f(x)=x</div></div>"""
    questions = parse_assignment_questions(html)
    assert len(questions) == 2
    assert questions[0]["stem"] == "1. 求 x² +y²"
    assert questions[0]["options"] == ["A. 2", "B. 3"]
    assert "我的答案" not in str(questions)
    assert parse_assignment_questions("<p>暂不允许查看作业</p>") == []
    assert len(parse_assignment_questions(f'<div class="marBom60">{html}</div>')) == 2


@pytest.mark.asyncio
async def test_fetch_follows_authorized_report_and_rejects_redirect_to_external_host():
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/view"):
            return httpx.Response(
                200,
                text='<input name="workId" value="1"><input name="workAnswerId" value="2"><input name="courseId" value="3"><input name="classId" value="4">',
            )
        return httpx.Response(
            200,
            text='<div class="questionLi"><div class="mark_name">题干</div><ul class="mark_letter"><li>A.选项</li></ul></div>',
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        result = await fetch_assignment_questions(
            SimpleNamespace(client=http), WORK_URL
        )
    assert result[0]["options"] == ["A.选项"]
    assert len(requests) == 2
    assert all(request.method == "GET" for request in requests)
    requests.clear()

    def redirect(request):
        requests.append(request)
        return httpx.Response(
            302, headers={"location": "https://example.invalid/work/private"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(redirect)) as http:
        with pytest.raises(ChaoxingFetchError, match="assignment_url_not_allowed"):
            await fetch_assignment_questions(SimpleNamespace(client=http), WORK_URL)
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_content_failure_preserves_snapshot_and_recovers_on_submission(
    repository, monkeypatch
):
    now = datetime.now(timezone.utc).isoformat()
    repository.save_assignment_content(
        user_id="u",
        external_id="work",
        questions=QUESTIONS,
        remote_status="pending",
        fetched_at=now,
    )
    state = SimpleNamespace(
        user=UserRow("u", "u", "hash"), client=object(), now_iso=now, warnings=[]
    )
    state.client = SimpleNamespace(client=object())
    batches = [({}, [{"external_id": "work", "link": WORK_URL, "status": "completed"}])]
    fetch = AsyncMock(side_effect=ChaoxingFetchError("network_error"))
    monkeypatch.setattr(
        "app.services.chaoxing.assignment_sync.fetch_assignment_questions", fetch
    )
    assert await sync_assignment_contents(repository, state, batches) == "network_error"
    assert (
        repository.get_assignment_content(user_id="u", external_id="work")["questions"]
        == QUESTIONS
    )
    assert (
        repository.get_assignment_content(user_id="other", external_id="work") is None
    )
    fetch.side_effect = None
    fetch.return_value = QUESTIONS
    assert await sync_assignment_contents(repository, state, batches) is None
    assert (
        repository.get_assignment_content(user_id="u", external_id="work")[
            "remote_status"
        ]
        == "completed"
    )
    await sync_assignment_contents(repository, state, batches)
    assert fetch.await_count == 2
    state.now_iso = (datetime.fromisoformat(now) + timedelta(days=1)).isoformat()
    await sync_assignment_contents(repository, state, batches)
    assert fetch.await_count == 3


@pytest.mark.asyncio
async def test_bounded_content_batches_rotate_failures_instead_of_starving_later_works(
    repository, monkeypatch
):
    fetch = AsyncMock(side_effect=ChaoxingFetchError("network_error"))
    monkeypatch.setattr(
        "app.services.chaoxing.assignment_sync.fetch_assignment_questions", fetch
    )
    state = SimpleNamespace(
        user=UserRow("u", "u", "hash"),
        client=SimpleNamespace(client=object()),
        now_iso=datetime.now(timezone.utc).isoformat(),
        warnings=[],
    )
    batches = [
        (
            {},
            [
                {"external_id": str(i), "link": f"{WORK_URL}&item={i}"}
                for i in range(14)
            ],
        )
    ]
    await sync_assignment_contents(repository, state, batches)
    assert fetch.await_count == 12
    await sync_assignment_contents(repository, state, batches)
    assert fetch.call_args_list[12].args[1].endswith("item=12")
    assert fetch.call_args_list[13].args[1].endswith("item=13")


@pytest.mark.asyncio
async def test_daily_schedule_survives_worker_recreation_and_retries_partial_results(
    repository, monkeypatch
):
    repository.save_credentials("u", {"cookie": "test"})
    close = AsyncMock()
    monkeypatch.setattr(
        "app.services.chaoxing.daily_sync.ChaoxingClient",
        lambda **kw: SimpleNamespace(client=SimpleNamespace(aclose=close)),
    )
    sync = AsyncMock(return_value={"complete": True})
    container = SimpleNamespace(
        chaoxing_repository=repository,
        user_repository=SimpleNamespace(
            get_user_by_id=lambda uid: UserRow(uid, uid, "hash")
        ),
        chaoxing_sync_service=SimpleNamespace(sync=sync),
    )
    await ChaoxingDailySyncWorker(container).tick()
    await ChaoxingDailySyncWorker(container).tick()
    assert sync.await_count == close.await_count == 1
    now = datetime.now(timezone.utc)
    assert repository.due_auto_sync_users(now=now + timedelta(hours=23)) == []
    assert repository.due_auto_sync_users(now=now + timedelta(hours=25)) == ["u"]
    repository.reset_auto_sync("u")
    sync.return_value = {
        "complete": False,
        "warnings": ["assignment_content:network_error"],
    }
    await ChaoxingDailySyncWorker(container).tick()
    assert repository.due_auto_sync_users(now=now + timedelta(minutes=20)) == []
    assert repository.due_auto_sync_users(now=now + timedelta(minutes=35)) == ["u"]
    repository.delete_credentials("u")
    assert repository.due_auto_sync_users(now=now + timedelta(days=2)) == []


def test_daily_claim_is_exclusive_and_expired_lease_is_recoverable(repository):
    repository.save_credentials("u", {"cookie": "test"})
    now = datetime.now(timezone.utc)
    assert repository.claim_auto_sync(user_id="u", now=now)
    assert not repository.claim_auto_sync(user_id="u", now=now)
    assert repository.due_auto_sync_users(now=now + timedelta(minutes=14)) == []
    assert repository.claim_auto_sync(user_id="u", now=now + timedelta(minutes=16))


def test_finishing_old_sync_cannot_reconnect_or_overwrite_an_account(repository):
    repository.save_credentials("u", {"cookie": "old"})
    repository.delete_credentials("u")
    repository.touch_credentials("u", {"cookie": "old"})
    assert repository.get_credentials("u") is None
    repository.save_credentials("u", {"cookie": "new"})
    repository.touch_credentials("u", {"cookie": "old"})
    assert repository.get_credentials("u") == {"cookie": "new"}


def review_setup(script=None):
    container, transport, http, headers, course_id = _setup(script)
    client = MagicClassFusionClient(
        base_url=container.settings.magicclass_service_url,
        secret=container.settings.magicclass_internal_secret,
        transport=transport,
    )
    http.app.dependency_overrides[chaoxing_assignments._client] = lambda: client
    user = container.user_repository.get_user_by_username("student_demo")
    task = container.personal_task_repository.create_task(
        user_id=user.id,
        title="函数练习",
        source="chaoxing",
        external_id="work",
        course_id=course_id,
    )
    return container, transport, http, headers, user, task


def test_review_gates_submission_current_content_and_ownership_before_using_provider():
    container, transport, http, headers, user, task = review_setup()
    path = f"/api/v1/chaoxing/assignments/{task.id}"
    response = http.get(path + "/content", headers=headers)
    assert response.status_code == 200
    assert response.json()["available"] is False
    assert http.post(path + "/classroom", headers=headers).status_code == 409
    container.personal_task_repository.complete(task.id, user_id=user.id)
    assert (
        http.post(path + "/classroom", headers=headers).json()["message"]
        == "assignment_content_not_current"
    )
    assert http.get(path + "/content").status_code == 401
    assert (
        http.get(
            "/api/v1/chaoxing/assignments/missing/content", headers=headers
        ).status_code
        == 404
    )
    with container.db.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at, updated_at) VALUES ('other', 'other', 'hash', 'now', 'now')"
        )
        conn.execute("UPDATE personal_tasks SET user_id='other' WHERE id=?", (task.id,))
    assert http.get(path + "/content", headers=headers).status_code == 404
    assert transport.calls == []


def test_review_passes_real_questions_options_and_practice_requirements_with_stable_identity():
    script = [
        (200, {"llm": True}),
        (201, {"id": "ws_review"}),
        (201, {"source": "provider", "job": {"id": "job_review", "status": "queued"}}),
    ] * 2
    container, transport, http, headers, user, task = review_setup(script)
    container.personal_task_repository.complete(task.id, user_id=user.id)
    container.chaoxing_repository.save_assignment_content(
        user_id=user.id,
        external_id=task.external_id,
        questions=QUESTIONS,
        remote_status="completed",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
    path = f"/api/v1/chaoxing/assignments/{task.id}/classroom"
    first = http.post(path, headers=headers)
    second = http.post(path, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["job"]["id"] == second.json()["job"]["id"] == "job_review"
    generations = [
        call for call in transport.calls if call["url"].endswith("/generate")
    ]
    assert generations[0]["json"]["mode"] == "slide"
    prompt = generations[0]["json"]["prompt"]
    assert QUESTIONS[0]["stem"] in prompt and "B. 3" in prompt
    assert "至少3道" in prompt and "可以复用部分原题选项" in prompt
    assert "官方答案" in prompt and "quiz" in prompt
    assert (
        generations[0]["headers"]["Idempotency-Key"]
        == generations[1]["headers"]["Idempotency-Key"]
    )
    container.chaoxing_repository.save_assignment_content(
        user_id=user.id,
        external_id=task.external_id,
        questions=[{**QUESTIONS[0], "stem": "新版题目"}],
        remote_status="pending",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
    assert http.post(path, headers=headers).status_code == 409


def test_review_does_not_generate_a_fake_lesson_when_provider_is_unconfigured():
    container, transport, http, headers, user, task = review_setup(
        [(200, {"llm": False})]
    )
    container.personal_task_repository.complete(task.id, user_id=user.id)
    container.chaoxing_repository.save_assignment_content(
        user_id=user.id,
        external_id=task.external_id,
        questions=QUESTIONS,
        remote_status="completed",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
    result = http.post(
        f"/api/v1/chaoxing/assignments/{task.id}/classroom", headers=headers
    )
    assert result.status_code == 503
    assert len(transport.calls) == 1
