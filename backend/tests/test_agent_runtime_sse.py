from app.database.sqlite_db import Database
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.services.agent_runtime.event_store import AgentEventStore


def test_sse_resume_cursor_replays_only_later_ordered_events():
    db = Database(None)
    with db.transaction() as conn:
        conn.execute("INSERT INTO users(id,username,password_hash,created_at,updated_at) VALUES('u','u','x','n','n')")
    repo = AgentRuntimeRepository(db)
    job = repo.create_job(user_id="u", domain="test", objective_summary="safe")
    run = repo.create_run(job_id=job.id, user_id="u", domain="test", total_steps=3)
    store = AgentEventStore(repo)
    first = store.append(run_id=run.id, event_type="RUN_STARTED", summary="开始")
    second = store.append(run_id=run.id, event_type="CONTEXT_READY", summary="上下文就绪")
    third = store.append(run_id=run.id, event_type="MODEL_STARTED", summary="模型开始")

    resumed = store.replay(run_id=run.id, last_event_id=first.id)

    assert [item.id for item in resumed] == [second.id, third.id]
    assert [item.sequence for item in resumed] == [2, 3]
    assert all(not hasattr(item, "prompt") for item in resumed)
