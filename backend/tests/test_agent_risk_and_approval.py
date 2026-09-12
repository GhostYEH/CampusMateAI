"""Risk engine + approval gate 测试。"""
from __future__ import annotations

import pytest

from app.core.exceptions import AgentRuntimeError
from app.database.sqlite_db import reset_db_for_tests
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.schemas.agent_contract_enums import ApprovalStatus, RiskLevel
from app.services.agent_runtime.approval_gate import ApprovalGate
from app.services.agent_runtime.risk_engine import RiskEngine


@pytest.fixture
def approval_gate():
    db = reset_db_for_tests()
    conn = db._connect()
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u1', 'u1', 'x', 'student', 't', 't')"
        )
        conn.execute(
            "INSERT INTO agent_jobs (job_id, user_id, job_kind, status, created_at, updated_at) "
            "VALUES ('j1', 'u1', 'final_review', 'QUEUED', 't', 't')"
        )
        conn.execute(
            "INSERT INTO agent_runs (run_id, job_id, user_id, status, phase, "
            "created_at, updated_at) VALUES ('r1', 'j1', 'u1', 'QUEUED', 'IDLE', 't', 't')"
        )
        conn.commit()
    finally:
        db._release(conn)
    repo = AgentRuntimeRepository(db)
    return ApprovalGate(repo, default_ttl_minutes=30)


class TestRiskEngine:
    def test_manual_only_classification(self):
        engine = RiskEngine()
        for action in [
            "auth.login",
            "captcha.solve",
            "payment.pay",
            "registration.register",
            "assignment.submit",
            "external_submission.execute",
            "school_system.mutate",
        ]:
            assessment = engine.assess(action)
            assert assessment.risk_level == RiskLevel.MANUAL_ONLY, f"{action}"

    def test_confirm_required_classification(self):
        engine = RiskEngine()
        for action in ["plan.activate", "task.update", "research.source.fetch"]:
            assessment = engine.assess(action)
            assert assessment.risk_level == RiskLevel.CONFIRM_REQUIRED
            assert assessment.requires_approval is True

    def test_auto_safe_when_user_enabled(self):
        engine = RiskEngine()
        assessment = engine.assess("task.create", user_enabled_auto=True)
        assert assessment.risk_level == RiskLevel.AUTO_SAFE
        assert RiskEngine.can_auto_execute(assessment) is True

    def test_default_confirm_when_not_enabled(self):
        engine = RiskEngine()
        assessment = engine.assess("task.create")
        assert assessment.risk_level == RiskLevel.CONFIRM_REQUIRED

    def test_manual_only_never_auto_execute(self):
        engine = RiskEngine()
        assessment = engine.assess("payment.pay")
        assert RiskEngine.can_auto_execute(assessment) is False
        assert RiskEngine.is_manual_only(assessment) is True


class TestApprovalGate:
    def test_require_creates_pending_approval(self, approval_gate):
        aid = approval_gate.require(
            run_id="r1",
            user_id="u1",
            risk_level=RiskLevel.CONFIRM_REQUIRED,
            action_summary="激活计划",
        )
        apv = approval_gate._repo.get_approval(aid)
        assert apv.status == ApprovalStatus.PENDING.value

    def test_resolve_approved(self, approval_gate):
        aid = approval_gate.require(
            run_id="r1",
            user_id="u1",
            risk_level=RiskLevel.CONFIRM_REQUIRED,
            action_summary="x",
        )
        result = approval_gate.resolve(aid, decision="APPROVED", user_id="u1")
        assert result["status"] == ApprovalStatus.APPROVED.value

    def test_resolve_rejected(self, approval_gate):
        aid = approval_gate.require(
            run_id="r1",
            user_id="u1",
            risk_level=RiskLevel.CONFIRM_REQUIRED,
            action_summary="x",
        )
        result = approval_gate.resolve(aid, decision="REJECTED", user_id="u1")
        assert result["status"] == ApprovalStatus.REJECTED.value

    def test_resolve_already_resolved_raises(self, approval_gate):
        aid = approval_gate.require(
            run_id="r1",
            user_id="u1",
            risk_level=RiskLevel.CONFIRM_REQUIRED,
            action_summary="x",
        )
        approval_gate.resolve(aid, decision="APPROVED", user_id="u1")
        with pytest.raises(AgentRuntimeError):
            approval_gate.resolve(aid, decision="REJECTED", user_id="u1")

    def test_resolve_wrong_user_raises(self, approval_gate):
        aid = approval_gate.require(
            run_id="r1",
            user_id="u1",
            risk_level=RiskLevel.CONFIRM_REQUIRED,
            action_summary="x",
        )
        with pytest.raises(AgentRuntimeError) as exc:
            approval_gate.resolve(aid, decision="APPROVED", user_id="u2")
        assert exc.value.code == "AGENT_PERMISSION_DENIED"

    def test_manual_only_rejects_auto_approval(self, approval_gate):
        aid = approval_gate.require(
            run_id="r1",
            user_id="u1",
            risk_level=RiskLevel.MANUAL_ONLY,
            action_summary="提交作业",
        )
        with pytest.raises(AgentRuntimeError) as exc:
            approval_gate.resolve(aid, decision="APPROVED", reason="auto:batch")
        assert exc.value.code == "AGENT_PERMISSION_DENIED"

    def test_manual_only_allows_explicit_approval(self, approval_gate):
        aid = approval_gate.require(
            run_id="r1",
            user_id="u1",
            risk_level=RiskLevel.MANUAL_ONLY,
            action_summary="手动提交",
        )
        result = approval_gate.resolve(aid, decision="APPROVED", reason="用户手动确认")
        assert result["status"] == ApprovalStatus.APPROVED.value

    def test_nonexistent_approval_raises(self, approval_gate):
        with pytest.raises(AgentRuntimeError):
            approval_gate.resolve("nonexistent", decision="APPROVED")