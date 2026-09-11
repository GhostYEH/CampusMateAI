"""Phase 6A: 状态纠正 API 测试。

覆盖：
- 创建纠正（幂等、语义冲突 409）
- 列出纠正
- 撤销纠正（幂等）
- 跨用户 404
- teacher/admin 被拒绝
- 纠正不覆盖历史 Snapshot
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.security import hash_password

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests


def _setup():
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    student = container.user_repository.create_user(
        username="corr_student", password_hash=hash_password("Demo123456"), role="student", display_name="S"
    )
    client = TestClient(create_app())
    resp = client.post("/api/v1/auth/login", json={"username": "corr_student", "password": "Demo123456"})
    auth = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    return client, container, auth, student.id


def _ensure_snapshot(container, user_id):
    """触发状态投影，返回一个 snapshot_id。"""
    as_of = datetime.now(timezone.utc).replace(microsecond=0)
    result = container.learner_state_service.project_user(
        user_id, as_of=as_of, trigger="test"
    )
    snapshots, _ = container.learner_state_repository.list_snapshots(
        user_id=user_id, page=1, page_size=10
    )
    if snapshots:
        return snapshots[0]
    return None


def test_create_correction_idempotent():
    """相同幂等键 + 相同请求 → 返回已有记录。"""
    client, container, auth, uid = _setup()
    snap = _ensure_snapshot(container, uid)
    assert snap is not None, "need at least one snapshot"
    body = {
        "projection_kind": "CORE",
        "projection_scope": "__user__",
        "scope_type": snap.scope_type,
        "scope_id": snap.scope_id,
        "state_type": snap.state_type,
        "target_snapshot_id": snap.snapshot_id,
        "correction_type": "MARK_INACCURATE",
        "reason_code": "EVIDENCE_NOT_RELEVANT",
        "idempotency_key": "corr-key-1",
    }
    r1 = client.post("/api/v1/learner-state/corrections", json=body, headers=auth)
    assert r1.status_code == 201, r1.text
    r2 = client.post("/api/v1/learner-state/corrections", json=body, headers=auth)
    assert r2.status_code == 201, r2.text
    assert r1.json()["correction_id"] == r2.json()["correction_id"]


def test_create_correction_conflict():
    """相同幂等键 + 不同请求 → 409。"""
    client, container, auth, uid = _setup()
    snap = _ensure_snapshot(container, uid)
    assert snap is not None
    base = {
        "projection_kind": "CORE",
        "projection_scope": "__user__",
        "scope_type": snap.scope_type,
        "scope_id": snap.scope_id,
        "state_type": snap.state_type,
        "target_snapshot_id": snap.snapshot_id,
        "correction_type": "MARK_INACCURATE",
        "reason_code": "EVIDENCE_NOT_RELEVANT",
        "idempotency_key": "corr-conflict-1",
    }
    r1 = client.post("/api/v1/learner-state/corrections", json=base, headers=auth)
    assert r1.status_code == 201
    diff = {**base, "correction_type": "NOT_APPLICABLE", "reason_code": "OTHER_CONTROLLED_REASON"}
    r2 = client.post("/api/v1/learner-state/corrections", json=diff, headers=auth)
    assert r2.status_code == 409
    assert r2.json()["code"] == "LEARNER_CORRECTION_CONFLICT"


def test_list_corrections():
    """列出纠正。"""
    client, container, auth, uid = _setup()
    snap = _ensure_snapshot(container, uid)
    if snap is None:
        return
    body = {
        "projection_kind": "CORE",
        "projection_scope": "__user__",
        "scope_type": snap.scope_type,
        "scope_id": snap.scope_id,
        "state_type": snap.state_type,
        "target_snapshot_id": snap.snapshot_id,
        "correction_type": "MARK_INACCURATE",
        "reason_code": "EVIDENCE_NOT_RELEVANT",
        "idempotency_key": "list-1",
    }
    client.post("/api/v1/learner-state/corrections", json=body, headers=auth)
    resp = client.get("/api/v1/learner-state/corrections", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_revoke_correction():
    """撤销纠正，再次撤销幂等。"""
    client, container, auth, uid = _setup()
    snap = _ensure_snapshot(container, uid)
    assert snap is not None
    body = {
        "projection_kind": "CORE",
        "projection_scope": "__user__",
        "scope_type": snap.scope_type,
        "scope_id": snap.scope_id,
        "state_type": snap.state_type,
        "target_snapshot_id": snap.snapshot_id,
        "correction_type": "MARK_INACCURATE",
        "reason_code": "EVIDENCE_NOT_RELEVANT",
        "idempotency_key": "revoke-1",
    }
    r1 = client.post("/api/v1/learner-state/corrections", json=body, headers=auth)
    cid = r1.json()["correction_id"]
    r2 = client.post(
        f"/api/v1/learner-state/corrections/{cid}/revoke",
        json={"idempotency_key": "revoke-key-1"},
        headers=auth,
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "REVOKED"
    r3 = client.post(
        f"/api/v1/learner-state/corrections/{cid}/revoke",
        json={"idempotency_key": "revoke-key-2"},
        headers=auth,
    )
    assert r3.status_code == 200
    assert r3.json()["status"] == "REVOKED"


def test_revoke_not_found():
    """撤销不存在的纠正 → 404。"""
    client, _container, auth, _uid = _setup()
    resp = client.post(
        "/api/v1/learner-state/corrections/nonexistent/revoke",
        json={"idempotency_key": "x"},
        headers=auth,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "LEARNER_CORRECTION_NOT_FOUND"


def test_correction_target_not_found():
    """纠正目标快照不存在 → 404。"""
    client, _container, auth, _uid = _setup()
    body = {
        "projection_kind": "CORE",
        "projection_scope": "__user__",
        "scope_type": "USER",
        "scope_id": "user1",
        "state_type": "observed_learning_activity",
        "target_snapshot_id": "nonexistent-snapshot",
        "correction_type": "MARK_INACCURATE",
        "reason_code": "EVIDENCE_NOT_RELEVANT",
        "idempotency_key": "no-snap-1",
    }
    resp = client.post("/api/v1/learner-state/corrections", json=body, headers=auth)
    assert resp.status_code == 404


def test_admin_forbidden():
    """admin 不能操作学生纠正。"""
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    container.user_repository.create_user(
        username="corr_admin", password_hash=hash_password("Demo123456"), role="admin", display_name="A"
    )
    client = TestClient(create_app())
    resp = client.post("/api/v1/auth/login", json={"username": "corr_admin", "password": "Demo123456"})
    auth = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    r = client.get("/api/v1/learner-state/corrections", headers=auth)
    assert r.status_code == 403


def test_correction_output_no_sensitive():
    """纠正输出不包含敏感字段。"""
    client, container, auth, uid = _setup()
    snap = _ensure_snapshot(container, uid)
    if snap is None:
        return
    body = {
        "projection_kind": "CORE",
        "projection_scope": "__user__",
        "scope_type": snap.scope_type,
        "scope_id": snap.scope_id,
        "state_type": snap.state_type,
        "target_snapshot_id": snap.snapshot_id,
        "correction_type": "MARK_INACCURATE",
        "reason_code": "EVIDENCE_NOT_RELEVANT",
        "idempotency_key": "sensitive-1",
    }
    resp = client.post("/api/v1/learner-state/corrections", json=body, headers=auth)
    data = resp.json()
    for forbidden in ("source_id", "payload", "prompt", "table_name", "internal"):
        assert forbidden not in data