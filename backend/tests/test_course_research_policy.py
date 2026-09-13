import pytest

from app.services.course_research.policy import decide_research_policy


@pytest.mark.parametrize("policy", ["UNKNOWN", "EXAM_RESTRICTED", "AI_PROHIBITED"])
def test_restricted_policies_always_downgrade_full_solution(policy):
    decision = decide_research_policy("FULL_SOLUTION", policy)
    assert decision.effective_mode == "HINT"
    assert decision.warning_codes == ("ACADEMIC_POLICY_DOWNGRADED",)


def test_standard_policy_preserves_requested_mode():
    decision = decide_research_policy("REVIEW", "STANDARD")
    assert decision.effective_mode == "REVIEW"
    assert decision.warning_codes == ()
