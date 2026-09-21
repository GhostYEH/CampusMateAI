"""magic class 集成错误 —— 稳定错误码，供客户端与测试断言使用。

这些异常继承统一业务异常基类 AppException，由全局异常处理器输出为
`{code, message, details, request_id}`，不会向客户端泄露内部堆栈或凭据。
"""
from __future__ import annotations

from typing import Optional

from ...core.exceptions import AppException


class MagicClassNotEnabled(AppException):
    """互动课堂服务未启用（未配置 MAGICCLASS_ENABLED/MAGICCLASS_BASE_URL）。

    返回 503 且不影响课程详情与 CPM 基础聊天。
    """

    code = "MAGICCLASS_NOT_ENABLED"
    http_status = 503
    message = "互动课堂服务未启用"


class MagicClassUnavailable(AppException):
    """magicclass 服务连接失败/超时/不可达。"""

    code = "MAGICCLASS_UNAVAILABLE"
    http_status = 503
    message = "互动课堂服务不可用，请稍后重试"


class MagicClassAuthError(AppException):
    """magic class 返回 401 鉴权失败，可能意味着服务端凭据过期。"""

    code = "MAGICCLASS_AUTH_ERROR"
    http_status = 502
    message = "互动课堂服务鉴权失败，请稍后重试"


class MagicClassRateLimited(AppException):
    """magic class 返回 429。"""

    code = "MAGICCLASS_RATE_LIMITED"
    http_status = 429
    message = "互动课堂服务请求过于频繁，请稍后重试"


class MagicClassServerError(AppException):
    """magic class 返回 5xx。"""

    code = "MAGICCLASS_SERVER_ERROR"
    http_status = 502
    message = "互动课堂服务内部错误，请稍后重试"


class MagicClassProtocolError(AppException):
    """magicclass 返回的结构不符合契约（无效 JSON/缺字段）。"""

    code = "MAGICCLASS_PROTOCOL_ERROR"
    http_status = 502
    message = "互动课堂服务响应异常，请稍后重试"


class MagicClassIncompatible(AppException):
    """目标 magicclass 部署与 CampusMate 期望的契约不兼容（版本或端点语义）。

    这是**部署/配置**问题而非瞬时故障，因此与 `magicclassUnavailable` 严格区分：
    客户端应提示"版本不匹配"，而不是"稍后重试"。
    """

    code = "MAGICCLASS_INCOMPATIBLE"
    http_status = 503
    message = "互动课堂服务版本不兼容，已暂停生成"


class MagicClassInvalidOrigin(AppException):
    """返回的课堂 URL 与已配置 magic class Origin 不符，拒绝透传给客户端。"""

    code = "MAGICCLASS_INVALID_ORIGIN"
    http_status = 502
    message = "互动课堂返回地址校验失败"


# 说明：曾经存在 `MagicClassGenerationFailed`，但它从未被抛出过。
# 生成失败在设计上是**任务状态**（`status="failed"` + `error_code`），不是 HTTP 异常：
# 客户端是轮询任务的，抛出异常会让它拿不到失败状态与重试入口。因此删除该无用抽象。


__all__ = [
    "MagicClassNotEnabled",
    "MagicClassUnavailable",
    "MagicClassAuthError",
    "MagicClassRateLimited",
    "MagicClassServerError",
    "MagicClassProtocolError",
    "MagicClassIncompatible",
    "MagicClassInvalidOrigin",
]