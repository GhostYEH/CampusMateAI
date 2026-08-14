"""CampusMate EduConnector 数据行模型与枚举。

架构：universities 1:N edu_systems（一所学校可有多个教务系统）。
用户通过 edu_bindings 绑定到 edu_system（而非直接绑定 university）。
连接流程通过 edu_connections 状态机推进，不默认上传账号密码。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ===== 教务厂商枚举 =====
EDU_PROVIDER_ZHENGFANG = "zhengfang"
EDU_PROVIDER_QIANGZHI = "qiangzhi"
EDU_PROVIDER_QINGGUO = "qingguo"
EDU_PROVIDER_MOCK = "mock"
EDU_PROVIDER_UNSUPPORTED = "unsupported"
EDU_PROVIDER_UNKNOWN = "unknown"

KNOWN_PROVIDERS = (
    EDU_PROVIDER_ZHENGFANG,
    EDU_PROVIDER_QIANGZHI,
    EDU_PROVIDER_QINGGUO,
)

# ===== 教务系统类型 =====
EDU_SYSTEM_UNDERGRAD = "undergrad"
EDU_SYSTEM_POSTGRAD = "postgrad"
EDU_SYSTEM_UNSUPPORTED = "unsupported"
EDU_SYSTEM_UNKNOWN = "unknown"

# ===== system_key 常量 =====
SYSTEM_KEY_UNDERGRADUATE_MAIN = "undergraduate-main"
SYSTEM_KEY_GRADUATE_MAIN = "graduate-main"
SYSTEM_KEY_LEGACY_UNDERGRADUATE = "legacy-undergraduate"
SYSTEM_KEY_SSO = "sso"

# ===== 登录方式 (auth_type) =====
LOGIN_CAS = "cas"
LOGIN_SSO = "sso"
LOGIN_FORM = "form"
LOGIN_WEBVPN = "webvpn"
LOGIN_UNKNOWN = "unknown"

# ===== LoginExecutionMode =====
LOGIN_EXEC_CLIENT_WEBVIEW = "client_webview"
LOGIN_EXEC_CLIENT_BROWSER = "client_browser"
LOGIN_EXEC_BACKEND_HTTP = "backend_http"
LOGIN_EXEC_BACKEND_BROWSER = "backend_browser"
LOGIN_EXEC_MANUAL = "manual"
LOGIN_EXEC_UNSUPPORTED = "unsupported"

ALL_LOGIN_EXEC_MODES = (
    LOGIN_EXEC_CLIENT_WEBVIEW,
    LOGIN_EXEC_CLIENT_BROWSER,
    LOGIN_EXEC_BACKEND_HTTP,
    LOGIN_EXEC_BACKEND_BROWSER,
    LOGIN_EXEC_MANUAL,
    LOGIN_EXEC_UNSUPPORTED,
)

# ===== 验证码情况 =====
CAPTCHA_NONE = "none"
CAPTCHA_IMAGE = "image"
CAPTCHA_SLIDE = "slide"
CAPTCHA_SMS = "sms"
CAPTCHA_UNKNOWN = "unknown"

# ===== URL 状态 =====
URL_VERIFIED = "verified"
URL_UNVERIFIED = "unverified"
URL_NOT_DISCOVERED = "not_discovered"

# ===== 同步状态 =====
SYNC_PENDING = "pending"
SYNC_RUNNING = "running"
SYNC_SUCCESS = "success"
SYNC_FAILED = "failed"
SYNC_PARTIAL = "partial"

# ===== 绑定/连接状态 =====
BINDING_UNBOUND = "unbound"
BINDING_ACTIVE = "active"
BINDING_EXPIRED = "expired"
BINDING_REVOKED = "revoked"
BINDING_ERROR = "error"

# ===== Connection 状态机 =====
CONN_IDLE = "idle"
CONN_CONNECTING = "connecting"
CONN_AUTH_REQUIRED = "auth_required"
CONN_WAITING_USER_LOGIN = "waiting_user_login"
CONN_NEED_CAPTCHA = "need_captcha"
CONN_NEED_SLIDER = "need_slider"
CONN_NEED_SMS = "need_sms"
CONN_NEED_MFA = "need_mfa"
CONN_NEED_USER_ACTION = "need_user_action"
CONN_AUTHENTICATED = "authenticated"
CONN_SYNCING = "syncing"
CONN_CONNECTED = "connected"
CONN_SESSION_EXPIRED = "session_expired"
CONN_AUTH_FAILED = "auth_failed"
CONN_NETWORK_ERROR = "network_error"
CONN_SYSTEM_UNAVAILABLE = "system_unavailable"
CONN_UNSUPPORTED = "unsupported"
CONN_ERROR = "error"

ALL_CONNECTION_STATES = (
    CONN_IDLE,
    CONN_CONNECTING,
    CONN_AUTH_REQUIRED,
    CONN_WAITING_USER_LOGIN,
    CONN_NEED_CAPTCHA,
    CONN_NEED_SLIDER,
    CONN_NEED_SMS,
    CONN_NEED_MFA,
    CONN_NEED_USER_ACTION,
    CONN_AUTHENTICATED,
    CONN_SYNCING,
    CONN_CONNECTED,
    CONN_SESSION_EXPIRED,
    CONN_AUTH_FAILED,
    CONN_NETWORK_ERROR,
    CONN_SYSTEM_UNAVAILABLE,
    CONN_UNSUPPORTED,
    CONN_ERROR,
)

# ===== Session 类型 =====
SESSION_BACKEND_COOKIE = "backend_cookie"
SESSION_CLIENT_COOKIE = "client_cookie"
SESSION_TOKEN = "token"
SESSION_CAS = "cas_session"
SESSION_CLIENT_ONLY = "client_only"
SESSION_MOCK = "mock"

# ===== EduSystem 状态 =====
EDU_SYSTEM_STATUS_ACTIVE = "active"
EDU_SYSTEM_STATUS_BETA = "beta"
EDU_SYSTEM_STATUS_DEPRECATED = "deprecated"
EDU_SYSTEM_STATUS_DISABLED = "disabled"

# ===== 验证状态 =====
VERIFICATION_VERIFIED = "verified"
VERIFICATION_UNVERIFIED = "unverified"
VERIFICATION_FAILED = "failed"

# ===== 检测来源 =====
DETECTION_CONFIG = "CONFIG"
DETECTION_FINGERPRINT = "FINGERPRINT"
DETECTION_MANUAL = "MANUAL"
DETECTION_UNKNOWN = "UNKNOWN"


@dataclass
class EduSystemConfigRow:
    """edu_system_configs 行（旧表，保留兼容，迁移到 edu_systems）。"""
    id: str
    university_id: str
    provider: str = EDU_PROVIDER_UNKNOWN
    system_type: str = EDU_SYSTEM_UNKNOWN
    academic_system_url: Optional[str] = None
    academic_system_url_status: str = URL_NOT_DISCOVERED
    undergrad_system_url: Optional[str] = None
    undergrad_system_url_status: str = URL_NOT_DISCOVERED
    postgrad_system_url: Optional[str] = None
    postgrad_system_url_status: str = URL_NOT_DISCOVERED
    sso_url: Optional[str] = None
    sso_url_status: str = URL_NOT_DISCOVERED
    cas_url: Optional[str] = None
    cas_url_status: str = URL_NOT_DISCOVERED
    webvpn_url: Optional[str] = None
    webvpn_url_status: str = URL_NOT_DISCOVERED
    login_method: str = LOGIN_UNKNOWN
    captcha_type: str = CAPTCHA_UNKNOWN
    requires_campus_network: Optional[bool] = None
    supported_features: str = "[]"
    school_code: Optional[str] = None
    notes: Optional[str] = None
    data_source: str = "unknown"
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "EduSystemConfigRow":
        return cls(
            id=row["id"],
            university_id=row["university_id"],
            provider=row["provider"],
            system_type=row["system_type"],
            academic_system_url=row["academic_system_url"],
            academic_system_url_status=row["academic_system_url_status"],
            undergrad_system_url=row["undergrad_system_url"],
            undergrad_system_url_status=row["undergrad_system_url_status"],
            postgrad_system_url=row["postgrad_system_url"],
            postgrad_system_url_status=row["postgrad_system_url_status"],
            sso_url=row["sso_url"],
            sso_url_status=row["sso_url_status"],
            cas_url=row["cas_url"],
            cas_url_status=row["cas_url_status"],
            webvpn_url=row["webvpn_url"],
            webvpn_url_status=row["webvpn_url_status"],
            login_method=row["login_method"],
            captcha_type=row["captcha_type"],
            requires_campus_network=(
                bool(row["requires_campus_network"])
                if row["requires_campus_network"] is not None
                else None
            ),
            supported_features=row["supported_features"],
            school_code=row["school_code"],
            notes=row["notes"],
            data_source=row["data_source"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class EduSystemRow:
    """edu_systems 行：一所学校的一个教务系统（1:N）。

    UNIQUE(university_id, system_key) 保证同一学校同一 system_key 唯一。
    """
    id: str
    university_id: str
    system_key: str
    school_code: Optional[str] = None
    name: Optional[str] = None
    system_type: str = EDU_SYSTEM_UNKNOWN
    provider: str = EDU_PROVIDER_UNKNOWN
    provider_version: Optional[str] = None
    base_url: Optional[str] = None
    login_url: Optional[str] = None
    sso_url: Optional[str] = None
    vpn_url: Optional[str] = None
    auth_type: str = LOGIN_UNKNOWN
    login_execution_mode: str = LOGIN_EXEC_UNSUPPORTED
    captcha_type: str = CAPTCHA_UNKNOWN
    requires_campus_network: bool = False
    requires_vpn: bool = False
    status: str = EDU_SYSTEM_STATUS_ACTIVE
    verification_status: str = VERIFICATION_UNVERIFIED
    supported_features: str = "[]"
    last_verified_at: Optional[str] = None
    source: str = "unknown"
    notes: Optional[str] = None
    is_mock: bool = False
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "EduSystemRow":
        return cls(
            id=row["id"],
            university_id=row["university_id"],
            system_key=row["system_key"],
            school_code=row["school_code"],
            name=row["name"],
            system_type=row["system_type"],
            provider=row["provider"],
            provider_version=row["provider_version"],
            base_url=row["base_url"],
            login_url=row["login_url"],
            sso_url=row["sso_url"],
            vpn_url=row["vpn_url"],
            auth_type=row["auth_type"],
            login_execution_mode=row["login_execution_mode"],
            captcha_type=row["captcha_type"],
            requires_campus_network=bool(row["requires_campus_network"]),
            requires_vpn=bool(row["requires_vpn"]),
            status=row["status"],
            verification_status=row["verification_status"],
            supported_features=row["supported_features"],
            last_verified_at=row["last_verified_at"],
            source=row["source"],
            notes=row["notes"],
            is_mock=bool(row["is_mock"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class EduBindingRow:
    """edu_bindings 行：用户绑定到一个 edu_system（而非仅 university）。

    UNIQUE(user_id, edu_system_id) 允许一个用户绑定多个教务系统。
    credential_ref 引用安全存储中的凭证（不直接存密码）。
    """
    id: str
    user_id: str
    edu_system_id: Optional[str]
    university_id: str
    provider: str
    system_type: str = EDU_SYSTEM_UNDERGRAD
    external_student_id: Optional[str] = None
    external_student_name: Optional[str] = None
    connection_status: str = BINDING_UNBOUND
    session_type: Optional[str] = None
    credential_ref: Optional[str] = None
    last_authenticated_at: Optional[str] = None
    session_expires_at: Optional[str] = None
    last_synced_at: Optional[str] = None
    last_sync_status: Optional[str] = None
    last_error: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "EduBindingRow":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            edu_system_id=row["edu_system_id"] if "edu_system_id" in row.keys() else None,
            university_id=row["university_id"],
            provider=row["provider"],
            system_type=row["system_type"],
            external_student_id=row["external_student_id"],
            external_student_name=row["external_student_name"],
            connection_status=row["connection_status"] if "connection_status" in row.keys() else row.get("status", BINDING_UNBOUND),
            session_type=row["session_type"] if "session_type" in row.keys() else None,
            credential_ref=row["credential_ref"],
            last_authenticated_at=row["last_authenticated_at"] if "last_authenticated_at" in row.keys() else None,
            session_expires_at=row["session_expires_at"] if "session_expires_at" in row.keys() else None,
            last_synced_at=row["last_synced_at"],
            last_sync_status=row["last_sync_status"],
            last_error=row["last_error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class EduConnectionRow:
    """edu_connections 行：连接流程状态机。"""
    id: str
    user_id: str
    edu_system_id: str
    university_id: str
    state: str = CONN_IDLE
    provider: str = EDU_PROVIDER_UNKNOWN
    login_execution_mode: str = LOGIN_EXEC_UNSUPPORTED
    credential_ref: Optional[str] = None
    external_student_id: Optional[str] = None
    external_student_name: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "EduConnectionRow":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            edu_system_id=row["edu_system_id"],
            university_id=row["university_id"],
            state=row["state"],
            provider=row["provider"],
            login_execution_mode=row["login_execution_mode"],
            credential_ref=row["credential_ref"],
            external_student_id=row["external_student_id"],
            external_student_name=row["external_student_name"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class EduSyncRecordRow:
    """edu_sync_records 行：同步审计记录。

    错误信息必须脱敏，不得存储 password/cookie/token/验证码/Authorization header/完整 HTML。
    """
    id: str
    binding_id: str
    user_id: str
    sync_type: str
    status: str = SYNC_PENDING
    items_count: int = 0
    adapter: Optional[str] = None
    adapter_version: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: str = ""
    finished_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "EduSyncRecordRow":
        return cls(
            id=row["id"],
            binding_id=row["binding_id"],
            user_id=row["user_id"],
            sync_type=row["sync_type"],
            status=row["status"],
            items_count=row["items_count"],
            adapter=row["adapter"] if "adapter" in row.keys() else None,
            adapter_version=row["adapter_version"] if "adapter_version" in row.keys() else None,
            error_code=row["error_code"] if "error_code" in row.keys() else None,
            error_message=row["error_message"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )


__all__ = [
    "EDU_PROVIDER_ZHENGFANG",
    "EDU_PROVIDER_QIANGZHI",
    "EDU_PROVIDER_QINGGUO",
    "EDU_PROVIDER_MOCK",
    "EDU_PROVIDER_UNSUPPORTED",
    "EDU_PROVIDER_UNKNOWN",
    "KNOWN_PROVIDERS",
    "EDU_SYSTEM_UNDERGRAD",
    "EDU_SYSTEM_POSTGRAD",
    "EDU_SYSTEM_UNSUPPORTED",
    "EDU_SYSTEM_UNKNOWN",
    "SYSTEM_KEY_UNDERGRADUATE_MAIN",
    "SYSTEM_KEY_GRADUATE_MAIN",
    "SYSTEM_KEY_LEGACY_UNDERGRADUATE",
    "SYSTEM_KEY_SSO",
    "LOGIN_CAS",
    "LOGIN_SSO",
    "LOGIN_FORM",
    "LOGIN_WEBVPN",
    "LOGIN_UNKNOWN",
    "LOGIN_EXEC_CLIENT_WEBVIEW",
    "LOGIN_EXEC_CLIENT_BROWSER",
    "LOGIN_EXEC_BACKEND_HTTP",
    "LOGIN_EXEC_BACKEND_BROWSER",
    "LOGIN_EXEC_MANUAL",
    "LOGIN_EXEC_UNSUPPORTED",
    "ALL_LOGIN_EXEC_MODES",
    "CAPTCHA_NONE",
    "CAPTCHA_IMAGE",
    "CAPTCHA_SLIDE",
    "CAPTCHA_SMS",
    "CAPTCHA_UNKNOWN",
    "URL_VERIFIED",
    "URL_UNVERIFIED",
    "URL_NOT_DISCOVERED",
    "SYNC_PENDING",
    "SYNC_RUNNING",
    "SYNC_SUCCESS",
    "SYNC_FAILED",
    "SYNC_PARTIAL",
    "BINDING_UNBOUND",
    "BINDING_ACTIVE",
    "BINDING_EXPIRED",
    "BINDING_REVOKED",
    "BINDING_ERROR",
    "CONN_IDLE",
    "CONN_CONNECTING",
    "CONN_AUTH_REQUIRED",
    "CONN_WAITING_USER_LOGIN",
    "CONN_NEED_CAPTCHA",
    "CONN_NEED_SLIDER",
    "CONN_NEED_SMS",
    "CONN_NEED_MFA",
    "CONN_NEED_USER_ACTION",
    "CONN_AUTHENTICATED",
    "CONN_SYNCING",
    "CONN_CONNECTED",
    "CONN_SESSION_EXPIRED",
    "CONN_AUTH_FAILED",
    "CONN_NETWORK_ERROR",
    "CONN_SYSTEM_UNAVAILABLE",
    "CONN_UNSUPPORTED",
    "CONN_ERROR",
    "ALL_CONNECTION_STATES",
    "SESSION_BACKEND_COOKIE",
    "SESSION_CLIENT_COOKIE",
    "SESSION_TOKEN",
    "SESSION_CAS",
    "SESSION_CLIENT_ONLY",
    "SESSION_MOCK",
    "EDU_SYSTEM_STATUS_ACTIVE",
    "EDU_SYSTEM_STATUS_BETA",
    "EDU_SYSTEM_STATUS_DEPRECATED",
    "EDU_SYSTEM_STATUS_DISABLED",
    "VERIFICATION_VERIFIED",
    "VERIFICATION_UNVERIFIED",
    "VERIFICATION_FAILED",
    "DETECTION_CONFIG",
    "DETECTION_FINGERPRINT",
    "DETECTION_MANUAL",
    "DETECTION_UNKNOWN",
    "EduSystemConfigRow",
    "EduSystemRow",
    "EduBindingRow",
    "EduConnectionRow",
    "EduSyncRecordRow",
]
