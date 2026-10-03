"""同步/异步创建的幂等、权限、空正文与失败状态契约。"""
from types import SimpleNamespace

import pytest

from app.database.sqlite_db import Database
from app.repositories.notice_repository import NoticeRepository
from app.repositories.notice_workflow_repository import NoticeWorkflowRepository
from app.repositories.personal_task_repository import PersonalTaskRepository
from app.repositories.user_repository import UserRepository
from app.services.notice_workflow.interpreter import NoticeInterpreter, content_fingerprint
from app.services.notice_workflow.workflow_service import NoticeWorkflowService, WorkflowNotFound


@pytest.fixture
def context():
    db = Database(None)
    users = UserRepository(db)
    owner = users.create_user(username="workflow_owner", password_hash="test", role="student")
    other = users.create_user(username="workflow_other", password_hash="test", role="student")
    notices = NoticeRepository(db)
    workflows = NoticeWorkflowRepository(db)
    interpreter = NoticeInterpreter()
    service = NoticeWorkflowService(
        repository=workflows,
        interpreter=interpreter,
        notice_repository=notices,
        personal_task_repository=PersonalTaskRepository(db),
    )
    yield SimpleNamespace(
        service=service, notices=notices, workflows=workflows,
        interpreter=interpreter, owner=owner, other=other,
    )
    db.dispose()


async def _create(context, mode, **kwargs):
    if mode == "sync":
        return context.service.create_workflow_for_notice(**kwargs)
    return await context.service.create_workflow_for_notice_async(**kwargs)


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("title,content,expected", [
    ("标题", "正文", "正文"), ("标题", None, "标题"), ("", "", ""),
])
async def test_creation_analyzes_body_title_fallback_and_empty_text(context, mode, title, content, expected):
    notice = context.notices.create_or_update_notice(
        context.owner.id, "manual", "notice-1", title, content,
    )
    workflow = await _create(
        context, mode, user_id=context.owner.id, notice_id=notice.id,
    )
    assert workflow.content_fingerprint == content_fingerprint(expected, user_id=context.owner.id)
    assert workflow.source_id == context.workflows.get_source_by_code_for_user(
        "manual_input", context.owner.id,
    ).source_id
    assert workflow.status not in {"CREATED", "ANALYZING"}


@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_replay_skips_analysis_but_preserves_user_isolation(context, mode, monkeypatch):
    notice = context.notices.create_or_update_notice(
        context.owner.id, "manual", "notice-1", "通知", "请于2026年10月15日前提交申请表",
    )
    workflow = await _create(
        context, mode, user_id=context.owner.id, notice_id=notice.id, idempotency_key="key-1",
    )
    actions = context.workflows.list_actions_by_workflow(workflow.workflow_id)

    def unexpected_analysis(*args, **kwargs):
        pytest.fail("重复工作流不应再次解释通知")

    monkeypatch.setattr(context.interpreter, "interpret", unexpected_analysis)
    monkeypatch.setattr(context.interpreter, "interpret_async", unexpected_analysis)
    replay = await _create(
        context, mode, user_id=context.owner.id, notice_id="missing", idempotency_key="key-1",
    )
    duplicate_notice = context.notices.create_or_update_notice(
        context.owner.id, "manual", "notice-2", notice.title, notice.content,
    )
    duplicate = await _create(
        context, mode, user_id=context.owner.id, notice_id=duplicate_notice.id,
    )
    assert replay == duplicate == workflow
    assert context.workflows.list_actions_by_workflow(workflow.workflow_id) == actions
    with pytest.raises(WorkflowNotFound, match="通知不存在或无权访问"):
        await _create(
            context, mode, user_id=context.other.id, notice_id=notice.id, idempotency_key="key-1",
        )


@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_interpreter_failure_leaves_analyzing_state_without_actions(context, mode, monkeypatch):
    notice = context.notices.create_or_update_notice(
        context.owner.id, "manual", "notice-1", "通知", "申请表",
    )

    def fail(*args, **kwargs):
        raise RuntimeError("interpretation failed")

    monkeypatch.setattr(context.interpreter, "interpret", fail)
    monkeypatch.setattr(context.interpreter, "interpret_async", fail)
    with pytest.raises(RuntimeError, match="interpretation failed"):
        await _create(
            context, mode, user_id=context.owner.id, notice_id=notice.id, idempotency_key="key-1",
        )
    workflow = context.workflows.find_workflow_by_idempotency(context.owner.id, "key-1")
    assert workflow.status == "ANALYZING"
    assert context.workflows.list_actions_by_workflow(workflow.workflow_id) == []
