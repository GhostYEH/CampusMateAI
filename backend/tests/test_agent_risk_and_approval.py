"""Risk engine + approval gate 测试。"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

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
    def test_expiration_is_checked_after_waiting_for_the_write_lock(
        self, approval_gate, monkeypatch
    ):
        from app.repositories import agent_runtime_repository

        deadline = datetime.now(timezone.utc) + timedelta(minutes=10)
        repo = approval_gate._repo
        aid = repo.create_approval(
            run_id="r1",
            user_id="u1",
            risk_level="CONFIRM_REQUIRED",
            action_summary="等待写锁期间到期",
            expires_at=deadline.isoformat(),
        )
        clock = {"now": deadline - timedelta(seconds=1)}
        monkeypatch.setattr(
            agent_runtime_repository, "_now", lambda: clock["now"].isoformat()
        )
        transaction = repo._db.transaction

        @contextmanager
        def delayed_transaction(*, immediate=False):
            with transaction(immediate=immediate) as conn:
                # Model the clock advancing while the writer waits to enter.
                clock["now"] = deadline
                yield conn

        monkeypatch.setattr(repo._db, "transaction", delayed_transaction)
        assert repo.resolve_approval_if_pending(aid, status="APPROVED") is False
        assert repo.get_approval(aid).status == "EXPIRED"

    @pytest.mark.parametrize("decision", ["APPROVED", "REJECTED"])
    def test_deadline_is_rechecked_when_the_decision_is_written(
        self, approval_gate, monkeypatch, decision
    ):
        from app.repositories import agent_runtime_repository

        aid = approval_gate.require(
            run_id="r1",
            user_id="u1",
            risk_level=RiskLevel.CONFIRM_REQUIRED,
            action_summary="决策落库时已过期",
        )
        expires_at = approval_gate._repo.get_approval(aid).expires_at
        # The gate reads before expiration; a delayed write reaches the deadline.
        monkeypatch.setattr(agent_runtime_repository, "_now", lambda: expires_at)
        with pytest.raises(AgentRuntimeError) as exc:
            approval_gate.resolve(aid, decision=decision, user_id="u1")
        assert (exc.value.http_status, exc.value.code) == (410, "AGENT_INVALID_STATE")
        assert approval_gate._repo.get_approval(aid).status == "EXPIRED"

    @pytest.mark.parametrize("offset,accepted", [(-1, True), (0, False), (1, False)])
    def test_repository_decision_deadline_uses_instants_not_timezone_text(
        self, approval_gate, monkeypatch, offset, accepted
    ):
        from app.repositories import agent_runtime_repository

        deadline = datetime.now(timezone.utc) + timedelta(minutes=10)
        aid = approval_gate._repo.create_approval(
            run_id="r1",
            user_id="u1",
            risk_level="CONFIRM_REQUIRED",
            action_summary="时区边界",
            expires_at=deadline.astimezone(timezone(timedelta(hours=8))).isoformat(),
        )
        monkeypatch.setattr(
            agent_runtime_repository,
            "_now",
            lambda: (deadline + timedelta(microseconds=offset)).isoformat(),
        )
        assert (
            approval_gate._repo.resolve_approval_if_pending(aid, status="APPROVED")
            is accepted
        )
        assert approval_gate._repo.get_approval(aid).status == (
            "APPROVED" if accepted else "EXPIRED"
        )

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

    @pytest.mark.parametrize(
        ("decision", "expected_status", "expected_http_status", "replayed"),
        [
            ("APPROVED", "APPROVED", None, True),
            ("REJECTED", "APPROVED", 409, None),
        ],
    )
    def test_expiry_race_preserves_competing_approval(
        self,
        approval_gate,
        monkeypatch,
        decision,
        expected_status,
        expected_http_status,
        replayed,
    ):
        aid = approval_gate.require(
            run_id="r1",
            user_id="u1",
            risk_level=RiskLevel.CONFIRM_REQUIRED,
            action_summary="过期竞争测试",
            ttl_minutes=-1,
        )
        repo = approval_gate._repo
        original = repo.resolve_approval_if_pending

        def approve_before_expiration_cas(approval_id, *, status, decision_reason=None):
            if approval_id == aid and status == "EXPIRED":
                # Inject an already-settled competing decision; the expiry path
                # must preserve it even if its initial PENDING read was stale.
                repo.resolve_approval(approval_id, status="APPROVED")
                return False
            return original(approval_id, status=status, decision_reason=decision_reason)

        monkeypatch.setattr(
            repo, "resolve_approval_if_pending", approve_before_expiration_cas
        )
        if expected_http_status:
            with pytest.raises(AgentRuntimeError) as exc:
                approval_gate.resolve(aid, decision=decision, user_id="u1")
            assert exc.value.http_status == expected_http_status
            assert exc.value.code == "AGENT_APPROVAL_CONFLICT"
        else:
            result = approval_gate.resolve(aid, decision=decision, user_id="u1")
            assert result == {
                "approval_id": aid,
                "status": expected_status,
                "replayed": replayed,
            }
        assert repo.get_approval(aid).status == expected_status
