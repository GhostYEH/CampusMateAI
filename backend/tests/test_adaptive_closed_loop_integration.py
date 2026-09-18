from __future__ import annotations

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
