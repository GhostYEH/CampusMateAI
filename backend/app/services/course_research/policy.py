from ...models.course_research import ResearchPolicyDecision


RESTRICTED_POLICIES = frozenset({"EXAM_RESTRICTED", "AI_PROHIBITED", "UNKNOWN"})


def decide_research_policy(requested_mode: str, academic_policy: str) -> ResearchPolicyDecision:
    effective_mode = requested_mode
    warnings: list[str] = []
    if academic_policy in RESTRICTED_POLICIES and requested_mode == "FULL_SOLUTION":
        effective_mode = "HINT"
        warnings.append("ACADEMIC_POLICY_DOWNGRADED")
    return ResearchPolicyDecision(requested_mode, effective_mode, tuple(warnings))
