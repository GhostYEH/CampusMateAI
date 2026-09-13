import pytest

from app.core.exceptions import AppException
from app.database.sqlite_db import Database
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.repositories.agent_artifact_repository import AgentArtifactRepository
from app.services.agent_runtime.artifact_manager import ArtifactManager


def _repo():
    db = Database(None)
    with db.transaction() as conn:
        conn.execute("INSERT INTO users(id,username,password_hash,created_at,updated_at) VALUES('u','u','x','n','n')")
    return db, AgentRuntimeRepository(db)


def test_event_sequence_is_monotonic_and_resume_is_exclusive():
    _db, repo = _repo()
    job = repo.create_job(user_id="u", domain="test", objective_summary="safe")
    run = repo.create_run(job_id=job.id, user_id="u", domain="test", total_steps=2)
    first = repo.append_event(run_id=run.id, event_type="RUN_STARTED", summary="started")
    second = repo.append_event(run_id=run.id, event_type="CONTEXT_READY", summary="ready")
    assert (first.sequence, second.sequence) == (1, 2)
    assert [item.id for item in repo.list_events(run_id=run.id, after_event_id=first.id)] == [second.id]


def test_tool_call_idempotency_survives_repository_restart():
    db, repo = _repo()
    job = repo.create_job(user_id="u", domain="test", objective_summary="safe")
    run = repo.create_run(job_id=job.id, user_id="u", domain="test", total_steps=1)
    first, reused = repo.begin_tool_call(
        run_id=run.id, tool_name="task.create", idempotency_key="key", request_hash="abc"
    )
    rebuilt = AgentRuntimeRepository(db)
    second, reused = rebuilt.begin_tool_call(
        run_id=run.id, tool_name="task.create", idempotency_key="key", request_hash="abc"
    )
    assert reused is True and second.id == first.id
    with pytest.raises(AppException) as exc:
        rebuilt.begin_tool_call(
            run_id=run.id, tool_name="task.create", idempotency_key="key", request_hash="different"
        )
    assert exc.value.code == "AGENT_IDEMPOTENCY_CONFLICT"


def test_artifact_manager_writes_owned_content_and_rejects_traversal(tmp_path):
    db, runtime = _repo()
    job = runtime.create_job(user_id="u", domain="test", objective_summary="safe")
    run = runtime.create_run(job_id=job.id, user_id="u", domain="test", total_steps=1)
    manager = ArtifactManager(AgentArtifactRepository(db), tmp_path / "artifacts")

    artifact = manager.create(
        user_id="u", run_id=run.id, artifact_type="DAILY_AGENDA",
        version=1, mime_type="application/json", content=b'{"ok":true}',
    )

    assert manager.read(artifact_id=artifact.id, user_id="u") == b'{"ok":true}'
    with pytest.raises(AppException):
        manager._resolve("../escape.json")
    with pytest.raises(AppException):
        manager.read(artifact_id=artifact.id, user_id="other")
