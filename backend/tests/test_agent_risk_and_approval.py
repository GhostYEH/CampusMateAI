from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import AppException
from app.database.sqlite_db import Database
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.services.agent_runtime.approval_gate import ApprovalGate
from app.services.agent_runtime.risk_engine import RiskEngine


def _runtime():
    db = Database(None)
    with db.transaction() as conn:
        conn.execute("INSERT INTO users(id,username,password_hash,created_at,updated_at) VALUES('u','u','x','n','n')")
    repo = AgentRuntimeRepository(db)
    job = repo.create_job(user_id="u", domain="test", objective_summary="safe")
    run = repo.create_run(job_id=job.id, user_id="u", domain="test", total_steps=1)
    return repo, run


def test_risk_engine_never_executes_manual_only_actions():
    risk = RiskEngine()
    assert risk.classify("task.create", automation_enabled=True).risk_level == "AUTO_SAFE"
    assert risk.classify("external_submission.prepare", automation_enabled=True).risk_level == "CONFIRM_REQUIRED"
    assert risk.classify("payment.execute", automation_enabled=True).risk_level == "MANUAL_ONLY"


def test_approval_is_owned_expiring_and_never_implicitly_approved():
    repo, run = _runtime()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    gate = ApprovalGate(repo)
    approval = gate.create(
        run_id=run.id, user_id="u", action_digest="a" * 64, summary="确认创建任务",
        expires_at=now + timedelta(minutes=5), now=now,
    )
    assert approval.status == "PENDING"
    with pytest.raises(AppException):
        gate.decide(approval_id=approval.id, user_id="other", decision="APPROVED", now=now)
    expired = gate.decide(
        approval_id=approval.id, user_id="u", decision="APPROVED", now=now + timedelta(hours=1)
    )
    assert expired.status == "EXPIRED"
