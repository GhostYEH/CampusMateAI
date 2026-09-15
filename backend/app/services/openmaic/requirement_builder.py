"""OpenMAIC 课堂生成需求构造器。

职责：
- 把受控的学习模式(adaptive/explain/explore/practice/project)转成经过把关的
  requirement 文本，不伪造 OpenMAIC API 不支持的字段。
- 依据 health capabilities 开关 webSearch/imageGeneration/videoGeneration/tts，
  客户端无法直接传递任何 OpenMAIC Provider Key。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

_MODE_LABELS: Dict[str, str] = {
    "adaptive": "自适应学习课堂",
    "explain": "概念讲解与逐步推导",
    "explore": "可视化、3D、模拟实验、思维导图与小游戏探索",
    "practice": "练习、测验与反馈巩固",
    "project": "项目式学习(PBL)、角色任务与里程碑交付",
}

_MODE_PREFERENCES: Dict[str, str] = {
    "adaptive": (
        "请综合运用讲解答疑、幻灯片、单选/多选/简答测验、3D 可视化、交互式模拟实验、"
        "知识小游戏、思维导图、在线编程练习、项目式学习 PBL、多智能体/圆桌讨论、白板推导"
        "等合适的能力，为学生构建一门前置的自适应学习课堂。"
    ),
    "explain": (
        "请以概念讲解、逐步推导和白色画板推导为核心，辅以幻灯片与清晰的分步讲解，"
        "必要时穿插少量测验以确认理解。"
    ),
    "explore": (
        "请优先生成可视化内容：3D 可视化、交互式模拟实验、思维导图或知识小游戏，"
        "让学生通过探索理解概念；仍可补充必要的讲解与小结。"
    ),
    "practice": (
        "请以练习、测验和即时反馈为核心，覆盖单选、多选与简答，并给出参考答案与解析，"
        "帮助学生巩固并发现薄弱点。"
    ),
    "project": (
        "请设计项目式学习(PBL)：给出项目目标、角色任务、里程碑、交付物与评价标准，"
        "并可用多智能体或圆桌讨论辅助学生推进。"
    ),
}


def validate_mode(mode: str) -> str:
    normalized = (mode or "adaptive").strip().lower()
    if normalized not in _MODE_LABELS:
        raise ValueError(f"不支持的课堂模式: {mode}")
    return normalized


def mode_label(mode: str) -> str:
    return _MODE_LABELS[mode]


def _require_true(capabilities: Dict[str, bool], key: str) -> bool:
    return bool(capabilities.get(key, False))


def build_requirement(
    *,
    course_context: str,
    mode: str,
    learning_objective: Optional[str] = None,
    enable_web_search: bool = False,
    enable_image: bool = False,
    enable_video: bool = False,
    enable_tts: bool = False,
) -> str:
    """构造送入 OpenMAIC 的 requirement 文本。

    course_context 已经是经过授权、脱敏且截断的课程上下文，见 course_context.py。
    """
    lines: list[str] = []
    lines.append("你正在为一门具体课程为学生生成一节互动学习课堂。")
    lines.append("课程上下文(仅作背景，不得把生成内容当作学校官方规定或考试事实)：")
    lines.append(course_context)
    lines.append("")
    lines.append(f"这节课的形态偏好: {_MODE_LABELS[mode]}。")
    lines.append(_MODE_PREFERENCES[mode])
    if learning_objective:
        lines.append("学生学习目标: " + learning_objective.strip())
    lines.append(
        "请针对这门课的真实内容生成，不要套用固定学科模板；"
        "根据课程内容自主决定幻灯片、测验、实验、思维导图、PBL 等场景的组合。"
    )
    lines.append(
        "请保留完整可交互能力：AI 教师讲解、幻灯片、单选/多选/简答测验、"
        "3D 可视化、交互式模拟实验、知识小游戏、思维导图、在线编程练习、"
        "PBL、多智能体/圆桌讨论、白板推导，以及语音讲解与图片/视频(当能力可用时)。"
    )
    if not enable_web_search and not enable_image and not enable_video and not enable_tts:
        lines.append(
            "注意：本次调用不启用 webSearch、图片生成、视频生成与 TTS；"
            "不要依赖这些能力，也不要假装调用它们。"
        )
    return "\n".join(lines)


def build_input_payload(
    *,
    requirement: str,
    capabilities: Dict[str, bool],
    pdf_text: str = "",
) -> Dict[str, Any]:
    """根据 health capabilities 过滤可选能力，构造 GenerateClassroomInput。

    只发送源码确实支持的字段；enable* 全部由能力开关决定，不由客户端指定，
    从根上杜绝把 OpenMAIC 服务端凭据/Key 传递到服务。
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


__all__ = [
    "validate_mode",
    "mode_label",
    "build_requirement",
    "build_input_payload",
]