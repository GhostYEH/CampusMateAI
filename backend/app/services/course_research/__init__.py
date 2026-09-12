"""课程研究/作业辅助服务包(§8.2、§9.5)。

Coordinator 顺序调度 Researcher、WebResearcher、CitationVerifier、Tutor、Critic、
Synthesizer 逻辑角色,输出可追踪引用的 JSON/Markdown Artifact。
"""
from __future__ import annotations

from .policy import AcademicPolicy, SourcePolicy, build_effective_policy
from .pipeline import CourseResearchPipeline, CourseResearchResult

__all__ = [
    "AcademicPolicy",
    "SourcePolicy",
    "build_effective_policy",
    "CourseResearchPipeline",
    "CourseResearchResult",
]