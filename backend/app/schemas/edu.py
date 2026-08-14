"""CampusMate EduConnector Pydantic schemas。

统一教务数据契约：Profile / Schedule / Grade / Exam。
所有字段均允许 null，因为不同学校教务系统返回的字段差异很大，
DataNormalizer 负责把异构数据归一化到这些模型。
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, SecretStr


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
    external_student_id: Optional[str] = None
    external_student_name: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


class EduConnectionCreate(BaseModel):
    """创建连接请求。"""
    edu_system_id: str = Field(..., min_length=1, max_length=128)


class EduConnectionContinue(BaseModel):
    """推进连接状态请求。"""
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    captcha: Optional[str] = None
    sms_code: Optional[str] = None
    mfa_code: Optional[str] = None
    action: Optional[str] = None


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
    """课表单条。"""
    course_name: Optional[str] = None
    course_code: Optional[str] = None
    teacher: Optional[str] = None
    location: Optional[str] = None
    weekday: Optional[int] = Field(None, ge=1, le=7)
    start_section: Optional[int] = None
    end_section: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    weeks: Optional[str] = None
    semester: Optional[str] = None


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
]