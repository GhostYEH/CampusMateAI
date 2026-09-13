import hashlib

from ...core.exceptions import AppException
from ...repositories.notice_workflow_repository import NoticeWorkflowRepository
from .interpreter import interpret_notice
from .source_registry import require_source


class NoticeWorkflowService:
    def __init__(self, db, notices, workflows: NoticeWorkflowRepository, tasks):
        self.db, self.notices, self.workflows, self.tasks = db, notices, workflows, tasks

    def create_manual(self, user_id: str, content: str, title: str | None, published_at: str | None):
        normalized = " ".join(content.split())
        digest = hashlib.sha256(normalized.encode()).hexdigest()
        with self.db.query() as conn:
            existed = conn.execute("SELECT 1 FROM notices WHERE user_id=? AND source='manual_input' AND external_id=?", (user_id, f"manual:{digest}" )).fetchone()
        notice = self.notices.create_or_update_notice(user_id, "manual_input", f"manual:{digest}", title or "手动录入通知", content, published_at=published_at)
        return notice, bool(existed)

    def analyze(self, user_id: str, notice_id: str) -> dict:
        with self.db.query() as conn:
            notice = conn.execute("SELECT * FROM notices WHERE id=? AND user_id=?", (notice_id, user_id)).fetchone()
        if not notice:
            raise AppException(code="NOTICE_WORKFLOW_NOT_FOUND", http_status=404, message="通知不存在")
        source_code = require_source(notice["source"] if notice["source"] in {"android_system","chaoxing","campus_announcement","manual_input"} else "manual_input")
        content = notice["content"] or notice["title"]
        digest = hashlib.sha256(content.encode()).hexdigest()
        return self.workflows.upsert(user_id=user_id, notice_id=notice_id, source_code=source_code, content_digest=digest, interpreted=interpret_notice(notice["title"], content))

    def confirm(self, user_id: str, workflow_id: str, approved: bool) -> dict:
        workflow = self.workflows.get(workflow_id, user_id)
        if not workflow:
            raise AppException(code="NOTICE_WORKFLOW_NOT_FOUND", http_status=404, message="通知工作流不存在")
        status = "PROCESSING" if approved and workflow["action_risk"] != "MANUAL_ONLY" else "COMPLETED" if not approved else "WAITING_CONFIRMATION"
        return self.workflows.set_status(workflow_id, user_id, status)

    def execute(self, user_id: str, workflow_id: str, key: str) -> dict:
        workflow = self.workflows.get(workflow_id, user_id)
        if not workflow:
            raise AppException(code="NOTICE_WORKFLOW_NOT_FOUND", http_status=404, message="通知工作流不存在")
        if workflow["action_risk"] == "MANUAL_ONLY":
            raise AppException(code="AGENT_ACTION_MANUAL_ONLY", http_status=409, message="该操作只能由用户手动完成")
        if any(action["idempotency_key"] == key for action in workflow["actions"]):
            return workflow
        if workflow["status"] != "PROCESSING":
            raise AppException(code="AGENT_APPROVAL_REQUIRED", http_status=409, message="请先确认工作流")
        facts = __import__("json").loads(workflow["extracted_facts_json"])
        with self.db.transaction() as conn:
            previous = conn.execute("SELECT * FROM notification_workflow_actions WHERE workflow_id=? AND idempotency_key=?", (workflow_id, key)).fetchone()
            if not previous:
                task = self.tasks.create_task(user_id=user_id, title=facts["title"], source="notice_workflow", external_id=f"{workflow_id}:create_task", source_notice_id=f"workflow:{workflow_id}", conn=conn)
                self.workflows.record_action(workflow_id=workflow_id, user_id=user_id, risk=workflow["action_risk"], key=key, task_id=task.id, conn=conn)
                self.workflows.set_status(workflow_id, user_id, "COMPLETED", conn=conn)
        return self.workflows.get(workflow_id, user_id)
