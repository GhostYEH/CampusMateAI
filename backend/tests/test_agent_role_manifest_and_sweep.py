"""角色声明化与僵尸 run 兜底清理。"""
from __future__ import annotations

import json

import pytest

from app.database.sqlite_db import reset_db_for_tests
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.services.agent_runtime.agent_registry import AgentRegistry, load_roles_from_manifest
from app.services.agent_runtime.run_manager import RunManager

_DEFAULT_ROLES = (
    "planner",
    "analyzer",
    "notice_interpreter",
    "workflow_planner",
    "coordinator",
    "course_researcher",
    "web_researcher",
    "citation_verifier",
    "tutor",
    "critic",
    "synthesizer",
)


@pytest.fixture
def repo():
    db = reset_db_for_tests()
    conn = db._connect()
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u1', 'u1', 'x', 'student', 't', 't')"
        )
        conn.commit()
    finally:
        db._release(conn)
    return AgentRuntimeRepository(db)


# ===== 角色声明化 =====


def test_default_registry_loads_manifest_roles():
    registry = AgentRegistry()
    codes = {role.agent_code for role in registry.list_roles()}
    assert set(_DEFAULT_ROLES) <= codes
    assert registry.has_tool("planner", "plan.propose") is True
    assert registry.has_capability("citation_verifier", "citation.verify") is True


def test_new_role_can_be_added_by_data_only(tmp_path):
    """新增角色只改清单文件,不改运行时核心代码。"""
    manifest = tmp_path / "roles.json"
    manifest.write_text(
        json.dumps(
            {
                "roles": [
                    {
                        "agent_code": "exam_scheduler",
                        "version": "1.0",
                        "capabilities": ["exam.schedule"],
                        "tools": ["exam.read", "plan.propose"],
                        "model_policy": "fast_structured",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    registry = AgentRegistry(manifest_path=manifest)

    assert registry.get("exam_scheduler") is not None
    assert registry.has_tool("exam_scheduler", "exam.read") is True
    # 清单是唯一来源:未声明的默认角色不出现
    assert registry.get("planner") is None


def test_broken_manifest_falls_back_to_builtin_roles(tmp_path):
    manifest = tmp_path / "roles.json"
    manifest.write_text("{ this is not json", encoding="utf-8")

    registry = AgentRegistry(manifest_path=manifest)

    codes = {role.agent_code for role in registry.list_roles()}
    assert set(_DEFAULT_ROLES) <= codes


def test_manifest_rejects_entry_without_agent_code(tmp_path):
    manifest = tmp_path / "roles.json"
    manifest.write_text(json.dumps({"roles": [{"version": "1.0"}]}), encoding="utf-8")

    with pytest.raises(ValueError):
        load_roles_from_manifest(manifest)


# ===== 僵尸 run 兜底 =====


def _make_run(repo: AgentRuntimeRepository) -> str:
    job_id = repo.create_job(user_id="u1", job_kind="final_review", input_ref={})
    return repo.create_run(job_id=job_id, user_id="u1")


def _age_run(repo: AgentRuntimeRepository, run_id: str, *, minutes: int) -> None:
    from datetime import datetime, timedelta, timezone

    stale = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    conn = repo._conn()
    try:
        conn.execute(
            "UPDATE agent_runs SET updated_at = ? WHERE run_id = ?", (stale, run_id)
        )
        conn.commit()
    finally:
        repo._release(conn)


def test_stale_run_is_swept_to_failed(repo: AgentRuntimeRepository):
    run_id = _make_run(repo)
    manager = RunManager(repo)
    manager.transition(run_id, "RUNNING", phase="WAITING_FOR_MODEL")
    _age_run(repo, run_id, minutes=600)

    swept = manager.sweep_stale_runs(older_than_minutes=120)

    assert swept == 1
    run = repo.get_run(run_id)
    assert run["status"] == "FAILED"
    assert run["error_code"] == "AGENT_INVALID_STATE"


def test_fresh_run_is_not_swept(repo: AgentRuntimeRepository):
    run_id = _make_run(repo)
    manager = RunManager(repo)
    manager.transition(run_id, "RUNNING", phase="WAITING_FOR_MODEL")

    swept = manager.sweep_stale_runs(older_than_minutes=120)

    assert swept == 0
    assert repo.get_run(run_id)["status"] == "RUNNING"


def test_terminal_run_is_never_swept(repo: AgentRuntimeRepository):
    run_id = _make_run(repo)
    manager = RunManager(repo)
    manager.transition(run_id, "RUNNING", phase="WAITING_FOR_MODEL")
    manager.transition(run_id, "SUCCEEDED", phase="IDLE")
    _age_run(repo, run_id, minutes=600)

    assert manager.sweep_stale_runs(older_than_minutes=120) == 0
    assert repo.get_run(run_id)["status"] == "SUCCEEDED"
