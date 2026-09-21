"""读取并统计 magic class 课堂的**真实**组成。

为什么需要它：magic class 的生成接口只接受一个 `requirement` 字符串，**没有任何
"生成思维导图"之类的类型参数**。因此请求里的 mode 只是"意图"，最终产出什么完全
由生成器决定。唯一能如实告诉学生"这节课包含什么"的办法，是生成完成后回读
`GET /api/classroom?id={classroomId}`，按真实数据统计。

安全与健壮性：
- 只读端点，不修改任何数据；
- 只统计类型与计数，不落库、不打日志完整的 HTML / Prompt / 隐私内容；
- 出现本适配层还不认识的 `scene.type` / `widgetType` 时**安全降级**（计数并置位），
  不抛错、不臆造名称。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# 参考实现里真实存在的场景类型（packages/@magicclass/dsl/src/stage.ts）
KNOWN_SCENE_TYPES = ("slide", "quiz", "interactive", "pbl")

# interactive 内部真实存在的 widget 形态（packages/@magicclass/dsl/src/interactive.ts）
KNOWN_WIDGET_TYPES = (
    "simulation",
    "diagram",
    "code",
    "game",
    "visualization3d",
    "procedural-skill",
)

# 依赖外部 CDN 的 widget 形态
EXTERNAL_CDN_WIDGET_TYPES = ("visualization3d",)

# 白板动作前缀（参考实现的 Action 联合）
_WHITEBOARD_ACTION_PREFIX = "wb_"


@dataclass
class ClassroomComposition:
    """真实课堂组成的稳定 DTO（与 `schemas/magicclass.py` 一一对应）。"""

    classroom_id: str
    scene_total: int = 0
    scenes: List[Dict[str, Any]] = field(default_factory=list)
    widget_types: List[Dict[str, Any]] = field(default_factory=list)
    has_whiteboard: bool = False
    has_tts: bool = False
    has_multi_agent: bool = False
    has_unknown_scene_type: bool = False
    has_unknown_widget_type: bool = False
    requires_external_3d: bool = False
    external_3d_available: bool = True
    degraded: bool = False
    read_at: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classroom_id": self.classroom_id,
            "scene_total": self.scene_total,
            "scenes": self.scenes,
            "widget_types": self.widget_types,
            "has_whiteboard": self.has_whiteboard,
            "has_tts": self.has_tts,
            "has_multi_agent": self.has_multi_agent,
            "has_unknown_scene_type": self.has_unknown_scene_type,
            "has_unknown_widget_type": self.has_unknown_widget_type,
            "requires_external_3d": self.requires_external_3d,
            "external_3d_available": self.external_3d_available,
            "degraded": self.degraded,
            "read_at": self.read_at,
            "error": self.error,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _actions_of(scene: Dict[str, Any]) -> List[Dict[str, Any]]:
    actions = scene.get("actions")
    if not isinstance(actions, list):
        return []
    return [a for a in actions if isinstance(a, dict)]


def _scene_content(scene: Dict[str, Any]) -> Dict[str, Any]:
    content = scene.get("content")
    return content if isinstance(content, dict) else {}


def _has_multi_agent(scene: Dict[str, Any]) -> bool:
    config = scene.get("multiAgent")
    if isinstance(config, dict):
        # enabled 明确为 false 才算没有；缺字段时按存在处理（保守：宁可提示有）
        return config.get("enabled") is not False
    return False


def parse_classroom_composition(
    payload: Dict[str, Any],
    *,
    classroom_id: str,
    external_3d_available: bool = True,
) -> ClassroomComposition:
    """从 `GET /api/classroom?id=` 的响应体解析真实组成。

    对未知结构安全降级：缺字段按 0/False 处理，未知类型只计数不抛错。
    """
    classroom = payload.get("classroom") if isinstance(payload, dict) else None
    if not isinstance(classroom, dict):
        return ClassroomComposition(
            classroom_id=classroom_id,
            external_3d_available=external_3d_available,
            read_at=_now_iso(),
            error="课堂响应结构异常",
        )

    scenes = classroom.get("scenes")
    scene_list = [s for s in scenes if isinstance(s, dict)] if isinstance(scenes, list) else []
    stage = classroom.get("stage") if isinstance(classroom.get("stage"), dict) else {}

    scene_counts: Dict[str, int] = {}
    widget_counts: Dict[str, int] = {}
    unknown_scene = False
    unknown_widget = False
    has_whiteboard = False
    has_tts = False
    has_multi_agent = False

    if isinstance(stage.get("whiteboard"), list) and stage["whiteboard"]:
        has_whiteboard = True
    if stage.get("agentIds") or stage.get("generatedAgentConfigs"):
        has_multi_agent = True

    for scene in scene_list:
        scene_type = str(scene.get("type") or "").strip()
        if scene_type in KNOWN_SCENE_TYPES:
            scene_counts[scene_type] = scene_counts.get(scene_type, 0) + 1
        else:
            unknown_scene = True
            key = scene_type or "unknown"
            scene_counts[key] = scene_counts.get(key, 0) + 1

        if scene.get("whiteboards"):
            has_whiteboard = True
        if _has_multi_agent(scene):
            has_multi_agent = True

        content = _scene_content(scene)
        if scene_type == "interactive":
            widget_type = str(content.get("widgetType") or "").strip()
            if widget_type:
                if widget_type in KNOWN_WIDGET_TYPES:
                    widget_counts[widget_type] = widget_counts.get(widget_type, 0) + 1
                else:
                    unknown_widget = True
                    widget_counts[widget_type] = widget_counts.get(widget_type, 0) + 1

        for action in _actions_of(scene):
            action_type = str(action.get("type") or "")
            if action_type == "speech":
                has_tts = True
            elif action_type.startswith(_WHITEBOARD_ACTION_PREFIX):
                has_whiteboard = True

    requires_3d = any(
        widget in widget_counts for widget in EXTERNAL_CDN_WIDGET_TYPES
    )

    return ClassroomComposition(
        classroom_id=classroom_id,
        scene_total=len(scene_list),
        scenes=[
            {"type": key, "count": value} for key, value in sorted(scene_counts.items())
        ],
        widget_types=[
            {"widget_type": key, "count": value}
            for key, value in sorted(widget_counts.items())
        ],
        has_whiteboard=has_whiteboard,
        has_tts=has_tts,
        has_multi_agent=has_multi_agent,
        has_unknown_scene_type=unknown_scene,
        has_unknown_widget_type=unknown_widget,
        requires_external_3d=requires_3d,
        external_3d_available=external_3d_available,
        # 3D 依赖外网但环境不可达 → 降级（不是整节课失败）
        degraded=requires_3d and not external_3d_available,
        read_at=_now_iso(),
        error=None,
    )


__all__ = [
    "KNOWN_SCENE_TYPES",
    "KNOWN_WIDGET_TYPES",
    "EXTERNAL_CDN_WIDGET_TYPES",
    "ClassroomComposition",
    "parse_classroom_composition",
]
