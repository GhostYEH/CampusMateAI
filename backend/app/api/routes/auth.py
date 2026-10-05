"""Student authentication; historical privileged accounts receive ordinary access."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, Response

from ...core.config import Settings
from ...core.exceptions import (
    AppException,
    InvalidCredentials,
    StudentNumberExists,
    Unauthorized,
    UsernameExists,
    ValidationFailed,
)
from ...core.logging import logger
from ...core.rate_limit import request_rate_limit
from ...core.security import (
    create_access_token,
    create_refresh_token,
    decode_jwt,
    hash_password,
    hash_token,
    verify_password,
    JWTError,
)
from ...models.multi_role import UserRow
from ...schemas.multi_role import (
    AuthMeResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserPublic,
    UserProfileUpdate,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user, get_settings_dep

router = APIRouter(prefix="/auth", tags=["认证"])


def _container() -> ServiceContainer:
    return get_container()


def _enrich_user_public(user: UserRow, container: ServiceContainer) -> UserPublic:
    """构造 UserPublic 并按 university_id 补全 university_name，避免客户端二次请求。"""
    public_user = UserPublic(**user.to_public_dict())
    public_user.name = user.display_name or user.username
    if user.university_id:
        university = container.university_repository.get_by_id(user.university_id)
        if university is not None:
            public_user.university_name = university.name
    return public_user


def _create_user(req: RegisterRequest, container: ServiceContainer) -> UserPublic:
    """公开注册的校验和持久化。"""
    if req.role == "student" and req.teacher_number:
        raise ValidationFailed("学生角色不应携带 teacher_number")

    user_repo = container.user_repository
    if user_repo.get_user_by_username(req.username):
        raise UsernameExists()
    if req.student_number and user_repo.get_user_by_student_number(req.student_number):
        raise StudentNumberExists()
    try:
        created = user_repo.create_user(
            username=req.username,
            password_hash=hash_password(req.password),
            role=req.role,
            display_name=req.display_name,
            student_number=req.student_number,
            teacher_number=req.teacher_number,
            college=req.college,
            major=req.major,
            grade=req.grade,
        )
    except sqlite3.IntegrityError as exc:
        constraint = str(exc).lower()
        if "unique constraint failed: users.username" in constraint:
            raise UsernameExists() from exc
        if "unique constraint failed: users.student_number" in constraint:
            raise StudentNumberExists() from exc
        raise
    return UserPublic(**created.to_public_dict())


@router.post(
    "/login",
    response_model=TokenPair,
    summary="用户登录",
    dependencies=[Depends(request_rate_limit("login", limit=20))],
    responses={
        429: {"description": "请求过于频繁（RATE_LIMITED）；Retry-After 表示等待秒数"},
        200: {
            "description": "登录成功，返回访问令牌与刷新令牌",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "登录成功",
                            "value": {
                                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                "token_type": "Bearer",
                                "expires_in": 1800,
                                "expires_at": "2026-10-06T12:00:00+00:00",
                                "user": {
                                    "id": "u_demo",
                                    "uid": "u_demo",
                                    "username": "student_demo",
                                    "role": "student",
                                    "name": "演示学生",
                                    "display_name": "演示学生",
                                    "student_number": "20240001",
                                    "college": "计算机学院",
                                    "major": "软件工程",
                                    "grade": "2024",
                                    "avatar_url": None,
                                    "university_id": None,
                                    "university_name": None,
                                    "is_active": True,
                                    "created_at": "2026-09-01T08:00:00+00:00",
                                    "updated_at": "2026-09-01T08:00:00+00:00",
                                },
                            },
                        }
                    }
                }
            },
        },
    },
)
def login(
    req: Annotated[
        LoginRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "演示学生登录",
                    "value": {"username": "student_demo", "password": "Demo123456"},
                }
            }
        ),
    ],
    settings: Settings = Depends(get_settings_dep),
    container: ServiceContainer = Depends(_container),
) -> TokenPair:
    """使用用户名和密码登录，返回访问令牌与刷新令牌。

    - 密码错误或账号停用返回 401（INVALID_CREDENTIALS）。
    - 同一来源地址每 60 秒最多 20 次，超限返回 429（RATE_LIMITED）。
    """
    user_repo = container.user_repository
    user = user_repo.get_user_by_username(req.username)
    if user is None or not user.is_active:
        raise InvalidCredentials()
    if not verify_password(req.password, user.password_hash):
        raise InvalidCredentials()
    return _issue_tokens(user, settings, container)


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=201,
    summary="公开注册学生账号",
    dependencies=[Depends(request_rate_limit("register", limit=5))],
    responses={
        429: {"description": "请求过于频繁（RATE_LIMITED）；Retry-After 表示等待秒数"},
        201: {
            "description": "注册成功，返回新用户公开资料（不含密码哈希）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "注册成功",
                            "value": {
                                "id": "u_demo",
                                "uid": "u_demo",
                                "username": "student_demo",
                                "role": "student",
                                "name": "演示学生",
                                "display_name": "演示学生",
                                "student_number": "20240001",
                                "college": "计算机学院",
                                "major": "软件工程",
                                "grade": "2024",
                                "avatar_url": None,
                                "university_id": None,
                                "university_name": None,
                                "is_active": True,
                                "created_at": "2026-09-01T08:00:00+00:00",
                                "updated_at": "2026-09-01T08:00:00+00:00",
                            },
                        }
                    }
                }
            },
        },
    },
)
def register(
    req: Annotated[
        RegisterRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "注册学生账号",
                    "value": {
                        "username": "student_demo",
                        "password": "Demo123456",
                        "role": "student",
                        "display_name": "演示学生",
                        "student_number": "20240001",
                        "college": "计算机学院",
                        "major": "软件工程",
                        "grade": "2024",
                    },
                }
            }
        ),
    ],
    container: ServiceContainer = Depends(_container),
) -> UserPublic:
    """公开注册学生账号，无需鉴权。

    - 仅允许 role=student；注册成功后仍须调用 /auth/login 获取令牌，注册不自动登录。
    - 用户名或学号重复返回 409（USERNAME_EXISTS / STUDENT_NUMBER_EXISTS），学生携带 teacher_number 返回 422（VALIDATION_FAILED）。
    """
    return _create_user(req, container)


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="刷新访问令牌",
    responses={
        200: {
            "description": "换发成功，返回新的访问令牌与刷新令牌",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "换发成功",
                            "value": {
                                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                "token_type": "Bearer",
                                "expires_in": 1800,
                                "expires_at": "2026-10-06T12:00:00+00:00",
                                "user": {
                                    "id": "u_demo",
                                    "uid": "u_demo",
                                    "username": "student_demo",
                                    "role": "student",
                                    "name": "演示学生",
                                    "display_name": "演示学生",
                                    "student_number": "20240001",
                                    "college": "计算机学院",
                                    "major": "软件工程",
                                    "grade": "2024",
                                    "avatar_url": None,
                                    "university_id": None,
                                    "university_name": None,
                                    "is_active": True,
                                    "created_at": "2026-09-01T08:00:00+00:00",
                                    "updated_at": "2026-09-01T08:00:00+00:00",
                                },
                            },
                        }
                    }
                }
            },
        }
    },
)
def refresh(
    req: Annotated[
        RefreshRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "使用刷新令牌换发",
                    "value": {
                        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                    },
                }
            }
        ),
    ],
    settings: Settings = Depends(get_settings_dep),
    container: ServiceContainer = Depends(_container),
) -> TokenPair:
    """用 refresh token 换发新的 access token 与 refresh token。

    - 旧 refresh token 在换发后立即撤销，防止重放。
    - 令牌无效、类型错误、已撤销、已过期或用户停用一律返回 401（UNAUTHORIZED）。
    """
    try:
        payload = decode_jwt(req.refresh_token, settings.jwt_secret)
    except JWTError as e:
        raise Unauthorized(f"refresh token 无效: {e}") from e
    if payload.type != "refresh":
        raise Unauthorized("token 类型错误,期望 refresh token")
    refresh_repo = container.refresh_token_repository
    token_hash = hash_token(req.refresh_token)
    stored = refresh_repo.get_by_hash(token_hash)
    if stored is None or stored.revoked:
        raise Unauthorized("refresh token 已失效或不存在")
    if stored.expires_at < datetime.now(timezone.utc).isoformat():
        raise Unauthorized("refresh token 已过期")
    user = container.user_repository.get_user_by_id(payload.sub)
    if user is None or not user.is_active:
        raise Unauthorized("用户不存在或已停用")
    # 撤销旧 refresh token(防止重放)
    if not refresh_repo.revoke(token_hash):
        # Another refresh or logout may have consumed it after the read above.
        raise Unauthorized("refresh token 已失效或不存在")
    return _issue_tokens(user, settings, container)


@router.post(
    "/logout",
    summary="退出登录并撤销凭据",
    responses={
        200: {
            "description": "退出成功，已撤销刷新令牌与可信设备凭据",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "退出成功",
                            "value": {"ok": True, "message": "已退出登录"},
                        }
                    }
                }
            },
        },
    },
)
def logout(
    req: Annotated[
        LogoutRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "退出登录",
                    "value": {"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."},
                }
            }
        ),
    ],
    request: Request,
    response: Response,
    user: UserRow = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    container: ServiceContainer = Depends(_container),
) -> dict:
    """撤销当前 refresh token（若有），并撤销当前浏览器的可信设备凭据。

    - 可信设备凭据由 HttpOnly Cookie 携带，撤销后清除该 Cookie。
    - 撤销可信设备失败返回 503（统一错误信封），客户端可重试。
    """
    if req.refresh_token:
        token_hash = hash_token(req.refresh_token)
        container.refresh_token_repository.revoke(token_hash)
    # 撤销当前浏览器的可信设备凭据(避免退出后又被自动登录)
    cookie_name = settings.trusted_device_cookie_name
    cookie_token = request.cookies.get(cookie_name)
    if cookie_token:
        try:
            container.trusted_device_repository.revoke_by_token_hash(hash_token(cookie_token), user_id=user.id)
        except Exception as exc:
            logger.warning("trusted_device_logout_revoke_failed exception_type={}", type(exc).__name__)
            raise AppException("可信设备授权撤销失败，请重试", http_status=503) from exc
        response.delete_cookie(
            key=cookie_name, 
            path="/api/v1/auth",
            httponly=True,
            secure=settings.trusted_device_cookie_secure,
            samesite="lax"
        )
    return {"ok": True, "message": "已退出登录"}


@router.get(
    "/me",
    response_model=AuthMeResponse,
    summary="获取当前用户资料",
    responses={
        200: {
            "description": "返回当前登录用户的公开资料",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "获取成功",
                            "value": {
                                "user": {
                                    "id": "u_demo",
                                    "uid": "u_demo",
                                    "username": "student_demo",
                                    "role": "student",
                                    "name": "演示学生",
                                    "display_name": "演示学生",
                                    "student_number": "20240001",
                                    "college": "计算机学院",
                                    "major": "软件工程",
                                    "grade": "2024",
                                    "avatar_url": None,
                                    "university_id": None,
                                    "university_name": None,
                                    "is_active": True,
                                    "created_at": "2026-09-01T08:00:00+00:00",
                                    "updated_at": "2026-09-01T08:00:00+00:00",
                                }
                            },
                        }
                    }
                }
            },
        }
    },
)
def me(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AuthMeResponse:
    """返回当前登录用户的资料，需携带 Bearer access token。

    - 历史 admin/teacher 账号按普通用户权限解释，role 统一为 student。
    - 未登录或令牌失效返回 401（统一错误信封）。
    """
    return AuthMeResponse(user=_enrich_user_public(user, container))


@router.patch(
    "/me",
    response_model=UserPublic,
    summary="修改个人资料",
    responses={
        200: {
            "description": "更新成功，返回更新后的用户公开资料",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "更新成功",
                            "value": {
                                "id": "u_demo",
                                "uid": "u_demo",
                                "username": "student_demo",
                                "role": "student",
                                "name": "示例同学",
                                "display_name": "示例同学",
                                "student_number": "20240001",
                                "college": "示例学院",
                                "major": "软件工程",
                                "grade": "2026",
                                "avatar_url": None,
                                "university_id": None,
                                "university_name": None,
                                "is_active": True,
                                "created_at": "2026-09-01T08:00:00+00:00",
                                "updated_at": "2026-10-06T12:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def update_me(
    req: Annotated[
        UserProfileUpdate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "更新个人资料",
                    "value": {
                        "display_name": "示例同学",
                        "college": "示例学院",
                        "major": "软件工程",
                        "grade": "2026",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> UserPublic:
    """更新当前用户的个人资料，仅允许修改 display_name、college、major、grade。

    - 字段均可省略：省略保留原值，显式 null 清空。
    - 长度超限或提交未声明字段返回 422（VALIDATION_FAILED）；未登录返回 401。
    """
    updated = container.user_repository.update_user(user.id, fields=req.model_dump(exclude_unset=True))
    # Preserve the runtime downgrade when updating historical accounts.
    updated.role = "student"
    return _enrich_user_public(updated, container)


def _issue_tokens(
    user: UserRow,
    settings: Settings,
    container: ServiceContainer,
) -> TokenPair:
    # Old tokens and persisted roles never grant elevated privileges.
    effective_role = "student"
    access_token, access_payload = create_access_token(
        user.id, effective_role, settings.jwt_secret,
        expires_in_minutes=settings.access_token_expire_minutes,
    )
    refresh_token, refresh_payload = create_refresh_token(
        user.id, effective_role, settings.jwt_secret,
        expires_in_days=settings.refresh_token_expire_days,
    )
    # 持久化 refresh token 的哈希(不存原 token)
    expires_at = datetime.fromtimestamp(refresh_payload.exp, tz=timezone.utc).isoformat()
    container.refresh_token_repository.create_token(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=expires_at,
    )
    # 响应中返回降级后的角色,避免前端误判为 teacher
    public_user = _enrich_user_public(user, container)
    public_user.role = effective_role
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        expires_at=datetime.fromtimestamp(
            access_payload.exp,
            tz=timezone.utc,
        ).isoformat(),
        user=public_user,
    )


__all__ = ["router"]
