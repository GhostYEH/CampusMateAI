"""Declarative Skill/MCP capability registry.

Skills describe which governed runtime capabilities a workflow may compose.  The
manifest is metadata only: it never contains credentials, arbitrary code, or a
remote URL, and it cannot trigger execution by itself.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class AgentSkill:
    skill_code: str
    version: str
    description: str
    capabilities: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    transport: str = "internal"
    permission_policy: str = "student_owned_only"


_DEFAULT_SKILLS = (
    AgentSkill(
        "learning_goal_center", "1.0", "把学习目标转为可确认、可追踪、可重规划的任务计划",
        ("goal.aggregate", "plan.generate", "plan.execute", "plan.replan", "summary.create"),
        ("student.read", "course.read", "learner_state.read", "task.create", "plan.activate"),
    ),
    AgentSkill(
        "final_review", "1.0", "期末复习计划与每日跟进",
        ("plan.generate", "schedule.adapt", "evidence.collect"),
        ("exam.read", "task.create", "plan.activate"),
    ),
    AgentSkill(
        "course_research", "1.0", "基于课程资料的研究与作业辅助",
        ("research.coordinate", "citation.verify", "report.synthesize"),
        ("course.read", "knowledge.search", "research.report.create"),
    ),
    AgentSkill(
        "notice_workflow", "1.0", "校园通知解释与事务办理跟踪",
        ("notice.interpret", "workflow.plan", "action.track"),
        ("notice.read", "task.propose", "reminder.schedule"),
    ),
)


_MANIFEST_PATH = Path(__file__).with_name("skills.default.json")


def load_skills_from_manifest(path: Path | str) -> tuple[AgentSkill, ...]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("skills", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("Skill 清单格式不正确")
    skills: list[AgentSkill] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("skill_code"):
            raise ValueError("Skill 条目缺少 skill_code")
        transport = str(item.get("transport", "internal"))
        if transport not in {"internal", "mcp_manifest"}:
            raise ValueError("Skill transport 不受支持")
        # Manifest is intentionally limited to allowlisted metadata fields.
        skills.append(AgentSkill(
            skill_code=str(item["skill_code"]), version=str(item.get("version", "1.0")),
            description=str(item.get("description", ""))[:256],
            capabilities=tuple(str(x) for x in item.get("capabilities") or ()),
            tools=tuple(str(x) for x in item.get("tools") or ()), transport=transport,
            permission_policy=str(item.get("permission_policy", "student_owned_only")),
        ))
    return tuple(skills)


class SkillRegistry:
    def __init__(self, manifest_path: Optional[Path | str] = None) -> None:
        path = Path(manifest_path) if manifest_path is not None else _MANIFEST_PATH
        skills = _DEFAULT_SKILLS
        try:
            if path.exists():
                loaded = load_skills_from_manifest(path)
                if loaded:
                    skills = loaded
        except Exception:
            skills = _DEFAULT_SKILLS
        self._skills = {skill.skill_code: skill for skill in skills}

    def get(self, skill_code: str) -> Optional[AgentSkill]:
        return self._skills.get(skill_code)

    def list_skills(self) -> list[AgentSkill]:
        return list(self._skills.values())


__all__ = ["AgentSkill", "SkillRegistry", "load_skills_from_manifest"]
