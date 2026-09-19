"""决策应用的崩溃恢复与租约所有权。

`adaptive_replan_decisions` 进入 `APPLYING` 之后，进程可能在任意一点被杀：

1. 刚拿到处理权就崩（还没生成任何后继）；
2. 后继计划已暂存、血缘还没绑定；
3. 计划与干预血缘都已绑定、只差最后把决策写成 `APPLIED`。

这三种残留都必须能被**重启后的 Worker 幂等完成**：不重复生成后继、不产生第二条
正式计划、不留下悬空血缘。同时"重启可恢复"绝不能退化成"任何人都能随时抢占
`APPLYING`" —— 抢占的唯一依据是**租约过期**，租约未过期时其他 Worker 必须原样退出。

这些测试用 `_WorkerCrash`（`BaseException` 子类）模拟进程被杀：它绕过 Worker 里
所有 `except Exception` 处理路径，因此数据库会停在崩溃瞬间的真实状态，
而不是被错误处理顺手推进成 `FAILED`。
"""
from __future__ import annotations

import threading
from datetime import timedelta

import pytest

from app.services.adaptive_agent.replanning_worker import AdaptiveReplanningWorker

from test_adaptive_closed_loop_integrity import (  # noqa: F401 - 复用真实场景夹具
    _decision_of,
    _declining_scenario,
    _due_after,
    _evaluation_of,
    _rows,
    _staged_successors,
    _successors,
)

LEASE_SECONDS = 60
# 崩溃点与恢复点之间的间隔必须明显大于租约，否则"恢复"会变成"抢占"。
RECOVERY_DELAY = timedelta(minutes=10)
# 租约尚未过期的时刻：用来证明"不得无条件抢占 APPLYING"。
WITHIN_LEASE_DELAY = timedelta(seconds=10)

class _WorkerCrash(BaseException):
    """模拟 Worker 进程被杀：不被 `except Exception` 捕获。"""


def _decision_row(container, user_id: str, evaluation_id: str) -> dict:
    rows = _rows(
        container,
        "SELECT * FROM adaptive_replan_decisions WHERE user_id=? AND evaluation_id=?",
        (user_id, evaluation_id),
    )
    assert rows, "决策必须已经落库"
    return rows[0]


def _plan_lineage(container, user_id: str) -> list[dict]:
    return _rows(
        container,
        "SELECT plan_id, supersedes_plan_id, superseded_by_plan_id FROM learning_plans "
        "WHERE user_id=? ORDER BY created_at, plan_id",
        (user_id,),
    )


def _worker(container, *, clock):
    """一个独立的 Worker 实例（每个实例自带 owner，代表一个真实进程）。"""
    return AdaptiveReplanningWorker(
        repository=container.adaptive_intervention_repository,
        intervention_service=container.adaptive_intervention_service,
        clock=lambda: clock,
    )


def _crash_after_claim(container, due):
    """崩溃点 1：刚把决策推进到 APPLYING，还没生成任何后继。"""
    service = container.adaptive_intervention_service
    original = service.replan_from_evaluation

    def exploding(**_kwargs):
        raise _WorkerCrash()

    service.replan_from_evaluation = exploding
    try:
        with pytest.raises(_WorkerCrash):
            _worker(container, clock=due).tick(batch_size=10)
    finally:
        service.replan_from_evaluation = original


def _crash_before_lineage(container, due):
    """崩溃点 2：后继计划已暂存，血缘绑定还没发生。"""
    repository = container.adaptive_intervention_repository
    original = repository.link_replanned

    def exploding(**_kwargs):
        raise _WorkerCrash()

    repository.link_replanned = exploding
    try:
        with pytest.raises(_WorkerCrash):
            _worker(container, clock=due).tick(batch_size=10)
    finally:
        repository.link_replanned = original


def _crash_before_applied(container, due):
    """崩溃点 3：计划与干预血缘都已绑定，只差把决策写成 APPLIED。"""
    repository = container.adaptive_intervention_repository
    original = repository.update_decision_status

    def exploding(*, user_id, decision_id, status, failure_code=None):
        if status == "APPLIED":
            raise _WorkerCrash()
        return original(user_id=user_id, decision_id=decision_id, status=status, failure_code=failure_code)

    repository.update_decision_status = exploding
    try:
        with pytest.raises(_WorkerCrash):
            _worker(container, clock=due).tick(batch_size=10)
    finally:
        repository.update_decision_status = original


def _assert_recovered(container, student, planned, *, expected_successor: int = 1):
    """恢复后必须是一个明确的终态，且后继唯一。"""
    old = planned.intervention
    old_plan_id = planned.plan.plan_id
    evaluation_row, _evaluation = _evaluation_of(container, student, old.intervention_id)

    decision = _decision_of(container, student, evaluation_row.evaluation_id)
    assert decision.status == "APPLIED", decision
    assert decision.decision == "REPLAN"
    # 终态不该继续占着租约。
    assert getattr(decision, "lease_owner", None) is None
    assert getattr(decision, "lease_expires_at", None) is None

    successors = _successors(container, student.id, old.intervention_id)
    assert len(successors) == expected_successor, successors
    assert successors[0]["status"] == "PLAN_GENERATED"

    old_row = container.adaptive_intervention_repository.get(
        user_id=student.id, intervention_id=old.intervention_id
    )
    assert old_row.status == "SUPERSEDED"
    assert old_row.superseded_by_intervention_id == successors[0]["intervention_id"]

    lineage = _plan_lineage(container, student.id)
    by_id = {row["plan_id"]: row for row in lineage}
    new_plan_id = successors[0]["plan_id"]
    assert by_id[old_plan_id]["superseded_by_plan_id"] == new_plan_id
    assert by_id[new_plan_id]["supersedes_plan_id"] == old_plan_id
    # 只有一个正式计划，且没有任何暂存残留。
    assert [row["plan_id"] for row in lineage if row["superseded_by_plan_id"] is None] == [new_plan_id]
    assert _staged_successors(container, student.id) == []


# ======================================================== 崩溃点 1：刚进入 APPLYING

def test_crash_right_after_claim_recovers_idempotently():
    container, student, _goal, planned = _declining_scenario("crash_after_claim_student")
    due = _due_after(planned)

    _crash_after_claim(container, due)

    evaluation_row, _evaluation = _evaluation_of(container, student, planned.intervention.intervention_id)
    crashed = _decision_row(container, student.id, evaluation_row.evaluation_id)
    assert crashed["status"] == "APPLYING", "崩溃必须停在 APPLYING，而不是被错误处理推进"
    assert crashed.get("lease_owner"), "处理权必须带所有者，否则无法判断谁还能继续"
    assert crashed.get("lease_expires_at"), "处理权必须带过期时间，否则残留会永久卡死"

    # 崩溃瞬间：没有任何后继被生成。
    assert _successors(container, student.id, planned.intervention.intervention_id) == []
    assert _staged_successors(container, student.id) == []

    recovery_at = due + RECOVERY_DELAY
    report = _worker(container, clock=recovery_at).tick(batch_size=10)
    assert report.failed == 0, "租约过期后重启必须能接着做完，而不是记成失败"
    assert report.applied == 1
    _assert_recovered(container, student, planned)


# ==================================================== 崩溃点 2：后继暂存、血缘未绑定

def test_crash_after_successor_staged_before_lineage_recovers_without_duplicate():
    container, student, _goal, planned = _declining_scenario("crash_before_lineage_student")
    due = _due_after(planned)

    _crash_before_lineage(container, due)

    evaluation_row, _evaluation = _evaluation_of(container, student, planned.intervention.intervention_id)
    crashed = _decision_row(container, student.id, evaluation_row.evaluation_id)
    assert crashed["status"] == "APPLYING"
    assert crashed.get("lease_owner")

    staged = _staged_successors(container, student.id)
    assert len(staged) == 1, "崩溃前应当已经生成暂存后继"
    assert staged[0]["status"] == "PROPOSED"
    assert staged[0]["supersedes_intervention_id"] is None
    # 半截血缘绝不能出现。
    assert _successors(container, student.id, planned.intervention.intervention_id) == []

    recovery_at = due + RECOVERY_DELAY
    report = _worker(container, clock=recovery_at).tick(batch_size=10)
    assert report.failed == 0
    assert report.applied == 1

    _assert_recovered(container, student, planned)
    # 恢复必须复用同一个暂存后继，而不是再生成一个。
    assert _successors(container, student.id, planned.intervention.intervention_id)[0][
        "intervention_id"
    ] == staged[0]["intervention_id"]
    assert len(_plan_lineage(container, student.id)) == 2


# ================================================ 崩溃点 3：血缘已绑定、只差 APPLIED

def test_crash_after_lineage_bound_before_applied_recovers():
    container, student, _goal, planned = _declining_scenario("crash_before_applied_student")
    due = _due_after(planned)

    _crash_before_applied(container, due)

    evaluation_row, _evaluation = _evaluation_of(container, student, planned.intervention.intervention_id)
    crashed = _decision_row(container, student.id, evaluation_row.evaluation_id)
    assert crashed["status"] == "APPLYING", "血缘已绑定但决策还没写成 APPLIED"
    assert crashed.get("lease_owner")

    # 血缘已经真实成立：旧干预被替代、后继是正式版本。
    bound = _successors(container, student.id, planned.intervention.intervention_id)
    assert len(bound) == 1
    assert bound[0]["status"] == "PLAN_GENERATED"

    recovery_at = due + RECOVERY_DELAY
    report = _worker(container, clock=recovery_at).tick(batch_size=10)
    assert report.failed == 0, "已经完成的工作不能被重复执行或记成失败"
    assert report.applied == 1

    _assert_recovered(container, student, planned)
    # 恢复只能收口决策状态，绝不能产生第二个后继或第二份计划。
    assert len(_plan_lineage(container, student.id)) == 2


# ============================================================ 不得无条件抢占 APPLYING

def test_applying_decision_is_not_preempted_before_lease_expiry():
    container, student, _goal, planned = _declining_scenario("crash_no_preempt_student")
    due = _due_after(planned)

    _crash_after_claim(container, due)
    evaluation_row, _evaluation = _evaluation_of(container, student, planned.intervention.intervention_id)
    crashed = _decision_row(container, student.id, evaluation_row.evaluation_id)

    # 租约还没过期：另一个 Worker 必须原样退出。
    early = _worker(container, clock=due + WITHIN_LEASE_DELAY).tick(batch_size=10)
    assert early.failed == 0

    still = _decision_row(container, student.id, evaluation_row.evaluation_id)
    assert still["status"] == "APPLYING", "租约未过期时不得被抢占"
    assert still.get("lease_owner") == crashed.get("lease_owner"), "处理权不能被别的 Worker 悄悄拿走"
    assert _successors(container, student.id, planned.intervention.intervention_id) == []
    assert _staged_successors(container, student.id) == []

    # 租约过期后才允许接手。
    late = _worker(container, clock=due + RECOVERY_DELAY).tick(batch_size=10)
    assert late.applied == 1
    _assert_recovered(container, student, planned)


def test_concurrent_workers_on_expired_lease_still_produce_one_successor():
    """租约过期后两个 Worker 同时抢：仍然只能有一个有效执行者、一个后继。"""
    container, student, _goal, planned = _declining_scenario("crash_concurrent_student")
    due = _due_after(planned)

    _crash_after_claim(container, due)
    evaluation_row, _evaluation = _evaluation_of(container, student, planned.intervention.intervention_id)

    repository = container.adaptive_intervention_repository
    barrier = threading.Barrier(2, timeout=60)
    original_list = repository.list_pending_decisions

    def synced_list(**kwargs):
        rows = original_list(**kwargs)
        barrier.wait()
        return rows

    repository.list_pending_decisions = synced_list
    recovery_at = due + RECOVERY_DELAY
    reports: list = []
    errors: list = []

    def run_tick() -> None:
        worker = _worker(container, clock=recovery_at)
        try:
            reports.append(worker.tick(batch_size=10))
        except BaseException as exc:  # noqa: BLE001 - 记录后由断言暴露
            errors.append(exc)

    threads = [
        threading.Thread(target=run_tick, daemon=True)
        for index in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)

    assert not errors, errors
    assert len(reports) == 2

    _assert_recovered(container, student, planned)
    assert len(_plan_lineage(container, student.id)) == 2

    decision = _decision_of(container, student, evaluation_row.evaluation_id)
    assert decision.status == "APPLIED"
    assert getattr(decision, "lease_owner", None) is None


# ============================================ 老库残留行：租约未知也不能变成永久锁

def test_lease_unknown_applying_row_is_recoverable_only_after_a_full_lease_window():
    """补列后老库里的 APPLYING 残留行没有租约。

    它既不能被当成永久锁（否则这些行永远卡死），也不能被立刻抢走
    （否则"刚崩溃"和"早就崩溃"就分不出来了）。判定依据是：从 `created_at`
    起算已经过了整整一个租约窗口。
    """
    container, student, _goal, planned = _declining_scenario("crash_legacy_lease_student")
    due = _due_after(planned)

    _crash_after_claim(container, due)
    evaluation_row, _evaluation = _evaluation_of(container, student, planned.intervention.intervention_id)
    repository = container.adaptive_intervention_repository

    # 模拟老库：清掉租约列，只留一条 APPLYING 残留。
    # `created_at` 必须与合成时钟对齐 —— 真实环境里两者同源（都取墙上时钟），
    # 这里的 `due` 是人为构造的评估时刻，所以显式写回，否则"是否过完一个租约窗口"
    # 就没有可比较的基准。
    with repository._db.transaction() as conn:
        conn.execute(
            "UPDATE adaptive_replan_decisions SET lease_owner=NULL, lease_expires_at=NULL, "
            "created_at=? WHERE user_id=? AND evaluation_id=?",
            (due.isoformat(), student.id, evaluation_row.evaluation_id),
        )
    decision_id = _decision_row(container, student.id, evaluation_row.evaluation_id)["decision_id"]

    # 刚崩不久：租约未知 + 还没过完一个租约窗口 → 不得抢占。
    fresh = repository.claim_decision(
        user_id=student.id, decision_id=decision_id, owner="worker-B",
        lease_seconds=LEASE_SECONDS, now=due + WITHIN_LEASE_DELAY,
    )
    assert fresh is False, "租约未知不等于可以立刻抢走"
    assert _decision_row(container, student.id, evaluation_row.evaluation_id)["status"] == "APPLYING"

    # 过完一个完整租约窗口后：必须可恢复，否则老库残留会永久卡死。
    report = _worker(container, clock=due + RECOVERY_DELAY).tick(batch_size=10)
    assert report.failed == 0
    assert report.applied == 1
    _assert_recovered(container, student, planned)
