import json

from fastapi import APIRouter, Depends

from ...core.exceptions import AppException
from ...models.multi_role import UserRow
from ...schemas.notice_workflow import NoticeWorkflowOut, SourceAutomationOut, SourceAutomationUpdate, WorkflowActionOut, WorkflowConfirmation, WorkflowExecute
from ...services.container import ServiceContainer, get_container
from ...services.notice_workflow.source_registry import require_source
from ..deps import require_role

router = APIRouter(tags=["notice-workflows"])


def _container() -> ServiceContainer:
    return get_container()


def _out(row: dict, container: ServiceContainer) -> NoticeWorkflowOut:
    return NoticeWorkflowOut(
        workflow_id=row["id"], notice_id=row["notice_id"], status=row["status"], source_code=row["source_code"],
        source_revision=row["source_revision"], extracted_facts=json.loads(row["extracted_facts_json"]),
        uncertainty_codes=json.loads(row["uncertainty_json"]), checklist=json.loads(row["checklist_json"]),
        action_risk=row["action_risk"], difference=json.loads(row["difference_json"]),
        automation_enabled=container.notice_workflow_repository.automation_enabled(row["user_id"], row["source_code"]),
        actions=[WorkflowActionOut(action_id=item["id"], action_type=item["action_type"], risk_level=item["risk_level"], status=item["status"], task_id=item["task_id"], error_code=item["error_code"]) for item in row["actions"]],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


@router.post("/notices/{notice_id}/workflow", response_model=NoticeWorkflowOut)
def analyze(notice_id: str, user: UserRow = Depends(require_role("student")), container: ServiceContainer = Depends(_container)):
    return _out(container.notice_workflow_service.analyze(user.id, notice_id), container)


@router.get("/notice-workflows/{workflow_id}", response_model=NoticeWorkflowOut)
def get_workflow(workflow_id: str, user: UserRow = Depends(require_role("student")), container: ServiceContainer = Depends(_container)):
    row = container.notice_workflow_repository.get(workflow_id, user.id)
    if not row:
        raise AppException(code="NOTICE_WORKFLOW_NOT_FOUND", http_status=404, message="通知工作流不存在")
    return _out(row, container)


@router.post("/notice-workflows/{workflow_id}/confirm", response_model=NoticeWorkflowOut)
def confirm(workflow_id: str, payload: WorkflowConfirmation, user: UserRow = Depends(require_role("student")), container: ServiceContainer = Depends(_container)):
    return _out(container.notice_workflow_service.confirm(user.id, workflow_id, payload.approved), container)


@router.post("/notice-workflows/{workflow_id}/execute", response_model=NoticeWorkflowOut)
def execute(workflow_id: str, payload: WorkflowExecute, user: UserRow = Depends(require_role("student")), container: ServiceContainer = Depends(_container)):
    return _out(container.notice_workflow_service.execute(user.id, workflow_id, payload.idempotency_key), container)


@router.put("/notice-sources/{source_code}/automation", response_model=SourceAutomationOut)
def set_automation(source_code: str, payload: SourceAutomationUpdate, user: UserRow = Depends(require_role("student")), container: ServiceContainer = Depends(_container)):
    require_source(source_code)
    enabled = container.notice_workflow_repository.set_automation(user.id, source_code, payload.enabled)
    return SourceAutomationOut(source_code=source_code, automation_enabled=enabled)
