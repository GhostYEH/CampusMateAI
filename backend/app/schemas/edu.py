"""CampusMate EduConnector Pydantic schemas。

统一教务数据契约：Profile / Schedule / Grade / Exam。
所有字段均允许 null，因为不同学校教务系统返回的字段差异很大，
DataNormalizer 负责把异构数据归一化到这些模型。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, SecretStr, field_validator


# ===== extra_info 敏感字段过滤 =====

# 绝不放入 extra_info 的键（大小写不敏感子串匹配）
_EXTRA_INFO_BLOCKED_SUBSTRINGS = (
    "cookie", "token", "csrf", "jsessionid", "session", "password", "passwd",
    "secret", "credential", "authorization", "auth_header", "api_key",
    "private_key", "access_key", "refresh_token", "bearer",
)

# 技术内部字段（精确匹配）
_EXTRA_INFO_BLOCKED_EXACT = {
    "provider", "adapter_id", "adapter", "row_index", "raw_id", "source_url",
    "internal_id", "html_selector", "raw_html", "raw_json", "raw_text",
    "source_hash", "sync_batch_id", "edu_system_id", "university_id",
    "user_id", "binding_id", "connection_id", "is_stale", "last_seen_at",
    "created_at", "updated_at", "id",
}


def sanitize_extra_info(raw: Any) -> Optional[Dict[str, Any]]:
    """过滤 extra_info：只保留适合用户查看的课程业务字段。

    - 拒绝 dict/list 以外的类型
    - 拒绝敏感键（cookie/token/session/password 等）
    - 拒绝技术内部字段（provider/adapter_id/raw_html 等）
    - 值只保留 str/int/float/bool/None（以及嵌套 dict/list，递归过滤）
    - 过滤后为空则返回 None
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None

    def _blocked_key(key: str) -> bool:
        if not isinstance(key, str):
            return True
        if key in _EXTRA_INFO_BLOCKED_EXACT:
            return True
        lowered = key.lower()
        for sub in _EXTRA_INFO_BLOCKED_SUBSTRINGS:
            if sub in lowered:
                return True
        return False

    def _clean_value(v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        if isinstance(v, dict):
            cleaned = {}
            for k, val in v.items():
                if _blocked_key(str(k)):
                    continue
                cv = _clean_value(val)
                if cv is not None:
                    cleaned[str(k)] = cv
            return cleaned if cleaned else None
        if isinstance(v, (list, tuple)):
            items = []
            for it in v:
                cv = _clean_value(it)
                if cv is not None:
                    items.append(cv)
            return items if items else None
        return None

    result: Dict[str, Any] = {}
    for key, value in raw.items():
        if _blocked_key(str(key)):
            continue
        cleaned = _clean_value(value)
        if cleaned is not None:
            result[str(key)] = cleaned
    return result if result else None


# ===== 教务系统配置 =====


class EduSystemOut(BaseModel):
    """edu_systems 出参（1:N）。"""
    id: str
    university_id: str
    system_key: str
    school_code: Optional[str] = None
    name: Optional[str] = None
    system_type: str
    provider: str
    provider_version: Optional[str] = None
    base_url: Optional[str] = None
    login_url: Optional[str] = None
    sso_url: Optional[str] = None
    vpn_url: Optional[str] = None
    auth_type: str
    login_execution_mode: str
    captcha_type: str
    requires_campus_network: bool = False
    requires_vpn: bool = False
    status: str
    verification_status: str
    supported_features: List[str] = Field(default_factory=list)
    last_verified_at: Optional[str] = None
    source: str
    notes: Optional[str] = None
    is_mock: bool = False
    created_at: str
    updated_at: str


class EduSystemUpsert(BaseModel):
    """管理员 upsert edu_systems 入参。"""
    system_key: str = Field(..., min_length=1, max_length=128)
    school_code: Optional[str] = None
    name: Optional[str] = None
    system_type: Optional[str] = None
    provider: Optional[str] = None
    provider_version: Optional[str] = None
    base_url: Optional[str] = None
    login_url: Optional[str] = None
    sso_url: Optional[str] = None
    vpn_url: Optional[str] = None
    auth_type: Optional[str] = None
    login_execution_mode: Optional[str] = None
    captcha_type: Optional[str] = None
    requires_campus_network: Optional[bool] = None
    requires_vpn: Optional[bool] = None
    status: Optional[str] = None
    verification_status: Optional[str] = None
    supported_features: Optional[List[str]] = None
    adapter_config: Optional[Dict[str, Any]] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    is_mock: Optional[bool] = None


class EduConnectionOut(BaseModel):
    """edu_connections 出参。"""
    id: str
    user_id: str
    edu_system_id: str
    university_id: str
    state: str
    provider: str
    login_execution_mode: str
    portal_url: Optional[str] = None
    external_student_id: Optional[str] = None
    external_student_name: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


class EduConnectionCreate(BaseModel):
    """创建连接请求。"""
    edu_system_id: str = Field(..., min_length=1, max_length=128)


class EduCookie(BaseModel):
    """A scoped browser cookie without pretending unavailable attributes are known."""

    name: str = Field(..., min_length=1, max_length=256)
    value: str = Field(..., max_length=4096)
    domain: Optional[str] = Field(None, max_length=253)
    path: Optional[str] = Field(None, max_length=1024)
    secure: Optional[bool] = None
    http_only: Optional[bool] = None
    same_site: Optional[Literal["Lax", "Strict", "None"]] = None
    expires: Optional[int] = Field(None, ge=0, le=253402300799)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if any(char in value for char in "()<>@,;:\\\"/[]?={} \t") or _has_control_characters(value):
            raise ValueError("cookie name contains invalid characters")
        return value

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        if _has_control_characters(value):
            raise ValueError("cookie value contains control characters")
        return value

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.lower().lstrip(".")
        if not normalized or "/" in normalized or _has_control_characters(normalized) or not re.fullmatch(r"[a-z0-9.-]+", normalized):
            raise ValueError("cookie domain is invalid")
        return normalized

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not value.startswith("/") or "?" in value or "#" in value or _has_control_characters(value):
            raise ValueError("cookie path is invalid")
        return value


def _has_control_characters(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


class EduConnectionContinue(BaseModel):
    """推进连接状态请求。

    支持两种登录路径：
    1. backend_http: username + password（后端代理登录）
    2. client_webview: cookies + current_url + user_agent（客户端 WebView 登录完成后回传）

    action 可选值：
    - CLIENT_WEBVIEW_COMPLETE: 客户端 WebView 登录完成，回传 cookies
    - POLL: 客户端轮询当前状态（不推进）
    - CANCEL: 取消连接
    - SUBMIT_WITH_CAPTCHA: 携带验证码提交登录（需配合 pre_login_token + captcha）
    """
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    captcha: Optional[str] = None
    sms_code: Optional[str] = None
    mfa_code: Optional[str] = None
    action: Optional[str] = None
    cookies: Optional[Dict[str, str]] = None
    cookie_jar: List[EduCookie] = Field(default_factory=list, max_length=64)
    current_url: Optional[str] = None
    user_agent: Optional[str] = Field(None, max_length=512)
    pre_login_token: Optional[str] = None
    verification_session_id: Optional[str] = None

    @field_validator("user_agent")
    @classmethod
    def validate_user_agent(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and _has_control_characters(value):
            raise ValueError("user_agent contains control characters")
        return value


class EduPreLoginResult(BaseModel):
    """预登录结果（获取验证码图片等预登录数据）。

    流程：
    1. 客户端调用 pre-login，后端 GET 登录页并提取验证码图片
    2. 后端将 cookie + csrftoken 绑定到 pre_login_token，返回图片 base64
    3. 客户端展示图片，用户输入验证码
    4. 客户端调用 continue(action=SUBMIT_WITH_CAPTCHA, pre_login_token, username, password, captcha)
    5. 后端复用预登录 cookie + csrftoken + 验证码完成登录 POST
    """
    pre_login_token: str
    verification_session_id: Optional[str] = None
    captcha_required: bool
    captcha_type: str = "none"
    challenge_type: str = "none"
    captcha_image_base64: Optional[str] = None
    captcha_mime_type: Optional[str] = None
    captcha_image_url: Optional[str] = None
    expires_at: str


class EduProbeRequest(BaseModel):
    """教务系统 URL 探测请求（不需要 university_id）。"""
    portal_url: str = Field(..., min_length=1, max_length=512)


class EduProbeResult(BaseModel):
    """教务系统 URL 探测结果。"""
    portal_url: str
    provider: str = "unknown"
    provider_confidence: float = 0.0
    reachable: bool = False
    http_status: Optional[int] = None
    final_url: Optional[str] = None
    title: Optional[str] = None
    is_edu_page: bool = False
    suggested_login_mode: str = "backend_http"
    challenge_type: str = "none"
    evidence: List[dict] = Field(default_factory=list)
    error: Optional[str] = None


class EduConnectionFromUrlRequest(BaseModel):
    """从教务系统 URL 创建连接（便捷流程，不需预先 edu_system_id）。

    university_id 可选；若未提供则使用当前用户的 university_id。
    """
    portal_url: str = Field(..., min_length=1, max_length=512)
    university_id: Optional[str] = None


class EduSystemConfigOut(BaseModel):
    """edu_system_configs 出参。

    所有 URL 字段都附带 url_status，明确标注是 verified / unverified / not_discovered，
    严禁编造 URL。
    """
    id: str
    university_id: str
    provider: str
    system_type: str
    academic_system_url: Optional[str] = None
    academic_system_url_status: str
    undergrad_system_url: Optional[str] = None
    undergrad_system_url_status: str
    postgrad_system_url: Optional[str] = None
    postgrad_system_url_status: str
    sso_url: Optional[str] = None
    sso_url_status: str
    cas_url: Optional[str] = None
    cas_url_status: str
    webvpn_url: Optional[str] = None
    webvpn_url_status: str
    login_method: str
    captcha_type: str
    requires_campus_network: Optional[bool] = None
    supported_features: List[str] = Field(default_factory=list)
    school_code: Optional[str] = None
    notes: Optional[str] = None
    data_source: str
    created_at: str
    updated_at: str


class EduSystemConfigUpsert(BaseModel):
    """管理员 upsert edu_system_configs 入参。

    university_id 必填，其余字段可选；未提供的字段保持原值。
    严禁编造 URL：若不确定，应留空并将对应 url_status 设为 not_discovered。
    """
    university_id: str = Field(..., min_length=1, max_length=128)
    provider: Optional[str] = None
    system_type: Optional[str] = None
    academic_system_url: Optional[str] = None
    academic_system_url_status: Optional[str] = None
    undergrad_system_url: Optional[str] = None
    undergrad_system_url_status: Optional[str] = None
    postgrad_system_url: Optional[str] = None
    postgrad_system_url_status: Optional[str] = None
    sso_url: Optional[str] = None
    sso_url_status: Optional[str] = None
    cas_url: Optional[str] = None
    cas_url_status: Optional[str] = None
    webvpn_url: Optional[str] = None
    webvpn_url_status: Optional[str] = None
    login_method: Optional[str] = None
    captcha_type: Optional[str] = None
    requires_campus_network: Optional[bool] = None
    supported_features: Optional[List[str]] = None
    school_code: Optional[str] = None
    notes: Optional[str] = None
    data_source: Optional[str] = None


# ===== 绑定 =====


class EduBindRequest(BaseModel):
    """学生绑定教务账号。

    username/password 仅用于一次认证，不会明文存储；
    认证成功后由 SessionManager 保存 session，credential_ref 引用安全存储。
    """
    username: str = Field(..., min_length=1, max_length=128)
    password: SecretStr = Field(...)
    system_type: str = Field("undergrad", description="undergrad / postgrad")


class EduBindingOut(BaseModel):
    """edu_bindings 出参（不含凭证）。"""
    id: str
    user_id: str
    edu_system_id: Optional[str] = None
    university_id: str
    provider: str
    supported_features: List[str] = Field(default_factory=list)
    system_type: str
    external_student_id: Optional[str] = None
    external_student_name: Optional[str] = None
    connection_status: str
    session_type: Optional[str] = None
    last_authenticated_at: Optional[str] = None
    session_expires_at: Optional[str] = None
    last_synced_at: Optional[str] = None
    last_sync_status: Optional[str] = None
    last_error: Optional[str] = None
    created_at: str
    updated_at: str


# ===== 统一教务数据契约 =====


class EduProfile(BaseModel):
    """学生基本信息（归一化后）。"""
    external_student_id: Optional[str] = None
    name: Optional[str] = None
    gender: Optional[str] = None
    college: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    class_name: Optional[str] = None
    enrollment_year: Optional[str] = None
    schooling_length: Optional[str] = None


class EduScheduleItem(BaseModel):
    """课表单条。

    字段策略：教务系统能提供多少有效信息就保存多少。
    所有字段可选 nullable，不同学校差异由 DataNormalizer 归一化。
    extra_info 保存标准模型未覆盖但对用户有意义的业务字段（已脱敏）。
    """
    course_name: Optional[str] = None
    course_code: Optional[str] = None
    teacher: Optional[str] = None
    teachers: Optional[List[str]] = None
    location: Optional[str] = None
    campus: Optional[str] = None
    building: Optional[str] = None
    classroom: Optional[str] = None
    weekday: Optional[int] = Field(None, ge=1, le=7)
    start_section: Optional[int] = None
    end_section: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    weeks: Optional[str] = None
    week_text: Optional[str] = None
    credit: Optional[float] = None
    course_nature: Optional[str] = None
    course_category: Optional[str] = None
    course_type: Optional[str] = None
    teaching_class: Optional[str] = None
    class_name: Optional[str] = None
    college: Optional[str] = None
    department: Optional[str] = None
    assessment_method: Optional[str] = None
    exam_type: Optional[str] = None
    total_hours: Optional[float] = None
    theory_hours: Optional[float] = None
    practice_hours: Optional[float] = None
    language: Optional[str] = None
    note: Optional[str] = None
    semester: Optional[str] = None
    semester_id: Optional[str] = None
    extra_info: Optional[Dict[str, Any]] = None


class EduSchedule(BaseModel):
    """课表（归一化后）。"""
    semester: Optional[str] = None
    items: List[EduScheduleItem] = Field(default_factory=list)


class EduGradeItem(BaseModel):
    """成绩单条。"""
    course_name: Optional[str] = None
    course_code: Optional[str] = None
    credit: Optional[float] = None
    score: Optional[str] = None
    grade_point: Optional[float] = None
    semester: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None


class EduGrade(BaseModel):
    """成绩（归一化后）。"""
    semester: Optional[str] = None
    gpa: Optional[float] = None
    items: List[EduGradeItem] = Field(default_factory=list)


class EduExamItem(BaseModel):
    """考试单条。"""
    course_name: Optional[str] = None
    course_code: Optional[str] = None
    exam_type: Optional[str] = None
    location: Optional[str] = None
    seat: Optional[str] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    semester: Optional[str] = None
    notes: Optional[str] = None


class EduExam(BaseModel):
    """考试安排（归一化后）。"""
    semester: Optional[str] = None
    items: List[EduExamItem] = Field(default_factory=list)


# ===== 同步记录 =====


class EduSyncRecordOut(BaseModel):
    id: str
    binding_id: str
    sync_type: str
    status: str
    items_count: int
    error_message: Optional[str] = None
    started_at: str
    finished_at: Optional[str] = None


class EduSyncResult(BaseModel):
    """同步操作结果。"""
    sync_type: str
    status: str
    items_count: int = 0
    error_message: Optional[str] = None
    profile: Optional[EduProfile] = None
    schedule: Optional[EduSchedule] = None
    grade: Optional[EduGrade] = None
    exam: Optional[EduExam] = None
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    failed: int = 0
    sync_batch_id: Optional[str] = None
    semester: Optional[str] = None
    persisted: bool = False


# ===== 探测 =====


class EduDetectResult(BaseModel):
    """SystemDetector 探测结果。

    根据学校信息识别教务厂商与系统类型，但不编造 URL。
    confidence 为 0.0~1.0 的浮点数，evidence 标注探测依据。
    """
    university_id: str
    provider: str
    system_type: str
    detected: bool
    confidence: float = 0.0
    evidence: List[dict] = Field(default_factory=list)
    detection_source: str = "UNKNOWN"
    reason: Optional[str] = None


# ===== 教务系统发现（Discovery）=====


class EduDiscoverySubmitUrlRequest(BaseModel):
    """用户手动提交教务系统 URL。"""
    university_id: str
    candidate_url: str = Field(..., min_length=1, max_length=512)


class EduDiscoverySubmitUrlResult(BaseModel):
    """用户提交 URL 后的检测结果。"""
    school_code: Optional[str] = None
    school_name: Optional[str] = None
    candidate_url: str
    provider: str = "UNKNOWN"
    provider_confidence: float = 0.0
    reachable: bool = False
    http_status: Optional[int] = None
    final_url: Optional[str] = None
    title: Optional[str] = None
    is_edu_page: bool = False
    evidence: List[dict] = Field(default_factory=list)
    verification_status: str = "CANDIDATE"
    saved: bool = False
    error: Optional[str] = None


class EduDiscoveryCandidateOut(BaseModel):
    """候选数据库条目出参（管理后台用）。"""
    school_code: str
    school_name: str
    candidate_url: str
    provider: str
    source_type: str
    source_url: Optional[str] = None
    confidence: float = 0.0
    verification_status: str
    http_status: Optional[int] = None
    final_url: Optional[str] = None
    title: Optional[str] = None
    evidence: List[dict] = Field(default_factory=list)
    last_checked_at: Optional[str] = None
    province: Optional[str] = None
    level: Optional[str] = None
    official_domain: Optional[str] = None
    wakeup_supported: bool = False
    wakeup_source_date: Optional[str] = None
    discovered_at: Optional[str] = None
    reason: Optional[str] = None
    review_action: Optional[str] = None


class EduDiscoveryReviewRequest(BaseModel):
    """管理后台审核操作。"""
    action: str = Field(..., description="confirm|reject|mark_historical|mark_intranet|reverify")


class EduDiscoveryStatsOut(BaseModel):
    """发现统计。"""
    universities_total: int = 0
    candidates_total: int = 0
    by_status: dict = Field(default_factory=dict)
    by_provider: dict = Field(default_factory=dict)
    wakeup_supported: int = 0
    verified_official: int = 0
    verified_live: int = 0
    candidate: int = 0
    not_discovered: int = 0
    dead: int = 0


__all__ = [
    "EduSystemConfigOut",
    "EduSystemConfigUpsert",
    "EduBindRequest",
    "EduBindingOut",
    "EduProfile",
    "EduScheduleItem",
    "EduSchedule",
    "EduGradeItem",
    "EduGrade",
    "EduExamItem",
    "EduExam",
    "EduSyncRecordOut",
    "EduSyncResult",
    "EduDetectResult",
    "EduDiscoverySubmitUrlRequest",
    "EduDiscoverySubmitUrlResult",
    "EduDiscoveryCandidateOut",
    "EduDiscoveryReviewRequest",
    "EduDiscoveryStatsOut",
    "EduCookie",
    "EduConnectionContinue",
    "EduPreLoginResult",
    "EduConnectionCreate",
    "EduConnectionOut",
    "EduProbeRequest",
    "EduProbeResult",
    "EduConnectionFromUrlRequest",
    "sanitize_extra_info",
]
