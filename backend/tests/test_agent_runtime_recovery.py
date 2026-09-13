from app.database.sqlite_db import Database
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.services.agent_runtime.run_manager import RunManager


def test_incomplete_runs_enter_recovery_checking():
    db = Database(None)
    with db.transaction() as conn:
        conn.execute("INSERT INTO users(id,username,password_hash,created_at,updated_at) VALUES('u','u','x','n','n')")
    repo = AgentRuntimeRepository(db)
    job = repo.create_job(user_id="u", domain="test", objective_summary="safe")
    run = repo.create_run(job_id=job.id, user_id="u", domain="test", total_steps=2)
    repo.update_run(run_id=run.id, status="RUNNING", phase="WAITING_FOR_TOOL")

    recovered = RunManager(repo).mark_incomplete_runs_for_recovery()

    assert [item.id for item in recovered] == [run.id]
    assert recovered[0].phase == "RECOVERY_CHECKING"


def test_cancelled_and_finished_runs_are_not_recovered():
    db = Database(None)
    with db.transaction() as conn:
        conn.execute("INSERT INTO users(id,username,password_hash,created_at,updated_at) VALUES('u','u','x','n','n')")
    repo = AgentRuntimeRepository(db)
    for status in ("SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"):
        job = repo.create_job(user_id="u", domain=status, objective_summary="safe")
        run = repo.create_run(job_id=job.id, user_id="u", domain=status, total_steps=1)
        repo.update_run(run_id=run.id, status=status, phase="IDLE")
    assert RunManager(repo).mark_incomplete_runs_for_recovery() == []
