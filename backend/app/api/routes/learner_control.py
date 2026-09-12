"""Phase 6A: 学生世界模型控制 API 路由。

所有端点仅限学生本人操作，teacher/admin 不可代替学生。
输出严格排除内部表名、source_id、原文、凭据等敏感信息。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

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

router = APIRouter(prefix="/learner-state", tags=["learner-control"])


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


@router.post("/corrections", response_model=CorrectionOut, status_code=201)
def create_correction(
    body: CorrectionCreate,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> CorrectionOut:
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


@router.get("/corrections", response_model=CorrectionPage)
def list_corrections(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: str | None = Query(None, pattern="^(ACTIVE|REVOKED)$"),
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> CorrectionPage:
    rows, total = container.learner_control_service.list_corrections(
        user_id=user.id, page=page, page_size=page_size, status=status
    )
    return CorrectionPage(
        items=[_correction_out(r) for r in rows],
        total=total, page=page, page_size=page_size,
        has_more=page * page_size < total,
    )


@router.post("/corrections/{correction_id}/revoke", response_model=CorrectionOut)
def revoke_correction(
    correction_id: str,
    body: CorrectionRevokeRequest,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> CorrectionOut:
    row = container.learner_control_service.revoke_correction(
        user_id=user.id, correction_id=correction_id
    )
    container.learner_control_service.record_event(
        user_id=user.id, event_type="learner_correction_revoked"
    )
    return _correction_out(row)


# ===== 数据源控制 =====


@router.get("/data-controls", response_model=DataSourceControlList)
def list_data_controls(
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> DataSourceControlList:
    rows = container.learner_control_service.list_source_controls(user_id=user.id)
    return DataSourceControlList(items=[_source_control_out(r) for r in rows])


@router.put("/data-controls/{source_key}", response_model=DataSourceControlOut)
def update_data_control(
    source_key: str,
    body: DataSourceControlUpdate,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> DataSourceControlOut:
    row = container.learner_control_service.update_source_control(
        user_id=user.id, source_key=source_key, status=body.status
    )
    event_type = "data_source_paused" if body.status == "PAUSED" else "data_source_resumed"
    container.learner_control_service.record_event(
        user_id=user.id, event_type=event_type, metadata={"source_key": source_key}
    )
    return _source_control_out(row)


# ===== 世界模型删除 =====


@router.post("/delete-request", response_model=DeleteRequestOut)
def request_deletion(
    body: DeleteRequestCreate,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> DeleteRequestOut:
    row = container.learner_control_service.request_deletion(
        user_id=user.id, scope=body.scope, idempotency_key=body.idempotency_key
    )
    container.learner_control_service.record_event(
        user_id=user.id, event_type="learner_model_delete_requested", metadata={"scope": body.scope}
    )
    return _delete_request_out(row)


@router.get("/delete-status", response_model=DeleteStatusOut)
def get_delete_status(
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> DeleteStatusOut:
    rows = container.learner_control_service.list_delete_requests(user_id=user.id)
    if not rows:
        return DeleteStatusOut()
    history = [_delete_request_out(r) for r in rows]
    return DeleteStatusOut(latest=history[0], history=history)


# ===== 安全导出摘要 =====


@router.get("/data-summary", response_model=DataSummaryOut)
def get_data_summary(
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> DataSummaryOut:
    data = container.learner_control_service.get_data_summary(user_id=user.id)
    return DataSummaryOut(**data)


# ===== 模型透明度 =====


@router.get("/model-transparency", response_model=ModelTransparencyOut)
def get_model_transparency(
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> ModelTransparencyOut:
    data = container.learner_control_service.get_model_transparency(user_id=user.id)
    return ModelTransparencyOut(
        capabilities=[
            ModelCapabilityTransparencyOut(**cap) for cap in data["capabilities"]
        ],
        campusmate_lm_enabled=data["campusmate_lm_enabled"],
        campusmate_lm_affects_production=data["campusmate_lm_affects_production"],
        shadow_results_modify_plans=data["shadow_results_modify_plans"],
    )


@router.get("/canary-gate/{capability_name}")
def check_canary_gate(
    capability_name: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
):
    result = container.learner_control_service.canary_gate(capability_name=capability_name)
    return result


__all__ = ["router"]