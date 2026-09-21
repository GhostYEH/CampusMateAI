"""magicclass 互动课堂适配层。

结构：
- client.py            magicclass /api 客户端(ACCESS_CODE / health / 契约指纹探针 / 提交 / 轮询、URL/ID/step 校验)
- compatibility.py     契约指纹与版本判定(版本只记录，不单独决定兼容)
- errors.py            稳定错误码
- requirement_builder 学习意图 → requirement → GenerateClassroomInput
- course_context       课程上下文构造 + 统一权限校验
- result_store         课堂会话 JSON 文件持久化 + 跨进程原子预占 + 历史裁剪
- classroom_service    编排(状态/生成/轮询/幂等/结果)

所有服务端凭据(含 MAGICCLASS_ACCESS_CODE)只存在于后端配置，绝不发送/返回客户端。
"""
from .client import (
    GENERATION_STEPS,
    JOB_STATUS_VALUES,
    JOB_STEP_VALUES,
    PROBE_CHECKS,
    PROBE_JOB_ID,
    MagicClassClient,
    MagicClassHealth,
    MagicClassProbeResult,
    normalize_step,
    normalize_status,
)
from .classroom_service import PUBLIC_STEPS, MagicClassClassroomService
from .compatibility import (
    COMPATIBLE,
    INCOMPATIBLE,
    OPTIONAL_CAPABILITIES,
    UNKNOWN,
    CompatibilityVerdict,
    effective_capabilities,
    is_degraded,
    resolve_compatibility,
    unavailable_capabilities,
    version_source,
)
from .composition import (
    KNOWN_SCENE_TYPES,
    KNOWN_WIDGET_TYPES,
    ClassroomComposition,
    parse_classroom_composition,
)
from .course_context import (
    ContextLimits,
    LearningContext,
    MaterialRef,
    assert_course_access,
    build_course_context,
    build_cpm_course_block,
    build_learning_context,
)
from .errors import (
    MagicClassAuthError,
    MagicClassIncompatible,
    MagicClassInvalidOrigin,
    MagicClassNotEnabled,
    MagicClassProtocolError,
    MagicClassRateLimited,
    MagicClassServerError,
    MagicClassUnavailable,
)
from .requirement_builder import (
    CANONICAL_MODES,
    LEGACY_MODE_ALIASES,
    AdaptiveSignals,
    StudentBrief,
    build_input_payload,
    build_requirement,
    choose_adaptive_mode,
    mode_label,
    normalize_mode,
    validate_mode,
)
from .result_store import (
    MagicClassReservation,
    MagicClassResultStore,
    MagicClassSession,
)

__all__ = [
    "MagicClassClient",
    "MagicClassHealth",
    "MagicClassProbeResult",
    "MagicClassClassroomService",
    "MagicClassResultStore",
    "MagicClassSession",
    "MagicClassReservation",
    "assert_course_access",
    "build_course_context",
    "build_cpm_course_block",
    "GENERATION_STEPS",
    "JOB_STEP_VALUES",
    "JOB_STATUS_VALUES",
    "PROBE_CHECKS",
    "PROBE_JOB_ID",
    "PUBLIC_STEPS",
    "CANONICAL_MODES",
    "LEGACY_MODE_ALIASES",
    "AdaptiveSignals",
    "StudentBrief",
    "choose_adaptive_mode",
    "mode_label",
    "normalize_mode",
    "validate_mode",
    "ContextLimits",
    "LearningContext",
    "MaterialRef",
    "build_learning_context",
    "ClassroomComposition",
    "parse_classroom_composition",
    "KNOWN_SCENE_TYPES",
    "KNOWN_WIDGET_TYPES",
    "normalize_step",
    "normalize_status",
    "COMPATIBLE",
    "INCOMPATIBLE",
    "UNKNOWN",
    "OPTIONAL_CAPABILITIES",
    "CompatibilityVerdict",
    "effective_capabilities",
    "is_degraded",
    "resolve_compatibility",
    "unavailable_capabilities",
    "version_source",
    "MagicClassAuthError",
    "MagicClassIncompatible",
    "MagicClassInvalidOrigin",
    "MagicClassNotEnabled",
    "MagicClassProtocolError",
    "MagicClassRateLimited",
    "MagicClassServerError",
    "MagicClassUnavailable",
]
