from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskDecision:
    risk_level: str
    executable: bool


class RiskEngine:
    MANUAL_ONLY = frozenset({"payment.execute", "authentication.perform", "captcha.solve", "assignment.submit", "external_system.mutate"})
    CONFIRM = frozenset({"external_submission.prepare", "plan.activate", "task.update"})

    def classify(self, action: str, *, automation_enabled: bool) -> RiskDecision:
        if action in self.MANUAL_ONLY or action not in self.MANUAL_ONLY | self.CONFIRM | {"task.create", "reminder.schedule", "task.propose"}:
            return RiskDecision("MANUAL_ONLY", False)
        if action in self.CONFIRM or not automation_enabled:
            return RiskDecision("CONFIRM_REQUIRED", False)
        return RiskDecision("AUTO_SAFE", True)
