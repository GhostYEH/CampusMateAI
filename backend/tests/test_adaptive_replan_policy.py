from app.services.adaptive_agent.replan_policy import ReplanDecisionPolicy


def test_insufficient_evidence_waits_and_never_replans() -> None:
    decision = ReplanDecisionPolicy().decide(
        evaluation={"observed_outcome": "INSUFFICIENT_EVIDENCE", "adoption": "COMPLETED"},
        state={}, goal={"status": "active"}, now="2026-09-18T00:00:00+00:00",
    )
    assert decision.decision == "WAIT_FOR_EVIDENCE"
    assert "insufficient_state_evidence" in decision.reason_codes


def test_decline_or_rising_stress_replans_with_explainable_adjustment() -> None:
    decision = ReplanDecisionPolicy().decide(
        evaluation={"observed_outcome": "DECLINED", "adoption": "IN_PROGRESS"},
        state={"stress_risk": 0.9}, goal={"status": "active"}, now="2026-09-18T00:00:00+00:00",
    )
    assert decision.decision == "REPLAN"
    assert "reduce_workload" in decision.suggested_adjustments


def test_completed_goal_suspends() -> None:
    assert ReplanDecisionPolicy().decide(
        evaluation={"observed_outcome": "IMPROVED", "adoption": "COMPLETED"}, state={},
        goal={"status": "completed"}, now="2026-09-18T00:00:00+00:00",
    ).decision == "SUSPEND"
