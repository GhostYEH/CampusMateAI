"""通知工作流 API 路由(§9.4)。

由 notices.py include,不修改 router.py。所有写请求支持 Idempotency-Key。
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Header

from ...models.multi_role import UserRow
from ...repositories.notice_workflow_repository import NoticeWorkflowRepository
from ...schemas.notice_workflow import (
    ActionDecisionIn,
    ActionExecuteIn,
    ActionResultOut,
    NotificationSourceOut,
    NotificationSourcePatchIn,
    WorkflowActionOut,
    WorkflowCreateIn,
    WorkflowOut,
    WorkflowReanalyzeIn,
    WorkflowStepOut,
)
from ...services.container import ServiceContainer, get_container
from ...services.notice_workflow.interpreter import NoticeInterpreter
from ...services.notice_workflow.workflow_service import (
    ActionStateConflict,
    NoticeWorkflowService,
    WorkflowActionNotFound,
    WorkflowNotFound,
    WorkflowStateConflict,
)
from ..deps import student_only

router = APIRouter()


def _build_service(container: ServiceContainer) -> NoticeWorkflowService:
    repo = NoticeWorkflowRepository(container.db)
    return NoticeWorkflowService(
        repository=repo,
        interpreter=NoticeInterpreter(provider=None),
        notice_repository=container.notice_repository,
        personal_task_repository=container.personal_task_repository,
    )


def _container() -> ServiceContainer:
    return get_container()


def _steps_out(steps_json: Optional[str]) -> list[WorkflowStepOut]:
    if not steps_json:
        return []
    try:
        data = json.loads(steps_json)
    except (ValueError, TypeError):
        return []
    out = []
    for item in data:
        if isinstance(item, dict):
            out.append(
                WorkflowStepOut(
                    step=str(item.get("step", ""))[:512],
                    done=bool(item.get("done", False)),
                )
            )
        elif isinstance(item, str):
            out.append(WorkflowStepOut(step=item[:512], done=False))
    return out


def _action_out(a) -> WorkflowActionOut:
    return WorkflowActionOut(
        action_id=a.action_id,
        workflow_id=a.workflow_id,
        action_type=a.action_type,
        title=a.title,
        risk_level=a.risk_level,
        status=a.status,
        external_ref=a.external_ref,
        expires_at=a.expires_at,
        error_code=a.error_code,
        error_message=a.error_message,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


def _workflow_out(wf, actions) -> WorkflowOut:
    materials = []
    if wf.materials_json:
        try:
            materials = json.loads(wf.materials_json)
        except (ValueError, TypeError):
            materials = []
    source_evidence = []
    if wf.source_evidence_json:
        try:
            source_evidence = json.loads(wf.source_evidence_json)
        except (ValueError, TypeError):
            source_evidence = []
    uncertainty = []
    if wf.uncertainty_json:
        try:
            uncertainty = json.loads(wf.uncertainty_json)
        except (ValueError, TypeError):
            uncertainty = []
    return WorkflowOut(
        workflow_id=wf.workflow_id,
        user_id=wf.user_id,
        notice_id=wf.notice_id,
        source_id=wf.source_id,
        status=wf.status,
        title=wf.title,
        deadline=wf.deadline,
        location=wf.location,
        audience=wf.audience,
        materials=materials,
        steps=_steps_out(wf.steps_json),
        source_evidence=source_evidence,
        confidence=wf.confidence,
        uncertainty=uncertainty,
        error_code=wf.error_code,
        error_message=wf.error_message,
        created_at=wf.created_at,
        updated_at=wf.updated_at,
        actions=[_action_out(a) for a in actions],
    )


# ===== notification-sources =====


@router.get("/notification-sources", response_model=list[NotificationSourceOut])
def list_sources(
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> list[NotificationSourceOut]:
    service = _build_service(container)
    return [
        NotificationSourceOut(
            source_id=s.source_id,
            code=s.code,
            display_name=s.display_name,
            kind=s.kind,
            automation_enabled=s.automation_enabled,
            permission_scope=s.permission_scope,
        )
        for s in service.list_sources()
    ]


@router.patch("/notification-sources/{source_id}", response_model=NotificationSourceOut)
def patch_source(
    source_id: str,
    body: NotificationSourcePatchIn,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> NotificationSourceOut:
    service = _build_service(container)
    row = service.patch_source(
        source_id,
        automation_enabled=body.automation_enabled,
        display_name=body.display_name,
    )
    if not row:
        raise WorkflowNotFound("通知来源不存在")
    return NotificationSourceOut(
        source_id=row.source_id,
        code=row.code,
        display_name=row.display_name,
        kind=row.kind,
        automation_enabled=row.automation_enabled,
        permission_scope=row.permission_scope,
    )


# ===== workflow =====


@router.post("/notices/{notice_id}/workflow", response_model=WorkflowOut)
def create_workflow(
    notice_id: str,
    body: WorkflowCreateIn,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> WorkflowOut:
    service = _build_service(container)
    effective_key = body.idempotency_key or idempotency_key
    wf = service.create_workflow_for_notice(
        user_id=user.id,
        notice_id=notice_id,
        idempotency_key=effective_key,
    )
    actions = service.list_actions(wf.workflow_id, user_id=user.id)
    return _workflow_out(wf, actions)


@router.get("/notice-workflows/{workflow_id}", response_model=WorkflowOut)
def get_workflow(
    workflow_id: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> WorkflowOut:
    service = _build_service(container)
    wf = service.get_workflow(workflow_id, user_id=user.id)
    actions = service.list_actions(workflow_id, user_id=user.id)
    return _workflow_out(wf, actions)


@router.post("/notice-workflows/{workflow_id}/reanalyze", response_model=WorkflowOut)
def reanalyze_workflow(
    workflow_id: str,
    body: WorkflowReanalyzeIn,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> WorkflowOut:
    service = _build_service(container)
    effective_key = body.idempotency_key or idempotency_key
    wf = service.reanalyze(workflow_id, user_id=user.id, idempotency_key=effective_key)
    actions = service.list_actions(workflow_id, user_id=user.id)
    return _workflow_out(wf, actions)


# ===== actions =====


@router.post(
    "/notice-workflow-actions/{action_id}/decision", response_model=WorkflowActionOut
)
def decide_action(
    action_id: str,
    body: ActionDecisionIn,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> WorkflowActionOut:
    service = _build_service(container)
    effective_key = body.idempotency_key or idempotency_key
    action = service.decide_action(
        action_id,
        user_id=user.id,
        decision=body.decision,
        reason=body.reason,
        idempotency_key=effective_key,
    )
    return _action_out(action)


@router.post(
    "/notice-workflow-actions/{action_id}/execute", response_model=ActionResultOut
)
def execute_action(
    action_id: str,
    body: ActionExecuteIn,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> ActionResultOut:
    service = _build_service(container)
    effective_key = body.idempotency_key or idempotency_key
    action = service.execute_action(
        action_id, user_id=user.id, idempotency_key=effective_key
    )
    result = None
    if action.result_json:
        try:
            result = json.loads(action.result_json)
        except (ValueError, TypeError):
            result = None
    return ActionResultOut(
        action_id=action.action_id,
        status=action.status,
        external_ref=action.external_ref,
        result=result,
        error_code=action.error_code,
        error_message=action.error_message,
    )


__all__ = ["router"]