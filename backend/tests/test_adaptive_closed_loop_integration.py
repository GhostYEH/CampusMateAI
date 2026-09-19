from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.core.security import hash_password
from app.services.container import reset_container_for_tests


def test_real_container_tick_persists_baseline_comparison_decision_and_event():
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    student = container.user_repository.create_user(
        username="closed_loop_student", password_hash=hash_password("Demo123456"), role="student"
    )
    other = container.user_repository.create_user(
        username="closed_loop_other", password_hash=hash_password("Demo123456"), role="student"
    )
    container.personal_task_repository.create_task(
        user_id=student.id, title="真实闭环任务",
        deadline=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
    )
    goal = container.student_goal_repository.create_goal(
        user_id=student.id, name="闭环目标", category="ACADEMIC",
        target_date=(datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat(),
        idempotency_key="closed-loop-goal",
    )[0]
    planned = container.adaptive_intervention_service.plan_for_goal(
        user_id=student.id, goal_id=goal.goal_id, available_minutes=60,
        idempotency_key="closed-loop-intervention",
    )
    due = datetime(2026, 9, 19, tzinfo=timezone.utc)
    with container.adaptive_intervention_repository._db.transaction() as conn:
        conn.execute(
            "UPDATE adaptive_interventions SET observation_due_at=? WHERE intervention_id=?",
            ((due - timedelta(minutes=1)).isoformat(), planned.intervention.intervention_id),
        )
    worker = container.adaptive_replanning_worker
    worker._clock = lambda: due
    report = worker.tick(batch_size=10)
    assert report.scanned == 1
    stored = container.adaptive_intervention_repository.get_evaluation(
        user_id=student.id, intervention_id=planned.intervention.intervention_id
    )
    assert stored is not None
    evaluation = container.adaptive_intervention_service._restore_evaluation(stored)
    assert evaluation.state_comparison["before_run_ids"]
    assert evaluation.state_comparison["after_run_ids"]
    decision = container.adaptive_intervention_repository.get_decision(
        user_id=student.id, evaluation_id=evaluation.evaluation_id
    )
    assert decision is not None
    # The real projection has an execution signal but no completed work.  The
    # policy may conservatively continue while evidence accumulates; neither
    # CONTINUE nor WAIT_FOR_EVIDENCE is allowed to create a successor.
    assert decision.decision in {"CONTINUE", "WAIT_FOR_EVIDENCE"}
    assert decision.status == "APPLIED"
    with container.adaptive_intervention_repository._db.query() as conn:
        successor_count = conn.execute(
            "SELECT COUNT(*) FROM adaptive_interventions "
            "WHERE user_id=? AND supersedes_intervention_id=?",
            (student.id, planned.intervention.intervention_id),
        ).fetchone()[0]
    assert successor_count == 0
    events, _ = container.learner_event_repository.list_for_user(
        user_id=student.id, source="adaptive_intervention", page=1, page_size=20
    )
    assert {event.event_type for event in events} >= {"intervention_observed", "intervention_decided"}
    assert container.adaptive_intervention_repository.get(
        user_id=other.id, intervention_id=planned.intervention.intervention_id
    ) is None


def test_real_container_replan_creates_and_binds_one_successor(monkeypatch):
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    student = container.user_repository.create_user(
        username="real_replan_student", password_hash=hash_password("Demo123456"), role="student"
    )
    container.personal_task_repository.create_task(
        user_id=student.id, title="可重规划任务",
        deadline=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
    )
    goal = container.student_goal_repository.create_goal(
        user_id=student.id, name="重规划目标", category="ACADEMIC",
        target_date=(datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat(),
        idempotency_key="real-replan-goal",
    )[0]
    planned = container.adaptive_intervention_service.plan_for_goal(
        user_id=student.id, goal_id=goal.goal_id, available_minutes=60,
        idempotency_key="real-replan-intervention",
    )
    due = datetime(2026, 9, 19, tzinfo=timezone.utc)
    with container.adaptive_intervention_repository._db.transaction() as conn:
        conn.execute(
            "UPDATE adaptive_interventions SET observation_due_at=? WHERE intervention_id=?",
            ((due - timedelta(minutes=1)).isoformat(), planned.intervention.intervention_id),
        )

    # This is a real worker/service/repository path.  Only the post-state
    # projection is controlled so the integration test deterministically
    # exercises the DECLINED/high-pressure branch without mocking replan itself.
    def declined_comparison(**_kwargs):
        return {
            "outcome": "DECLINED", "confidence": 0.8,
            "before_values": {"completion_rate": 0.8, "stress_risk": 0.2},
            "after_values": {"completion_rate": 0.4, "stress_risk": 0.9},
            "delta": {"completion_rate": -0.4, "stress_risk": -0.7},
            "relevant_dimensions": ["completion_rate", "stress_risk"],
            "evidence_refs": ["before-snapshot", "after-snapshot"],
            "dimensions": {}, "warnings": [],
        }

    monkeypatch.setattr(container.adaptive_intervention_service._state_normalizer, "compare", declined_comparison)
    worker = container.adaptive_replanning_worker
    worker._clock = lambda: due
    report = worker.tick(batch_size=10)
    assert report.applied == 1

    old = container.adaptive_intervention_repository.get(
        user_id=student.id, intervention_id=planned.intervention.intervention_id
    )
    evaluation_row = container.adaptive_intervention_repository.get_evaluation(
        user_id=student.id, intervention_id=planned.intervention.intervention_id
    )
    assert old is not None and evaluation_row is not None
    decision = container.adaptive_intervention_repository.get_decision(
        user_id=student.id, evaluation_id=evaluation_row.evaluation_id
    )
    assert decision is not None and decision.decision == "REPLAN" and decision.status == "APPLIED"
    assert "reduce_workload" in json.loads(decision.suggested_adjustments_json)

    with container.adaptive_intervention_repository._db.query() as conn:
        successors = conn.execute(
            "SELECT * FROM adaptive_interventions WHERE user_id=? AND supersedes_intervention_id=?",
            (student.id, old.intervention_id),
        ).fetchall()
    assert len(successors) == 1
    successor = container.adaptive_intervention_repository.get(
        user_id=student.id, intervention_id=successors[0]["intervention_id"]
    )
    assert successor is not None
    assert old.status == "SUPERSEDED"
    assert successor.status == "PLAN_GENERATED"
    assert successor.source_evaluation_id == evaluation_row.evaluation_id
    assert successor.replan_decision_id == decision.decision_id
    assert successor.supersedes_intervention_id == old.intervention_id
    successor_strategy = json.loads(successor.strategy_json)
    assert successor_strategy["planning_parameters"]["workload_scale"] < json.loads(old.strategy_json)["planning_parameters"]["workload_scale"]

    # The durable decision and idempotent replan key prevent a second successor.
    assert worker.tick(batch_size=10).scanned == 0
    with container.adaptive_intervention_repository._db.query() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM adaptive_interventions WHERE user_id=? AND supersedes_intervention_id=?",
            (student.id, old.intervention_id),
        ).fetchone()[0] == 1
    events, _ = container.learner_event_repository.list_for_user(
        user_id=student.id, source="adaptive_intervention", page=1, page_size=50
    )
    assert any(event.event_type == "intervention_replanned" for event in events)
