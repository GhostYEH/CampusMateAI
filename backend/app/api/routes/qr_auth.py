"""QR 扫码登录与可信设备路由。

接口概览:
- POST /auth/qr/create        公开，Web 创建 QR Login Session
- POST /auth/qr/scan          需登录(手机)，扫码绑定用户
- POST /auth/qr/confirm       需登录(手机)，确认登录 Web
- POST /auth/qr/cancel        需登录(手机)，取消
- GET  /auth/qr/{sid}/status  用 browser_token 查询状态
- POST /auth/qr/exchange      公开，Web 兑换登录态
- POST /auth/trusted-device/auto-login  公开，可信设备自动登录
- GET  /auth/trusted-devices  需登录，列出当前用户可信设备
- POST /auth/trusted-device/revoke      需登录，撤销可信设备

安全:
- 二维码只含 session_id + scan_token，不含 JWT/userId/密码。
- browser_token 不写入二维码，仅浏览器持有。
- scan/confirm/cancel 从手机 JWT 获取 user_id，不从 body 信任。
- exchange 原子迁移 CONFIRMED -> CONSUMED，防重放。
- trusted-device token 通过 HttpOnly Cookie 传递。
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Request, Response

from ...core.config import Settings
from ...core.exceptions import (
    QrAlreadyConfirmed,
    QrAlreadyConsumed,
    QrAlreadyScanned,
    QrBrowserTokenInvalid,
    QrCancelled,
    QrExpired,
    QrInvalid,
    QrNotConfirmed,
    QrRateLimited,
    QrUserMismatch,
    TrustedDeviceExpired,
    TrustedDeviceInvalid,
    TrustedDeviceRevoked,
    Unauthorized,
)
from ...core.qr_payload import build_qr_payload
from ...core.rate_limit import RateLimited, check_request_rate
from ...core.security import hash_token
from ..deps import current_user, get_settings_dep
from .auth import _issue_tokens
from ...models.multi_role import UserRow
from ...schemas.multi_role import TokenPair
from ...schemas.qr_auth import (
    QrCancelRequest,
    QrConfirmRequest,
    QrConfirmResponse,
    QrCreateRequest,
    QrCreateResponse,
    QrExchangeRequest,
    QrScanRequest,
    QrScanResponse,
    QrStatusResponse,
    TrustedDeviceAutoLoginRequest,
    TrustedDeviceListItem,
    TrustedDeviceListResponse,
    TrustedDeviceRevokeRequest,
)
from ...services.container import ServiceContainer, get_container

router = APIRouter(prefix="/auth", tags=["扫码登录"])


def _container() -> ServiceContainer:
    return get_container()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _parse_user_agent(ua: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """从 User-Agent 解析 browser_name / os_name / device_label。

    轻量解析，不引入 user-agents 库。
    """
    if not ua:
        return None, None, None
    browser_name = None
    os_name = None
    ua_lower = ua.lower()
    # Browser
    if "edg/" in ua_lower:
        browser_name = "Edge"
    elif "chrome/" in ua_lower and "chromium" not in ua_lower:
        browser_name = "Chrome"
    elif "firefox/" in ua_lower:
        browser_name = "Firefox"
    elif "safari/" in ua_lower and "chrome/" not in ua_lower:
        browser_name = "Safari"
    # OS
    if "windows" in ua_lower:
        os_name = "Windows"
    elif "mac os" in ua_lower or "macintosh" in ua_lower:
        os_name = "macOS"
    elif "linux" in ua_lower:
        os_name = "Linux"
    elif "android" in ua_lower:
        os_name = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        os_name = "iOS"
    device_label = f"{browser_name} · {os_name}" if browser_name and os_name else (browser_name or os_name)
    return browser_name, os_name, device_label


def _is_expired(expires_at: str) -> bool:
    try:
        return datetime.fromisoformat(expires_at) <= _now()
    except Exception:
        return True


def _set_trusted_device_cookie(
    response: Response,
    cookie_name: str,
    token: str,
    expires_days: int,
    secure: bool,
) -> None:
    """设置可信设备 HttpOnly Cookie。"""
    response.set_cookie(
        key=cookie_name,
        value=token,
        max_age=expires_days * 86400,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/api/v1/auth",
    )


def _clear_trusted_device_cookie(response: Response, cookie_name: str) -> None:
    response.delete_cookie(
        key=cookie_name,
        path="/api/v1/auth",
    )


# ===== QR Create =====


@router.post(
    "/qr/create",
    response_model=QrCreateResponse,
    summary="创建扫码登录会话",
    responses={
        429: {"description": "创建过于频繁（QR_RATE_LIMITED）；Retry-After 表示等待秒数"},
        200: {
            "description": "创建成功，返回会话标识、二维码内容与浏览器凭据",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "创建成功",
                            "value": {
                                "session_id": "qr_sess_demo001",
                                "qr_payload": "campusmate://qr-login?sid=qr_sess_demo001&token=scan_token_demo_0123456789abcdef",
                                "browser_token": "browser_token_demo_0123456789abcdef",
                                "status": "PENDING",
                                "expires_at": "2026-10-06T12:05:00+00:00",
                                "expires_in": 300,
                            },
                        }
                    }
                }
            },
        },
    },
)
def qr_create(
    req: Annotated[
        QrCreateRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "Web 创建会话",
                    "value": {
                        "device_id": "web_demo_device",
                        "browser_name": "Chrome",
                        "os_name": "Windows",
                    },
                }
            }
        ),
    ],
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    container: ServiceContainer = Depends(_container),
) -> QrCreateResponse:
    """Web 创建扫码登录会话，无需鉴权。

    - 二维码仅含 session_id 与 scan_token；browser_token 只返回给当前浏览器，不写入二维码。
    - 按来源地址与 device_id 双重限流，超限返回 429（QR_RATE_LIMITED）。
    """
    qr_repo = container.qr_login_session_repository
    now = _now()
    # 无条件按 ASGI peer 限流：清理会话、生成凭据和写库之前先拒绝。
    # 身份取自 request.client.host，不自行解析 X-Forwarded-For（转发头只有
    # 可信代理处理后才会反映到 ASGI 地址）。device_id 保持可选，下面的设备
    # 限制只是额外保护。进程内计数是单实例额度，不是跨实例全局配额。
    try:
        check_request_rate(
            request,
            "qr_create",
            limit=settings.qr_create_rate_max,
            window=settings.qr_create_rate_window_seconds,
        )
    except RateLimited as exc:
        raise QrRateLimited(exc.retry_after) from exc
    # 简单防刷：同一 device_id 在窗口期内限制创建次数
    if req.device_id:
        window_start = (now - timedelta(seconds=settings.qr_create_rate_window_seconds)).isoformat()
        recent = qr_repo.count_recent_by_device(req.device_id, window_start)
        if recent >= settings.qr_create_rate_max:
            raise QrRateLimited()
    # 惰性清理过期记录
    try:
        qr_repo.cleanup_expired(now.isoformat(), settings.qr_login_cleanup_batch)
    except Exception:
        pass
    # 生成随机凭据
    scan_token = secrets.token_urlsafe(32)  # 256 bit
    browser_token = secrets.token_urlsafe(32)  # 256 bit
    scan_token_hash = hash_token(scan_token)
    browser_token_hash = hash_token(browser_token)
    # 解析 User-Agent
    ua = request.headers.get("user-agent")
    browser_name, os_name, device_label = _parse_user_agent(ua)
    # 优先使用请求显式传入的 browser/os，否则用 UA 解析结果
    browser_name = req.browser_name or browser_name
    os_name = req.os_name or os_name
    if not device_label:
        device_label = f"{browser_name} · {os_name}" if browser_name and os_name else (browser_name or os_name)
    expires_at = (now + timedelta(seconds=settings.qr_login_expire_seconds)).isoformat()
    session = qr_repo.create_session(
        scan_token_hash=scan_token_hash,
        browser_token_hash=browser_token_hash,
        device_id=req.device_id,
        browser_name=browser_name,
        os_name=os_name,
        device_label=device_label,
        user_agent=ua,
        expires_at=expires_at,
    )
    qr_payload = build_qr_payload(session.id, scan_token)
    return QrCreateResponse(
        session_id=session.id,
        qr_payload=qr_payload,
        browser_token=browser_token,
        status=session.status,
        expires_at=session.expires_at,
        expires_in=settings.qr_login_expire_seconds,
    )


# ===== QR Scan =====


@router.post(
    "/qr/scan",
    response_model=QrScanResponse,
    summary="手机扫码绑定会话",
    responses={
        200: {
            "description": "扫码成功，会话进入 SCANNED 状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "扫码成功",
                            "value": {
                                "session_id": "qr_sess_demo001",
                                "browser_name": "Chrome",
                                "os_name": "Windows",
                                "device_label": "Chrome · Windows",
                                "expires_at": "2026-10-06T12:05:00+00:00",
                                "status": "SCANNED",
                            },
                        }
                    }
                }
            },
        }
    },
)
def qr_scan(
    req: Annotated[
        QrScanRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "手机扫码",
                    "value": {
                        "session_id": "qr_sess_demo001",
                        "scan_token": "scan_token_demo_0123456789abcdef0123456789abcdef",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> QrScanResponse:
    """手机扫码，将当前登录用户绑定到扫码会话，需登录。

    - 会话不存在或 scan_token 不匹配返回 400（QR_INVALID）；已过期返回 410（QR_EXPIRED）。
    - 已取消返回 409（QR_CANCELLED）；已确认或已被其他账号扫描返回 409（QR_ALREADY_SCANNED）；同一用户重复扫码幂等返回成功。
    """
    qr_repo = container.qr_login_session_repository
    session = qr_repo.get_session(req.session_id)
    if session is None:
        raise QrInvalid("二维码不存在。")
    # 校验 scan_token
    expected_hash = hash_token(req.scan_token)
    if not secrets.compare_digest(expected_hash, session.scan_token_hash):
        raise QrInvalid("scan token 不匹配。")
    # 检查过期
    if _is_expired(session.expires_at):
        qr_repo.mark_expired(session.id)
        raise QrExpired()
    # 检查状态
    if session.status == "CANCELLED":
        raise QrCancelled()
    if session.status in ("CONFIRMED", "CONSUMED"):
        raise QrAlreadyScanned("二维码已确认，不能重复扫描。")
    if session.status == "SCANNED":
        if session.user_id and session.user_id != user.id:
            raise QrAlreadyScanned("二维码已被其他账号扫描。")
        # 同一用户重复扫描，幂等返回
        return QrScanResponse(
            session_id=session.id,
            browser_name=session.browser_name,
            os_name=session.os_name,
            device_label=session.device_label,
            expires_at=session.expires_at,
            status="SCANNED",
        )
    # PENDING -> SCANNED
    updated = qr_repo.mark_scanned(session.id, user_id=user.id)
    if updated is None:
        # 并发竞争，重新查状态
        fresh = qr_repo.get_session(session.id)
        if fresh and fresh.status == "SCANNED":
            if fresh.user_id != user.id:
                raise QrAlreadyScanned("二维码已被其他账号扫描。")
            return QrScanResponse(
                session_id=fresh.id,
                browser_name=fresh.browser_name,
                os_name=fresh.os_name,
                device_label=fresh.device_label,
                expires_at=fresh.expires_at,
                status="SCANNED",
            )
        raise QrAlreadyScanned()
    return QrScanResponse(
        session_id=updated.id,
        browser_name=updated.browser_name,
        os_name=updated.os_name,
        device_label=updated.device_label,
        expires_at=updated.expires_at,
        status="SCANNED",
    )


# ===== QR Confirm =====


@router.post(
    "/qr/confirm",
    response_model=QrConfirmResponse,
    summary="手机确认扫码登录",
    responses={
        200: {
            "description": "确认成功，会话进入 CONFIRMED 状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "确认成功",
                            "value": {
                                "session_id": "qr_sess_demo001",
                                "status": "CONFIRMED",
                                "trust_device": False,
                            },
                        }
                    }
                }
            },
        }
    },
)
def qr_confirm(
    req: Annotated[
        QrConfirmRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "手机确认登录",
                    "value": {
                        "session_id": "qr_sess_demo001",
                        "scan_token": "scan_token_demo_0123456789abcdef0123456789abcdef",
                        "trust_device": False,
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> QrConfirmResponse:
    """手机确认登录 Web，需登录。

    - 会话不存在或 scan_token 不匹配返回 400（QR_INVALID）；已过期返回 410（QR_EXPIRED）。
    - 已取消返回 409（QR_CANCELLED）；已消费返回 409（QR_ALREADY_CONSUMED）；确认用户与扫描用户不一致返回 403（QR_USER_MISMATCH）。
    """
    qr_repo = container.qr_login_session_repository
    session = qr_repo.get_session(req.session_id)
    if session is None:
        raise QrInvalid("二维码不存在。")
    # 校验 scan_token
    expected_hash = hash_token(req.scan_token)
    if not secrets.compare_digest(expected_hash, session.scan_token_hash):
        raise QrInvalid("scan token 不匹配。")
    # 检查过期
    if _is_expired(session.expires_at):
        qr_repo.mark_expired(session.id)
        raise QrExpired()
    # 检查状态
    if session.status == "CANCELLED":
        raise QrCancelled()
    if session.status == "CONSUMED":
        raise QrAlreadyConsumed()
    if session.status == "CONFIRMED":
        # 幂等：同一用户重复确认
        if session.user_id != user.id:
            raise QrUserMismatch()
        return QrConfirmResponse(
            session_id=session.id,
            status="CONFIRMED",
            trust_device=session.trust_device,
        )
    if session.status != "SCANNED":
        raise QrInvalid("二维码尚未扫描。")
    # 校验确认用户与扫描用户一致
    if session.user_id != user.id:
        raise QrUserMismatch()
    # SCANNED -> CONFIRMED
    updated = qr_repo.mark_confirmed(session.id, user_id=user.id, trust_device=req.trust_device)
    if updated is None:
        raise QrInvalid("状态迁移失败，二维码可能已被其他操作修改。")
    return QrConfirmResponse(
        session_id=updated.id,
        status="CONFIRMED",
        trust_device=updated.trust_device,
    )


# ===== QR Cancel =====


@router.post(
    "/qr/cancel",
    summary="手机取消扫码登录",
    responses={
        200: {
            "description": "取消成功，会话进入 CANCELLED 状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "取消成功",
                            "value": {"ok": True, "status": "CANCELLED"},
                        }
                    }
                }
            },
        }
    },
)
def qr_cancel(
    req: Annotated[
        QrCancelRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "手机取消登录",
                    "value": {
                        "session_id": "qr_sess_demo001",
                        "scan_token": "scan_token_demo_0123456789abcdef0123456789abcdef",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> dict:
    """手机取消扫码登录，需登录。

    - 会话不存在或 scan_token 不匹配返回 400（QR_INVALID）。
    - 已确认返回 409（QR_ALREADY_CONFIRMED）；已消费返回 409（QR_ALREADY_CONSUMED）；已取消则幂等返回成功。
    """
    qr_repo = container.qr_login_session_repository
    session = qr_repo.get_session(req.session_id)
    if session is None:
        raise QrInvalid("二维码不存在。")
    # 校验 scan_token
    expected_hash = hash_token(req.scan_token)
    if not secrets.compare_digest(expected_hash, session.scan_token_hash):
        raise QrInvalid("scan token 不匹配。")
    updated = qr_repo.mark_cancelled(session.id, user_id=user.id)
    if updated is None:
        # 可能已确认/已消费/已过期
        if session.status == "CONFIRMED":
            raise QrAlreadyConfirmed("二维码已确认，不能取消。")
        if session.status == "CONSUMED":
            raise QrAlreadyConsumed()
        if session.status == "CANCELLED":
            return {"ok": True, "status": "CANCELLED"}
        raise QrInvalid("当前状态不允许取消。")
    return {"ok": True, "status": "CANCELLED"}


# ===== QR Status =====


@router.get(
    "/qr/{session_id}/status",
    response_model=QrStatusResponse,
    summary="查询扫码会话状态",
    responses={
        200: {
            "description": "查询成功，返回会话当前状态与过期时间",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "查询成功",
                            "value": {
                                "session_id": "qr_sess_demo001",
                                "status": "SCANNED",
                                "expires_at": "2026-10-06T12:05:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def qr_status(
    session_id: str,
    request: Request,
    container: ServiceContainer = Depends(_container),
) -> QrStatusResponse:
    """Web 用 browser_token 查询扫码会话状态。

    - browser_token 通过 Authorization: Bearer 或 X-Browser-Token 头传递，避免仅知道 session_id 的人查询状态。
    - 缺少或错误凭据返回 401（QR_BROWSER_TOKEN_INVALID）；会话不存在返回 400（QR_INVALID）。
    """
    browser_token = request.headers.get("x-browser-token")
    if not browser_token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            browser_token = auth[7:]
    if not browser_token:
        raise QrBrowserTokenInvalid("缺少 browser_token。")
    qr_repo = container.qr_login_session_repository
    session = qr_repo.get_session(session_id)
    if session is None:
        raise QrInvalid("二维码不存在。")
    # 校验 browser_token
    expected_hash = hash_token(browser_token)
    if not secrets.compare_digest(expected_hash, session.browser_token_hash):
        raise QrBrowserTokenInvalid()
    # 惰性过期
    status = session.status
    if status in ("PENDING", "SCANNED") and _is_expired(session.expires_at):
        qr_repo.mark_expired(session.id)
        status = "EXPIRED"
    return QrStatusResponse(
        session_id=session.id,
        status=status,
        expires_at=session.expires_at,
    )


# ===== QR Exchange =====


@router.post(
    "/qr/exchange",
    response_model=TokenPair,
    summary="兑换扫码登录令牌",
    responses={
        200: {
            "description": "兑换成功，返回访问令牌与刷新令牌",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "兑换成功",
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
def qr_exchange(
    req: Annotated[
        QrExchangeRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "Web 兑换登录态",
                    "value": {
                        "session_id": "qr_sess_demo001",
                        "browser_token": "browser_token_demo_0123456789abcdef",
                    },
                }
            }
        ),
    ],
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings_dep),
    container: ServiceContainer = Depends(_container),
) -> TokenPair:
    """Web 用 browser_token 兑换登录态，无需鉴权。

    - 原子迁移 CONFIRMED -> CONSUMED，防止重放；若 trust_device=true 同时建立可信设备 Cookie。
    - 未确认返回 409（QR_NOT_CONFIRMED）；已消费返回 409（QR_ALREADY_CONSUMED）；已取消返回 409（QR_CANCELLED）；已过期返回 410（QR_EXPIRED）；凭据无效返回 401（QR_BROWSER_TOKEN_INVALID）。
    """
    qr_repo = container.qr_login_session_repository
    session = qr_repo.get_session(req.session_id)
    if session is None:
        raise QrInvalid("二维码不存在。")
    # 校验 browser_token
    expected_hash = hash_token(req.browser_token)
    if not secrets.compare_digest(expected_hash, session.browser_token_hash):
        raise QrBrowserTokenInvalid()
    # 检查状态
    if session.status == "CANCELLED":
        raise QrCancelled()
    if session.status in ("PENDING", "SCANNED"):
        # 惰性过期
        if _is_expired(session.expires_at):
            qr_repo.mark_expired(session.id)
            raise QrExpired()
        raise QrNotConfirmed()
    if session.status == "EXPIRED":
        raise QrExpired()
    if session.status == "CONSUMED":
        raise QrAlreadyConsumed()
    if session.status != "CONFIRMED":
        raise QrInvalid(f"二维码状态异常: {session.status}")
    # 检查过期
    if _is_expired(session.expires_at):
        qr_repo.mark_expired(session.id)
        raise QrExpired()
    # 原子迁移 CONFIRMED -> CONSUMED
    consumed = qr_repo.mark_consumed(session.id, browser_token_hash=expected_hash)
    if consumed is None:
        # 并发竞争：可能已被消费
        fresh = qr_repo.get_session(session.id)
        if fresh and fresh.status == "CONSUMED":
            raise QrAlreadyConsumed()
        raise QrInvalid("兑换失败，二维码状态可能已变更。")
    # 获取用户
    user = container.user_repository.get_user_by_id(consumed.user_id or "")
    if user is None or not user.is_active:
        raise Unauthorized("用户不存在或已停用")
    # 复用现有 _issue_tokens 签发正常 TokenPair
    token_pair = _issue_tokens(user, settings, container)
    # 若 trust_device=true，建立可信设备
    if consumed.trust_device:
        _establish_trusted_device(
            request=request,
            response=response,
            user=user,
            session=consumed,
            settings=settings,
            container=container,
        )
    return token_pair


def _establish_trusted_device(
    *,
    request: Request,
    response: Response,
    user: UserRow,
    session,
    settings: Settings,
    container: ServiceContainer,
) -> None:
    """为当前 Web 浏览器建立可信设备记录并设置 Cookie。"""
    trusted_repo = container.trusted_device_repository
    # 生成可信设备 token（256 bit）
    trusted_token = secrets.token_urlsafe(32)
    token_hash = hash_token(trusted_token)
    # device_id：优先用 session.device_id，否则用 user_id + browser 派生
    device_id = session.device_id or f"web_{hashlib.sha256((user.id + (session.browser_name or '') + (session.os_name or '')).encode()).hexdigest()[:16]}"
    expires_at = (_now() + timedelta(days=settings.trusted_device_expire_days)).isoformat()
    # 若已存在同 user + device 的有效记录，先撤销旧的再建新的
    existing = trusted_repo.get_active_by_user_and_device(user.id, device_id)
    if existing:
        trusted_repo.revoke(existing.id)
    trusted_repo.create_device(
        user_id=user.id,
        device_id=device_id,
        token_hash=token_hash,
        device_name=session.device_label,
        browser_name=session.browser_name,
        os_name=session.os_name,
        user_agent=session.user_agent,
        expires_at=expires_at,
    )
    _set_trusted_device_cookie(
        response=response,
        cookie_name=settings.trusted_device_cookie_name,
        token=trusted_token,
        expires_days=settings.trusted_device_expire_days,
        secure=settings.trusted_device_cookie_secure,
    )


# ===== Trusted Device Auto Login =====


@router.post(
    "/trusted-device/auto-login",
    response_model=TokenPair,
    summary="可信设备自动登录",
    responses={
        200: {
            "description": "自动登录成功，返回访问令牌与刷新令牌",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "自动登录成功",
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
def trusted_device_auto_login(
    req: Annotated[
        TrustedDeviceAutoLoginRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "可信设备自动登录",
                    "value": {"device_id": "web_demo_device"},
                }
            }
        ),
    ],
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings_dep),
    container: ServiceContainer = Depends(_container),
) -> TokenPair:
    """浏览器使用可信设备 Cookie 自动登录，无需鉴权。

    - 凭据由 HttpOnly Cookie 携带，缺失或无效返回 401（TRUSTED_DEVICE_INVALID）；已撤销返回 401（TRUSTED_DEVICE_REVOKED）；已过期返回 401（TRUSTED_DEVICE_EXPIRED）。
    - 校验失败会清除对应 Cookie。
    """
    cookie_name = settings.trusted_device_cookie_name
    trusted_token = request.cookies.get(cookie_name)
    if not trusted_token:
        raise TrustedDeviceInvalid("缺少可信设备凭据。")
    trusted_repo = container.trusted_device_repository
    token_hash = hash_token(trusted_token)
    device = trusted_repo.get_by_token_hash(token_hash)
    if device is None:
        _clear_trusted_device_cookie(response, cookie_name)
        raise TrustedDeviceInvalid()
    if device.revoked_at is not None:
        _clear_trusted_device_cookie(response, cookie_name)
        raise TrustedDeviceRevoked()
    if _is_expired(device.expires_at):
        _clear_trusted_device_cookie(response, cookie_name)
        raise TrustedDeviceExpired()
    user = container.user_repository.get_user_by_id(device.user_id)
    if user is None or not user.is_active:
        _clear_trusted_device_cookie(response, cookie_name)
        raise Unauthorized("用户不存在或已停用")
    # 更新 last_used_at
    trusted_repo.update_last_used(device.id)
    # 签发正常 TokenPair
    return _issue_tokens(user, settings, container)


# ===== Trusted Device 管理 =====


@router.get(
    "/trusted-devices",
    response_model=TrustedDeviceListResponse,
    summary="列出可信设备",
    responses={
        200: {
            "description": "返回当前用户所有有效可信设备，is_current 标记当前浏览器",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "查询成功",
                            "value": {
                                "devices": [
                                    {
                                        "id": "td_demo001",
                                        "device_id": "web_demo_device",
                                        "device_name": "Chrome · Windows",
                                        "browser_name": "Chrome",
                                        "os_name": "Windows",
                                        "created_at": "2026-09-01T08:00:00+00:00",
                                        "last_used_at": "2026-10-06T11:00:00+00:00",
                                        "expires_at": "2026-10-13T08:00:00+00:00",
                                        "is_current": True,
                                    }
                                ]
                            },
                        }
                    }
                }
            },
        }
    },
)
def list_trusted_devices(
    request: Request,
    user: UserRow = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    container: ServiceContainer = Depends(_container),
) -> TrustedDeviceListResponse:
    """列出当前用户的有效可信设备，需登录。

    - 仅返回未撤销且未过期的记录，按创建时间倒序。
    - 与当前浏览器 Cookie 匹配的设备 is_current 为 true。
    """
    trusted_repo = container.trusted_device_repository
    # 查询当前用户所有未删除的可信设备
    now = _now_iso()
    with container.db.query() as conn:
        cur = conn.execute(
            """
            SELECT * FROM trusted_devices
            WHERE user_id = ? AND revoked_at IS NULL AND expires_at > ?
            ORDER BY created_at DESC
            """,
            (user.id, now),
        )
        rows = cur.fetchall()
    # 判断哪个是当前浏览器（通过 cookie token hash 匹配）
    from ...models.qr_auth import TrustedDeviceRow
    current_token_hash = None
    cookie_token = request.cookies.get(settings.trusted_device_cookie_name)
    if cookie_token:
        current_token_hash = hash_token(cookie_token)
    items = []
    for row in rows:
        dev = TrustedDeviceRow.from_row(row)
        items.append(TrustedDeviceListItem(
            id=dev.id,
            device_id=dev.device_id,
            device_name=dev.device_name,
            browser_name=dev.browser_name,
            os_name=dev.os_name,
            created_at=dev.created_at,
            last_used_at=dev.last_used_at,
            expires_at=dev.expires_at,
            is_current=(current_token_hash is not None and dev.token_hash == current_token_hash),
        ))
    return TrustedDeviceListResponse(devices=items)


@router.post(
    "/trusted-device/revoke",
    summary="撤销可信设备",
    responses={
        200: {
            "description": "撤销完成，返回操作结果",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "撤销成功",
                            "value": {"ok": True, "message": "已撤销设备"},
                        }
                    }
                }
            },
        }
    },
)
def revoke_trusted_device(
    req: Annotated[
        TrustedDeviceRevokeRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "撤销指定设备",
                    "value": {"device_id": "web_demo_device"},
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
    """撤销可信设备，需登录。

    - req.device_id 为空时撤销当前 Cookie 对应的设备（即退出登录时撤销本浏览器）。
    - 撤销当前设备会同时清除 Cookie；无凭据时幂等返回成功。
    """
    trusted_repo = container.trusted_device_repository
    cookie_name = settings.trusted_device_cookie_name
    if not req.device_id:
        # 撤销当前 Cookie 对应设备
        cookie_token = request.cookies.get(cookie_name)
        if not cookie_token:
            return {"ok": True, "message": "无当前设备凭据"}
        token_hash = hash_token(cookie_token)
        trusted_repo.revoke_by_token_hash(token_hash, user_id=user.id)
        _clear_trusted_device_cookie(response, cookie_name)
        return {"ok": True, "message": "已撤销当前设备"}
    # 撤销指定 device_id 的所有有效记录
    now = _now_iso()
    with container.db.transaction() as conn:
        conn.execute(
            """
            UPDATE trusted_devices SET revoked_at = ?
            WHERE user_id = ? AND device_id = ? AND revoked_at IS NULL
            """,
            (now, user.id, req.device_id),
        )
    # 若撤销的是当前设备，清除 Cookie
    cookie_token = request.cookies.get(cookie_name)
    if cookie_token:
        current_hash = hash_token(cookie_token)
        current_dev = trusted_repo.get_by_token_hash(current_hash)
        if current_dev and current_dev.device_id == req.device_id:
            _clear_trusted_device_cookie(response, cookie_name)
    return {"ok": True, "message": "已撤销设备"}


__all__ = ["router"]
