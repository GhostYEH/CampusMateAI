"""FastAPI 依赖: JWT 解析、当前用户、RBAC、所属班级/课程权限校验。

设计原则:
- JWT 通过 Authorization: Bearer <token> 传入。
- access token 短有效期;refresh token 仅用于换发 access token。
- 失败统一抛 Unauthorized,不泄露用户名是否存在。
- RBAC 通过 require_role 装饰器实现,具体业务权限在 route 内部校验。
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..core.config import Settings, get_settings
from ..core.exceptions import Forbidden, Unauthorized
from ..core.security import JWTError, decode_jwt
from ..core.rate_limit import check_request_rate
from ..models.multi_role import UserRow
from ..services.container import ServiceContainer, get_container

_bearer = HTTPBearer(auto_error=False)


def get_settings_dep() -> Settings:
    return get_settings()


def _decode_access_token(
    token: str,
    settings: Settings,
) -> UserRow:
    """解析 access token 并返回 UserRow。失败抛 Unauthorized。

    历史 teacher/admin 账号运行时降级为 student，保留数据库记录。
    JWT 中的旧角色不赋予额外权限。
    """
    try:
        payload = decode_jwt(token, settings.jwt_secret)
    except JWTError as e:
        raise Unauthorized(f"token 无效: {e}") from e
    if payload.type != "access":
        raise Unauthorized("token 类型错误")
    container = get_container()
    user = container.user_repository.get_user_by_id(payload.sub)
    if user is None or not user.is_active:
        raise Unauthorized("用户不存在或已停用")
    if user.role != "student":
        raise Unauthorized("无效的用户角色")
    return user


def current_user(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> UserRow:
    """从 Authorization 头解析当前用户。

    - 优先解析 `Authorization: Bearer <access_token>`
    - 也支持 query 参数 `?access_token=` (用于 SSE/EventSource,因为浏览器不支持自定义 header)
    """
    token: Optional[str] = None
    if creds is not None and creds.credentials:
        token = creds.credentials
    if token is None:
        # 回退到 query 参数(SSE 场景)
        token = request.query_params.get("access_token")
    if not token:
        raise Unauthorized("缺少认证 token")
    return _decode_access_token(token, settings)


def current_user_optional(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[UserRow]:
    """可选认证: 缺 token 返回 None;有 token 必须有效。"""
    token: Optional[str] = None
    if creds is not None and creds.credentials:
        token = creds.credentials
    if token is None:
        token = request.query_params.get("access_token")
    if not token:
        return None
    try:
        return _decode_access_token(token, settings)
    except Unauthorized:
        return None


def require_role(*roles: str):
    """依赖工厂: 限定当前用户必须为指定角色之一,否则抛 Forbidden。

    用法: `user: UserRow = Depends(require_role("student"))`
    """
    expected = set(roles)

    def _check(user: UserRow = Depends(current_user)) -> UserRow:
        if user.role not in expected:
            raise Forbidden("当前角色无权执行此操作")
        return user

    return _check


def limit_anonymous_chat(request: Request, user: Optional[UserRow] = Depends(current_user_optional)) -> None:
    if user is None:
        check_request_rate(request, "anonymous_chat", limit=10)


def student_only(user: UserRow = Depends(current_user)) -> UserRow:
    """Student-only gate that does not treat legacy teacher accounts as students."""
    if user.role != "student" or getattr(user, "original_role", None) == "teacher":
        raise Forbidden("当前角色无权访问学生学习计划")
    return user


__all__ = [
    "current_user",
    "current_user_optional",
    "require_role",
    "student_only",
]
