"""OpenMAIC 互动课堂适配层。

结构：
- client.py            OpenMAIC /api 客户端(health / 提交 / 轮询、URL/ID 校验)
- errors.py            稳定错误码
- requirement_builder 学习模式 → requirement → GenerateClassroomInput
- course_context       课程上下文构造 + 权限校验
- result_store         复用 AgentArtifact 的会话持久化
- classroom_service    编排(生成/轮询/幂等/结果)

所有服务端凭据只存在于后端配置，绝不发送/返回客户端。
"""
from .client import OpenMAICClient, OpenMAICHealth
from .classroom_service import OpenMAICClassroomService
from .course_context import assert_course_access, build_course_context
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
from .result_store import OpenMAICResultStore, OpenMAICSession