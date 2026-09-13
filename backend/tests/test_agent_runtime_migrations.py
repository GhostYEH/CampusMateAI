from app.database.sqlite_db import Database


EXPECTED_TABLES = {
    "agent_jobs", "agent_runs", "agent_run_steps", "agent_context_snapshots",
    "agent_tool_calls", "agent_model_calls", "agent_events", "agent_memories",
    "agent_approvals", "agent_citations", "agent_artifacts",
}


def test_agent_runtime_schema_is_idempotent_and_complete(tmp_path):
    path = tmp_path / "runtime.db"
    first = Database(path)
    first.dispose()
    second = Database(path)
    with second.query() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert EXPECTED_TABLES <= tables
    second.dispose()


def test_agent_runtime_rows_cascade_with_user(tmp_path):
    db = Database(tmp_path / "cascade.db")
    with db.transaction() as conn:
        conn.execute("INSERT INTO users(id,username,password_hash,created_at,updated_at) VALUES('u','u','x','n','n')")
        conn.execute("INSERT INTO agent_jobs(id,user_id,domain,objective_summary,status,created_at,updated_at) VALUES('j','u','test','safe','ACTIVE','n','n')")
        conn.execute("INSERT INTO agent_runs(id,job_id,user_id,domain,status,phase,progress_current,progress_total,created_at,updated_at) VALUES('r','j','u','test','RUNNING','IDLE',0,1,'n','n')")
        conn.execute("DELETE FROM users WHERE id='u'")
    with db.query() as conn:
        assert conn.execute("SELECT COUNT(*) FROM agent_runs").fetchone()[0] == 0
    db.dispose()
