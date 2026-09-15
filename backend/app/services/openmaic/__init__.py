"""OpenMAIC 互动课堂适配层。

结构：
- client.py            OpenMAIC /api 客户端(ACCESS_CODE / health / 提交 / 轮询、URL/ID/step 校验)
- errors.py            稳定错误码
- requirement_builder 学习模式 → requirement → GenerateClassroomInput
- course_context       课程上下文构造 + 统一权限校验
- result_store         课堂会话 JSON 文件持久化 + 跨进程原子预占 + 历史裁剪
- classroom_service    编排(状态/生成/轮询/幂等/结果)

所有服务端凭据(含 OPENMAIC_ACCESS_CODE)只存在于后端配置，绝不发送/返回客户端。
"""
from .client import (
    GENERATION_STEPS,
    JOB_STATUS_VALUES,
    JOB_STEP_VALUES,
    OpenMAICClient,
    OpenMAICHealth,
    normalize_step,
    normalize_status,
)
from .classroom_service import PUBLIC_STEPS, OpenMAICClassroomService
from .course_context import (
    assert_course_access,
    build_course_context,
    build_cpm_course_block,
)
from .errors import (
    OpenMAICAuthError,
    OpenMAICGenerationFailed,
    OpenMAICInvalidOrigin,
    OpenMAICNotEnabled,
    OpenMAICProtocolError,
    OpenMAICRateLimited,
    OpenMAICServerError,
    OpenMAICUnavailable,
)
from .result_store import (
    OpenMAICReservation,
    OpenMAICResultStore,
    OpenMAICSession,
)

__all__ = [
    "OpenMAICClient",
    "OpenMAICHealth",
    "OpenMAICClassroomService",
    "OpenMAICResultStore",
    "OpenMAICSession",
    "OpenMAICReservation",
    "assert_course_access",
    "build_course_context",
    "build_cpm_course_block",
    "GENERATION_STEPS",
    "JOB_STEP_VALUES",
    "JOB_STATUS_VALUES",
    "PUBLIC_STEPS",
    "normalize_step",
    "normalize_status",
    "OpenMAICAuthError",
    "OpenMAICGenerationFailed",
    "OpenMAICInvalidOrigin",
    "OpenMAICNotEnabled",
    "OpenMAICProtocolError",
    "OpenMAICRateLimited",
    "OpenMAICServerError",
    "OpenMAICUnavailable",
]
