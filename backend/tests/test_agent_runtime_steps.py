from datetime import datetime, timedelta, timezone

from app.database.sqlite_db import Database
from app.repositories.agent_runtime_repository import AgentRuntimeRepository


def _runtime():
    db = Database(None)
    with db.transaction() as conn:
        for uid in ("u", "other"):
            conn.execute(
                "INSERT INTO users(id,username,password_hash,created_at,updated_at) VALUES(?,?,'x','n','n')",
                (uid, uid),
            )
    repo = AgentRuntimeRepository(db)
    job = repo.create_job(user_id="u", domain="final_review", objective_summary="复习")
    run = repo.create_run(job_id=job.id, user_id="u", domain="final_review", total_steps=7)
    return repo, run


def test_step_sequence_is_unique_and_only_progresses_forward():
    repo, run = _runtime()
    first = repo.ensure_step(run_id=run.id, sequence=1, role="planner", safe_summary="验证归属")
    again = repo.ensure_step(run_id=run.id, sequence=1, role="planner", safe_summary="验证归属")
    assert again.id == first.id
    assert again.status == "PENDING"

    repo.start_step(run_id=run.id, sequence=1)
    done = repo.finish_step(run_id=run.id, sequence=1, status="DONE", safe_summary="归属已确认")
    assert (done.status, done.safe_summary) == ("DONE", "归属已确认")
    assert done.finished_at is not None

    repo.ensure_step(run_id=run.id, sequence=2, role="planner", safe_summary="生成版本")
    steps = repo.list_steps(run_id=run.id)
    assert [step.sequence for step in steps] == [1, 2]
    assert [step.status for step in steps] == ["DONE", "PENDING"]


def test_progress_is_monotonic_so_replays_never_move_it_backwards():
    repo, run = _runtime()
    repo.set_progress(run_id=run.id, current=5)
    repo.set_progress(run_id=run.id, current=2)
    assert repo.get_run(run_id=run.id).progress_current == 5


def test_tool_call_finish_records_terminal_status():
    repo, run = _runtime()
    call, reused = repo.begin_tool_call(
        run_id=run.id, tool_name="task.create", idempotency_key="k1", request_hash="h1"
    )
    assert reused is False
    finished = repo.finish_tool_call(call_id=call.id, status="SUCCEEDED", result_digest="d1")
    assert (finished.status, finished.result_digest) == ("SUCCEEDED", "d1")
    assert finished.finished_at is not None


def test_context_snapshot_binds_run_to_domain_object():
    repo, run = _runtime()
    valid_until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    snapshot_id = repo.create_context_snapshot(
        run_id=run.id, user_id="u",
        scope={"campaign_id": "campaign_1", "exam_id": "exam_1"},
        facts={"daily_capacity_minutes": 90},
        source_refs=["student_exams:exam_1"], source_digest="d", valid_until=valid_until,
    )
    assert repo.get_run(run_id=run.id).context_snapshot_id == snapshot_id
    snapshot = repo.get_context_snapshot(snapshot_id=snapshot_id, user_id="u")
    assert snapshot["scope"]["campaign_id"] == "campaign_1"
    assert snapshot["facts"]["daily_capacity_minutes"] == 90
    assert repo.get_context_snapshot(snapshot_id=snapshot_id, user_id="other") is None


def test_find_run_for_scope_is_exact_and_user_scoped():
    repo, run = _runtime()
    repo.create_context_snapshot(
        run_id=run.id, user_id="u", scope={"campaign_id": "campaign_1"}, facts={},
        source_refs=[], source_digest="d", valid_until="2999-01-01T00:00:00+00:00",
    )
    assert repo.find_run_for_scope(user_id="u", domain="final_review", key="campaign_id", value="campaign_1").id == run.id
    assert repo.find_run_for_scope(user_id="u", domain="final_review", key="campaign_id", value="campaign_2") is None
    assert repo.find_run_for_scope(user_id="other", domain="final_review", key="campaign_id", value="campaign_1") is None
    assert repo.find_run_for_scope(user_id="u", domain="course_research", key="campaign_id", value="campaign_1") is None


def test_pending_approval_lookup_ignores_decided_rows():
    repo, run = _runtime()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    approval = repo.create_approval(
        run_id=run.id, user_id="u", risk_level="CONFIRM_REQUIRED", action_digest="a" * 64,
        summary="确认激活", expires_at=(now + timedelta(minutes=10)).isoformat(), now=now.isoformat(),
    )
    assert repo.pending_approval_for_run(run_id=run.id).id == approval.id
    repo.decide_approval(approval_id=approval.id, user_id="u", status="APPROVED", decided_at=now.isoformat())
    assert repo.pending_approval_for_run(run_id=run.id) is None
    assert repo.latest_approval_for_run(run_id=run.id).status == "APPROVED"
