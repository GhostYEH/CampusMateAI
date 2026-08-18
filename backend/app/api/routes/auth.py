"""认证路由 — login / register / refresh / logout / me / admin 创建用户。

设计要点:
- 登录失败统一返回 401 INVALID_CREDENTIALS,不泄露用户名是否存在。
- access token 短有效期(默认 30 分钟),refresh token 较长有效期(默认 14 天)。
- refresh token 仅以哈希存入数据库,不可逆。
- logout 撤销 refresh token(可选撤销 access token: 当前实现不维护 access token 状态,
  因为其有效期短,泄露风险有限;若需要强制下线,可扩展 jti 黑名单)。
- POST /auth/register: 公开注册接口,仅允许 student 角色。
  admin 必须由管理员通过 /auth/admin/users 创建。
- POST /auth/admin/users: 仅 admin 可创建学生/管理员账号,执行完整真实业务流程,
  无任何"演示专用通道"。所有验收账号均通过此接口创建。

角色模型:
- CampusMate AI 只存在 student 与 admin 两类系统角色。
- 历史数据库中可能存在 role='teacher' 的旧记录,登录时按兼容处理(见 _issue_tokens),
  但不再允许新建 teacher 账号。
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, Response

from ...core.config import Settings, get_settings
from ...core.exceptions import (
    InvalidCredentials,
    StudentNumberExists,
    TeacherNumberExists,
    Unauthorized,
    UserNotFound,
    UsernameExists,
    ValidationFailed,
)
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
    Page,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserCreate,
    UserAdminUpdate,
    UserPublic,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user, get_settings_dep, require_role

router = APIRouter(prefix="/auth", tags=["auth"])


def _container() -> ServiceContainer:
    return get_container()


@router.post("/login", response_model=TokenPair)
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


@router.post("/register", response_model=UserPublic, status_code=201)
def register(
    req: RegisterRequest,
    container: ServiceContainer = Depends(_container),
) -> UserPublic:
    """公开注册接口(无需鉴权)。

    限制:
    - 仅允许注册 student 角色;admin 必须由管理员通过 /auth/admin/users 创建。
    - 注册成功后用户仍需走 /auth/login 登录获取 token(注册不自动登录)。
    - 用户名/学号唯一性校验同 admin_create_user。

    安全:
    - 密码以 PBKDF2-HMAC-SHA256 哈希存储,不返回密码或哈希。
    - 返回 UserPublic(不含 password_hash)。
    """
    # 角色一致性校验(student 不应携带 teacher_number)
    if req.role == "student" and req.teacher_number:
        raise ValidationFailed("学生角色不应携带 teacher_number")

    user_repo = container.user_repository
    # 唯一性校验
    if user_repo.get_user_by_username(req.username):
        raise UsernameExists()
    if req.student_number and user_repo.get_user_by_student_number(req.student_number):
        raise StudentNumberExists()
    if req.teacher_number and user_repo.get_user_by_teacher_number(req.teacher_number):
        raise TeacherNumberExists()

    hashed = hash_password(req.password)
    created = user_repo.create_user(
        username=req.username,
        password_hash=hashed,
        role=req.role,
        display_name=req.display_name,
        student_number=req.student_number,
        teacher_number=req.teacher_number,
        college=req.college,
        major=req.major,
        grade=req.grade,
    )
    return UserPublic(**created.to_public_dict())


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
    refresh_repo.revoke(token_hash)
    return _issue_tokens(user, settings, container)


@router.post("/logout")
def logout(
    req: LogoutRequest,
    request: Request,
    response: Response,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> dict:
    """撤销当前 refresh token(若有)，并撤销当前浏览器的可信设备凭据。"""
    if req.refresh_token:
        token_hash = hash_token(req.refresh_token)
        container.refresh_token_repository.revoke(token_hash)
    # 撤销当前浏览器的可信设备凭据(避免退出后又被自动登录)
    cookie_name = "campus_trusted_device"
    cookie_token = request.cookies.get(cookie_name)
    if cookie_token:
        try:
            container.trusted_device_repository.revoke_by_token_hash(hash_token(cookie_token))
        except Exception:
            pass
        response.delete_cookie(key=cookie_name, path="/api/v1/auth")
    return {"ok": True, "message": "已退出登录"}


@router.get("/me", response_model=AuthMeResponse)
def me(user: UserRow = Depends(current_user)) -> AuthMeResponse:
    return AuthMeResponse(user=UserPublic(**user.to_public_dict()))


@router.post("/admin/users", response_model=UserPublic, status_code=201)
def admin_create_user(
    req: UserCreate,
    user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> UserPublic:
    """管理员创建用户接口(仅 admin 角色)。

    用于在真实数据库中创建学生/管理员验收账号,执行完整真实业务流程,
    无任何"演示专用通道"或绕过认证的特殊账号。

    权限校验:
    - 仅 admin 角色可调用(require_role("admin"))
    - 用户名/学号唯一性校验
    - role 与 student_number 一致性校验

    安全:
    - 密码以 PBKDF2-HMAC-SHA256 哈希存储,不返回密码或哈希
    - 返回 UserPublic(不含 password_hash)
    """
    # 一致性校验: 角色与学号匹配
    if req.role == "student" and req.teacher_number:
        raise ValidationFailed("学生角色不应携带 teacher_number")
    if req.role == "admin" and (req.student_number or req.teacher_number):
        raise ValidationFailed("管理员角色不应携带学号或工号")

    user_repo = container.user_repository
    # 唯一性校验
    if user_repo.get_user_by_username(req.username):
        raise UsernameExists()
    if req.student_number and user_repo.get_user_by_student_number(req.student_number):
        raise StudentNumberExists()
    if req.teacher_number and user_repo.get_user_by_teacher_number(req.teacher_number):
        raise TeacherNumberExists()

    hashed = hash_password(req.password)
    created = user_repo.create_user(
        username=req.username,
        password_hash=hashed,
        role=req.role,
        display_name=req.display_name,
        student_number=req.student_number,
        teacher_number=req.teacher_number,
        college=req.college,
        major=req.major,
        grade=req.grade,
    )
    return UserPublic(**created.to_public_dict())


@router.get("/admin/users", response_model=Page)
def admin_list_users(
    role: str | None = Query(None, pattern="^(student|admin)$"),
    is_active: bool | None = Query(None),
    query: str | None = Query(None, max_length=128),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> Page:
    rows, total = container.user_repository.list_users(
        role=role,
        is_active=is_active,
        query=query,
        page=page,
        page_size=page_size,
    )
    items = [UserPublic(**row.to_public_dict()) for row in rows]
    return Page.from_rows(items, total=total, page=page, page_size=page_size)


@router.patch("/admin/users/{user_id}", response_model=UserPublic)
def admin_update_user(
    user_id: str,
    req: UserAdminUpdate,
    user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> UserPublic:
    target = container.user_repository.get_user_by_id(user_id)
    if target is None:
        raise UserNotFound()
    fields = req.model_dump(exclude_unset=True)
    if target.id == user.id:
        if fields.get("is_active") is False:
            raise ValidationFailed("不能停用当前登录的管理员账号")
        if "role" in fields and fields["role"] != "admin":
            raise ValidationFailed("不能修改当前登录账号的管理员角色")
    updated = container.user_repository.update_user(user_id, fields=fields)
    if updated is None:
        raise UserNotFound()
    # 停用用户时撤销其所有可信设备，防止停用后仍可通过 trusted device 登录
    if fields.get("is_active") is False:
        try:
            container.trusted_device_repository.revoke_all_for_user(user_id)
        except Exception:
            pass
    return UserPublic(**updated.to_public_dict())


def _issue_tokens(
    user: UserRow,
    settings: Settings,
    container: ServiceContainer,
) -> TokenPair:
    # 兼容旧 teacher 账号: CampusMate AI 只存在 student / admin 两类系统角色。
    # 历史数据库中可能存在 role='teacher' 的记录,登录时将其降级为 student,
    # 不修改数据库,仅在 JWT 中降级,避免旧数据导致登录失败。
    effective_role = user.role
    if effective_role == "teacher":
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
    public_user = UserPublic(**user.to_public_dict())
    public_user.name = user.display_name or user.username
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
