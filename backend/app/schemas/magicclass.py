"""互动课堂(magic class 适配层)API schema。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from ..services.magicclass.requirement_builder import (
    CANONICAL_MODES,
    LEGACY_MODE_ALIASES,
    normalize_mode,
)

# 9 个学生生成意图；旧值 explore/practice/project 仍被接受并归一化
VALID_MODES = set(CANONICAL_MODES)
VALID_DIFFICULTY_LEVELS = {"beginner", "standard", "advanced"}

# 意图的展示标签，供客户端在"生成前"向学生说明这次会做什么
MODE_INTENT_LABELS: Dict[str, str] = {
    "adaptive": "自动推荐",
    "explain": "概念讲解",
    "quiz": "练习测验",
    "simulation": "实验模拟",
    "visualization": "3D/可视化",
    "mindmap": "思维导图",
    "coding": "编程实验",
    "pbl": "项目式学习",
    "review": "考前复习",
}


class MagicClassGenerateRequest(BaseModel):
    """学生发起一次课堂生成。

    所有补充信息都是可选的；`selected_material_ids` 只用于筛选服务端已授权的资料，
    客户端提交的任何资料标题或正文都不被信任。
    """

    mode: str = Field(
        "adaptive",
        description="生成意图：adaptive/explain/quiz/simulation/visualization/mindmap/coding/pbl/review",
    )
    learning_objective: Optional[str] = Field(
        None, max_length=500, description="学生明确选择的学习目标(可选)"
    )
    current_difficulty: Optional[str] = Field(
        None, max_length=500, description="学生当前卡在哪里(可选)"
    )
    desired_duration_minutes: Optional[int] = Field(
        None, ge=5, le=180, description="期望学习时长(分钟，可选)"
    )
    difficulty_level: Optional[str] = Field(
        None, description="难度：beginner/standard/advanced(可选)"
    )
    wants_more_practice: bool = Field(False, description="是否需要更多练习")
    selected_material_ids: List[str] = Field(
        default_factory=list, max_length=20, description="希望使用的课程资料 ID 列表"
    )

    @field_validator("mode")
    @classmethod
    def _mode_valid(cls, v: str) -> str:
        return normalize_mode(v)

    @field_validator("difficulty_level")
    @classmethod
    def _difficulty_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = str(v).strip().lower()
        if not normalized:
            return None
        if normalized not in VALID_DIFFICULTY_LEVELS:
            raise ValueError(f"不支持的难度: {v}")
        return normalized

    @field_validator("selected_material_ids")
    @classmethod
    def _materials_valid(cls, v: List[str]) -> List[str]:
        out: List[str] = []
        for item in v or []:
            text = str(item or "").strip()
            if text and text not in out:
                out.append(text)
        return out[:20]


class MagicClassMaterialOut(BaseModel):
    """学生可选用的课程资料（只暴露 id/标题/类型）。"""

    id: str
    title: str
    kind: str = "资料"


class MagicClassPlanOut(BaseModel):
    """生成**之前**给学生看的信息：会用什么课程、哪些资料、为什么推荐这个形态。"""

    course_id: str
    course_name: str
    mode: str
    mode_label: str
    requested_mode: str
    adaptive_reason: Optional[str] = None
    # 形态只是"意图"，最终内容组合由 magic class 生成器决定
    intent_note: str = "内容形态只是生成意图，最终包含哪些形式由生成器根据课程内容决定。"
    materials: List[MagicClassMaterialOut] = Field(default_factory=list)
    selected_material_ids: List[str] = Field(default_factory=list)
    context_sources: Dict[str, str] = Field(default_factory=dict)
    context_updated_at: Dict[str, str] = Field(default_factory=dict)
    context_truncated: bool = False
    # 读取失败的集合（必须区分"真的没有"与"读不到"）
    context_warnings: List[str] = Field(default_factory=list)
    capabilities: Dict[str, bool] = Field(default_factory=dict)
    external_3d_available: bool = True
    can_generate: bool = False
    reason: Optional[str] = None


class MagicClassStatusOut(BaseModel):
    """互动课堂状态契约。

    - configured: 后端是否配置了 magicclass（MAGICCLASS_ENABLED + BASE_URL）。
    - available:  目标服务**真实可达**且契约指纹通过（不因配置非空就为真）。
    - enabled:    == configured and available，客户端据此决定是否展示生成入口。
    - unavailable: 配置了但当前连不上（瞬时故障，可重试）。
    - incompatible: 能连上但接口契约/版本不匹配（部署问题，重试无用）。
    - degraded:   可用，但部分可选能力不可用（见 unavailable_capabilities）。
    - embed_origin: **浏览器公开 Origin**，与内部 BASE_URL 分离；未配置时为 None（fail-closed）。
    - browser_embed_available: 学生浏览器能否安全内嵌课堂；服务端可认证不代表浏览器可认证。
    """

    enabled: bool
    configured: bool = False
    available: bool = False
    incompatible: bool = False
    degraded: bool = False
    compatibility: str = "unknown"
    compatibility_reason: Optional[str] = None
    service: str = "magicclass"
    version: str = ""
    version_source: str = "unknown"
    # 版本越界只作为运维告警，不单独判 incompatible（见 compatibility.py 的说明）
    version_out_of_range: bool = False
    capabilities: Dict[str, bool] = Field(default_factory=dict)
    unavailable_capabilities: List[str] = Field(default_factory=list)
    unavailable: bool = False
    embed_origin: Optional[str] = None
    browser_embed_available: bool = False
    browser_embed_reason: Optional[str] = None
    # 3D(visualization3d) 依赖学生浏览器访问外部 CDN；关闭时 UI 需标注不可用
    external_3d_available: bool = True
    poll_interval_ms: int = 5000
    poll_max_seconds: int = 1800
    checked_at: str = ""
    # 未启用/不可用时的说明文案
    reason: Optional[str] = None


class MagicClassSessionOut(BaseModel):
    session_id: str
    course_id: str
    mode: str
    requested_mode: Optional[str] = None
    adaptive_reason: Optional[str] = None
    job_id: Optional[str] = None
    status: str
    step: str
    progress: int = 0
    message: str = ""
    error: Optional[str] = None
    classroom_id: Optional[str] = None
    # **浏览器公开**地址：由 public_url 按当前 MAGICCLASS_EMBED_ORIGIN 现场投影。
    # 绝不直接序列化数据库里历史保存的 classroom_url（那可能是内部 Docker 地址）。
    url: Optional[str] = None
    url_unavailable_reason: Optional[str] = None
    scenes_count: Optional[int] = None
    # 终态语义：terminal / retryable / partial（不创造 magic class 不存在的状态值）
    terminal: bool = False
    retryable: bool = False
    partial: bool = False
    error_code: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_session(cls, s, *, settings) -> "MagicClassSessionOut":
        """`settings` 是**必填**关键字参数。

        刻意不给默认值：任何新增的下发路径若忘记传入配置，会立刻 `TypeError`，
        而不是静默把数据库里的原始 URL 泄漏出去。
        """
        from ..services.magicclass.public_url import project_session_url

        terminal = s.status in ("succeeded", "failed")
        partial = bool(
            s.status == "succeeded"
            and s.scenes_count is not None
            and s.partial
        )
        url, url_reason = project_session_url(settings, s)
        return cls(
            session_id=s.session_id,
            course_id=s.course_id,
            mode=s.mode,
            requested_mode=s.requested_mode,
            adaptive_reason=s.adaptive_reason,
            job_id=s.job_id,
            status=s.status,
            step=s.step,
            progress=s.progress,
            message=s.message,
            error=s.error,
            classroom_id=s.classroom_id,
            url=url,
            url_unavailable_reason=url_reason,
            scenes_count=s.scenes_count,
            terminal=terminal,
            retryable=terminal,
            partial=partial,
            error_code=s.error_code,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )


class MagicClassGenerateOut(BaseModel):
    accepted: bool = True
    session: MagicClassSessionOut
    poll_interval_ms: int = 5000
    mode: str
    requested_mode: Optional[str] = None
    adaptive_reason: Optional[str] = None
    materials: List[MagicClassMaterialOut] = Field(default_factory=list)
    # 本次请求的个性化来源：snapshot（原任务快照，权威）/ client_body / legacy_mode_only
    request_source: Optional[str] = None
    request_source_note: Optional[str] = None
    # 学生指定但无法解析（不存在/越权/已删除）的资料 id —— 显式报告，绝不静默忽略
    materials_unresolved: List[str] = Field(default_factory=list)
    materials_warning: Optional[str] = None


class MagicClassSceneCountOut(BaseModel):
    """真实课堂里某一种 scene.type 的数量。"""

    type: str
    count: int = 0


class MagicClassWidgetCountOut(BaseModel):
    """interactive 场景内部 widgetType 的分布。"""

    widget_type: str
    count: int = 0


class MagicClassCompositionOut(BaseModel):
    """**真实**课堂组成（读取 GET /api/classroom?id= 后统计）。

    必须如实反映生成结果，不得根据请求 mode 推断。
    """

    classroom_id: str
    scene_total: int = 0
    scenes: List[MagicClassSceneCountOut] = Field(default_factory=list)
    widget_types: List[MagicClassWidgetCountOut] = Field(default_factory=list)
    has_whiteboard: bool = False
    has_tts: bool = False
    has_multi_agent: bool = False
    # 出现了本适配层还不认识的 scene.type / widgetType 时置位（安全降级，不报错）
    has_unknown_scene_type: bool = False
    has_unknown_widget_type: bool = False
    # 3D 依赖外部 CDN；课堂里有 3D 内容但环境不可达时为 True（degraded，不是失败）
    requires_external_3d: bool = False
    external_3d_available: bool = True
    degraded: bool = False
    read_at: str = ""
    error: Optional[str] = None


class MagicClassClassroomOut(BaseModel):
    session_id: str
    classroom_id: Optional[str] = None
    # **浏览器公开**地址（按 MAGICCLASS_EMBED_ORIGIN 现场构造）。
    # 未配置公开 Origin 时为 None —— 客户端应显示"已生成但当前部署未开放浏览器访问"，
    # 绝不能回落到内部服务地址。
    url: Optional[str] = None
    url_unavailable_reason: Optional[str] = None
    mode: str
    scenes_count: Optional[int] = None
    created_at: str = ""
    # 真实课堂组成（阶段 3 读取 GET /api/classroom?id= 得到；读取失败时为 None）
    composition: Optional[MagicClassCompositionOut] = None


class MagicClassClassroomsOut(BaseModel):
    enabled: bool
    items: List[MagicClassClassroomOut] = Field(default_factory=list)


__all__ = [
    "MagicClassGenerateRequest",
    "MagicClassStatusOut",
    "MagicClassSessionOut",
    "MagicClassGenerateOut",
    "MagicClassClassroomOut",
    "MagicClassClassroomsOut",
    "MagicClassPlanOut",
    "MagicClassMaterialOut",
    "MagicClassCompositionOut",
    "MagicClassSceneCountOut",
    "MagicClassWidgetCountOut",
    "MODE_INTENT_LABELS",
    "VALID_MODES",
    "VALID_DIFFICULTY_LEVELS",
]
