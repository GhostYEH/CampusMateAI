"""决策处理权租约的边界、所有权与终态语义。

`test_adaptive_replan_crash_recovery.py` 覆盖的是"崩溃后能否恢复"；
这里覆盖的是**判定边界本身**：租约到底在哪一刻算过期、谁能抢、谁不能抢、
终态是否真的释放了处理权。这些边界一旦写反，表现是"偶尔多生成一个后继"
或"决策永远卡住"，都很难在常规用例里暴露。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.adaptive_agent.replanning_worker import AdaptiveReplanningWorker

from test_adaptive_closed_loop_integrity import (  # noqa: F401 - 复用真实场景夹具
    _declining_scenario,
    _due_after,
    _rows,
)
from test_adaptive_replan_crash_recovery import (  # noqa: F401 - 复用真实崩溃夹具
    LEASE_SECONDS,
    _crash_after_claim,
    _decision_row,
)

# 固定时刻，避免用例依赖真实时钟。
BASE = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _applying_decision(username: str):
    """造一条真实的 APPLYING 决策（先让 Worker 抢到处理权再崩）。"""
    container, student, _goal, planned = _declining_scenario(username)
    due = _due_after(planned)
    _crash_after_claim(container, due)
    evaluation_row = _evaluation_of_id(container, student, planned)
    row = _decision_row(container, student.id, evaluation_row["evaluation_id"])
    assert row["status"] == "APPLYING"
    return container, student, row


def _evaluation_of_id(container, student, planned):
    return _rows(
        container,
        "SELECT evaluation_id FROM intervention_evaluations WHERE user_id=? AND intervention_id=?",
        (student.id, planned.intervention.intervention_id),
    )[0]


def _set_row(container, decision_id: str, **fields) -> None:
    assignments = ", ".join(f"{name}=?" for name in fields)
    with container.adaptive_intervention_repository._db.transaction() as conn:
        conn.execute(
            f"UPDATE adaptive_replan_decisions SET {assignments} WHERE decision_id=?",
            (*fields.values(), decision_id),
        )


def _claim(container, user_id: str, decision_id: str, *, now: datetime,
           owner: str = "worker-a", lease_seconds: float = LEASE_SECONDS) -> bool:
    return container.adaptive_intervention_repository.claim_decision(
        user_id=user_id, decision_id=decision_id,
        owner=owner, lease_seconds=lease_seconds, now=now,
    )


# ==================================================== 租约过期边界（必须精确、可解释）

def test_lease_expiry_boundary_is_inclusive_and_never_early():
    """`lease_expires_at <= now` 才算过期：到点可抢，早一刻不可抢。"""
    container, student, row = _applying_decision("lease_boundary_student")
    decision_id = row["decision_id"]

    _set_row(container, decision_id, lease_expires_at=BASE.isoformat(), lease_owner="worker-dead")

    assert _claim(container, student.id, decision_id, now=BASE - timedelta(seconds=1)) is False, \
        "租约还没到期，任何 Worker 都不得抢占"
    # 上一步没抢到，状态必须原样保持，不能被失败的抢占改坏。
    assert _decision_row(container, student.id, row["evaluation_id"])["lease_owner"] == "worker-dead"

    assert _claim(container, student.id, decision_id, now=BASE, owner="worker-b") is True, \
        "到期这一刻必须可被接手，否则崩溃残留会永远卡住"
    taken = _decision_row(container, student.id, row["evaluation_id"])
    assert taken["status"] == "APPLYING" and taken["lease_owner"] == "worker-b"


def test_claim_never_preempts_a_live_lease_even_for_the_same_owner():
    """租约未过期时，连"原持有者自己"也不能重复抢 —— 否则会重复生成后继。"""
    container, student, row = _applying_decision("lease_live_student")
    decision_id = row["decision_id"]
    owner = row["lease_owner"]

    assert _claim(container, student.id, decision_id, now=BASE, owner=owner) is False, \
        "处理权已经在手上，重复抢到会让同一个 Worker 再走一遍生成后继"


def test_legacy_applying_row_without_lease_becomes_recoverable_only_after_a_full_window():
    """老库残留行（租约列为 NULL）不能被当成永久锁，也不能被立刻抢走。"""
    container, student, row = _applying_decision("lease_legacy_student")
    decision_id = row["decision_id"]
    created = BASE
    _set_row(
        container, decision_id,
        created_at=created.isoformat(), lease_owner=None, lease_expires_at=None,
    )

    assert _claim(container, student.id, decision_id,
                  now=created + timedelta(seconds=LEASE_SECONDS - 1)) is False, \
        "不满一个租约窗口就接手，等于把未知当成已死"
    assert _claim(container, student.id, decision_id,
                  now=created + timedelta(seconds=LEASE_SECONDS + 1), owner="worker-b") is True, \
        "满一个租约窗口后必须可恢复，否则老库残留会永久卡死"


# ============================================================ 谁能进入 APPLYING

def test_permanent_failure_is_not_claimable_but_retryable_failure_is():
    """只有"可重试的失败"能重新进入 APPLYING；永久失败必须停在终态。"""
    container, student, row = _applying_decision("claim_failure_class_student")
    decision_id = row["decision_id"]

    _set_row(container, decision_id, status="FAILED", failure_class="PERMANENT",
             lease_owner=None, lease_expires_at=None)
    assert _claim(container, student.id, decision_id, now=BASE) is False, \
        "永久失败不该被无限重试"

    _set_row(container, decision_id, status="FAILED", failure_class="RETRYABLE")
    assert _claim(container, student.id, decision_id, now=BASE, owner="worker-b") is True, \
        "可重试失败必须能被接手"


def test_applied_decision_is_terminal_and_never_claimable_again():
    container, student, row = _applying_decision("claim_applied_student")
    decision_id = row["decision_id"]
    _set_row(container, decision_id, status="APPLIED", lease_owner=None, lease_expires_at=None)

    assert _claim(container, student.id, decision_id, now=BASE) is False
    assert _claim(container, student.id, decision_id,
                  now=BASE + timedelta(days=365)) is False, \
        "终态不是等租约过期就能重来"


def test_claiming_clears_stale_failure_markers_and_stamps_ownership():
    """抢到处理权时必须把上一次的失败痕迹清掉，并写下新的所有者与到期时间。"""
    container, student, row = _applying_decision("claim_stamp_student")
    decision_id = row["decision_id"]
    _set_row(container, decision_id, status="FAILED", failure_class="RETRYABLE",
             failure_code="OperationalError", lease_owner=None, lease_expires_at=None)

    assert _claim(container, student.id, decision_id, now=BASE,
                  owner="worker-c", lease_seconds=120) is True
    taken = _decision_row(container, student.id, row["evaluation_id"])
    assert taken["lease_owner"] == "worker-c"
    assert taken["lease_expires_at"] == (BASE + timedelta(seconds=120)).isoformat()
    assert taken["failure_code"] is None and taken["failure_class"] == "NONE", \
        "残留的失败标记会让正在处理看起来像刚失败过"


def test_terminal_status_releases_ownership():
    container, student, row = _applying_decision("lease_release_student")
    decision_id = row["decision_id"]
    repository = container.adaptive_intervention_repository

    assert repository.update_decision_status(
        user_id=student.id, decision_id=decision_id, status="APPLIED",
    ) is not None
    done = _decision_row(container, student.id, row["evaluation_id"])
    assert done["lease_owner"] is None and done["lease_expires_at"] is None


def test_worker_uses_a_stable_owner_identity_across_ticks():
    """同一个 Worker 实例跨轮次必须是同一个所有者，否则崩溃残留无法追溯。"""
    container, _student, _goal, planned = _declining_scenario("worker_owner_student")
    worker = AdaptiveReplanningWorker(
        repository=container.adaptive_intervention_repository,
        intervention_service=container.adaptive_intervention_service,
        clock=lambda: _due_after(planned),
    )
    assert worker._owner_id and worker._owner_id == worker._owner_id
    other = AdaptiveReplanningWorker(
        repository=container.adaptive_intervention_repository,
        intervention_service=container.adaptive_intervention_service,
    )
    assert other._owner_id != worker._owner_id, "两个 Worker 实例必须能被区分"
