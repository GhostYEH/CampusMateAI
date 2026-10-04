"""Student authentication; historical privileged accounts receive ordinary access."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response

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

router = APIRouter(prefix="/auth", tags=["auth"])


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


@router.post("/login", response_model=TokenPair, dependencies=[Depends(request_rate_limit("login", limit=20))], responses={429: {"description": "请求过于频繁（RATE_LIMITED）；Retry-After 表示等待秒数"}})
def login(
    req: LoginRequest,
    settings: Settings = Depends(get_settings_dep),
    container: ServiceContainer = Depends(_container),
) -> TokenPair:
    user_repo = container.user_repository
    user = user_repo.get_user_by_username(req.username)
    if user is None or not user.is_active:
        raise InvalidCredentials()
    if not verify_password(req.password, user.password_hash):
        raise InvalidCredentials()
    return _issue_tokens(user, settings, container)


@router.post("/register", response_model=UserPublic, status_code=201, dependencies=[Depends(request_rate_limit("register", limit=5))], responses={429: {"description": "请求过于频繁（RATE_LIMITED）；Retry-After 表示等待秒数"}})
def register(
    req: RegisterRequest,
    container: ServiceContainer = Depends(_container),
) -> UserPublic:
    """公开注册接口(无需鉴权)。

    限制:
    - 仅允许注册 student 角色。
    - 注册成功后用户仍需走 /auth/login 登录获取 token(注册不自动登录)。
    - 校验用户名和学号的唯一性。

    安全:
    - 密码以 PBKDF2-HMAC-SHA256 哈希存储,不返回密码或哈希。
    - 返回 UserPublic(不含 password_hash)。
    """
    return _create_user(req, container)


@router.post("/refresh", response_model=TokenPair)
def refresh(
    req: RefreshRequest,
    settings: Settings = Depends(get_settings_dep),
    container: ServiceContainer = Depends(_container),
) -> TokenPair:
    """用 refresh token 换发新的 access token + refresh token。

    旧 refresh token 在换发后被撤销(防止重放)。
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


@router.post("/logout")
def logout(
    req: LogoutRequest,
    request: Request,
    response: Response,
    user: UserRow = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    container: ServiceContainer = Depends(_container),
) -> dict:
    """撤销当前 refresh token(若有)，并撤销当前浏览器的可信设备凭据。"""
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


@router.get("/me", response_model=AuthMeResponse)
def me(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AuthMeResponse:
    return AuthMeResponse(user=_enrich_user_public(user, container))


@router.patch("/me", response_model=UserPublic)
def update_me(
    req: UserProfileUpdate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> UserPublic:
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
