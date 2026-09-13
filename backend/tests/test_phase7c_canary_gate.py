"""Phase 7C: 只读金丝雀门禁测试。

覆盖 7 项门禁：
1. 全局 canary feature flag
2. 用户 MODEL_SHADOW 数据源控制
3. 候选模型配置可用
4. capability 只读
5. promotion ELIGIBLE_FOR_CANARY
6. 质量/安全/性能门禁通过
7. 熔断器未打开
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests


def _canary_settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        campusmate_lm_canary_enabled=True,
        campusmate_lm_enabled=True,
        campusmate_lm_base_url="http://test-candidate:8000",
        campusmate_lm_api_key="test-key",
        campusmate_lm_model_name="test-model",
    )


def _setup(settings: Settings | None = None):
    s = settings or _canary_settings()
    container = reset_container_for_tests(s)
    student = container.user_repository.create_user(
        username="canary_student", password_hash=hash_password("Demo123456"), role="student", display_name="S"
    )
    client = TestClient(create_app())
    resp = client.post("/api/v1/auth/login", json={"username": "canary_student", "password": "Demo123456"})
    auth = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    return client, container, auth, student.id


def _insert_promotion_decision(container, capability_name, decision, failed_gates=None):
    now = datetime.now(timezone.utc).isoformat()
    gates_json = json.dumps(failed_gates or [])
    with container.db.transaction() as conn:
        conn.execute(
            """INSERT INTO model_promotion_decisions
               (decision_id, model_key, model_version, capability_name, capability_version,
                dataset_version, evaluator_version, threshold_version, metrics_digest,
                decision, failed_gates_json, created_at)
               VALUES (?, 'campusmate-lm', 'candidate-v1', ?, 'v1',
                'ds-v1', 'eval-v1', 'th-v1', 'digest-placeholder',
                ?, ?, ?)""",
            (f"promo_{capability_name}_{now}", capability_name, decision, gates_json, now),
        )


def _insert_shadow_run(container, user_id, capability_name, used_fallback=True):
    now = datetime.now(timezone.utc).isoformat()
    shadow_id = f"shadow_{capability_name}_{now}"
    with container.db.transaction() as conn:
        conn.execute(
            """INSERT INTO model_shadow_runs
               (shadow_run_id, scope, user_id, request_id, capability_name, capability_version,
                production_model_key, candidate_model_key, dataset_version, online_sample_version,
                prompt_version, input_digest, expected_output_digest, candidate_output_digest,
                created_at, expires_at)
               VALUES (?, 'ONLINE', ?, ?, ?, 'v1', 'mature', 'campusmate-lm', 'ds-v1', 'online-v1',
                'pv1', 'dig1', NULL, 'out1', ?, ?)""",
            (shadow_id, user_id, f"req_{shadow_id}", capability_name, now, now),
        )
        conn.execute(
            """INSERT INTO model_shadow_results
               (shadow_run_id, schema_valid, policy_valid, abstained, used_fallback,
                failure_code, latency_ms, resource_metrics_json, evaluator_version, created_at)
               VALUES (?, 1, 1, 0, ?, NULL, 100, '{}', 'eval-v1', ?)""",
            (shadow_id, int(used_fallback), now),
        )


# ===== Gate 1: canary feature flag =====


def test_canary_feature_flag_disabled():
    """全局 canary feature flag 关闭时拒绝。"""
    settings = Settings(app_env="test", database_url="sqlite:///:memory:", campusmate_lm_canary_enabled=False)
    client, container, auth, uid = _setup(settings)
    _insert_promotion_decision(container, "learning_summary_v1", "ELIGIBLE_FOR_CANARY")
    result = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=uid)
    assert result["allowed"] is False
    assert result["reason"] == "canary_feature_flag_disabled"


# ===== Gate 2: user source control =====


def test_model_shadow_paused_for_user():
    """当前用户 MODEL_SHADOW 暂停时拒绝。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "learning_summary_v1", "ELIGIBLE_FOR_CANARY")
    container.learner_control_service.update_source_control(
        user_id=uid, source_key="MODEL_SHADOW", status="PAUSED"
    )
    result = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=uid)
    assert result["allowed"] is False
    assert result["reason"] == "model_shadow_paused_for_user"


def test_cross_user_source_control():
    """用户 A 暂停 MODEL_SHADOW 不影响用户 B。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "learning_summary_v1", "ELIGIBLE_FOR_CANARY")
    student_b = container.user_repository.create_user(
        username="canary_student_b", password_hash=hash_password("Demo123456"), role="student", display_name="B"
    )
    container.learner_control_service.update_source_control(
        user_id=uid, source_key="MODEL_SHADOW", status="PAUSED"
    )
    result_a = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=uid)
    assert result_a["allowed"] is False
    result_b = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=student_b.id)
    assert result_b["allowed"] is True


# ===== Gate 3: candidate model configured =====


def test_candidate_model_not_configured():
    """候选模型未配置时拒绝。"""
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        campusmate_lm_canary_enabled=True,
        campusmate_lm_enabled=False,
    )
    client, container, auth, uid = _setup(settings)
    _insert_promotion_decision(container, "learning_summary_v1", "ELIGIBLE_FOR_CANARY")
    result = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=uid)
    assert result["allowed"] is False
    assert result["reason"] == "candidate_model_not_configured"


# ===== Gate 4: read-only capability =====


def test_write_capability_rejected():
    """写能力永远不走 canary。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "write_capability_test_v1", "ELIGIBLE_FOR_CANARY")
    result = container.learner_control_service.canary_gate(capability_name="write_capability_test_v1", user_id=uid)
    assert result["allowed"] is False
    assert result["reason"] == "capability_is_not_read_only"


def test_error_classification_rejected():
    """非只读能力不走 canary。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "another_write_capability_v1", "ELIGIBLE_FOR_CANARY")
    result = container.learner_control_service.canary_gate(capability_name="another_write_capability_v1", user_id=uid)
    assert result["allowed"] is False


# ===== Gate 5: promotion status =====


def test_read_only_capability_allowed_when_eligible():
    """只读能力在 ELIGIBLE_FOR_CANARY 状态时可以通过 canary。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "learning_summary_v1", "ELIGIBLE_FOR_CANARY")
    result = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=uid)
    assert result["allowed"] is True
    assert result["reason"] is None


def test_read_only_capability_rejected_when_shadow_only():
    """只读能力在 SHADOW_ONLY 状态时不走 canary。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "learning_summary_v1", "SHADOW_ONLY")
    result = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=uid)
    assert result["allowed"] is False
    assert "status_is_" in result["reason"]


def test_no_promotion_decision_rejected():
    """没有 promotion decision 时不走 canary。"""
    client, container, auth, uid = _setup()
    result = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=uid)
    assert result["allowed"] is False
    assert result["reason"] == "no_promotion_decision"


def test_tool_routing_capability_allowed_when_eligible():
    """read_only_tool_routing_v1 在 ELIGIBLE_FOR_CANARY 状态时可以通过 canary。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "read_only_tool_routing_v1", "ELIGIBLE_FOR_CANARY")
    result = container.learner_control_service.canary_gate(capability_name="read_only_tool_routing_v1", user_id=uid)
    assert result["allowed"] is True


# ===== Gate 6: quality gates =====


def test_quality_gates_failed():
    """门禁未全部通过时拒绝。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(
        container, "learning_summary_v1", "ELIGIBLE_FOR_CANARY",
        failed_gates=["SCHEMA_VALIDATION_FAILED"],
    )
    result = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=uid)
    assert result["allowed"] is False
    assert result["reason"] == "quality_gates_failed"
    assert "SCHEMA_VALIDATION_FAILED" in result["failed_gates"]


def test_performance_not_measured_gate_failed():
    """性能未测量时拒绝。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(
        container, "learning_summary_v1", "ELIGIBLE_FOR_CANARY",
        failed_gates=["PERFORMANCE_NOT_MEASURED"],
    )
    result = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=uid)
    assert result["allowed"] is False
    assert result["reason"] == "quality_gates_failed"


# ===== Gate 7: circuit breaker =====


def test_circuit_breaker_open():
    """熔断器打开时拒绝。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "learning_summary_v1", "ELIGIBLE_FOR_CANARY")
    runner = container.model_shadow_runner
    for _ in range(runner.circuit_breaker_threshold):
        runner._record_failure("learning_summary_v1")
    result = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=uid)
    assert result["allowed"] is False
    assert result["reason"] == "circuit_breaker_open"


def test_circuit_breaker_closed_after_success():
    """熔断器在成功后重置，canary 恢复允许。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "learning_summary_v1", "ELIGIBLE_FOR_CANARY")
    runner = container.model_shadow_runner
    for _ in range(runner.circuit_breaker_threshold):
        runner._record_failure("learning_summary_v1")
    runner._record_success("learning_summary_v1")
    result = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=uid)
    assert result["allowed"] is True


# ===== API endpoint tests =====


def test_api_endpoint_write_capability():
    """API 端点验证写能力被拒绝。"""
    client, container, auth, uid = _setup()
    resp = client.get("/api/v1/learner-state/canary-gate/write_capability_test_v1", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["allowed"] is False


def test_api_endpoint_feature_flag_disabled():
    """API 端点验证 feature flag 关闭时拒绝。"""
    settings = Settings(app_env="test", database_url="sqlite:///:memory:", campusmate_lm_canary_enabled=False)
    client, container, auth, uid = _setup(settings)
    _insert_promotion_decision(container, "learning_summary_v1", "ELIGIBLE_FOR_CANARY")
    resp = client.get("/api/v1/learner-state/canary-gate/learning_summary_v1", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["allowed"] is False
    assert resp.json()["reason"] == "canary_feature_flag_disabled"


def test_api_endpoint_allowed():
    """API 端点验证全部门禁通过时允许。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "learning_summary_v1", "ELIGIBLE_FOR_CANARY")
    resp = client.get("/api/v1/learner-state/canary-gate/learning_summary_v1", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["allowed"] is True


# ===== Model transparency tests =====


def test_model_transparency_no_shadow_runs():
    """没有 shadow run 时 real_inference_observed=False, fixture_only=False。"""
    client, container, auth, uid = _setup()
    data = container.learner_control_service.get_model_transparency(user_id=uid)
    assert data["real_inference_observed"] is False
    assert data["fixture_only"] is False
    assert data["uses_real_model_inference"] is False
    assert data["uses_fixed_prediction_file"] is True
    assert data["last_real_inference_at"] is None


def test_model_transparency_fixture_only():
    """有 shadow run 但全部 fallback 时 fixture_only=True。"""
    client, container, auth, uid = _setup()
    _insert_shadow_run(container, uid, "learning_summary_v1", used_fallback=True)
    data = container.learner_control_service.get_model_transparency(user_id=uid)
    assert data["real_inference_observed"] is False
    assert data["fixture_only"] is True
    assert data["uses_real_model_inference"] is False
    assert data["uses_fixed_prediction_file"] is True


def test_model_transparency_real_inference():
    """有非 fallback shadow run 时 real_inference_observed=True。"""
    client, container, auth, uid = _setup()
    _insert_shadow_run(container, uid, "learning_summary_v1", used_fallback=False)
    data = container.learner_control_service.get_model_transparency(user_id=uid)
    assert data["real_inference_observed"] is True
    assert data["fixture_only"] is False
    assert data["uses_real_model_inference"] is True
    assert data["uses_fixed_prediction_file"] is False
    assert data["last_real_inference_at"] is not None


def test_model_transparency_cross_user():
    """用户 A 的 shadow run 不影响用户 B 的透明度。"""
    client, container, auth, uid = _setup()
    student_b = container.user_repository.create_user(
        username="canary_student_b", password_hash=hash_password("Demo123456"), role="student", display_name="B"
    )
    _insert_shadow_run(container, uid, "learning_summary_v1", used_fallback=False)
    data_a = container.learner_control_service.get_model_transparency(user_id=uid)
    data_b = container.learner_control_service.get_model_transparency(user_id=student_b.id)
    assert data_a["real_inference_observed"] is True
    assert data_b["real_inference_observed"] is False


def test_model_transparency_canary_active():
    """ELIGIBLE_FOR_CANARY + 只读 + 门禁通过 + 模型配置 → canary_active=True。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "learning_summary_v1", "ELIGIBLE_FOR_CANARY")
    data = container.learner_control_service.get_model_transparency(user_id=uid)
    assert data["read_only_canary_active"] is True
    cap = next(c for c in data["capabilities"] if c["capability_name"] == "learning_summary_v1")
    assert cap["quality_gate_passed"] is True
    assert cap["performance_measured"] is True


def test_model_transparency_canary_not_active_when_not_configured():
    """候选模型未配置时 canary_active=False。"""
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        campusmate_lm_canary_enabled=True,
        campusmate_lm_enabled=False,
    )
    client, container, auth, uid = _setup(settings)
    _insert_promotion_decision(container, "learning_summary_v1", "ELIGIBLE_FOR_CANARY")
    data = container.learner_control_service.get_model_transparency(user_id=uid)
    assert data["read_only_canary_active"] is False
