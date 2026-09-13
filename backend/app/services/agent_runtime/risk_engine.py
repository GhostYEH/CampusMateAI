from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskDecision:
    risk_level: str
    executable: bool


class RiskEngine:
    MANUAL_ONLY = frozenset({"payment.execute", "authentication.perform", "captcha.solve", "assignment.submit", "external_system.mutate"})
    CONFIRM = frozenset({"external_submission.prepare", "plan.activate", "task.update"})
    # 显式只读/低风险白名单：不在此集合内的动作一律按 MANUAL_ONLY 处理。
    SAFE = frozenset({
        "task.create", "reminder.schedule", "task.propose", "artifact.create",
        "student.read", "course.read", "exam.read", "learner_state.read",
        "plan.propose", "knowledge.search",
    })

    def classify(self, action: str, *, automation_enabled: bool) -> RiskDecision:
        if action in self.MANUAL_ONLY or action not in self.MANUAL_ONLY | self.CONFIRM | self.SAFE:
            return RiskDecision("MANUAL_ONLY", False)
        if action in self.CONFIRM or not automation_enabled:
            return RiskDecision("CONFIRM_REQUIRED", False)
        return RiskDecision("AUTO_SAFE", True)
