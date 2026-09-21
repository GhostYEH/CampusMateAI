"""课程上下文构造器 —— 授权、脱敏、限长后再送入 magicclass / CPM。

安全约束：
- 后端重新查询课程与章节，绝不信任客户端提交的课程名/章节/掌握率/资料正文。
- 只发送课程名称、代码、学期、描述、章节标题、知识点标题、已授权资料标题与
  受控摘要等教学事实；绝不发送学习通账号/密码/Cookie、CampusMate JWT、他人数据、
  不必要的个人成绩与附件原文。
- "薄弱"信号只用**可观察**事实：实测逐点掌握率（现实中通常没有），
  否则退化为"未完成章节"。不把推测当事实、不编造掌握率数字。

所有集合都有数量上限、单项字符上限与总字符上限，并且裁剪是确定性的。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

from ...core.exceptions import CourseNotFound, Forbidden
from ...models.multi_role import CourseRow, UserRow
from ..course_access import can_view_course
from ..chaoxing.sync_facts import last_chaoxing_sync_at
from .requirement_builder import AdaptiveSignals

if TYPE_CHECKING:
    from ...services.container import ServiceContainer

# 送入生成 requirements 的文本上限(默认值；实际由配置控制)
_MAX_CONTEXT_CHARS = 4000


@dataclass(frozen=True)
class ContextLimits:
    """每类集合的数量上限、单项字符上限与总字符上限。"""

    total_chars: int = _MAX_CONTEXT_CHARS
    description_chars: int = 300
    chapters: int = 20
    chapter_title_chars: int = 120
    knowledge_points: int = 20
    knowledge_tags: int = 8
    # 未完成章节作为薄弱信号时的条数上限
    weak_areas: int = 8
    materials: int = 15
    material_title_chars: int = 120
    material_excerpt_chars: int = 800
    assignments: int = 15
    assignment_title_chars: int = 120
    exams: int = 10
    exam_title_chars: int = 120


@dataclass(frozen=True)
class MaterialRef:
    """可被学生勾选使用的课程资料（只暴露 id/标题/类型）。"""

    id: str
    title: str
    kind: str


@dataclass(frozen=True)
class LearningContext:
    """一次生成所需的学习上下文（文本 + 结构化元数据）。"""

    text: str
    materials: Tuple[MaterialRef, ...] = ()
    signals: AdaptiveSignals = field(default_factory=AdaptiveSignals)
    # 各集合的数据来源（供 UI/审计展示，不含任何凭据）
    sources: Dict[str, str] = field(default_factory=dict)
    # 各来源的更新时间（能拿到才写，拿不到留空，不伪造）
    updated_at: Dict[str, str] = field(default_factory=dict)
    truncated: bool = False
    # 进入 magic class pdfContent.text 的受控正文摘要
    material_text: str = ""
    # 读取失败的集合说明。**必须**区分"真的没有"与"读不到"：
    # 读取异常绝不能被静默吞成空列表。
    warnings: List[str] = field(default_factory=list)
    # 本次实际生效的资料 id（服务端授权范围内的最终结果）
    selected_material_ids: Tuple[str, ...] = ()
    # 学生指定了但**无法解析**的资料 id（不存在 / 越权 / 已删除）。
    # 绝不能静默忽略：调用方必须据此给出明确语义（降级或报错）。
    unresolved_material_ids: Tuple[str, ...] = ()


# ===== 权限 =====


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


# ===== 小工具 =====


def _clip(text: Any, limit: int) -> str:
    value = str(text or "").strip()
    if limit <= 0 or len(value) <= limit:
        return value
    return value[:limit] + "…"


def _format_rate(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return f"{round(float(value), 2)}%"
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(raw: Any) -> Optional[datetime]:
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ===== 集合读取（全部按 user_id + course_id 严格过滤）=====


def _knowledge_lines(
    container: ServiceContainer,
    user: UserRow,
    course_id: str,
    *,
    max_points: int = 20,
    max_tags: int = 12,
    warnings: Optional[List[str]] = None,
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
    except Exception as exc:  # noqa: BLE001 - 上下文增强失败不得影响主流程
        # 不能把"读不到"伪装成"没有知识点"
        if warnings is not None:
            warnings.append(f"知识点上下文读取失败，已省略({type(exc).__name__})")
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


def _chapter_items(
    container: ServiceContainer,
    user: UserRow,
    course_id: str,
    warnings: Optional[List[str]] = None,
) -> List[Any]:
    try:
        return container.course_content_repository.list_items(
            user_id=user.id, course_id=course_id, kind="chapter", page_size=100
        )
    except Exception as exc:  # noqa: BLE001
        if warnings is not None:
            warnings.append(f"章节读取失败，已省略({type(exc).__name__})")
        return []


def _chapter_lines(items: Sequence[Any], *, limit: int, title_chars: int) -> List[str]:
    lines: List[str] = []
    for item in items[:limit]:
        title = _clip(getattr(item, "title", ""), title_chars)
        if not title:
            continue
        line = f"- {title}"
        if getattr(item, "status", "") == "completed":
            line += " (已完成)"
        lines.append(line)
    return lines


def _material_items(
    container: ServiceContainer,
    user: UserRow,
    course_id: str,
    warnings: Optional[List[str]] = None,
) -> List[Any]:
    try:
        items = container.course_content_repository.list_items(
            user_id=user.id, course_id=course_id, page_size=50
        )
    except Exception as exc:  # noqa: BLE001
        if warnings is not None:
            warnings.append(f"课程资料读取失败，已省略({type(exc).__name__})")
        return []
    return [item for item in items if (getattr(item, "kind", "") or "") != "chapter"]


def _material_lines(items: Sequence[Any], *, limit: int, title_chars: int, excerpt_chars: int) -> List[str]:
    lines: List[str] = []
    seen: set[str] = set()
    for item in items:
        title = _clip(getattr(item, "title", ""), title_chars)
        if not title or title in seen:
            continue
        seen.add(title)
        line = f"- {title} ({getattr(item, 'kind', '') or '资料'})"
        excerpt = _clip(getattr(item, "description", ""), excerpt_chars)
        if excerpt:
            line += f" — {excerpt}"
        lines.append(line)
        if len(lines) >= limit:
            break
    return lines


def _task_rows(
    container: ServiceContainer,
    user: UserRow,
    course_id: str,
    warnings: Optional[List[str]] = None,
) -> List[Any]:
    repository = getattr(container, "personal_task_repository", None)
    if repository is None:
        return []
    try:
        rows, _ = repository.list_tasks(user_id=user.id, page=1, page_size=200)
    except Exception as exc:  # noqa: BLE001
        if warnings is not None:
            warnings.append(f"作业/测验读取失败，已省略({type(exc).__name__})")
        return []
    return [row for row in rows if getattr(row, "course_id", None) == course_id]


def _assignment_lines(rows: Sequence[Any], *, limit: int, title_chars: int) -> List[str]:
    lines: List[str] = []
    for row in rows[:limit]:
        title = _clip(getattr(row, "title", ""), title_chars)
        if not title:
            continue
        status = getattr(row, "status", "") or "unknown"
        line = f"- {title} [状态: {status}]"
        deadline = _parse_datetime(getattr(row, "deadline", None))
        if deadline is not None:
            line += f" 截止: {deadline.date().isoformat()}"
        lines.append(line)
    return lines


def _exam_rows(
    container: ServiceContainer,
    user: UserRow,
    course_id: str,
    warnings: Optional[List[str]] = None,
) -> List[dict]:
    repository = getattr(container, "chaoxing_repository", None)
    if repository is None or not hasattr(repository, "list_exams"):
        return []
    try:
        return list(repository.list_exams(user_id=user.id, course_id=course_id) or [])
    except Exception as exc:  # noqa: BLE001
        if warnings is not None:
            warnings.append(f"考试读取失败，已省略({type(exc).__name__})")
        return []


def _exam_lines(rows: Sequence[dict], *, limit: int, title_chars: int) -> List[str]:
    lines: List[str] = []
    for row in rows[:limit]:
        title = _clip(row.get("title") or "学习通考试", title_chars)
        at = _parse_datetime(row.get("exam_at"))
        status = "已出分" if row.get("score") is not None else "未出分"
        line = f"- {title} [{status}]"
        if at is not None:
            line += f" 时间: {at.isoformat()}"
        else:
            line += " 时间: 未提供"
        lines.append(line)
    return lines


# ===== 信号 =====


def _build_signals(
    container: ServiceContainer,
    user: UserRow,
    course_id: str,
    *,
    chapters: Sequence[Any],
    materials: Sequence[Any],
    exams: Sequence[dict],
    limits: ContextLimits,
) -> AdaptiveSignals:
    weak_areas: List[str] = []
    for item in chapters:
        if (getattr(item, "status", "") or "") == "completed":
            continue
        title = _clip(getattr(item, "title", ""), limits.chapter_title_chars)
        if title and title not in weak_areas:
            weak_areas.append(title)
        if len(weak_areas) >= limits.weak_areas:
            break

    exam_days: Optional[int] = None
    exam_title: Optional[str] = None
    now = _now()
    upcoming = []
    for row in exams:
        at = _parse_datetime(row.get("exam_at"))
        if at is None or at < now:
            continue
        upcoming.append((at, row))
    if upcoming:
        upcoming.sort(key=lambda pair: pair[0])
        at, row = upcoming[0]
        exam_days = max(0, (at - now).days)
        exam_title = _clip(row.get("title") or "考试", limits.exam_title_chars)

    used_modes: FrozenSet[str] = frozenset()
    store = getattr(container, "magicclass_result_store", None)
    if store is not None:
        try:
            sessions = store.list_sessions(user_id=user.id, course_id=course_id)
            used_modes = frozenset(
                str(getattr(s, "mode", "") or "").strip()
                for s in sessions
                if getattr(s, "mode", None)
            )
        except Exception:  # noqa: BLE001
            used_modes = frozenset()

    return AdaptiveSignals(
        # 逐知识点掌握率目前在学习通数据里不存在，因此恒为空 —— 不编造。
        weak_points=(),
        weak_areas=tuple(weak_areas),
        upcoming_exam_days=exam_days,
        upcoming_exam_title=exam_title,
        has_chapters=bool(chapters),
        has_interactive_material=bool(materials),
        used_modes=used_modes,
    )


# ===== 主入口 =====


def build_learning_context(
    container: ServiceContainer,
    user: UserRow,
    course: CourseRow,
    *,
    limits: Optional[ContextLimits] = None,
    selected_material_ids: Sequence[str] = (),
) -> LearningContext:
    """构造经授权、脱敏、限长的学习上下文。

    `selected_material_ids` 只用于**筛选**服务端已授权的资料；无法匹配的 id 一律忽略，
    绝不因此去读取别的课程/别的用户的资料，也绝不接受客户端提交的正文。
    """
    limits = limits or ContextLimits()
    lines: List[str] = []
    sources: Dict[str, str] = {"course": "本地课程库"}
    updated_at: Dict[str, str] = {}
    warnings: List[str] = []

    lines.append(f"[课程] {_clip(course.name, 200)}")
    meta = []
    if course.code:
        meta.append(f"代码:{_clip(course.code, 40)}")
    if course.semester:
        meta.append(f"学期:{_clip(course.semester, 40)}")
    if course.provider:
        meta.append(f"来源:{_clip(course.provider, 40)}")
    if meta:
        lines.append("  " + " ".join(meta))
    if course.description:
        lines.append(f"[课程描述] {_clip(course.description, limits.description_chars)}")

    sync_at = last_chaoxing_sync_at(container, user.id)
    if sync_at:
        updated_at["chaoxing"] = sync_at
        lines.append(f"[数据来源与更新时间] 学习通数据最近成功同步: {sync_at}")

    chapters = _chapter_items(container, user, course.id, warnings)
    if chapters:
        sources["chapters"] = "学习通同步(章节)"
        lines.append(f"[章节](共 {len(chapters)} 条)")
        lines.extend(
            _chapter_lines(
                chapters, limit=limits.chapters, title_chars=limits.chapter_title_chars
            )
        )

    knowledge = _knowledge_lines(
        container,
        user,
        course.id,
        max_points=limits.knowledge_points,
        max_tags=limits.knowledge_tags,
        warnings=warnings,
    )
    if knowledge:
        sources["knowledge"] = "学习通知识图谱同步"
        lines.append("[知识点与掌握情况]")
        lines.extend(knowledge)

    materials = _material_items(container, user, course.id, warnings)
    material_lines = _material_lines(
        materials,
        limit=limits.materials,
        title_chars=limits.material_title_chars,
        excerpt_chars=limits.material_excerpt_chars,
    )
    if material_lines:
        sources["materials"] = "学习通课程资料同步"
        lines.append(f"[课程资料](共 {len(materials)} 条，仅标题与受控摘要)")
        lines.extend(material_lines)
    else:
        # 没有真实资料时不伪造
        lines.append("[课程资料] 本课程暂无已同步的可用资料正文。")

    tasks = _task_rows(container, user, course.id, warnings)
    assignment_lines = _assignment_lines(
        tasks, limit=limits.assignments, title_chars=limits.assignment_title_chars
    )
    if assignment_lines:
        sources["assignments"] = "学习通作业同步"
        lines.append("[作业/测验]")
        lines.extend(assignment_lines)

    exams = _exam_rows(container, user, course.id, warnings)
    exam_lines = _exam_lines(
        exams, limit=limits.exams, title_chars=limits.exam_title_chars
    )
    if exam_lines:
        sources["exams"] = "学习通考试同步"
        lines.append("[考试]")
        lines.extend(exam_lines)

    if warnings:
        lines.append("[上下文提示] 以下数据本次未能读取，生成结果可能不完整：" + "；".join(warnings))

    text = "\n".join(lines).strip()
    truncated = False
    if len(text) > limits.total_chars:
        text = text[: limits.total_chars] + "\n[已截断]"
        truncated = True

    selected = {str(mid) for mid in selected_material_ids if mid}
    # 先在**完整**授权资料集上按选择过滤，再按上限截断 —— 否则学生选中的第
    # `limits.materials + 1` 条资料会被上限悄悄丢掉，表现为"选了但没用上"。
    # 同时显式记录无法解析的 id：它们可能不存在、属于别的课程，或已被删除。
    candidates = (
        [item for item in materials if str(getattr(item, "id", "") or "") in selected]
        if selected
        else list(materials)
    )
    refs: List[MaterialRef] = []
    seen_ids: set[str] = set()
    for item in candidates:
        item_id = str(getattr(item, "id", "") or "")
        title = _clip(getattr(item, "title", ""), limits.material_title_chars)
        if not item_id or not title or item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        refs.append(MaterialRef(id=item_id, title=title, kind=getattr(item, "kind", "") or "资料"))
        if len(refs) >= limits.materials:
            break
    resolved_ids = tuple(ref.id for ref in refs)
    unresolved = tuple(sorted(selected - set(resolved_ids))) if selected else ()

    signals = _build_signals(
        container,
        user,
        course.id,
        chapters=chapters,
        materials=materials,
        exams=exams,
        limits=limits,
    )
    material_text = "\n".join(
        [
            _clip(course.name, 200),
            *(
                [f"章节: " + "、".join(_chapter_lines(chapters, limit=limits.chapters, title_chars=limits.chapter_title_chars))]
                if chapters
                else []
            ),
            *material_lines,
        ]
    ).strip()
    if len(material_text) > limits.total_chars:
        material_text = material_text[: limits.total_chars]

    return LearningContext(
        text=text,
        materials=tuple(refs),
        signals=signals,
        sources=sources,
        updated_at=updated_at,
        truncated=truncated,
        material_text=material_text,
        warnings=warnings,
        selected_material_ids=resolved_ids,
        unresolved_material_ids=unresolved,
    )


@dataclass(frozen=True)
class CourseFacts:
    """生成前要展示给学生的**结构化课程事实**。

    与 `LearningContext` 的区别是用途：那份是喂给模型的文本，这份是给学生看的
    摘要，用来在生成前说清"这门课现在到底有什么"。两者都只含教学事实，都不含
    任何凭据、他人数据或附件原文。

    `synced` 与 `warnings` 必须分开表达，因为它们指向**完全不同**的下一步：
    `synced=False` 且无 warning 表示"这门课还没同步资料"（要去做同步），
    有 warning 表示"这次没读到"（重试有用）。把它们合并成一句话会让第二种
    情况永远等不到重试。
    """

    course_id: str
    name: str
    code: str
    semester: str
    description: str
    knowledge_points: Tuple[str, ...] = ()
    materials: Tuple[MaterialRef, ...] = ()
    chapters: Tuple[str, ...] = ()
    sources: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    synced: bool = False
    updated_at: str = ""


def build_course_facts(
    container: ServiceContainer,
    user: UserRow,
    course: CourseRow,
    *,
    limits: Optional[ContextLimits] = None,
) -> CourseFacts:
    """汇总一门课已同步的知识点与可用资料（只读，不触发任何同步）。

    读取失败一律记进 `warnings` 而不是当作"没有"——这是本函数唯一容易写错的地方，
    也是它存在的原因：生成前的提示必须区分"没同步"与"没读到"。
    """
    limits = limits or ContextLimits()
    warnings: List[str] = []

    points: List[str] = []
    repository = getattr(container, "chaoxing_repository", None)
    if repository is not None:
        try:
            rows = repository.list_knowledge_points(user_id=user.id, course_id=course.id)
        except Exception as exc:  # noqa: BLE001 - 只读摘要失败不得影响主流程
            warnings.append(f"知识点读取失败，已省略({type(exc).__name__})")
            rows = []
        for row in rows:
            name = str(row.get("name") or "").strip()
            if name and name not in points:
                points.append(name)
            if len(points) >= limits.knowledge_points:
                break

    chapters: List[str] = []
    for item in _chapter_items(container, user, course.id, warnings)[: limits.chapters]:
        title = _clip(getattr(item, "title", ""), limits.chapter_title_chars)
        if title and title not in chapters:
            chapters.append(title)

    materials: List[MaterialRef] = []
    seen: set[str] = set()
    for item in _material_items(container, user, course.id, warnings):
        item_id = str(getattr(item, "id", "") or "")
        title = _clip(getattr(item, "title", ""), limits.material_title_chars)
        if not item_id or not title or item_id in seen:
            continue
        seen.add(item_id)
        materials.append(MaterialRef(id=item_id, title=title, kind=getattr(item, "kind", "") or "资料"))
        if len(materials) >= limits.materials:
            break

    sync_at = last_chaoxing_sync_at(container, user.id) or ""
    sources: Dict[str, str] = {"course": "本地课程库"}
    if chapters:
        sources["chapters"] = "学习通同步(章节)"
    if points:
        sources["knowledge"] = "学习通知识图谱同步"
    if materials:
        sources["materials"] = "学习通课程资料同步"

    return CourseFacts(
        course_id=str(course.id),
        name=_clip(course.name, 200),
        code=_clip(course.code, 40),
        semester=_clip(course.semester, 40),
        description=_clip(course.description, limits.description_chars),
        knowledge_points=tuple(points),
        materials=tuple(materials),
        chapters=tuple(chapters),
        sources=sources,
        warnings=warnings,
        # 只有真实拿到内容才算已同步；一个都没有时界面必须如实提示。
        synced=bool(points or materials or chapters),
        updated_at=sync_at,
    )


def build_course_context(
    container: ServiceContainer,
    user: UserRow,
    course: CourseRow,
    *,
    max_chars: int = _MAX_CONTEXT_CHARS,
) -> str:
    """构造经授权、脱敏的课程学习上下文文本(用于课堂生成)。"""
    return build_learning_context(
        container, user, course, limits=ContextLimits(total_chars=max_chars)
    ).text


def build_cpm_course_block(
    container: ServiceContainer,
    user: UserRow,
    course: CourseRow,
    *,
    max_chars: int = 2500,
) -> str:
    """构造 CPM 使用的课程上下文块(章节/知识点/作业/课堂存在状态)。"""
    lines: List[str] = []
    # CPM 的上下文块是"提示性"文本，没有结构化返回位；读取失败只记录不影响主流程。
    warnings: List[str] = []
    lines.append(f"[课程] {course.name} ({course.code or '无代码'}) 学期:{course.semester or '未知'}")
    if course.description:
        lines.append(f"[课程描述] {_clip(course.description, 300)}")

    chapters = _chapter_items(container, user, course.id, warnings)
    if chapters:
        lines.append("[章节]")
        lines.extend(_chapter_lines(chapters, limit=12, title_chars=120))

    knowledge = _knowledge_lines(
        container, user, course.id, max_points=12, max_tags=8, warnings=warnings
    )
    if knowledge:
        lines.append("[知识点与掌握情况]")
        lines.extend(knowledge)

    tasks = _task_rows(container, user, course.id, warnings)
    assignment_lines = _assignment_lines(tasks, limit=10, title_chars=120)
    if assignment_lines:
        lines.append("[作业/测验主题]")
        lines.extend(assignment_lines)

    exams = _exam_rows(container, user, course.id, warnings)
    exam_lines = _exam_lines(exams, limit=5, title_chars=120)
    if exam_lines:
        lines.append("[考试]")
        lines.extend(exam_lines)

    # 已生成互动课堂的存在状态与可用学习模式(用于引导学生打开课堂)
    store = getattr(container, "magicclass_result_store", None)
    if store is not None:
        sessions = store.list_sessions(user_id=user.id, course_id=course.id)
        # 用 classroom_id 判断"已生成"：公开地址可能因为未配置 MAGICCLASS_EMBED_ORIGIN 而为空，
        # 但课堂确实已经生成，不该因此对学生说"没有课堂"。
        finished = [s for s in sessions if s.status == "succeeded" and s.classroom_id]
        modes = sorted({s.mode for s in finished})
        if finished:
            lines.append(
                "[互动课堂](由 magic class 生成的辅助学习内容，非学校官方规定): "
                f"已存在 {len(finished)} 个课堂，可用模式: {', '.join(modes) or '未记录'}"
            )

    text = "\n".join(lines).strip()
    if len(text) > max_chars:
        text = text[:max_chars]
    return text


__all__ = [
    "ContextLimits",
    "LearningContext",
    "MaterialRef",
    "assert_course_access",
    "build_course_context",
    "build_learning_context",
    "build_cpm_course_block",
]
