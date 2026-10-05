"""Phase 6A: 学生世界模型控制 API 路由。

所有端点仅限学生本人操作，teacher/admin 不可代替学生。
输出严格排除内部表名、source_id、原文、凭据等敏感信息。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query

from ...models.multi_role import UserRow
from ...schemas.learner_control import (
    CorrectionCreate,
    CorrectionOut,
    CorrectionPage,
    CorrectionRevokeRequest,
    DataSummaryOut,
    DataSourceControlList,
    DataSourceControlOut,
    DataSourceControlUpdate,
    DeleteCountSummary,
    DeleteRequestCreate,
    DeleteRequestOut,
    DeleteStatusOut,
    ModelCapabilityTransparencyOut,
    ModelTransparencyOut,
)
from ...services.container import ServiceContainer, get_container
from ..deps import student_only

router = APIRouter(prefix="/learner-state", tags=["数据控制"])


def _container() -> ServiceContainer:
    return get_container()


def _correction_out(row) -> CorrectionOut:
    return CorrectionOut(
        correction_id=row.correction_id,
        projection_kind=row.projection_kind,
        projection_scope=row.projection_scope,
        scope_type=row.scope_type,
        scope_id=row.scope_id,
        state_type=row.state_type,
        target_snapshot_id=row.target_snapshot_id,
        correction_type=row.correction_type,
        reason_code=row.reason_code,
        status=row.status,
        created_at=row.created_at,
        revoked_at=row.revoked_at,
        correction_version=row.correction_version,
    )


def _source_control_out(row) -> DataSourceControlOut:
    return DataSourceControlOut(
        source_key=row.source_key,
        status=row.status,
        updated_at=row.updated_at,
        can_pause=row.status == "ENABLED",
        can_resume=row.status != "ENABLED",
    )


def _delete_request_out(row) -> DeleteRequestOut:
    return DeleteRequestOut(
        request_id=row.request_id,
        scope=row.scope,
        status=row.status,
        before_counts=DeleteCountSummary(**row.before_counts),
        after_counts=DeleteCountSummary(**row.after_counts),
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


# ===== 状态纠正 =====


@router.post(
    "/corrections",
    response_model=CorrectionOut,
    status_code=201,
    summary="创建状态纠正",
    responses={
        201: {
            "description": "状态纠正创建成功，返回最新纠正版本",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "标记任务量估计不准确",
                            "value": {
                                "correction_id": "corr_demo_1",
                                "projection_kind": "CORE",
                                "projection_scope": "__user__",
                                "scope_type": "USER",
                                "scope_id": "u_demo",
                                "state_type": "task_workload",
                                "target_snapshot_id": "snap_demo_1",
                                "correction_type": "MARK_INACCURATE",
                                "reason_code": "TASK_ALREADY_COMPLETED",
                                "status": "ACTIVE",
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "revoked_at": None,
                                "correction_version": 1,
                            },
                        }
                    }
                }
            },
        }
    },
)
def create_correction(
    body: Annotated[
        CorrectionCreate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "纠正任务量状态估计",
                    "value": {
                        "projection_kind": "CORE",
                        "projection_scope": "__user__",
                        "scope_type": "USER",
                        "scope_id": "u_demo",
                        "state_type": "task_workload",
                        "target_snapshot_id": "snap_demo_1",
                        "correction_type": "MARK_INACCURATE",
                        "reason_code": "TASK_ALREADY_COMPLETED",
                        "idempotency_key": "correction-demo-1",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> CorrectionOut:
    """创建一条针对本人学生状态快照的状态纠正记录。

    - 仅限学生本人操作，teacher/admin 不可代操作。
    - 同一 idempotency_key 与同一目标快照重复提交为幂等重放。
    """
    row = container.learner_control_service.create_correction(
        user_id=user.id,
        projection_kind=body.projection_kind,
        projection_scope=body.projection_scope,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        state_type=body.state_type,
        target_snapshot_id=body.target_snapshot_id,
        correction_type=body.correction_type,
        reason_code=body.reason_code,
        idempotency_key=body.idempotency_key,
    )
    container.learner_control_service.record_event(
        user_id=user.id, event_type="learner_correction_submitted"
    )
    return _correction_out(row)


@router.get(
    "/corrections",
    response_model=CorrectionPage,
    summary="列出状态纠正",
    responses={
        200: {
            "description": "当前学生的状态纠正分页列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "状态纠正列表",
                            "value": {
                                "items": [
                                    {
                                        "correction_id": "corr_demo_1",
                                        "projection_kind": "CORE",
                                        "projection_scope": "__user__",
                                        "scope_type": "USER",
                                        "scope_id": "u_demo",
                                        "state_type": "task_workload",
                                        "target_snapshot_id": "snap_demo_1",
                                        "correction_type": "MARK_INACCURATE",
                                        "reason_code": "TASK_ALREADY_COMPLETED",
                                        "status": "ACTIVE",
                                        "created_at": "2026-10-06T08:00:00+00:00",
                                        "revoked_at": None,
                                        "correction_version": 1,
                                    }
                                ],
                                "total": 1,
                                "page": 1,
                                "page_size": 50,
                                "has_more": False,
                            },
                        }
                    }
                }
            },
        }
    },
)
def list_corrections(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: str | None = Query(None, pattern="^(ACTIVE|REVOKED)$"),
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> CorrectionPage:
    """分页列出当前学生的状态纠正记录。

    - status 可选 ACTIVE/REVOKED 过滤。
    - 仅返回本人记录，按创建时间倒序。
    """
    rows, total = container.learner_control_service.list_corrections(
        user_id=user.id, page=page, page_size=page_size, status=status
    )
    return CorrectionPage(
        items=[_correction_out(r) for r in rows],
        total=total, page=page, page_size=page_size,
        has_more=page * page_size < total,
    )


@router.post(
    "/corrections/{correction_id}/revoke",
    response_model=CorrectionOut,
    summary="撤销状态纠正",
    responses={
        200: {
            "description": "状态纠正撤销成功，返回已撤销的纠正记录",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "撤销纠正记录",
                            "value": {
                                "correction_id": "corr_demo_1",
                                "projection_kind": "CORE",
                                "projection_scope": "__user__",
                                "scope_type": "USER",
                                "scope_id": "u_demo",
                                "state_type": "task_workload",
                                "target_snapshot_id": "snap_demo_1",
                                "correction_type": "MARK_INACCURATE",
                                "reason_code": "TASK_ALREADY_COMPLETED",
                                "status": "REVOKED",
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "revoked_at": "2026-10-06T09:00:00+00:00",
                                "correction_version": 2,
                            },
                        }
                    }
                }
            },
        }
    },
)
def revoke_correction(
    correction_id: str,
    body: Annotated[
        CorrectionRevokeRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "撤销指定纠正记录",
                    "value": {"idempotency_key": "revoke-demo-1"},
                }
            }
        ),
    ],
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> CorrectionOut:
    """撤销本人已创建的状态纠正记录。

    - 仅能撤销本人记录，记录不存在或不属于本人返回 404。
    - 已撤销的记录重复撤销返回 409。
    """
    row = container.learner_control_service.revoke_correction(
        user_id=user.id, correction_id=correction_id
    )
    container.learner_control_service.record_event(
        user_id=user.id, event_type="learner_correction_revoked"
    )
    return _correction_out(row)


# ===== 数据源控制 =====


@router.get(
    "/data-controls",
    response_model=DataSourceControlList,
    summary="列出数据来源控制",
    responses={
        200: {
            "description": "当前学生各数据源的控制状态列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "数据来源控制列表",
                            "value": {
                                "items": [
                                    {
                                        "source_key": "CORE_STUDY",
                                        "status": "ENABLED",
                                        "updated_at": "2026-10-06T08:00:00+00:00",
                                        "can_pause": True,
                                        "can_resume": False,
                                    }
                                ]
                            },
                        }
                    }
                }
            },
        }
    },
)
def list_data_controls(
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> DataSourceControlList:
    """列出当前学生所有数据来源的控制状态与可暂停/可恢复标记。"""
    rows = container.learner_control_service.list_source_controls(user_id=user.id)
    return DataSourceControlList(items=[_source_control_out(r) for r in rows])


@router.put(
    "/data-controls/{source_key}",
    response_model=DataSourceControlOut,
    summary="更新数据来源控制",
    responses={
        200: {
            "description": "数据来源控制更新成功，返回更新后的状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "暂停某数据来源",
                            "value": {
                                "source_key": "CHAOXING",
                                "status": "PAUSED",
                                "updated_at": "2026-10-06T08:00:00+00:00",
                                "can_pause": False,
                                "can_resume": True,
                            },
                        }
                    }
                }
            },
        }
    },
)
def update_data_control(
    source_key: str,
    body: Annotated[
        DataSourceControlUpdate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "把学习通来源标记为暂停",
                    "value": {"status": "PAUSED", "idempotency_key": "control-demo-1"},
                }
            }
        ),
    ],
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> DataSourceControlOut:
    """更新指定数据来源的启用/暂停状态。

    - status 仅支持 ENABLED/PAUSED。
    - 不支持的数据源返回 400，幂等键冲突返回 409。
    """
    row = container.learner_control_service.update_source_control(
        user_id=user.id, source_key=source_key, status=body.status
    )
    event_type = "data_source_paused" if body.status == "PAUSED" else "data_source_resumed"
    container.learner_control_service.record_event(
        user_id=user.id, event_type=event_type, metadata={"source_key": source_key}
    )
    return _source_control_out(row)


# ===== 世界模型删除 =====


@router.post(
    "/delete-request",
    response_model=DeleteRequestOut,
    summary="发起数据删除",
    responses={
        200: {
            "description": "删除请求已受理，返回删除范围与前后计数",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "删除世界模型状态数据",
                            "value": {
                                "request_id": "del_demo_1",
                                "scope": "STATE_ONLY",
                                "status": "COMPLETED",
                                "before_counts": {
                                    "projection_runs": 4,
                                    "snapshots": 12,
                                    "evidence": 30,
                                    "learner_events": 48,
                                    "corrections": 2,
                                    "learning_plans": 3,
                                    "plan_items": 9,
                                    "plan_feedback": 1,
                                    "plan_evaluations": 1,
                                    "shadow_runs": 5,
                                },
                                "after_counts": {
                                    "projection_runs": 4,
                                    "snapshots": 0,
                                    "evidence": 0,
                                    "learner_events": 48,
                                    "corrections": 2,
                                    "learning_plans": 3,
                                    "plan_items": 9,
                                    "plan_feedback": 1,
                                    "plan_evaluations": 1,
                                    "shadow_runs": 5,
                                },
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "completed_at": "2026-10-06T08:00:01+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def request_deletion(
    body: Annotated[
        DeleteRequestCreate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "删除本人世界模型状态数据",
                    "value": {"scope": "STATE_ONLY", "idempotency_key": "delete-demo-1"},
                }
            }
        ),
    ],
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> DeleteRequestOut:
    """发起一次针对本人世界模型数据的删除请求。

    - scope 取固定枚举，非法范围返回 400。
    - 同一 idempotency_key 不同删除范围返回 409。
    """
    row = container.learner_control_service.request_deletion(
        user_id=user.id, scope=body.scope, idempotency_key=body.idempotency_key
    )
    container.learner_control_service.record_event(
        user_id=user.id, event_type="learner_model_delete_requested", metadata={"scope": body.scope}
    )
    return _delete_request_out(row)


@router.get(
    "/delete-status",
    response_model=DeleteStatusOut,
    summary="读取删除状态",
    responses={
        200: {
            "description": "最新删除请求与历史记录；无记录时 latest 为 null",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取删除状态",
                            "value": {
                                "latest": {
                                    "request_id": "del_demo_1",
                                    "scope": "STATE_ONLY",
                                    "status": "COMPLETED",
                                    "before_counts": {
                                        "projection_runs": 4,
                                        "snapshots": 12,
                                        "evidence": 30,
                                        "learner_events": 48,
                                        "corrections": 2,
                                        "learning_plans": 3,
                                        "plan_items": 9,
                                        "plan_feedback": 1,
                                        "plan_evaluations": 1,
                                        "shadow_runs": 5,
                                    },
                                    "after_counts": {
                                        "projection_runs": 4,
                                        "snapshots": 0,
                                        "evidence": 0,
                                        "learner_events": 48,
                                        "corrections": 2,
                                        "learning_plans": 3,
                                        "plan_items": 9,
                                        "plan_feedback": 1,
                                        "plan_evaluations": 1,
                                        "shadow_runs": 5,
                                    },
                                    "created_at": "2026-10-06T08:00:00+00:00",
                                    "completed_at": "2026-10-06T08:00:01+00:00",
                                },
                                "history": [],
                            },
                        }
                    }
                }
            },
        }
    },
)
def get_delete_status(
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> DeleteStatusOut:
    """读取本人最新删除请求状态与历史；从未发起时 latest 为 null。"""
    rows = container.learner_control_service.list_delete_requests(user_id=user.id)
    if not rows:
        return DeleteStatusOut()
    history = [_delete_request_out(r) for r in rows]
    return DeleteStatusOut(latest=history[0], history=history)


# ===== 安全导出摘要 =====


@router.get(
    "/data-summary",
    response_model=DataSummaryOut,
    summary="读取数据概况",
    responses={
        200: {
            "description": "本人世界模型数据的计数、数据源状态与版本摘要",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "数据概况摘要",
                            "value": {
                                "event_count": 48,
                                "snapshot_count": 12,
                                "correction_count": 2,
                                "learning_plan_count": 3,
                                "plan_feedback_count": 1,
                                "plan_evaluation_count": 1,
                                "shadow_run_count": 5,
                                "enabled_sources": ["CORE_STUDY", "PERSONAL_TASK"],
                                "paused_sources": ["CHAOXING"],
                                "oldest_recorded_at": "2026-09-01T08:00:00+00:00",
                                "newest_recorded_at": "2026-10-06T08:00:00+00:00",
                                "estimator_versions": ["estimator_v1"],
                                "planner_versions": ["planner_v1"],
                                "evaluator_versions": ["evaluator_v1"],
                            },
                        }
                    }
                }
            },
        }
    },
)
def get_data_summary(
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> DataSummaryOut:
    """读取本人世界模型数据的计数、数据源状态与版本摘要，不含任何敏感原文。"""
    data = container.learner_control_service.get_data_summary(user_id=user.id)
    return DataSummaryOut(**data)


# ===== 模型透明度 =====


@router.get(
    "/model-transparency",
    response_model=ModelTransparencyOut,
    summary="读取模型透明度",
    responses={
        200: {
            "description": "各能力的生产方法与候选模型只读金丝雀状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "模型透明度信息",
                            "value": {
                                "capabilities": [
                                    {
                                        "capability_name": "learning_summary_v1",
                                        "capability_version": "v1",
                                        "production_method": "deterministic_baseline",
                                        "campusmate_lm_status": "SHADOW_ONLY",
                                        "quality_gate_passed": True,
                                        "performance_gate_passed": True,
                                        "performance_measured": True,
                                        "last_evaluated_at": "2026-10-06T08:00:00+00:00",
                                        "uses_real_model_inference": False,
                                        "uses_fixed_prediction_file": True,
                                    }
                                ],
                                "campusmate_lm_enabled": False,
                                "campusmate_lm_affects_production": False,
                                "shadow_results_modify_plans": False,
                                "read_only_canary_active": False,
                                "uses_real_model_inference": False,
                                "uses_fixed_prediction_file": True,
                                "real_inference_observed": False,
                                "last_real_inference_at": None,
                                "fixture_only": True,
                            },
                        }
                    }
                }
            },
        }
    },
)
def get_model_transparency(
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> ModelTransparencyOut:
    """读取候选模型的生产接线状态与各能力透明度信息。

    - 明确候选模型是否影响生产、是否为固定预测文件回放。
    - 只读接口，不触发任何真实模型推理。
    """
    data = container.learner_control_service.get_model_transparency(user_id=user.id)
    return ModelTransparencyOut(
        capabilities=[
            ModelCapabilityTransparencyOut(**cap) for cap in data["capabilities"]
        ],
        campusmate_lm_enabled=data["campusmate_lm_enabled"],
        campusmate_lm_affects_production=data["campusmate_lm_affects_production"],
        shadow_results_modify_plans=data["shadow_results_modify_plans"],
        read_only_canary_active=data.get("read_only_canary_active", False),
        uses_real_model_inference=data.get("uses_real_model_inference", False),
        uses_fixed_prediction_file=data.get("uses_fixed_prediction_file", True),
        real_inference_observed=data.get("real_inference_observed", False),
        last_real_inference_at=data.get("last_real_inference_at"),
        fixture_only=data.get("fixture_only", False),
    )


@router.get(
    "/canary-gate/{capability_name}",
    summary="检查只读门禁",
    responses={
        200: {
            "description": "门禁检查结果：allowed 表示是否放行，reason 说明原因",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "能力未获放行",
                            "value": {"allowed": False, "reason": "canary_feature_flag_disabled"},
                        }
                    }
                }
            },
        }
    },
)
def check_canary_gate(
    capability_name: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
):
    """只读检查指定能力是否可以通过候选模型金丝雀门禁。

    - 依次校验 feature flag、数据源策略、只读能力、promotion 与熔断状态。
    - 仅返回 allowed 与 reason，不执行任何模型调用。
    """
    result = container.learner_control_service.canary_gate(capability_name=capability_name, user_id=user.id)
    return result


__all__ = ["router"]