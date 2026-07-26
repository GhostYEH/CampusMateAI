"""FastAPI 依赖: JWT 解析、当前用户、RBAC、所属班级/课程权限校验。

设计原则:
- JWT 通过 Authorization: Bearer <token> 传入。
- access token 短有效期;refresh token 仅用于换发 access token。
- 失败统一抛 Unauthorized,不泄露用户名是否存在。
- RBAC 通过 require_role 装饰器实现,具体业务权限在 route 内部校验。
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..core.config import Settings, get_settings
from ..core.exceptions import Forbidden, Unauthorized
from ..core.security import JWTError, decode_jwt, hash_token
from ..models.multi_role import UserRow
from ..repositories.multi_role_repository import (
    ClassGroupRepository,
    CourseRepository,
    EnrollmentRepository,
    RefreshTokenRepository,
    UserRepository,
)
from ..services.container import ServiceContainer, get_container

_bearer = HTTPBearer(auto_error=False)


def _container() -> ServiceContainer:
    return get_container()


def _user_repo(c: ServiceContainer = Depends(_container)) -> UserRepository:
    return c.user_repository


def _refresh_repo(c: ServiceContainer = Depends(_container)) -> RefreshTokenRepository:
    return c.refresh_token_repository


def get_settings_dep() -> Settings:
    return get_settings()


def _decode_access_token(
    token: str,
    settings: Settings,
) -> UserRow:
    """解析 access token 并返回 UserRow。失败抛 Unauthorized。"""
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

    用法: `user: UserRow = Depends(require_role("teacher","admin"))`
    """
    expected = set(roles)

    def _check(user: UserRow = Depends(current_user)) -> UserRow:
        if user.role not in expected:
            raise Forbidden("当前角色无权执行此操作")
        return user

    return _check


# ===== 业务权限辅助 =====


def assert_teacher_of_course(course_id: str, user: UserRow) -> None:
    """断言 user 是该课程的负责教师(或管理员)。"""
    if user.role == "admin":
        return
    container = get_container()
    course = container.course_repository.get_course(course_id)
    if course is None:
        # 抛 NotFound 而不是 Forbidden,避免泄露存在性
        from ..core.exceptions import CourseNotFound
        raise CourseNotFound()
    if course.teacher_id != user.id:
        raise Forbidden("无权管理此课程")


def assert_teacher_of_class(class_id: str, user: UserRow) -> None:
    if user.role == "admin":
        return
    container = get_container()
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        from ..core.exceptions import ClassGroupNotFound
        raise ClassGroupNotFound()
    assert_teacher_of_course(cls.course_id, user)


def assert_student_in_class(class_id: str, user: UserRow) -> None:
    if user.role == "admin":
        return
    if user.role != "student":
        raise Forbidden("仅学生可访问此班级内容")
    container = get_container()
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        from ..core.exceptions import ClassGroupNotFound
        raise ClassGroupNotFound()
    enr = container.enrollment_repository.get_enrollment(class_id, user.id)
    if enr is None or enr.status != "active":
        raise Forbidden("你未加入此班级")


__all__ = [
    "current_user",
    "current_user_optional",
    "require_role",
    "assert_teacher_of_course",
    "assert_teacher_of_class",
    "assert_student_in_class",
]
