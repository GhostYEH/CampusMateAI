"""通知工作流 API 路由(§9.4)。

由 notices.py include,不修改 router.py。所有写请求支持 Idempotency-Key。
"""
from __future__ import annotations

import json
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Header, Request
from starlette.concurrency import run_in_threadpool

from ...core.exceptions import AgentIdempotencyConflict, AgentRuntimeError
from ...repositories.agent_runtime_repository import build_request_hash

from ...models.multi_role import UserRow
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
from ...services.notice_workflow.workflow_service import (
    NoticeWorkflowService,
    WorkflowNotFound,
)
from ..deps import student_only

router = APIRouter(tags=["通知事务"])


def _build_service(container: ServiceContainer) -> NoticeWorkflowService:
    return container.notice_workflow_service


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


@router.get(
    "/notification-sources",
    response_model=list[NotificationSourceOut],
    summary="列出通知来源",
    responses={
        200: {
            "description": "返回当前用户可用的通知来源列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "通知来源列表",
                            "value": [
                                {
                                    "source_id": "src_manual",
                                    "code": "manual_input",
                                    "display_name": "手动输入",
                                    "kind": "MANUAL",
                                    "automation_enabled": False,
                                    "permission_scope": None,
                                },
                                {
                                    "source_id": "src_android",
                                    "code": "android_system",
                                    "display_name": "安卓系统通知",
                                    "kind": "SYSTEM",
                                    "automation_enabled": True,
                                    "permission_scope": "notification_listener",
                                },
                            ],
                        }
                    }
                }
            },
        },
    },
)
def list_sources(
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> list[NotificationSourceOut]:
    """列出当前用户可用的通知来源及其自动化开关。"""
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
        for s in service.list_sources(user_id=user.id)
    ]


@router.patch(
    "/notification-sources/{source_id}",
    response_model=NotificationSourceOut,
    summary="修改通知来源",
    responses={
        200: {
            "description": "返回更新后的通知来源",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "已更新的通知来源",
                            "value": {
                                "source_id": "src_android",
                                "code": "android_system",
                                "display_name": "安卓系统通知",
                                "kind": "SYSTEM",
                                "automation_enabled": True,
                                "permission_scope": "notification_listener",
                            },
                        }
                    }
                }
            },
        },
    },
)
def patch_source(
    source_id: str,
    body: Annotated[
        NotificationSourcePatchIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "开启自动化并重命名来源",
                    "value": {
                        "automation_enabled": True,
                        "display_name": "安卓系统通知",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> NotificationSourceOut:
    """修改指定通知来源的显示名称或自动化开关。"""
    service = _build_service(container)
    row = service.patch_source(
        source_id,
        user_id=user.id,
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


@router.post(
    "/notices/{notice_id}/workflow",
    response_model=WorkflowOut,
    summary="创建通知事务",
    responses={
        200: {
            "description": "返回创建的通知事务及其可执行动作",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "通知事务解析结果",
                            "value": {
                                "workflow_id": "wf_20261006_001",
                                "user_id": "u_demo",
                                "notice_id": "notice_manual_3f1a2b4c",
                                "source_id": "src_manual",
                                "status": "WAITING_CONFIRMATION",
                                "title": "提交暑期社会实践材料",
                                "deadline": "2026-07-30T23:59:00+08:00",
                                "location": "信息工程学院办公室",
                                "audience": "2024级",
                                "materials": ["实践申请表", "实践证明材料"],
                                "steps": [
                                    {"step": "填写实践申请表", "done": False},
                                    {"step": "提交纸质材料至学院办公室", "done": False},
                                ],
                                "source_evidence": [
                                    "请2024级学生于7月30日前提交实践申请材料"
                                ],
                                "confidence": 0.82,
                                "uncertainty": [],
                                "error_code": None,
                                "error_message": None,
                                "created_at": "2026-10-06T10:00:00+08:00",
                                "updated_at": "2026-10-06T10:00:00+08:00",
                                "actions": [
                                    {
                                        "action_id": "act_20261006_001",
                                        "workflow_id": "wf_20261006_001",
                                        "action_type": "CREATE_REMINDER",
                                        "title": "创建截止提醒",
                                        "risk_level": "CONFIRM_REQUIRED",
                                        "status": "PROPOSED",
                                        "external_ref": None,
                                        "expires_at": None,
                                        "error_code": None,
                                        "error_message": None,
                                        "created_at": "2026-10-06T10:00:00+08:00",
                                        "updated_at": "2026-10-06T10:00:00+08:00",
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        },
    },
)
async def create_workflow(
    notice_id: str,
    body: Annotated[
        WorkflowCreateIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "为指定通知创建事务",
                    "value": {"idempotency_key": "wf_demo_001"},
                }
            }
        ),
    ],
    request: Request,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> WorkflowOut:
    """为指定通知创建解析事务，返回解析结果与可执行动作。"""
    service = _build_service(container)
    effective_key = body.idempotency_key or idempotency_key
    runtime_repo = container.agent_runtime_repository
    if effective_key:
        existing = await run_in_threadpool(container.notice_workflow_repository.find_workflow_by_idempotency,
            user.id, effective_key
        )
        if existing:
            if existing.notice_id != notice_id:
                raise AgentIdempotencyConflict()
            actions = await run_in_threadpool(service.list_actions, existing.workflow_id, user_id=user.id)
            return _workflow_out(existing, actions)
    if await run_in_threadpool(container.notice_repository.get_notice, user.id, notice_id) is None:
        raise WorkflowNotFound("通知不存在或无权访问")
    created = await run_in_threadpool(runtime_repo.create_job_with_run_and_event,
        user_id=user.id,
        job_kind="notice_workflow",
        input_ref={"notice_id": notice_id},
        idempotency_key=effective_key,
        request_id=getattr(request.state, "request_id", None),
        request_hash=build_request_hash("notice_workflow", {"notice_id": notice_id}),
    )
    if created["replayed"]:
        raise AgentRuntimeError("幂等请求仍在处理中", code="AGENT_INVALID_STATE", http_status=409)
    job_id, run_id = created["job_id"], created["run_id"]
    await run_in_threadpool(container.agent_run_manager.transition,
        run_id, "RUNNING", phase="WAITING_FOR_MODEL"
    )
    # 取消检查点:进入通知解析前确认 run 仍可推进。
    await run_in_threadpool(container.agent_run_manager.assert_active, run_id)
    wf = await service.create_workflow_for_notice_async(
        user_id=user.id,
        notice_id=notice_id,
        idempotency_key=effective_key,
        run_id=run_id,
    )
    await run_in_threadpool(runtime_repo.update_job_input_ref,
        job_id, {"notice_id": notice_id, "workflow_id": wf.workflow_id}
    )
    await run_in_threadpool(container.agent_run_manager.transition, run_id, "SUCCEEDED", phase="IDLE")
    actions = await run_in_threadpool(service.list_actions, wf.workflow_id, user_id=user.id)
    return _workflow_out(wf, actions)


@router.get(
    "/notice-workflows/{workflow_id}",
    response_model=WorkflowOut,
    summary="读取通知事务",
    responses={
        200: {
            "description": "返回指定通知事务的解析结果与动作列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "通知事务详情",
                            "value": {
                                "workflow_id": "wf_20261006_001",
                                "user_id": "u_demo",
                                "notice_id": "notice_manual_3f1a2b4c",
                                "source_id": "src_manual",
                                "status": "WAITING_CONFIRMATION",
                                "title": "提交暑期社会实践材料",
                                "deadline": "2026-07-30T23:59:00+08:00",
                                "location": "信息工程学院办公室",
                                "audience": "2024级",
                                "materials": ["实践申请表", "实践证明材料"],
                                "steps": [
                                    {"step": "填写实践申请表", "done": False},
                                    {"step": "提交纸质材料至学院办公室", "done": False},
                                ],
                                "source_evidence": [
                                    "请2024级学生于7月30日前提交实践申请材料"
                                ],
                                "confidence": 0.82,
                                "uncertainty": [],
                                "error_code": None,
                                "error_message": None,
                                "created_at": "2026-10-06T10:00:00+08:00",
                                "updated_at": "2026-10-06T10:00:00+08:00",
                                "actions": [
                                    {
                                        "action_id": "act_20261006_001",
                                        "workflow_id": "wf_20261006_001",
                                        "action_type": "CREATE_REMINDER",
                                        "title": "创建截止提醒",
                                        "risk_level": "CONFIRM_REQUIRED",
                                        "status": "PROPOSED",
                                        "external_ref": None,
                                        "expires_at": None,
                                        "error_code": None,
                                        "error_message": None,
                                        "created_at": "2026-10-06T10:00:00+08:00",
                                        "updated_at": "2026-10-06T10:00:00+08:00",
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        },
    },
)
def get_workflow(
    workflow_id: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> WorkflowOut:
    """读取指定通知事务的解析结果与动作列表。"""
    service = _build_service(container)
    wf = service.get_workflow(workflow_id, user_id=user.id)
    actions = service.list_actions(workflow_id, user_id=user.id)
    return _workflow_out(wf, actions)


@router.post(
    "/notice-workflows/{workflow_id}/reanalyze",
    response_model=WorkflowOut,
    summary="重新分析通知事务",
    responses={
        200: {
            "description": "返回重新分析后的通知事务与动作列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "重新分析结果",
                            "value": {
                                "workflow_id": "wf_20261006_001",
                                "user_id": "u_demo",
                                "notice_id": "notice_manual_3f1a2b4c",
                                "source_id": "src_manual",
                                "status": "WAITING_CONFIRMATION",
                                "title": "提交暑期社会实践材料",
                                "deadline": "2026-07-30T23:59:00+08:00",
                                "location": "信息工程学院办公室",
                                "audience": "2024级",
                                "materials": ["实践申请表", "实践证明材料"],
                                "steps": [
                                    {"step": "填写实践申请表", "done": False},
                                    {"step": "提交纸质材料至学院办公室", "done": False},
                                ],
                                "source_evidence": [
                                    "请2024级学生于7月30日前提交实践申请材料"
                                ],
                                "confidence": 0.85,
                                "uncertainty": [],
                                "error_code": None,
                                "error_message": None,
                                "created_at": "2026-10-06T10:00:00+08:00",
                                "updated_at": "2026-10-06T10:05:00+08:00",
                                "actions": [
                                    {
                                        "action_id": "act_20261006_002",
                                        "workflow_id": "wf_20261006_001",
                                        "action_type": "CREATE_REMINDER",
                                        "title": "创建截止提醒",
                                        "risk_level": "CONFIRM_REQUIRED",
                                        "status": "PROPOSED",
                                        "external_ref": None,
                                        "expires_at": None,
                                        "error_code": None,
                                        "error_message": None,
                                        "created_at": "2026-10-06T10:05:00+08:00",
                                        "updated_at": "2026-10-06T10:05:00+08:00",
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        },
    },
)
def reanalyze_workflow(
    workflow_id: str,
    body: Annotated[
        WorkflowReanalyzeIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "重新分析指定通知事务",
                    "value": {"idempotency_key": "wf_reanalyze_001"},
                }
            }
        ),
    ],
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> WorkflowOut:
    """按最新内容重新分析通知事务并更新动作。"""
    service = _build_service(container)
    effective_key = body.idempotency_key or idempotency_key
    wf = service.reanalyze(workflow_id, user_id=user.id, idempotency_key=effective_key)
    actions = service.list_actions(workflow_id, user_id=user.id)
    return _workflow_out(wf, actions)


# ===== actions =====


@router.post(
    "/notice-workflow-actions/{action_id}/decision",
    response_model=WorkflowActionOut,
    summary="决定事务动作",
    responses={
        200: {
            "description": "返回更新后的通知事务动作",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "动作已批准",
                            "value": {
                                "action_id": "act_20261006_001",
                                "workflow_id": "wf_20261006_001",
                                "action_type": "CREATE_REMINDER",
                                "title": "创建截止提醒",
                                "risk_level": "CONFIRM_REQUIRED",
                                "status": "APPROVED",
                                "external_ref": None,
                                "expires_at": None,
                                "error_code": None,
                                "error_message": None,
                                "created_at": "2026-10-06T10:00:00+08:00",
                                "updated_at": "2026-10-06T10:02:00+08:00",
                            },
                        }
                    }
                }
            },
        },
    },
)
def decide_action(
    action_id: str,
    body: Annotated[
        ActionDecisionIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "批准创建截止提醒动作",
                    "value": {
                        "decision": "APPROVED",
                        "reason": "信息核对无误",
                        "idempotency_key": "action_decision_001",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> WorkflowActionOut:
    """对通知事务动作提交通过或拒绝决定。"""
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
    "/notice-workflow-actions/{action_id}/execute",
    response_model=ActionResultOut,
    summary="执行事务动作",
    responses={
        200: {
            "description": "返回动作执行状态、外部引用与结果",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "动作执行完成",
                            "value": {
                                "action_id": "act_20261006_001",
                                "status": "DONE",
                                "external_ref": "reminder_9f2c1a7d",
                                "result": {
                                    "reminder_id": "reminder_9f2c1a7d",
                                    "trigger_at": "2026-07-29T23:59:00+08:00",
                                },
                                "error_code": None,
                                "error_message": None,
                            },
                        }
                    }
                }
            },
        },
    },
)
def execute_action(
    action_id: str,
    body: Annotated[
        ActionExecuteIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "执行已批准的动作",
                    "value": {"idempotency_key": "action_execute_001"},
                }
            }
        ),
    ],
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> ActionResultOut:
    """在用户已批准后执行指定通知事务动作。"""
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
