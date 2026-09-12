"""Phase 7C: 只读金丝雀门禁测试。"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests


def _setup():
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    student = container.user_repository.create_user(
        username="canary_student", password_hash=hash_password("Demo123456"), role="student", display_name="S"
    )
    client = TestClient(create_app())
    resp = client.post("/api/v1/auth/login", json={"username": "canary_student", "password": "Demo123456"})
    auth = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    return client, container, auth, student.id


def _insert_promotion_decision(container, capability_name, decision):
    now = datetime.now(timezone.utc).isoformat()
    with container.db.transaction() as conn:
        conn.execute(
            """INSERT INTO model_promotion_decisions
               (decision_id, model_key, model_version, capability_name, capability_version,
                dataset_version, evaluator_version, threshold_version, metrics_digest,
                decision, failed_gates_json, created_at)
               VALUES (?, 'campusmate-lm', 'candidate-v1', ?, 'v1',
                'ds-v1', 'eval-v1', 'th-v1', 'digest-placeholder',
                ?, '[]', ?)""",
            (f"promo_{capability_name}_{now}", capability_name, decision, now),
        )


def test_write_capability_rejected():
    """写能力永远不走 canary。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "c_kc_classification_v1", "ELIGIBLE_FOR_CANARY")
    result = container.learner_control_service.canary_gate(capability_name="c_kc_classification_v1")
    assert result["allowed"] is False
    assert result["reason"] == "capability_is_not_read_only"


def test_read_only_capability_allowed_when_eligible():
    """只读能力在 ELIGIBLE_FOR_CANARY 状态时可以通过 canary。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "learning_summary_v1", "ELIGIBLE_FOR_CANARY")
    result = container.learner_control_service.canary_gate(capability_name="learning_summary_v1")
    assert result["allowed"] is True
    assert result["reason"] is None


def test_read_only_capability_rejected_when_shadow_only():
    """只读能力在 SHADOW_ONLY 状态时不走 canary。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "learning_summary_v1", "SHADOW_ONLY")
    result = container.learner_control_service.canary_gate(capability_name="learning_summary_v1")
    assert result["allowed"] is False
    assert "status_is_" in result["reason"]


def test_no_promotion_decision_rejected():
    """没有 promotion decision 时不走 canary。"""
    client, container, auth, uid = _setup()
    result = container.learner_control_service.canary_gate(capability_name="learning_summary_v1")
    assert result["allowed"] is False
    assert result["reason"] == "no_promotion_decision"


def test_tool_routing_capability_allowed_when_eligible():
    """read_only_tool_routing_v1 在 ELIGIBLE_FOR_CANARY 状态时可以通过 canary。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "read_only_tool_routing_v1", "ELIGIBLE_FOR_CANARY")
    result = container.learner_control_service.canary_gate(capability_name="read_only_tool_routing_v1")
    assert result["allowed"] is True


def test_error_classification_rejected():
    """c_error_classification_v1 不走 canary（非只读）。"""
    client, container, auth, uid = _setup()
    _insert_promotion_decision(container, "c_error_classification_v1", "ELIGIBLE_FOR_CANARY")
    result = container.learner_control_service.canary_gate(capability_name="c_error_classification_v1")
    assert result["allowed"] is False


def test_api_endpoint_write_capability():
    """API 端点验证写能力被拒绝。"""
    client, container, auth, uid = _setup()
    resp = client.get("/api/v1/learner-state/canary-gate/c_kc_classification_v1", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["allowed"] is False


def test_api_endpoint_read_only_capability():
    """API 端点验证只读能力。"""
    client, container, auth, uid = _setup()
    resp = client.get("/api/v1/learner-state/canary-gate/learning_summary_v1", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["allowed"] is False
    assert resp.json()["reason"] == "no_promotion_decision"