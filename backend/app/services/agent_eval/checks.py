"""评测检查实现:每个函数对应 cases.py 里的一个 check 名称。

检查在隔离数据库上运行,不访问网络、不写真实用户数据。
失败时抛异常;runner 负责收集结果,不吞掉失败。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from ...database.sqlite_db import reset_db_for_tests
from ...repositories.agent_runtime_repository import AgentRuntimeRepository
from ..agent_runtime.agent_registry import AgentRegistry
from ..agent_runtime.cancellation import ensure_run_active
from ..agent_runtime.context_budget import compact_facts
from ..agent_runtime.hard_deny import hard_deny_reason
from ..agent_runtime.risk_engine import RiskEngine
from ..agent_runtime.run_manager import RunManager
from ..llm.base import LLMError, LLMResponse
from ..llm.model_router import ModelRouter, extract_token_usage
from ..llm.openai_compatible import StubLLMClient
from ..llm.provider_registry import ProviderRegistry
from ..llm.provider_errors import classify_provider_error
from ...core.config import Settings


def _isolated_repo() -> AgentRuntimeRepository:
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


# ===== L0 =====


def check_context_budget_keeps_scalars() -> None:
    facts = {"daily_capacity_minutes": 120, "materials": "课程资料正文" * 800}
    compacted, report = compact_facts(facts, budget_tokens=300)
    assert report["truncated"] is True, "超预算上下文应被标记截断"
    assert compacted["daily_capacity_minutes"] == 120, "标量事实不得被裁剪"
    assert report["estimated_tokens"] <= 300, "裁剪后必须落回预算内"


def check_hard_deny_payment() -> None:
    assert hard_deny_reason("payment.pay") is not None
    assert hard_deny_reason("task.create", {"title": "把验证码 1234 填进去"}) is not None
    assert hard_deny_reason("task.create", {"title": "复习数据库"}) is None


def check_risk_grading() -> None:
    engine = RiskEngine()
    assert engine.assess("payment.pay", user_enabled_auto=True).risk_level.value == "MANUAL_ONLY"
    assert engine.assess("plan.activate").risk_level.value == "CONFIRM_REQUIRED"
    assert engine.assess("task.create", user_enabled_auto=True).risk_level.value == "AUTO_SAFE"


def check_usage_extraction() -> None:
    response = LLMResponse(
        "ok",
        raw={"usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}},
    )
    usage = extract_token_usage(response)
    assert usage["total_tokens"] == 10
    assert extract_token_usage(None) == {}


# ===== L1 =====


def check_role_manifest() -> None:
    registry = AgentRegistry()
    planner = registry.get("planner")
    assert planner is not None, "默认角色清单必须可用"
    assert "plan.propose" in planner.tools
    assert registry.has_capability("critic", "critic.review") is True


def check_primary_provider_fallback() -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        llm_provider="openai_compatible",
        llm_base_url="https://api.example.invalid/v1",
        llm_api_key="placeholder-not-a-real-key",
        llm_model="demo-model",
        zhipu_llm_base_url="",
        zhipu_llm_api_key="",
        zhipu_llm_model="",
        xunfei_llm_base_url="",
        xunfei_llm_api_key="",
        xunfei_llm_model="",
    )
    registry = ProviderRegistry(settings)
    assert registry.get("primary") is not None, "未配智谱/讯飞时应注册 primary"
    for status in registry.status():
        assert "api_key" not in status and "base_url" not in status


def check_dual_review_degrades() -> None:
    import asyncio

    settings = Settings(
        _env_file=None,
        app_env="test",
        llm_provider="openai_compatible",
        llm_base_url="https://api.example.invalid/v1",
        llm_api_key="placeholder-not-a-real-key",
        llm_model="demo-model",
        zhipu_llm_base_url="",
        zhipu_llm_api_key="",
        zhipu_llm_model="",
        xunfei_llm_base_url="",
        xunfei_llm_api_key="",
        xunfei_llm_model="",
    )
    registry = ProviderRegistry(settings)
    registry.get("primary").client = StubLLMClient(response_text="ok")
    router = ModelRouter(registry)
    result = asyncio.run(
        router.route([{"role": "user", "content": "ping"}], route_policy="dual_review")
    )
    assert result.status == "fallback", "单 provider 时 dual_review 必须标记降级"
    assert result.fallback_reason == "dual_review_degraded_single_provider"


def check_cancel_terminal_guard() -> None:
    repo = _isolated_repo()
    job_id = repo.create_job(user_id="u1", job_kind="final_review", input_ref={})
    run_id = repo.create_run(job_id=job_id, user_id="u1")
    manager = RunManager(repo)
    manager.transition(run_id, "RUNNING", phase="WAITING_FOR_MODEL")
    manager.transition(run_id, "CANCELLED", phase="IDLE")

    try:
        ensure_run_active(repo, run_id)
    except Exception as exc:  # noqa: BLE001 - 只关心"被拒绝"
        assert getattr(exc, "code", "") == "AGENT_RUN_CANCELLED"
    else:
        raise AssertionError("取消后的 run 不应继续推进")


def check_stale_run_sweep() -> None:
    repo = _isolated_repo()
    job_id = repo.create_job(user_id="u1", job_kind="final_review", input_ref={})
    run_id = repo.create_run(job_id=job_id, user_id="u1")
    manager = RunManager(repo)
    manager.transition(run_id, "RUNNING", phase="WAITING_FOR_MODEL")
    stale = (datetime.now(timezone.utc) - timedelta(minutes=600)).isoformat()
    conn = repo._conn()
    try:
        conn.execute("UPDATE agent_runs SET updated_at = ? WHERE run_id = ?", (stale, run_id))
        conn.commit()
    finally:
        repo._release(conn)

    assert manager.sweep_stale_runs(older_than_minutes=120) == 1
    assert repo.get_run(run_id)["status"] == "FAILED"


# ===== L2 业务流程不变量 =====


def check_notice_action_not_auto_executed() -> None:
    """通知事务:外部提交类动作必须落在 MANUAL_ONLY,且被硬拒绝层拦住。"""
    engine = RiskEngine()
    assessment = engine.assess("external_submission.execute", user_enabled_auto=True)
    assert assessment.risk_level.value == "MANUAL_ONLY"
    assert engine.can_auto_execute(assessment) is False
    assert hard_deny_reason("external_submission.execute") is not None


def check_research_policy_restriction() -> None:
    """课程研究:考试限制下不返回完整代答(客户端不能自证 ALLOWED)。"""
    from ...schemas.agent_contract_enums import AcademicPolicy as AcademicPolicyEnum
    from ...schemas.agent_contract_enums import AssistanceMode
    from ..course_research.policy import SourcePolicy, build_effective_policy

    effective = build_effective_policy(
        requested_mode=AssistanceMode.FULL_SOLUTION,
        academic_candidates=[AcademicPolicyEnum.ALLOWED, AcademicPolicyEnum.EXAM_RESTRICTED],
        source_policy=SourcePolicy(),
    )
    assert effective.academic_policy == AcademicPolicyEnum.EXAM_RESTRICTED, "必须取最严格策略"
    assert effective.effective_mode != AssistanceMode.FULL_SOLUTION, "考试限制下不得完整代答"
    assert effective.degraded is True


def _field(row: object, name: str):
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def check_final_review_version_immutable() -> None:
    """期末复习:计划版本只能追加,旧版本内容不被覆盖。"""
    from ...database.sqlite_db import Database
    from ...repositories.final_review_repository import FinalReviewRepository

    db: Database = reset_db_for_tests()
    conn = db._connect()
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u1', 'u1', 'x', 'student', 't', 't')"
        )
        conn.commit()
    finally:
        db._release(conn)

    repo = FinalReviewRepository(db)
    campaign = repo.create_campaign(
        user_id="u1", exam_ids=["exam_1"], daily_capacity_minutes=120
    )
    campaign_id = _field(campaign, "campaign_id")
    assert campaign_id, "应创建复习活动"

    repo.create_plan_version(
        campaign_id=campaign_id, version=1, user_id="u1", plan={"days": []}
    )
    repo.create_plan_version(
        campaign_id=campaign_id,
        version=2,
        user_id="u1",
        plan={"days": [{"day_offset": 0}]},
        supersedes_version=1,
    )

    versions = repo.list_plan_versions(campaign_id, user_id="u1")
    assert [_field(item, "version") for item in versions] == [1, 2], "版本必须按序追加"
    stored_first = next(item for item in versions if _field(item, "version") == 1)
    raw_plan = _field(stored_first, "plan_json") or _field(stored_first, "plan")
    assert "day_offset" not in str(raw_plan), "新版本不得覆盖旧版本内容"


_CHECKS: dict[str, Callable[[], None]] = {
    "check_context_budget_keeps_scalars": check_context_budget_keeps_scalars,
    "check_hard_deny_payment": check_hard_deny_payment,
    "check_risk_grading": check_risk_grading,
    "check_usage_extraction": check_usage_extraction,
    "check_role_manifest": check_role_manifest,
    "check_primary_provider_fallback": check_primary_provider_fallback,
    "check_dual_review_degrades": check_dual_review_degrades,
    "check_cancel_terminal_guard": check_cancel_terminal_guard,
    "check_stale_run_sweep": check_stale_run_sweep,
    "check_notice_action_not_auto_executed": check_notice_action_not_auto_executed,
    "check_research_policy_restriction": check_research_policy_restriction,
    "check_final_review_version_immutable": check_final_review_version_immutable,
}


def resolve_check(name: str) -> Callable[[], None]:
    try:
        return _CHECKS[name]
    except KeyError as exc:  # pragma: no cover - 规格与实现不一致时明确报错
        raise KeyError(f"评测用例声明的 check 未实现: {name}") from exc


__all__ = ["resolve_check"]
