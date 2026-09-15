"""课程上下文构造器 —— 授权、脱敏、截断后再送入 OpenMAIC / CPM。

安全约束：
- 后端重新查询课程与章节，绝不信任客户端提交的课程名/章节/掌握率。
- 只发送课程名称、代码、学期、描述、章节标题、知识点标题、已授权资料标题等
  教学事实；绝不发送学习通账号/密码/Cookie、CampusMate JWT、他人数据、
  不必要的个人成绩与附件正文。
- "掌握项"只描述可观察的章节完成证据，不把推测当事实。
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ...core.exceptions import CourseNotFound, Forbidden
from ...models.multi_role import CourseRow, UserRow
from ..course_access import can_view_course

if TYPE_CHECKING:
    from ...services.container import ServiceContainer

# 送入生成 requirements 的文本上限(由配置控制，这里只做界面约束)
_MAX_CONTEXT_CHARS = 4000


def assert_course_access(
    container: ServiceContainer,
    user: UserRow,
    course_id: str,
) -> CourseRow:
    """校验当前用户对课程的访问权。失败抛 CourseNotFound / Forbidden。

    复用统一课程可见性策略(course_access.can_view_course)，与课程详情/内容/
    知识图谱/CPM 上下文保持同一口径：管理员、已加入班级的课程，或学生自己
    导入的学习通课程都可访问。
    """
    course = container.course_repository.get_course(course_id)
    if course is None:
        raise CourseNotFound()
    if user.role == "admin":
        return course
    if user.role != "student":
        raise Forbidden("仅学生可生成互动课堂")
    if not can_view_course(container, user, course):
        raise Forbidden("无权访问该课程")
    return course


def _format_rate(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return f"{round(float(value), 2)}%"
    except (TypeError, ValueError):
        return None


def _knowledge_lines(
    container: ServiceContainer,
    user: UserRow,
    course_id: str,
    *,
    max_points: int = 20,
    max_tags: int = 12,
) -> List[str]:
    """当前课程的知识点与知识图谱统计(含真实掌握率)。

    数据来源是该用户自己同步落库的学习通知识图谱观测，严格按 user_id + course_id
    过滤，只输出课程级统计与知识点名称，不含任何他人身份信息。
    未同步过时不编造，直接返回空。
    """
    repository = getattr(container, "chaoxing_repository", None)
    if repository is None:
        return []
    lines: List[str] = []
    try:
        graphs = repository.list_knowledge_graphs(user_id=user.id)
        points = repository.list_knowledge_points(user_id=user.id, course_id=course_id)
    except Exception:  # noqa: BLE001 - 上下文增强失败不得影响主流程
        return []
    graph = next((row for row in graphs if row.get("course_id") == course_id), None)
    if graph is not None:
        stats: List[str] = []
        count = graph.get("knowledge_point_count")
        if count is not None:
            try:
                stats.append(f"知识点数:{int(count)}")
            except (TypeError, ValueError):
                pass
        own = _format_rate(graph.get("own_mastery_rate"))
        class_avg = _format_rate(graph.get("class_mastery_rate"))
        if own:
            stats.append(f"我的掌握率:{own}")
        if class_avg:
            stats.append(f"班级平均掌握率:{class_avg}")
        try:
            if graph.get("own_mastery_rate") is not None and graph.get("class_mastery_rate") is not None:
                gap = round(
                    float(graph["own_mastery_rate"]) - float(graph["class_mastery_rate"]), 2
                )
                stats.append(f"与班级差:{gap} 个百分点(正数=领先)")
        except (TypeError, ValueError):
            pass
        own_done = _format_rate(graph.get("own_completion_rate"))
        if own_done:
            stats.append(f"我的完成率:{own_done}")
        if stats:
            lines.append(
                "- 知识图谱统计(课程级，来自已同步的真实观测): " + " ".join(stats)
            )

    names: List[str] = []
    for row in points:
        name = str(row.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
        if len(names) >= max_points:
            break
    if names:
        lines.append("- 知识点: " + "、".join(names))

    tags: List[str] = []
    for row in points:
        raw = row.get("tags")
        decoded: Any = raw
        if isinstance(raw, str) and raw.strip():
            try:
                decoded = json.loads(raw)
            except (TypeError, ValueError):
                decoded = []
        if isinstance(decoded, list):
            for tag in decoded:
                text = str(tag or "").strip()
                if text and text not in tags:
                    tags.append(text)
        if len(tags) >= max_tags:
            break
    if tags:
        lines.append("- 知识点标签: " + "、".join(tags[:max_tags]))
    return lines


def _chapter_lines(container: ServiceContainer, user: UserRow, course_id: str) -> List[str]:
    items = container.course_content_repository.list_items(
        user_id=user.id, course_id=course_id, kind="chapter", page_size=100
    )
    lines: List[str] = []
    for item in items:
        title = (item.title or "").strip()
        if not title:
            continue
        status = "已完成" if item.status == "completed" else ("学习中" if item.status == "in_progress" else "未完成")
        line = f"- {title}"
        if item.status == "completed":
            line += " (已完成的章节)"
        lines.append(line)
    return lines


def _resource_lines(container: ServiceContainer, user: UserRow, course_id: str) -> List[str]:
    """已授权课程资料的标题与描述(不含附件正文)。"""
    items = container.course_content_repository.list_items(
        user_id=user.id, course_id=course_id, page_size=50
    )
    lines: List[str] = []
    seen: set[str] = set()
    for item in items:
        title = (item.title or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        line = f"- {title} ({item.kind or '资料'})"
        if item.description:
            line += f" — {item.description.strip()[:80]}"
        lines.append(line)
    return lines[:30]


def _assignment_topics(
    container: ServiceContainer, user: UserRow, course_id: str
) -> List[str]:
    """该课程相关作业/测验/考试的主题(仅标题，不含答案)。"""
    topics: List[str] = []
    seen: set[str] = set()
    for e in container.enrollment_repository.list_user_classes(user.id):
        if e.get("course_id") != course_id:
            continue
        class_id = e.get("class_group_id") or e.get("class_id")
        if not class_id:
            continue
        assignments, _ = container.assignment_repository.list_assignments(
            class_group_id=class_id, page=1, page_size=100
        )
        for a in assignments:
            title = (a.title or "").strip()
            if not title or title in seen:
                continue
            seen.add(title)
            topics.append(title)
    return topics[:20]


def build_course_context(
    container: ServiceContainer,
    user: UserRow,
    course: CourseRow,
    *,
    max_chars: int = _MAX_CONTEXT_CHARS,
) -> str:
    """构造经授权、脱敏的课程学习上下文文本(用于课堂生成)。"""
    lines: List[str] = []
    lines.append(f"[课程] {course.name}")
    meta = []
    if course.code:
        meta.append(f"代码:{course.code}")
    if course.semester:
        meta.append(f"学期:{course.semester}")
    if course.provider:
        meta.append(f"来源:{course.provider}")
    if meta:
        lines.append("  " + " ".join(meta))
    if course.description:
        lines.append(f"[课程描述] {course.description.strip()[:500]}")

    chapters = _chapter_lines(container, user, course.id)
    if chapters:
        lines.append("[章节]")
        lines.extend(chapters[:25])

    knowledge = _knowledge_lines(container, user, course.id)
    if knowledge:
        lines.append("[知识点与掌握情况]")
        lines.extend(knowledge)

    resources = _resource_lines(container, user, course.id)
    if resources:
        lines.append("[课程资料(标题)]")
        lines.extend(resources)

    topics = _assignment_topics(container, user, course.id)
    if topics:
        lines.append("[作业/测验主题]")
        lines.extend(topics)

    text = "\n".join(lines).strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[已截断]"
    return text


def build_cpm_course_block(
    container: ServiceContainer,
    user: UserRow,
    course: CourseRow,
    *,
    max_chars: int = 2500,
) -> str:
    """构造 CPM 使用的课程上下文块(章节/知识点/作业/课堂存在状态)。"""
    lines: List[str] = []
    lines.append(f"[课程] {course.name} ({course.code or '无代码'}) 学期:{course.semester or '未知'}")
    if course.description:
        lines.append(f"[课程描述] {course.description.strip()[:300]}")

    chapters = _chapter_lines(container, user, course.id)
    if chapters:
        lines.append("[章节]")
        lines.extend(chapters[:12])

    knowledge = _knowledge_lines(container, user, course.id, max_points=12, max_tags=8)
    if knowledge:
        lines.append("[知识点与掌握情况]")
        lines.extend(knowledge)

    topics = _assignment_topics(container, user, course.id)
    if topics:
        lines.append("[作业/测验主题]")
        lines.extend(topics[:10])

    # 已生成互动课堂的存在状态与可用学习模式(用于引导学生打开课堂)
    store = getattr(container, "openmaic_result_store", None)
    if store is not None:
        sessions = store.list_sessions(user_id=user.id, course_id=course.id)
        finished = [s for s in sessions if s.status == "succeeded" and s.classroom_url]
        modes = sorted({s.mode for s in finished})
        if finished:
            lines.append(
                "[互动课堂](由 OpenMAIC 生成的辅助学习内容，非学校官方规定): "
                f"已存在 {len(finished)} 个课堂，可用模式: {', '.join(modes) or '未记录'}"
            )

    text = "\n".join(lines).strip()
    if len(text) > max_chars:
        text = text[:max_chars]
    return text


__all__ = [
    "assert_course_access",
    "build_course_context",
    "build_cpm_course_block",
]