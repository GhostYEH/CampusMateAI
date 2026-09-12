"""Phase 6A: 学生世界模型控制的业务逻辑层。

协调 repository、state service 和 knowledge service，
实现状态纠正、数据源控制、世界模型删除和安全导出摘要。
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Optional

from ..core.exceptions import (
    LearnerCorrectionNotFound,
    LearnerCorrectionSnapshotMismatch,
    LearnerModelDataNotFound,
    LearnerSourceNotSupported,
    NotFoundError,
)
from ..repositories.learner_control_repository import (
    DEFAULT_SOURCES,
    DataSourceControlRow,
    DeleteRequestRow,
    LearnerControlRepository,
    CorrectionRow,
)
from ..repositories.learner_state_repository import LearnerStateRepository
from ..repositories.model_shadow_repository import ModelShadowRepository


class LearnerControlService:
    """学生世界模型控制服务。"""

    def __init__(
        self,
        repository: LearnerControlRepository,
        state_repository: LearnerStateRepository,
        shadow_repository: ModelShadowRepository,
    ) -> None:
        self._repo = repository
        self._state_repo = state_repository
        self._shadow_repo = shadow_repository

    # ===== 状态纠正 =====

    def create_correction(
        self,
        *,
        user_id: str,
        projection_kind: str,
        projection_scope: str,
        scope_type: str,
        scope_id: str,
        state_type: str,
        target_snapshot_id: str,
        correction_type: str,
        reason_code: str,
        idempotency_key: str,
    ) -> CorrectionRow:
        """创建状态纠正。

        纠正不能修改历史 Snapshot，只作为新的可审计输入。
        验证目标快照存在且属于当前用户。
        验证请求字段与目标快照完全一致，不一致返回稳定 409，不泄露真实字段。
        """
        snapshot = self._state_repo.get_snapshot(
            user_id=user_id,
            snapshot_id=target_snapshot_id,
            projection_kind=projection_kind,
            projection_scope=projection_scope,
        )
        if snapshot is None:
            raise NotFoundError()
        if (
            snapshot.scope_type != scope_type
            or snapshot.scope_id != scope_id
            or snapshot.state_type != state_type
        ):
            raise LearnerCorrectionSnapshotMismatch()
        return self._repo.create_correction(
            user_id=user_id,
            projection_kind=projection_kind,
            projection_scope=projection_scope,
            scope_type=scope_type,
            scope_id=scope_id,
            state_type=state_type,
            target_snapshot_id=target_snapshot_id,
            correction_type=correction_type,
            reason_code=reason_code,
            idempotency_key=idempotency_key,
        )

    def list_corrections(
        self,
        *,
        user_id: str,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
    ) -> tuple[list[CorrectionRow], int]:
        return self._repo.list_corrections(
            user_id=user_id, page=page, page_size=page_size, status=status
        )

    def revoke_correction(self, *, user_id: str, correction_id: str) -> CorrectionRow:
        return self._repo.revoke_correction(user_id=user_id, correction_id=correction_id)

    def get_active_corrections(self, *, user_id: str) -> list[CorrectionRow]:
        """返回当前用户的所有活跃纠正，供投影服务使用。"""
        return self._repo.list_active_corrections(user_id=user_id)

    # ===== 数据源控制 =====

    def list_source_controls(self, *, user_id: str) -> list[DataSourceControlRow]:
        return self._repo.list_source_controls(user_id=user_id)

    def update_source_control(
        self,
        *,
        user_id: str,
        source_key: str,
        status: str,
    ) -> DataSourceControlRow:
        if source_key not in DEFAULT_SOURCES:
            raise LearnerSourceNotSupported()
        return self._repo.upsert_source_control(
            user_id=user_id, source_key=source_key, status=status
        )

    def is_source_paused(self, *, user_id: str, source_key: str) -> bool:
        return self._repo.is_source_paused(user_id=user_id, source_key=source_key)

    # ===== 世界模型删除 =====


    def request_deletion(
        self,
        *,
        user_id: str,
        scope: str,
        idempotency_key: str,
    ) -> DeleteRequestRow:
        """原子化删除指定范围的学生模型数据。

        单事务内完成：幂等检查 + before count + delete + after count + record。
        中途任一步骤失败，整体回滚。
        """
        valid_scopes = {
            "STATE_ONLY", "EVENTS_AND_STATE", "KNOWLEDGE_ONLY",
            "PLANS_ONLY", "MODEL_SHADOW_ONLY", "ALL_LEARNER_MODEL_DATA",
        }
        if scope not in valid_scopes:
            raise NotFoundError()
        return self._repo.request_deletion_atomic(
            user_id=user_id,
            scope=scope,
            idempotency_key=idempotency_key,
        )

    def list_delete_requests(self, *, user_id: str, limit: int = 10) -> list[DeleteRequestRow]:
        return self._repo.list_delete_requests(user_id=user_id, limit=limit)

    # ===== 数据摘要 =====

    def get_data_summary(self, *, user_id: str) -> dict[str, Any]:
        return self._repo.get_data_summary(user_id=user_id)

    # ===== 模型透明度 =====

    def get_model_transparency(self, *, user_id: str) -> dict[str, Any]:
        """返回非敏感能力状态，供前端展示模型透明度。"""
        capabilities = []
        capability_defs = [
            ("c_kc_classification_v1", "1.0", "deterministic_taxonomy_match"),
            ("c_error_classification_v1", "1.0", "error_code_whitelist_match"),
            ("learning_summary_v1", "1.0", "evidence_grounded_summary"),
            ("read_only_tool_routing_v1", "1.0", "read_only_allowlist"),
        ]
        with self._shadow_repo._db.transaction() as conn:
            for cap_name, cap_version, prod_method in capability_defs:
                promo_row = conn.execute(
                    """SELECT * FROM model_promotion_decisions
                    WHERE capability_name=? ORDER BY created_at DESC LIMIT 1""",
                    (cap_name,),
                ).fetchone()
                if promo_row is None:
                    campusmate_lm_status = "SHADOW_ONLY"
                    quality_gate_passed = False
                    performance_gate_passed = False
                    performance_measured = False
                    last_evaluated_at = None
                else:
                    campusmate_lm_status = promo_row["decision"]
                    failed_gates = json.loads(promo_row["failed_gates_json"] or "[]")
                    quality_gate_passed = len(failed_gates) == 0
                    performance_gate_passed = False
                    performance_measured = False
                    last_evaluated_at = (
                        datetime.fromisoformat(promo_row["created_at"])
                        if promo_row["created_at"]
                        else None
                    )
                capabilities.append({
                    "capability_name": cap_name,
                    "capability_version": cap_version,
                    "production_method": prod_method,
                    "campusmate_lm_status": campusmate_lm_status,
                    "quality_gate_passed": quality_gate_passed,
                    "performance_gate_passed": performance_gate_passed,
                    "performance_measured": performance_measured,
                    "last_evaluated_at": last_evaluated_at,
                    "uses_real_model_inference": False,
                    "uses_fixed_prediction_file": True,
                })
        return {
            "capabilities": capabilities,
            "campusmate_lm_enabled": False,
            "campusmate_lm_affects_production": False,
            "shadow_results_modify_plans": False,
        }

    # ===== 产品事件 =====

    def record_event(
        self,
        *,
        user_id: str,
        event_type: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        self._repo.record_product_event(
            user_id=user_id, event_type=event_type, metadata=metadata
        )


__all__ = ["LearnerControlService"]