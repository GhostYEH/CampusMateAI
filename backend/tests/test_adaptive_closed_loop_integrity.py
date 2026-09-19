"""自适应闭环的真实性、并发安全与集成不变量。

这批测试刻意**不使用** comparator monkeypatch、不伪造 `DECLINED`、不直接改状态列：
它们驱动真实容器、真实状态投影、真实 comparator 与真实 Worker，断言的是闭环本身
能不能在"没有页面访问、没有人工触发"的前提下自己走完并留下一致的血缘。
"""
from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.adaptive_agent.replan_policy import ReplanDecisionPolicy
from app.services.adaptive_agent.replanning_worker import AdaptiveReplanningWorker
from app.services.adaptive_agent.state_outcome_comparator import StateOutcomeComparator
from app.services.container import reset_container_for_tests

# ====================================================================== 时间语义

CAPTURE = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
EVALUATION = CAPTURE + timedelta(days=7)


def _provenance(**overrides):
    """一份完整、时间顺序合法的 before/after provenance。"""
    record = {
        "before_data_quality": "verified", "after_data_quality": "verified",
        "before_confidence": 1.0, "after_confidence": 1.0,
        "before_snapshot_id": "lsnap_before_0001", "after_snapshot_id": "lsnap_after_0001",
        "before_run_id": "lrun_before_0001", "after_run_id": "lrun_after_0001",
        "before_observed_at": CAPTURE.isoformat(),
        "after_observed_at": EVALUATION.isoformat(),
        # before 的 TTL 只有 1 小时；观察窗口是 7 天。
        "before_valid_until": (CAPTURE + timedelta(hours=1)).isoformat(),
        "after_valid_until": (EVALUATION + timedelta(days=1)).isoformat(),
        "evidence_refs": ["lsnap_before_0001", "lsnap_after_0001"],
    }
    record.update(overrides)
    return record


def _compare(record, *, before_value=0.4, after_value=0.6,
             baseline_capture_at=CAPTURE.isoformat()) -> dict:
    return StateOutcomeComparator().compare(
        before={"mastery": before_value, "_dimensions": {"mastery": record}},
        after={"mastery": after_value, "_dimensions": {"mastery": record}},
        strategy_code="FOUNDATION_REINFORCEMENT",
        comparison_as_of=EVALUATION.isoformat(),
        baseline_capture_at=baseline_capture_at,
    )


def test_historical_baseline_valid_at_capture_remains_comparable():
    """before 是历史事实：只要采集时刻在它的有效窗口内，就不该在评估时被判失效。"""
    result = _compare(_provenance())

    assert result["outcome"] != "INSUFFICIENT_EVIDENCE"
    assert result["outcome"] == "IMPROVED"
    assert result["confidence"] > 0.0
    assert result["warnings"] == []


def test_baseline_invalid_when_already_stale_at_capture():
    """before 在采集时刻就已经过期/质量不可用 → 保守判证据不足。"""
    expired = _compare(_provenance(before_valid_until=(CAPTURE - timedelta(hours=1)).isoformat()))
    assert expired["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert expired["confidence"] == 0.0

    stale = _compare(_provenance(before_data_quality="stale", before_confidence=0.25))
    assert stale["outcome"] == "INSUFFICIENT_EVIDENCE"

    unavailable = _compare(_provenance(before_data_quality="unavailable", before_confidence=0.0))
    assert unavailable["outcome"] == "INSUFFICIENT_EVIDENCE"


def test_after_snapshot_must_be_fresh_at_evaluation():
    """after 是当前观测：它在评估时刻过期就不可比较（不能靠延长 TTL 规避）。"""
    expired = _compare(_provenance(after_valid_until=(EVALUATION - timedelta(hours=1)).isoformat()))
    assert expired["outcome"] == "INSUFFICIENT_EVIDENCE"


def test_reversed_or_future_observation_order_is_degraded_conservatively():
    """before_observed_at < after_observed_at <= evaluation_as_of 必须成立。"""
    reversed_order = _compare(_provenance(
        before_observed_at=EVALUATION.isoformat(),
        after_observed_at=CAPTURE.isoformat(),
    ))
    assert reversed_order["outcome"] == "INSUFFICIENT_EVIDENCE"

    future_after = _compare(_provenance(
        after_observed_at=(EVALUATION + timedelta(days=1)).isoformat(),
        after_valid_until=(EVALUATION + timedelta(days=2)).isoformat(),
    ))
    assert future_after["outcome"] == "INSUFFICIENT_EVIDENCE"


def test_missing_provenance_degrades_confidence_without_inventing_evidence():
    """完全没有 provenance 时保持旧的保守行为：压低置信度，但不凭空断言改善。"""
    result = StateOutcomeComparator().compare(
        before={"mastery": 0.4}, after={"mastery": 0.9},
        strategy_code="FOUNDATION_REINFORCEMENT", comparison_as_of=EVALUATION.isoformat(),
    )
    assert result["outcome"] == "IMPROVED"
    assert result["confidence"] < 0.1
    assert result["warnings"] == ["incomplete_state_provenance"]


# ====================================================================== 真实容器

def _container(username: str):
    container = reset_container_for_tests(
        Settings(app_env="test", database_url="sqlite:///:memory:")
    )
    student = container.user_repository.create_user(
        username=username, password_hash=hash_password("Demo123456"), role="student"
    )
    return container, student


def _add_tasks(container, user_id: str, *, count: int, completed: bool = False, day_offset: int = 3):
    now = datetime.now(timezone.utc)
    rows = []
    for index in range(count):
        task = container.personal_task_repository.create_task(
            user_id=user_id,
            title=f"闭环任务{index}",
            deadline=(now + timedelta(days=day_offset, minutes=index)).isoformat(),
        )
        if completed:
            container.personal_task_repository.complete(task.id, user_id=user_id)
        rows.append(task)
    return rows


def _plan_intervention(container, student, *, key: str):
    goal = container.student_goal_repository.create_goal(
        user_id=student.id, name="闭环目标", category="ACADEMIC",
        target_date=(datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat(),
        idempotency_key=f"{key}-goal",
    )[0]
    planned = container.adaptive_intervention_service.plan_for_goal(
        user_id=student.id, goal_id=goal.goal_id, available_minutes=60,
        idempotency_key=f"{key}-intervention",
    )
    return goal, planned


def _due_after(planned, *, minutes: int = 1) -> datetime:
    due = datetime.fromisoformat(planned.intervention.observation_due_at.replace("Z", "+00:00"))
    return due + timedelta(minutes=minutes)


def _declining_scenario(username: str):
    """真实下降场景：基线一致性高，干预后积压激增使一致性真实下滑。"""
    container, student = _container(username)
    _add_tasks(container, student.id, count=1, day_offset=2)
    _add_tasks(container, student.id, count=6, completed=True, day_offset=-3)
    goal, planned = _plan_intervention(container, student, key=username)
    _add_tasks(container, student.id, count=25, day_offset=3)
    return container, student, goal, planned


def _rows(container, sql: str, params: tuple):
    with container.adaptive_intervention_repository._db.query() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _successors(container, user_id: str, old_intervention_id: str) -> list[dict]:
    """**已完成血缘绑定**的后继（旧干预的回指针指向它们）。"""
    return _rows(
        container,
        "SELECT * FROM adaptive_interventions WHERE user_id=? AND supersedes_intervention_id=? "
        "ORDER BY created_at, intervention_id",
        (user_id, old_intervention_id),
    )


def _staged_successors(container, user_id: str) -> list[dict]:
    """**暂存态**后继：已生成计划但还没完成血缘绑定（status=PROPOSED）。

    绑定失败时后继必须停在这个状态：它既不是正式版本，也没有任何血缘指针，
    因此不会被误认为"当前有效计划"，重试又能靠幂等键原样找回它。
    """
    return _rows(
        container,
        "SELECT * FROM adaptive_interventions WHERE user_id=? AND status='PROPOSED' "
        "ORDER BY created_at, intervention_id",
        (user_id,),
    )


def _evaluation_of(container, student, intervention_id: str):
    row = container.adaptive_intervention_repository.get_evaluation(
        user_id=student.id, intervention_id=intervention_id
    )
    assert row is not None
    return row, container.adaptive_intervention_service._restore_evaluation(row)


def _decision_of(container, student, evaluation_id: str):
    decision = container.adaptive_intervention_repository.get_decision(
        user_id=student.id, evaluation_id=evaluation_id
    )
    assert decision is not None
    return decision


def test_real_projection_decline_triggers_replan_without_comparator_mock():
    """真实投影 + 真实 comparator + 真实 Worker 必须自己走到 REPLAN 并生成后继。"""
    container, student, _goal, planned = _declining_scenario("integrity_decline_student")
    old = planned.intervention
    old_params = json.loads(old.strategy_json)["planning_parameters"]

    due = _due_after(planned)
    worker = container.adaptive_replanning_worker
    worker._clock = lambda: due
    report = worker.tick(batch_size=10)
    assert report.failed == 0

    evaluation_row, evaluation = _evaluation_of(container, student, old.intervention_id)
    comparison = evaluation.state_comparison
    assert evaluation.observed_outcome == "DECLINED", comparison
    assert comparison["before_values"]["consistency"] > comparison["after_values"]["consistency"]
    # 真实投影的 before/after 都带完整 provenance，缺一不可。
    assert comparison["before_run_ids"] and comparison["after_run_ids"]

    decision = _decision_of(container, student, evaluation_row.evaluation_id)
    assert decision.decision == "REPLAN"
    assert decision.status == "APPLIED"
    adjustments = json.loads(decision.suggested_adjustments_json)
    assert adjustments

    successors = _successors(container, student.id, old.intervention_id)
    assert len(successors) == 1
    assert successors[0]["status"] == "PLAN_GENERATED"
    new_params = json.loads(successors[0]["strategy_json"])["planning_parameters"]
    assert new_params != old_params


def test_real_projection_improvement_keeps_current_plan():
    """同一初始目标，仅改变干预后证据：真实改善必须 CONTINUE 且不生成后继。"""
    container, student = _container("integrity_improve_student")
    baseline_pending = _add_tasks(container, student.id, count=10, day_offset=5)
    _add_tasks(container, student.id, count=2, completed=True, day_offset=-3)
    goal, planned = _plan_intervention(container, student, key="integrity-improve")
    old = planned.intervention

    # 干预后：学生真的完成了大部分基线待办 → execution_consistency 上升。
    for task in baseline_pending[:-1]:
        container.personal_task_repository.complete(task.id, user_id=student.id)

    due = _due_after(planned)
    worker = container.adaptive_replanning_worker
    worker._clock = lambda: due
    report = worker.tick(batch_size=10)
    assert report.failed == 0

    evaluation_row, evaluation = _evaluation_of(container, student, old.intervention_id)
    assert evaluation.observed_outcome in {"IMPROVED", "STABLE"}
    assert evaluation.observed_outcome == "IMPROVED"

    decision = _decision_of(container, student, evaluation_row.evaluation_id)
    assert decision.decision == "CONTINUE"
    assert decision.status == "APPLIED"
    assert json.loads(decision.suggested_adjustments_json) == []
    assert _successors(container, student.id, old.intervention_id) == []


def test_concurrent_workers_create_exactly_one_successor():
    """两个 Worker 同时处理同一个 PENDING 决策：只能有一个拿到处理权。"""
    container, student, _goal, planned = _declining_scenario("integrity_concurrent_student")
    old = planned.intervention
    old_plan_id = planned.plan.plan_id
    due = _due_after(planned)

    repository = container.adaptive_intervention_repository
    service = container.adaptive_intervention_service

    # 只同步"读到的快照"，不改变任何判定：两个 Worker 都会拿到同一个 PENDING 决策。
    barrier = threading.Barrier(2, timeout=60)
    original_list = repository.list_pending_decisions

    def synced_list(**kwargs):
        rows = original_list(**kwargs)
        barrier.wait()
        return rows

    repository.list_pending_decisions = synced_list

    reports: list = []
    errors: list = []

    def run_tick():
        worker = AdaptiveReplanningWorker(
            repository=repository, intervention_service=service, clock=lambda: due,
        )
        try:
            reports.append(worker.tick(batch_size=10))
        except BaseException as exc:  # noqa: BLE001 - 记录后由断言暴露
            errors.append(exc)

    threads = [threading.Thread(target=run_tick, daemon=True) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)

    assert not errors, errors
    assert len(reports) == 2

    successors = _successors(container, student.id, old.intervention_id)
    assert len(successors) == 1, successors
    assert successors[0]["status"] == "PLAN_GENERATED"

    successor_plans = _rows(
        container,
        "SELECT * FROM learning_plans WHERE user_id=? AND supersedes_plan_id=?",
        (student.id, old_plan_id),
    )
    assert len(successor_plans) == 1, successor_plans

    evaluation_row, _evaluation = _evaluation_of(container, student, old.intervention_id)
    decision = _decision_of(container, student, evaluation_row.evaluation_id)
    assert decision.status == "APPLIED"
    assert decision.decision == "REPLAN"


def test_replan_updates_both_intervention_and_learning_plan_lineage():
    """干预血缘与计划血缘必须同时成立，且当前计划只剩新计划。"""
    container, student, _goal, planned = _declining_scenario("integrity_lineage_student")
    old = planned.intervention
    old_plan_id = planned.plan.plan_id

    due = _due_after(planned)
    worker = container.adaptive_replanning_worker
    worker._clock = lambda: due
    assert worker.tick(batch_size=10).applied == 1

    old_row = container.adaptive_intervention_repository.get(
        user_id=student.id, intervention_id=old.intervention_id
    )
    successors = _successors(container, student.id, old.intervention_id)
    assert len(successors) == 1
    new_intervention_id = successors[0]["intervention_id"]
    new_plan_id = successors[0]["plan_id"]

    assert old_row.status == "SUPERSEDED"
    assert old_row.superseded_by_intervention_id == new_intervention_id
    assert successors[0]["supersedes_intervention_id"] == old.intervention_id

    plan_rows = _rows(
        container,
        "SELECT plan_id, supersedes_plan_id, superseded_by_plan_id FROM learning_plans "
        "WHERE user_id=? ORDER BY created_at",
        (student.id,),
    )
    by_id = {row["plan_id"]: row for row in plan_rows}
    assert by_id[old_plan_id]["superseded_by_plan_id"] == new_plan_id
    assert by_id[new_plan_id]["supersedes_plan_id"] == old_plan_id

    current = [row for row in plan_rows if row["superseded_by_plan_id"] is None]
    assert [row["plan_id"] for row in current] == [new_plan_id]


def test_link_failure_keeps_old_plan_official_and_retry_recovers():
    """后继已生成但最终绑定失败：旧版本保持正式，重试复用同一个幂等后继。"""
    container, student, _goal, planned = _declining_scenario("integrity_link_failure_student")
    old = planned.intervention
    old_plan_id = planned.plan.plan_id
    due = _due_after(planned)

    repository = container.adaptive_intervention_repository
    original_link = repository.link_replanned
    attempts = {"count": 0}

    def flaky_link(**kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("lineage store unavailable")
        return original_link(**kwargs)

    repository.link_replanned = flaky_link

    worker = container.adaptive_replanning_worker
    worker._clock = lambda: due
    first = worker.tick(batch_size=10)
    assert first.failed == 1
    assert attempts["count"] == 1

    old_row = repository.get(user_id=student.id, intervention_id=old.intervention_id)
    assert old_row.status == "EVALUATED"
    assert old_row.superseded_by_intervention_id is None

    staged = _staged_successors(container, student.id)
    assert len(staged) == 1
    assert staged[0]["status"] == "PROPOSED"

    plan_rows = _rows(
        container,
        "SELECT plan_id, supersedes_plan_id, superseded_by_plan_id FROM learning_plans WHERE user_id=?",
        (student.id,),
    )
    by_id = {row["plan_id"]: row for row in plan_rows}
    assert by_id[old_plan_id]["superseded_by_plan_id"] is None
    new_plan_id = staged[0]["plan_id"]
    assert by_id[new_plan_id]["supersedes_plan_id"] is None
    assert by_id[new_plan_id]["superseded_by_plan_id"] is None

    evaluation_row, _evaluation = _evaluation_of(container, student, old.intervention_id)
    decision = _decision_of(container, student, evaluation_row.evaluation_id)
    assert decision.status == "FAILED"
    assert decision.failure_class == "RETRYABLE"

    # 重试：同一个幂等后继被复用，血缘在同一个事务里补上。
    retry_at = due + timedelta(minutes=5)
    worker._clock = lambda: retry_at
    second = worker.tick(batch_size=10)
    assert second.failed == 0
    assert second.applied == 1
    assert attempts["count"] == 2

    after_retry = _successors(container, student.id, old.intervention_id)
    assert len(after_retry) == 1
    assert after_retry[0]["intervention_id"] == staged[0]["intervention_id"]
    assert after_retry[0]["status"] == "PLAN_GENERATED"

    old_after = repository.get(user_id=student.id, intervention_id=old.intervention_id)
    assert old_after.status == "SUPERSEDED"
    assert old_after.superseded_by_intervention_id == staged[0]["intervention_id"]

    plan_rows = _rows(
        container,
        "SELECT plan_id, supersedes_plan_id, superseded_by_plan_id FROM learning_plans WHERE user_id=?",
        (student.id,),
    )
    by_id = {row["plan_id"]: row for row in plan_rows}
    assert len(plan_rows) == 2
    assert by_id[old_plan_id]["superseded_by_plan_id"] == new_plan_id
    assert by_id[new_plan_id]["supersedes_plan_id"] == old_plan_id
    assert [row["plan_id"] for row in plan_rows if row["superseded_by_plan_id"] is None] == [new_plan_id]

    final_decision = _decision_of(container, student, evaluation_row.evaluation_id)
    assert final_decision.status == "APPLIED"


# ====================================================================== 防抖边界

def _seed_recent_replan(container, student, planned, *, created_at: datetime, count: int = 1):
    """插入"最近已经重规划过"的历史后继行（夹具，不代表本次决策结果）。

    这些行代表**同一目标下更早的**几次重规划：它们靠 `supersedes_intervention_id
    IS NOT NULL` + `created_at` 触发防抖守卫，但刻意指向一个独立的"先前干预"，
    因此不会被 `_successors(旧干预)` 误认成本次决策产生的后继。
    """
    with container.adaptive_intervention_repository._db.transaction() as conn:
        for index in range(count):
            conn.execute(
                "INSERT INTO adaptive_interventions "
                "(intervention_id,user_id,goal_id,status,strategy_code,strategy_version,assessment_id,"
                "assessment_json,strategy_json,rationale_codes_json,expected_outcomes_json,"
                "baseline_state_digest,confidence,warning_codes_json,idempotency_key,"
                "supersedes_intervention_id,chain_depth,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    f"intv_seed_{index}", student.id, planned.intervention.goal_id, "SUPERSEDED",
                    planned.intervention.strategy_code, planned.intervention.strategy_version,
                    planned.intervention.assessment_id, planned.intervention.assessment_json,
                    planned.intervention.strategy_json, planned.intervention.rationale_codes_json,
                    planned.intervention.expected_outcomes_json, planned.intervention.baseline_state_digest,
                    planned.intervention.confidence, "[]", f"seed-replan-{index}",
                    f"intv_prior_{index}", 1,
                    created_at.isoformat(), created_at.isoformat(),
                ),
            )


def _assert_conservative_suspend(container, student, planned, due, expected_code: str):
    worker = container.adaptive_replanning_worker
    worker._clock = lambda: due
    report = worker.tick(batch_size=10)
    assert report.failed == 0, "防抖是安全策略，不是基础设施失败"

    evaluation_row, _evaluation = _evaluation_of(container, student, planned.intervention.intervention_id)
    decision = _decision_of(container, student, evaluation_row.evaluation_id)
    assert decision.decision == "SUSPEND"
    assert decision.status == "APPLIED"
    assert expected_code in json.loads(decision.reason_codes_json)
    assert json.loads(decision.suggested_adjustments_json) == []
    # 保守等待**不得**产生任何后继：既没有已绑定的，也没有暂存态的。
    assert _successors(container, student.id, planned.intervention.intervention_id) == []
    assert _staged_successors(container, student.id) == []


def test_replan_guard_cooldown_downgrades_to_suspend():
    container, student, _goal, planned = _declining_scenario("integrity_cooldown_student")
    due = _due_after(planned)
    _seed_recent_replan(container, student, planned, created_at=due - timedelta(hours=1))
    _assert_conservative_suspend(container, student, planned, due, "replan_cooldown_active")


def test_replan_guard_daily_limit_downgrades_to_suspend():
    container, student, _goal, planned = _declining_scenario("integrity_daily_limit_student")
    due = _due_after(planned)
    day_start = due.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    _seed_recent_replan(
        container, student, planned, created_at=day_start + timedelta(minutes=1), count=2,
    )
    _assert_conservative_suspend(container, student, planned, due, "replan_daily_limit_reached")


def test_replan_guard_chain_depth_downgrades_to_suspend():
    container, student, _goal, planned = _declining_scenario("integrity_chain_depth_student")
    due = _due_after(planned)
    with container.adaptive_intervention_repository._db.transaction() as conn:
        conn.execute(
            "UPDATE adaptive_interventions SET chain_depth=3 WHERE intervention_id=?",
            (planned.intervention.intervention_id,),
        )
    _assert_conservative_suspend(container, student, planned, due, "replan_chain_depth_exceeded")


def test_policy_downgrades_replan_when_guard_blocks():
    """策略层：被防抖拦住的 REPLAN 必须变成带稳定 reason code 的 SUSPEND。"""
    policy = ReplanDecisionPolicy()
    decision = policy.decide(
        evaluation={"observed_outcome": "DECLINED", "adoption": "COMPLETED"},
        state={}, goal={}, now=EVALUATION.isoformat(),
        evidence_refs=["inteval_x"], replan_guard_code="replan_cooldown_active",
    )
    assert decision.decision == "SUSPEND"
    assert decision.reason_codes == ["replan_cooldown_active"]


# ====================================================================== 调度健壮性

class _FlakyScanRepository:
    def __init__(self, failures: int = 1):
        self.scan_calls = 0
        self.pending_calls = 0
        self.failures = failures

    def list_due_for_evaluation(self, **_kwargs):
        self.scan_calls += 1
        if self.scan_calls <= self.failures:
            raise RuntimeError("scan exploded")
        return []

    def list_pending_decisions(self, **_kwargs):
        self.pending_calls += 1
        if self.pending_calls <= self.failures:
            raise RuntimeError("pending scan exploded")
        return []


async def test_scheduler_survives_scan_exception(monkeypatch):
    logged: list[tuple] = []

    class _Recorder:
        def warning(self, message, *args, **_kwargs):
            logged.append((message, args))

        def __getattr__(self, _name):
            return lambda *args, **kwargs: None

    import app.core.logging as logging_module

    monkeypatch.setattr(logging_module, "logger", _Recorder())

    repository = _FlakyScanRepository(failures=1)
    worker = AdaptiveReplanningWorker(
        repository=repository, intervention_service=object(), interval_seconds=0.01,
    )
    rounds = {"count": 0}

    async def sleeper(_seconds):
        rounds["count"] += 1
        if rounds["count"] >= 3:
            raise asyncio.CancelledError

    worker._sleeper = sleeper
    with pytest.raises(asyncio.CancelledError):
        await worker._run_loop()

    # 第一轮扫描抛异常后调度必须继续，而不是永久结束。
    assert repository.scan_calls >= 3
    assert repository.pending_calls >= 2
    # 结构化错误日志必须带上阶段与错误码（不含隐私内容）。
    assert any("error_code" in message for message, _args in logged), "必须留下结构化错误日志"
    assert any("RuntimeError" in args for _message, args in logged), "必须记录真实错误码"


def test_lifespan_first_tick_failure_does_not_block_startup(monkeypatch):
    from app.services.adaptive_agent import replanning_worker as worker_module

    def exploding_tick(self, **_kwargs):
        raise RuntimeError("first tick exploded")

    monkeypatch.setattr(worker_module.AdaptiveReplanningWorker, "tick", exploding_tick)

    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    assert container is not None

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200


# ====================================================================== 公开响应脱敏

def test_public_outcome_omits_internal_provenance_ids():
    container, student, _goal, planned = _declining_scenario("integrity_privacy_student")
    due = _due_after(planned)
    worker = container.adaptive_replanning_worker
    worker._clock = lambda: due
    assert worker.tick(batch_size=10).applied == 1

    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "integrity_privacy_student", "password": "Demo123456"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get(
        f"/api/v1/adaptive-interventions/{planned.intervention.intervention_id}/outcome",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    dumped = json.dumps(payload)

    for forbidden in ("before_run_id", "after_run_id", "snapshot_id", "evidence_refs",
                      "before_run_ids", "after_run_ids", "lsnap_", "lrun_"):
        assert forbidden not in dumped, forbidden

    assert payload["decision"] == "REPLAN"
    comparison = payload["state_comparison"]
    assert set(comparison) <= {
        "relevant_dimensions", "before_values", "after_values", "delta", "outcome",
        "confidence", "warnings", "comparison_as_of", "dimensions",
    }
    for record in (comparison.get("dimensions") or {}).values():
        assert set(record) <= {
            "before", "after", "before_data_quality", "after_data_quality",
            "before_confidence", "after_confidence", "before_observed_at", "after_observed_at",
        }


# ============================================================== Worker 生命周期

def test_replanning_interval_must_be_finite_positive_and_sane():
    """调度周期必须是有限正数且落在合理区间：NaN/0/负值/过大都必须在启动前拦下。"""
    for value in (0.0, -1.0, float("nan"), float("inf"), float("-inf"), 0.1, 86_401.0):
        with pytest.raises(ValidationError):
            Settings(
                app_env="test", database_url="sqlite:///:memory:",
                adaptive_replanning_interval_seconds=value,
            )
    for value in (0.5, 60.0, 86_400.0):
        settings = Settings(
            app_env="test", database_url="sqlite:///:memory:",
            adaptive_replanning_interval_seconds=value,
        )
        assert settings.adaptive_replanning_interval_seconds == value


async def test_worker_start_stop_restart_leaves_no_background_task():
    """start / stop / restart 之后不得遗留后台调度任务。"""
    repository = _FlakyScanRepository(failures=0)
    worker = AdaptiveReplanningWorker(
        repository=repository, intervention_service=object(), interval_seconds=0.01,
    )

    await worker.start()
    first = worker._task
    assert first is not None and not first.done()

    await worker.stop()
    assert worker._task is None
    assert first.done(), "关闭后旧调度任务必须真正结束"

    # 重启必须新建调度任务，而不是复用已结束的那个。
    await worker.start()
    second = worker._task
    assert second is not None and second is not first and not second.done()
    await worker.stop()
    assert worker._task is None
    assert second.done()

    leftover = [task for task in asyncio.all_tasks() if task.get_name() == "adaptive-replanning-worker"]
    assert leftover == [], "关闭后不允许遗留后台调度任务"


# ============================================================== 反馈与自证据隔离

def test_current_evaluation_events_do_not_feed_back_into_after_projection():
    """本次评估写出的 learner event 不得反向进入本次 after 投影（否则自证循环）。"""
    container, student = _container("integrity_self_evidence_student")
    evaluation_id = "inteval_self_evidence_0001"
    container.learner_event_service.record_intervention_event(
        user_id=student.id, event_type="intervention_observed",
        intervention_id="intv_self_evidence", goal_id="goal_self_evidence",
        evaluation_id=evaluation_id, occurred_at=datetime.now(timezone.utc),
        outcome="observed_completed", evidence_refs=[evaluation_id],
    )

    as_of = datetime.now(timezone.utc)
    projected = container.learner_state_service._collect_world_inputs(
        user_id=student.id, as_of=as_of,
    )
    excluded = container.learner_state_service._collect_world_inputs(
        user_id=student.id, as_of=as_of, exclude_evaluation_id=evaluation_id,
    )
    assert projected["events"], "事件必须真的落库，否则这条测试没有意义"
    assert excluded["events"] == [], "本次评估自己的事件不能进入本次 after 投影"


def test_plan_feedback_is_auxiliary_evidence_and_cannot_override_behavior():
    """反馈只是辅助证据：不能进维度/差值，也不能把真实下滑翻转成改善。"""
    container, student, _goal, planned = _declining_scenario("integrity_feedback_student")
    old = planned.intervention
    normalizer = container.adaptive_intervention_service._state_normalizer
    as_of = _due_after(planned)

    before = normalizer.compare(
        intervention=old, as_of=as_of, evaluation_id=None, strategy_code=old.strategy_code,
    )
    assert before["outcome"] == "DECLINED", before
    assert before["learning_plan_feedback"] == []

    # 反馈词表是固定枚举（见 learning_plan_feedback 的 CHECK 约束），
    # 这里用最"正面"的一项：它仍然不能把真实下滑翻转成改善。
    container.learning_plan_repository.add_feedback(
        plan_id=planned.plan.plan_id, user_id=student.id, feedback="HELPFUL",
    )
    after = normalizer.compare(
        intervention=old, as_of=as_of, evaluation_id=None, strategy_code=old.strategy_code,
    )

    assert after["learning_plan_feedback"], "反馈必须被读到"
    assert after["learning_plan_feedback"][0]["role"] == "AUXILIARY_EVIDENCE"
    assert "learning_plan_feedback" not in after["dimensions"]
    # 正面反馈不能改变真实行为证据：结论、置信度与差值必须逐项一致。
    assert after["outcome"] == "DECLINED", after
    for key in ("confidence", "delta", "before_values", "after_values", "relevant_dimensions"):
        assert after[key] == before[key], key
