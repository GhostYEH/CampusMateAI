from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentRole:
    code: str
    tools: frozenset[str]
    model_policy: str


class AgentRegistry:
    def __init__(self, roles: list[AgentRole]) -> None:
        self._roles = {role.code: role for role in roles}

    @classmethod
    def default(cls) -> "AgentRegistry":
        return cls([
            AgentRole("planner", frozenset({"student.read", "course.read", "exam.read", "learner_state.read", "plan.propose", "task.create"}), "reasoning_primary"),
            AgentRole("analyzer", frozenset({"student.read", "learner_state.read", "plan.propose"}), "reasoning_primary"),
            AgentRole("notice_interpreter", frozenset({"student.read", "task.propose"}), "fast_structured"),
            AgentRole("workflow_planner", frozenset({"task.propose", "task.create", "reminder.schedule", "external_submission.prepare"}), "reasoning_primary"),
            *[AgentRole(code, frozenset({"course.read", "knowledge.search", "research.source.fetch", "research.report.create"}), "reasoning_primary") for code in ("coordinator", "course_researcher", "web_researcher", "citation_verifier", "tutor", "critic", "synthesizer")],
        ])

    def get(self, code: str) -> AgentRole | None:
        return self._roles.get(code)
