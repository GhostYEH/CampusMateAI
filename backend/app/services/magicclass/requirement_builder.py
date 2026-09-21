"""magicclass 课堂生成需求构造器。

职责：
- 把 **9 个学生生成意图**（adaptive/explain/quiz/simulation/visualization/
  mindmap/coding/pbl/review）转成经过把关的 requirement 文本；旧值
  explore/practice/project 归一化到新意图，不破坏已有客户端。
- 依据 health capabilities 开关 webSearch/imageGeneration/videoGeneration/tts，
  客户端无法直接传递任何 magicclass Provider Key。
- **不要求 magicclass 输出不存在的 scene type**：其真实场景类型只有
  slide / quiz / interactive / pbl；3D、思维导图、编程、模拟都是 interactive
  内部的 widget 形态，只能作为「意图」表达，最终组合由生成器决定。
- adaptive 是确定性、可解释、可测试的（见 `choose_adaptive_mode`）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Optional, Sequence, Tuple

# ===== 意图集合 =====

# 9 个规范学生意图
CANONICAL_MODES: Tuple[str, ...] = (
    "adaptive",
    "explain",
    "quiz",
    "simulation",
    "visualization",
    "mindmap",
    "coding",
    "pbl",
    "review",
)

# 旧值 → 新意图（保留兼容，归一化后使用）
LEGACY_MODE_ALIASES: Dict[str, str] = {
    "explore": "simulation",
    "practice": "quiz",
    "project": "pbl",
}

_MODE_LABELS: Dict[str, str] = {
    "adaptive": "自适应学习课堂",
    "explain": "概念讲解与逐步推导",
    "quiz": "练习测验与即时反馈",
    "simulation": "交互式模拟实验",
    "visualization": "3D 与可视化理解",
    "mindmap": "知识结构与思维导图",
    "coding": "在线编程实验",
    "pbl": "项目式学习(PBL)",
    "review": "考前复习与薄弱点巩固",
}

# 每个意图一段「学生学习任务」描述。措辞是学生视角，且只描述希望达到的学习效果，
# 不承诺某种 scene type。
_MODE_TASKS: Dict[str, str] = {
    "adaptive": (
        "请根据这名学生当前的真实掌握情况与可用资料，自主决定最合适的一节课："
        "可以先讲清概念，也可以直接安排自测或动手实验。"
    ),
    "explain": (
        "请把这节课做成一次循序渐进的概念讲解：从学生已有的知识出发，"
        "把定义、直觉、推导步骤讲清楚，并在关键处停下来确认学生是否跟上。"
    ),
    "quiz": (
        "请把这节课做成一次自测：围绕本课程的核心概念出题，覆盖不同难度，"
        "每道题都给出解析，帮助学生发现自己到底卡在哪一步。"
    ),
    "simulation": (
        "请把这节课做成一次可以动手操作的实验：让学生调整参数、观察结果变化，"
        "从「试一试」里理解规律，而不是只读结论。"
    ),
    "visualization": (
        "请把这节课做成一次空间或结构上的可视化理解：让学生能旋转、缩放或切换视角，"
        "把抽象的式子或结构「看见」。"
    ),
    "mindmap": (
        "请把这节课做成一次知识结构梳理：把本章、本课的概念、关系与层级组织成一张"
        "可以展开的知识图，帮助学生建立整体框架。"
    ),
    "coding": (
        "请把这节课做成一次编程练习：给出可运行、可修改的代码，让学生改一改、跑一跑，"
        "用代码验证课上的结论。"
    ),
    "pbl": (
        "请把这节课做成一个项目式学习任务：给出真实情境下的项目目标、学生要扮演的角色、"
        "分阶段里程碑、要交付的成果以及评价标准，让学生在做项目的过程中学会知识。"
    ),
    "review": (
        "请把这节课做成一次考前复习：优先覆盖学生的薄弱知识点与高频考点，"
        "用自测与讲解交替的方式查漏补缺，并给出复习重点的顺序建议。"
    ),
}

# 自适应轮换池（顺序即优先级）
_ADAPTIVE_ROTATION: Tuple[str, ...] = ("quiz", "visualization", "mindmap", "coding", "explain")
# 距考试多少天内视为「临近考试」
_EXAM_WINDOW_DAYS = 14

_DIFFICULTY_LABELS: Dict[str, str] = {
    "beginner": "入门",
    "standard": "标准",
    "advanced": "进阶",
}

_DURATION_MIN = 5
_DURATION_MAX = 180


# ===== 学生输入 =====


@dataclass(frozen=True)
class StudentBrief:
    """学生本次生成请求里的补充信息（全部可选）。

    `selected_material_titles` 是**服务端**按 `selected_material_ids` 解析出来的
    已授权资料标题；客户端提交的标题/正文一律不被信任。
    """

    learning_objective: Optional[str] = None
    current_difficulty: Optional[str] = None
    desired_duration_minutes: Optional[int] = None
    difficulty_level: Optional[str] = None
    wants_more_practice: bool = False
    selected_material_titles: Tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return not any(
            (
                self.learning_objective,
                self.current_difficulty,
                self.desired_duration_minutes,
                self.difficulty_level,
                self.wants_more_practice,
                self.selected_material_titles,
            )
        )


#: 快照里允许出现的键（白名单）。**任何**未列入的键在反序列化时被丢弃 ——
#: 这是防止旧数据/脏数据把凭据或正文带进快照的第二道闸门。
_SNAPSHOT_FIELDS: Tuple[str, ...] = (
    "requested_mode",
    "mode",
    "learning_objective",
    "current_difficulty",
    "desired_duration_minutes",
    "difficulty_level",
    "wants_more_practice",
    "selected_material_ids",
)

#: 单个字段的长度上限，避免把超长文本写进磁盘/审计
_SNAPSHOT_TEXT_LIMIT = 500


@dataclass(frozen=True)
class GenerationRequestSnapshot:
    """一次生成的**学生输入**快照（不可变、可落盘、可重放）。

    为什么需要它：retry 的语义是"用**同一份**学生诉求再生成一次"。修复前
    retry 只把 `mode` 传下去，学习目标/难度/时长/练习偏好/资料选择全部丢失，
    学生说"只复习第三章矩阵"却被重试成通用课堂。

    隐私约束（快照会落盘，必须严格受限）：
    - 只保存**业务引用**：资料只存 id，绝不存标题或正文；
    - 绝不包含 ACCESS_CODE / Cookie / Token / 内部 URL；
    - 反序列化按 `_SNAPSHOT_FIELDS` 白名单过滤，未知键一律丢弃。
    """

    requested_mode: str = "adaptive"
    mode: str = "adaptive"
    learning_objective: Optional[str] = None
    current_difficulty: Optional[str] = None
    desired_duration_minutes: Optional[int] = None
    difficulty_level: Optional[str] = None
    wants_more_practice: bool = False
    selected_material_ids: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requested_mode": self.requested_mode,
            "mode": self.mode,
            "learning_objective": self.learning_objective,
            "current_difficulty": self.current_difficulty,
            "desired_duration_minutes": self.desired_duration_minutes,
            "difficulty_level": self.difficulty_level,
            "wants_more_practice": self.wants_more_practice,
            "selected_material_ids": list(self.selected_material_ids),
        }

    @classmethod
    def from_dict(cls, data: Any) -> Optional["GenerationRequestSnapshot"]:
        """从落盘数据还原。数据不合法时返回 None（调用方据此走兼容降级）。"""
        if not isinstance(data, dict):
            return None
        clean = {key: data[key] for key in _SNAPSHOT_FIELDS if key in data}

        def _text(value: Any) -> Optional[str]:
            if value is None:
                return None
            text = str(value).strip()
            return text[:_SNAPSHOT_TEXT_LIMIT] or None

        raw_ids = clean.get("selected_material_ids") or []
        if isinstance(raw_ids, str):
            raw_ids = [raw_ids]
        material_ids: list = []
        for item in raw_ids if isinstance(raw_ids, (list, tuple)) else []:
            text = str(item or "").strip()
            if text and text not in material_ids:
                material_ids.append(text)

        raw_duration = clean.get("desired_duration_minutes")
        duration: Optional[int]
        try:
            duration = int(raw_duration) if raw_duration is not None else None
        except (TypeError, ValueError):
            duration = None

        try:
            requested = normalize_mode(str(clean.get("requested_mode") or "adaptive"))
            resolved = normalize_mode(str(clean.get("mode") or requested))
        except ValueError:
            return None

        return cls(
            requested_mode=requested,
            mode=resolved,
            learning_objective=_text(clean.get("learning_objective")),
            current_difficulty=_text(clean.get("current_difficulty")),
            desired_duration_minutes=duration,
            difficulty_level=_text(clean.get("difficulty_level")),
            wants_more_practice=bool(clean.get("wants_more_practice")),
            selected_material_ids=tuple(material_ids[:20]),
        )

    def to_brief(self, *, selected_material_titles: Sequence[str] = ()) -> StudentBrief:
        """转成 requirement 构造器用的 brief。

        资料**标题**必须由调用方从服务端重新解析的上下文里传入 ——
        快照本身不存标题，也就无法被客户端伪造。
        """
        return StudentBrief(
            learning_objective=self.learning_objective,
            current_difficulty=self.current_difficulty,
            desired_duration_minutes=self.desired_duration_minutes,
            difficulty_level=self.difficulty_level,
            wants_more_practice=self.wants_more_practice,
            selected_material_titles=tuple(selected_material_titles),
        )


@dataclass(frozen=True)
class AdaptiveSignals:
    """adaptive 决策所依据的**真实**信号（由 course_context 从库里读出）。

    两类"薄弱"信号必须区分，不能互相冒充：

    - `weak_points`：**实测**的逐知识点掌握率 `(知识点名称, 掌握率)`。
      目前学习通只提供**课程级**平均掌握率（`chaoxing_knowledge_graphs`），
      `chaoxing_knowledge_points` 表里没有逐点掌握率，所以现实中它通常为空。
    - `weak_areas`：**可观察**的未完成章节名。当逐点掌握率缺失时用它作为
      "还没掌握"的信号，措辞上只说"章节尚未完成"，不谎称有掌握率数字。
    """

    # (知识点名称, 本人掌握率) —— 仅在有真实逐点数据时填充
    weak_points: Sequence[Tuple[str, float]] = field(default_factory=tuple)
    # 未完成章节名称 —— 可观察事实
    weak_areas: Sequence[str] = field(default_factory=tuple)
    upcoming_exam_days: Optional[int] = None
    upcoming_exam_title: Optional[str] = None
    has_chapters: bool = False
    has_interactive_material: bool = False
    used_modes: FrozenSet[str] = field(default_factory=frozenset)
    external_3d_available: bool = True


# ===== 模式归一化 =====


def normalize_mode(mode: Any) -> str:
    """把任意输入归一化到 9 个规范意图之一；无法识别时抛 ValueError。"""
    normalized = str(mode or "adaptive").strip().lower()
    if not normalized:
        return "adaptive"
    if normalized in CANONICAL_MODES:
        return normalized
    if normalized in LEGACY_MODE_ALIASES:
        return LEGACY_MODE_ALIASES[normalized]
    raise ValueError(f"不支持的课堂模式: {mode}")


def validate_mode(mode: str) -> str:
    """历史入口，语义与 `normalize_mode` 一致（旧名仍被接受）。"""
    return normalize_mode(mode)


def mode_label(mode: str) -> str:
    return _MODE_LABELS[normalize_mode(mode)]


# ===== 自适应决策 =====


def choose_adaptive_mode(signals: AdaptiveSignals) -> Tuple[str, str]:
    """确定性、可解释的 adaptive 选择。返回 `(mode, reason)`。

    规则（按优先级，输入全部来自真实上下文）：
    1. 临近考试（≤14 天）且有薄弱信号 → `review`
    2. 有薄弱信号且有可交互资料 → `simulation`，否则 → `quiz`
    3. 有章节且从未生成过课堂 → `explain`
    4. 其余在**未使用过**的意图里按固定顺序轮换（3D 不可用时跳过 `visualization`）

    `reason` 必须能解释「为什么推荐这个」，供 UI 直接展示；措辞必须与信号的
    真实来源一致（有实测掌握率才报数字，否则只说章节未完成）。
    """
    measured = [str(name).strip() for name, _ in signals.weak_points if str(name or "").strip()]
    areas = [str(name).strip() for name in signals.weak_areas if str(name or "").strip()]
    exam_soon = (
        signals.upcoming_exam_days is not None
        and 0 <= signals.upcoming_exam_days <= _EXAM_WINDOW_DAYS
    )
    exam = signals.upcoming_exam_title or "近期考试"

    if measured:
        gap_text = f"你在「{measured[0]}」等 {len(measured)} 个知识点上掌握不足"
    elif areas:
        gap_text = f"你还有「{areas[0]}」等 {len(areas)} 个章节没有完成"
    else:
        gap_text = ""

    if gap_text and exam_soon:
        return (
            "review",
            f"{gap_text}，且 {signals.upcoming_exam_days} 天后有{exam}，先安排一次考前复习。",
        )
    if gap_text and signals.has_interactive_material:
        return (
            "simulation",
            f"{gap_text}，本课程有可用于动手实验的资料，用交互实验来突破更有效。",
        )
    if gap_text:
        return (
            "quiz",
            f"{gap_text}，先做一组针对性自测，定位到底卡在哪一步。",
        )
    if signals.has_chapters and not signals.used_modes:
        return (
            "explain",
            "本课程已有章节内容，但你还没有生成过互动课堂，先做一次概念讲解打基础。",
        )

    pool = [
        mode
        for mode in _ADAPTIVE_ROTATION
        if mode != "visualization" or signals.external_3d_available
    ]
    unused = [mode for mode in pool if mode not in signals.used_modes]
    if unused:
        chosen = unused[0]
        if signals.used_modes:
            used_text = "、".join(sorted(signals.used_modes))
            return chosen, f"你已用过 {used_text}，换一种形态轮换：{_MODE_LABELS[chosen]}。"
        return chosen, f"还没有明显的薄弱点或考试压力，先从{_MODE_LABELS[chosen]}开始。"
    return "quiz", "常见形态基本都试过了，回到自测来巩固与查漏。"


# ===== requirement 构造 =====


def _brief_lines(brief: Optional[StudentBrief]) -> list:
    if brief is None or brief.is_empty():
        return []
    lines = ["学生的学习情况(由学生本人填写)："]
    if brief.learning_objective:
        lines.append(f"- 学习目标: {brief.learning_objective.strip()}")
    if brief.current_difficulty:
        lines.append(f"- 当前困惑: {brief.current_difficulty.strip()}")
    if brief.desired_duration_minutes:
        minutes = max(_DURATION_MIN, min(_DURATION_MAX, int(brief.desired_duration_minutes)))
        lines.append(f"- 期望时长: 约 {minutes} 分钟")
    label = _DIFFICULTY_LABELS.get(str(brief.difficulty_level or "").strip().lower())
    if label:
        lines.append(f"- 难度: {label}")
    if brief.wants_more_practice:
        lines.append("- 希望安排更多练习与自测")
    if brief.selected_material_titles:
        titles = "、".join(brief.selected_material_titles)
        lines.append(f"- 学生指定使用的课程资料: {titles}")
    return lines


def _capability_lines(
    *,
    enable_web_search: bool,
    enable_image: bool,
    enable_video: bool,
    enable_tts: bool,
    external_3d_available: bool,
) -> list:
    lines = []
    if not external_3d_available:
        lines.append(
            "注意：当前部署环境无法访问外部 3D 资源，3D 可视化形式不可用；"
            "请不要生成依赖 3D 的内容，改用其它交互形式。"
        )
    if not enable_web_search and not enable_image and not enable_video and not enable_tts:
        lines.append(
            "注意：本次调用不启用 webSearch、图片生成、视频生成与 TTS；"
            "不要依赖这些能力，也不要假装调用它们。"
        )
    return lines


def build_requirement(
    *,
    course_context: str,
    mode: str,
    learning_objective: Optional[str] = None,
    brief: Optional[StudentBrief] = None,
    enable_web_search: bool = False,
    enable_image: bool = False,
    enable_video: bool = False,
    enable_tts: bool = False,
    external_3d_available: bool = True,
) -> str:
    """构造送入 magic class 的 requirement 文本。

    course_context 已经是经过授权、脱敏且截断的课程上下文，见 course_context.py。
    """
    resolved = normalize_mode(mode)
    lines: list = []
    lines.append("这是一项面向学生本人的学习任务。你正在为一名学生生成一节可交互的学习课堂。")
    lines.append("课程上下文(仅作背景，不得把生成内容当作学校官方规定或考试事实)：")
    lines.append(course_context)
    lines.append("")
    lines.append(f"这节课的形态意图: {_MODE_LABELS[resolved]}。")
    lines.append(_MODE_TASKS[resolved])

    objective = None
    if brief is not None and brief.learning_objective:
        objective = brief.learning_objective
    elif learning_objective:
        objective = learning_objective
    if objective:
        lines.append("学生学习目标: " + objective.strip())

    lines.extend(_brief_lines(brief))
    lines.append("")
    lines.extend(
        _capability_lines(
            enable_web_search=enable_web_search,
            enable_image=enable_image,
            enable_video=enable_video,
            enable_tts=enable_tts,
            external_3d_available=external_3d_available,
        )
    )
    lines.append(
        "请针对这门课的真实内容生成，不要套用固定学科模板；"
        "根据课程内容自主决定讲解、测验、交互实验、项目式学习等形式的组合。"
    )
    lines.append(
        "最终内容组合由互动课堂生成器根据课程内容自行决定，不保证包含某一种特定形式。"
    )
    return "\n".join(line for line in lines if line != "")


def build_input_payload(
    *,
    requirement: str,
    capabilities: Dict[str, bool],
    pdf_text: str = "",
) -> Dict[str, Any]:
    """根据 health capabilities 过滤可选能力，构造 GenerateClassroomInput。

    只发送源码确实支持的字段；enable* 全部由能力开关决定，不由客户端指定，
    从根上杜绝把 magicclass 服务端凭据/Key 传递到服务。
    """
    return {
        "requirement": requirement,
        "pdfContent": {"text": pdf_text, "images": []},
        "enableWebSearch": _require_true(capabilities, "webSearch"),
        "enableImageGeneration": _require_true(capabilities, "imageGeneration"),
        "enableVideoGeneration": _require_true(capabilities, "videoGeneration"),
        "enableTTS": _require_true(capabilities, "tts"),
        "agentMode": "generate",
    }


def _require_true(capabilities: Dict[str, bool], key: str) -> bool:
    return bool(capabilities.get(key, False))


__all__ = [
    "CANONICAL_MODES",
    "LEGACY_MODE_ALIASES",
    "AdaptiveSignals",
    "GenerationRequestSnapshot",
    "StudentBrief",
    "normalize_mode",
    "validate_mode",
    "mode_label",
    "choose_adaptive_mode",
    "build_requirement",
    "build_input_payload",
]
