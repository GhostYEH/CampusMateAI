from app.services.adaptive_agent.state_outcome_comparator import StateOutcomeComparator


def test_comparator_reports_improvement_without_causal_claim() -> None:
    result = StateOutcomeComparator().compare(
        before={"mastery": 0.4, "error_rate": 0.5}, after={"mastery": 0.6, "error_rate": 0.3},
        strategy_code="FOUNDATION_REINFORCEMENT", comparison_as_of="2026-09-18T00:00:00+00:00",
    )
    assert result["outcome"] == "IMPROVED"
    assert result["relevant_dimensions"] == ["mastery", "error_rate"]


def test_comparator_refuses_outcome_when_states_are_not_comparable() -> None:
    result = StateOutcomeComparator().compare(
        before={}, after={}, strategy_code="FOUNDATION_REINFORCEMENT", comparison_as_of="2026-09-18T00:00:00+00:00",
    )
    assert result["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert result["warnings"] == ["missing_comparable_state_evidence"]
