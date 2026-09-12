"""Phase 6C: 演示场景测试。"""
from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.exceptions import DemoSeedRefused
from app.demo import learner_model as demo
from app.services.container import reset_container_for_tests


def _settings():
    return Settings(app_env="test", database_url="sqlite:///:memory:")


def test_seed_all_scenarios():
    for scenario in demo.SCENARIOS:
        s = _settings()
        reset_container_for_tests(s)
        result = demo.seed(scenario, settings=s)
        assert result["scenario"] == scenario
        assert "demo_user_id" in result


def test_seed_idempotent():
    s = _settings()
    reset_container_for_tests(s)
    r1 = demo.seed("deadline-pressure", settings=s)
    r2 = demo.seed("deadline-pressure", settings=s)
    assert r1["demo_user_id"] == r2["demo_user_id"]


def test_clear_removes_demo_data():
    s = _settings()
    reset_container_for_tests(s)
    demo.seed("pointer-recovery", settings=s)
    result = demo.clear("pointer-recovery", settings=s)
    assert result["removed_users"] == 1


def test_clear_idempotent():
    s = _settings()
    reset_container_for_tests(s)
    demo.seed("stale-source-replan", settings=s)
    demo.clear("stale-source-replan", settings=s)
    result = demo.clear("stale-source-replan", settings=s)
    assert result["removed_users"] == 0


def test_clear_does_not_affect_other_scenarios():
    s = _settings()
    reset_container_for_tests(s)
    demo.seed("deadline-pressure", settings=s)
    demo.seed("pointer-recovery", settings=s)
    demo.clear("deadline-pressure", settings=s)
    r2 = demo.clear("pointer-recovery", settings=s)
    assert r2["removed_users"] == 1


def test_production_env_refused():
    s = Settings(
        app_env="production",
        database_url="sqlite:///prod.db",
        jwt_secret="a" * 32,
        edu_session_store="encrypted_sqlite",
        edu_session_encryption_key="Gf0VL5Rs4+Dc1IpcPpTajuoZAxe3rtdlWzTWnRAT7CU=",
        edu_session_encryption_key_id="prod-key-1",
        auto_seed_demo_users=False,
        auto_import_demo=False,
    )
    with pytest.raises(DemoSeedRefused):
        demo.seed("deadline-pressure", settings=s)


def test_unknown_scenario_rejected():
    s = _settings()
    reset_container_for_tests(s)
    with pytest.raises(ValueError):
        demo.seed("unknown", settings=s)


def test_demo_users_are_synthetic():
    """演示用户使用合成 ID，不含真实个人数据。"""
    s = _settings()
    reset_container_for_tests(s)
    result = demo.seed("shadow-model-blocked", settings=s)
    assert result["demo_user_id"].startswith("demo_user_")