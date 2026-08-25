"""CampusMate EduConnector API 路由。

统一教务连接层端点：

- GET  /edu/detect?university_id=...           探测学校教务厂商
- GET  /edu/config/{university_id}             获取学校教务系统配置
- PUT  /edu/config/{university_id}             管理员更新教务系统配置
- GET  /edu/binding                            获取当前用户教务绑定
- POST /edu/bind                               绑定教务账号
- DELETE /edu/binding                          解绑
- POST /edu/sync/profile                       同步学生基本信息
- POST /edu/sync/schedule                      同步课表
- POST /edu/sync/grade                         同步成绩
- POST /edu/sync/exam                          同步考试安排
- GET  /edu/sync/records                       同步记录列表

所有端点均不返回密码或凭证明文。
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response

from ...core.exceptions import AppException, Forbidden, Unauthorized
from ...models.edu import (
    EDU_PROVIDER_UNKNOWN,
    EDU_PROVIDER_UNSUPPORTED,
    EduSystemConfigRow,
)
from ...models.multi_role import UserRow
from ...schemas.edu import (
    EduBindRequest,
    EduBindingOut,
    EduConnectionContinue,
    EduConnectionCreate,
    EduConnectionFromUrlRequest,
    EduConnectionOut,
    EduDetectResult,
    EduDiscoveryCandidateOut,
    EduDiscoveryReviewRequest,
    EduDiscoveryStatsOut,
    EduDiscoverySubmitUrlRequest,
    EduDiscoverySubmitUrlResult,
    EduPreLoginResult,
    EduProbeRequest,
    EduProbeResult,
    EduSyncRecordOut,
    EduSyncResult,
    EduSystemConfigOut,
    EduSystemConfigUpsert,
    EduSystemOut,
    EduSystemUpsert,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user, require_role


router = APIRouter(prefix="/edu", tags=["edu"])


class UniversityRequired(AppException):
    code = "UNIVERSITY_REQUIRED"
    http_status = 409
    message = "请先选择你的大学"


class EduBindingNotFound(AppException):
    code = "EDU_BINDING_NOT_FOUND"
    http_status = 404
    message = "未绑定教务账号"


class EduAdapterUnavailable(AppException):
    code = "EDU_ADAPTER_UNAVAILABLE"
    http_status = 503
    message = "教务系统 Adapter 暂不可用"


def _container() -> ServiceContainer:
    return get_container()


def _config_to_out(row: EduSystemConfigRow) -> EduSystemConfigOut:
    try:
        features = json.loads(row.supported_features) if row.supported_features else []
    except (TypeError, ValueError):
        features = []
    return EduSystemConfigOut(
        id=row.id,
        university_id=row.university_id,
        provider=row.provider,
        system_type=row.system_type,
        academic_system_url=row.academic_system_url,
        academic_system_url_status=row.academic_system_url_status,
        undergrad_system_url=row.undergrad_system_url,
        undergrad_system_url_status=row.undergrad_system_url_status,
        postgrad_system_url=row.postgrad_system_url,
        postgrad_system_url_status=row.postgrad_system_url_status,
        sso_url=row.sso_url,
        sso_url_status=row.sso_url_status,
        cas_url=row.cas_url,
        cas_url_status=row.cas_url_status,
        webvpn_url=row.webvpn_url,
        webvpn_url_status=row.webvpn_url_status,
        login_method=row.login_method,
        captcha_type=row.captcha_type,
        requires_campus_network=row.requires_campus_network,
        supported_features=features,
        school_code=row.school_code,
        notes=row.notes,
        data_source=row.data_source,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _binding_to_out(binding, *, supported_features: Optional[list[str]] = None) -> EduBindingOut:
    return EduBindingOut(
        id=binding.id,
        user_id=binding.user_id,
        edu_system_id=binding.edu_system_id,
        university_id=binding.university_id,
        provider=binding.provider,
        supported_features=supported_features or [],
        system_type=binding.system_type,
        external_student_id=binding.external_student_id,
        external_student_name=binding.external_student_name,
        connection_status=binding.connection_status,
        session_type=binding.session_type,
        last_authenticated_at=binding.last_authenticated_at,
        session_expires_at=binding.session_expires_at,
        last_synced_at=binding.last_synced_at,
        last_sync_status=binding.last_sync_status,
        last_error=binding.last_error,
        created_at=binding.created_at,
        updated_at=binding.updated_at,
    )


def _sync_record_to_out(record) -> EduSyncRecordOut:
    return EduSyncRecordOut(
        id=record.id,
        binding_id=record.binding_id,
        sync_type=record.sync_type,
        status=record.status,
        items_count=record.items_count,
        error_message=record.error_message,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


# ===== 探测 =====


@router.get("/detect", response_model=EduDetectResult)
def detect_university(
    university_id: str = Query(..., min_length=1, max_length=128),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduDetectResult:
    """探测学校教务厂商与系统类型（不编造 URL）。"""
    result = container.edu_connector.detect(university_id)
    return EduDetectResult(
        university_id=result.university_id,
        provider=result.provider,
        system_type=result.system_type,
        detected=result.detected,
        confidence=result.confidence,
        evidence=[{"source": e.source, "detail": e.detail, "weight": e.weight} for e in result.evidence],
        detection_source=result.detection_source,
        reason=result.reason,
    )


# ===== 配置 =====


@router.get("/config/{university_id}", response_model=EduSystemConfigOut)
def get_config(
    university_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduSystemConfigOut:
    """获取学校教务系统配置。

    若不存在，自动创建默认配置（所有 URL=null, url_status=not_discovered）。
    """
    row = container.edu_connector.ensure_config(university_id)
    return _config_to_out(row)


@router.put("/config/{university_id}", response_model=EduSystemConfigOut)
def upsert_config(
    university_id: str,
    request: EduSystemConfigUpsert,
    user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> EduSystemConfigOut:
    """管理员更新教务系统配置。

    严禁编造 URL：若不确定，应留空并将对应 url_status 设为 not_discovered。
    """
    if request.university_id != university_id:
        raise AppException(
            code="VALIDATION_FAILED",
            http_status=422,
            message="university_id 不一致",
        )
    kwargs = request.model_dump(exclude={"university_id"}, exclude_none=True)
    row = container.edu_connector.upsert_config(university_id, **kwargs)
    return _config_to_out(row)


# ===== 绑定 =====


@router.get("/binding", response_model=Optional[EduBindingOut])
def get_binding(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Optional[EduBindingOut]:
    """获取当前用户教务绑定（不含凭证）。"""
    binding = container.edu_connector.get_binding(user.id)
    return (
        _binding_to_out(
            binding,
            supported_features=container.edu_connector.get_provider_capabilities(binding.provider),
        )
        if binding
        else None
    )


@router.post("/bind", response_model=EduBindingOut)
async def bind(
    request: EduBindRequest,
    response: Response,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduBindingOut:
    """[deprecated] 兼容旧版一次性绑定接口。

    新客户端应使用 EduConnection：创建连接后调用 continue，认证成功再生成 EduBinding。
    本兼容端点仍委托同一个 EduConnector/Session/Binding 存储链路，并通过响应头提示迁移。

    需要先选择大学（PUT /profile/university）。
    username/password 仅用于一次认证，不会明文存储。
    """
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</api/v1/edu/connections/from-url>; rel="successor-version"'
    if not user.university_id:
        raise UniversityRequired()
    try:
        binding = await container.edu_connector.bind(
            user_id=user.id,
            university_id=user.university_id,
            username=request.username,
            password=request.password.get_secret_value(),
            system_type=request.system_type,
        )
    except PermissionError as e:
        raise AppException(
            code="EDU_LOGIN_FAILED",
            http_status=401,
            message=str(e) or "教务账号登录失败",
        )
    except AppException:
        raise
    except Exception as e:
        raise AppException(
            code="EDU_ADAPTER_UNAVAILABLE",
            http_status=503,
            message=f"教务系统 Adapter 暂不可用: {str(e)[:200]}",
        )
    return binding


@router.delete("/binding")
def unbind(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> dict:
    """解绑教务账号。"""
    container.edu_connector.unbind(user.id)
    return {"ok": True}


# ===== 同步 =====


def _require_binding_or_failed(user: UserRow, container: ServiceContainer):
    """获取绑定；未绑定返回 None（由调用方返回 failed EduSyncResult）。"""
    return container.edu_connector.get_binding(user.id)


@router.post("/sync/profile", response_model=EduSyncResult)
async def sync_profile(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduSyncResult:
    if _require_binding_or_failed(user, container) is None:
        return EduSyncResult(sync_type="profile", status="failed", error_message="未绑定教务账号")
    return await container.edu_connector.sync_profile(user.id)


@router.post("/sync/schedule", response_model=EduSyncResult)
async def sync_schedule(
    semester: Optional[str] = Query(None, max_length=64),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduSyncResult:
    if _require_binding_or_failed(user, container) is None:
        return EduSyncResult(sync_type="schedule", status="failed", error_message="未绑定教务账号")
    return await container.edu_connector.sync_schedule(user.id, semester=semester)


@router.post("/sync/grade", response_model=EduSyncResult)
async def sync_grade(
    semester: Optional[str] = Query(None, max_length=64),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduSyncResult:
    if _require_binding_or_failed(user, container) is None:
        return EduSyncResult(sync_type="grade", status="failed", error_message="未绑定教务账号")
    return await container.edu_connector.sync_grade(user.id, semester=semester)


@router.post("/sync/exam", response_model=EduSyncResult)
async def sync_exam(
    semester: Optional[str] = Query(None, max_length=64),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduSyncResult:
    if _require_binding_or_failed(user, container) is None:
        return EduSyncResult(sync_type="exam", status="failed", error_message="未绑定教务账号")
    return await container.edu_connector.sync_exam(user.id, semester=semester)


@router.get("/sync/records", response_model=list[EduSyncRecordOut])
def list_sync_records(
    limit: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> list[EduSyncRecordOut]:
    records = container.edu_connector.list_sync_records(user.id, limit=limit)
    return [_sync_record_to_out(r) for r in records]


# ===== 持久化教务数据读取（供三端展示真实课表/成绩）=====


@router.get("/schedule/semesters", response_model=list[str])
def list_schedule_semesters(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> list[str]:
    """列出已同步课表的所有学期。"""
    return container.edu_connector.list_schedule_semesters(user.id)


@router.get("/schedule/items")
def list_schedule_items(
    semester: Optional[str] = Query(None),
    include_stale: bool = Query(False),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> dict:
    """读取已持久化的课表条目。"""
    items = container.edu_connector.list_schedule_items(
        user.id, semester=semester, include_stale=include_stale
    )
    return {
        "semester": semester,
        "items_count": len(items),
        "items": [
            {
                "id": it.id,
                "semester": it.semester,
                "course_code": it.course_code,
                "course_name": it.course_name,
                "teacher": it.teacher,
                "teachers": it.teachers,
                "location": it.location,
                "campus": it.campus,
                "building": it.building,
                "classroom": it.classroom,
                "weekday": it.weekday,
                "start_section": it.start_section,
                "end_section": it.end_section,
                "start_time": it.start_time,
                "end_time": it.end_time,
                "weeks": it.weeks,
                "week_text": it.week_text,
                "credit": it.credit,
                "course_nature": it.course_nature,
                "course_category": it.course_category,
                "course_type": it.course_type,
                "teaching_class": it.teaching_class,
                "class_name": it.class_name,
                "college": it.college,
                "department": it.department,
                "assessment_method": it.assessment_method,
                "exam_type": it.exam_type,
                "total_hours": it.total_hours,
                "theory_hours": it.theory_hours,
                "practice_hours": it.practice_hours,
                "language": it.language,
                "note": it.note,
                "semester_id": it.semester_id,
                "extra_info": it.extra_info,
                "is_stale": it.is_stale,
                "last_seen_at": it.last_seen_at,
            }
            for it in items
        ],
    }


@router.get("/grade/semesters", response_model=list[str])
def list_grade_semesters(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> list[str]:
    """列出已同步成绩的所有学期。"""
    return container.edu_connector.list_grade_semesters(user.id)


@router.get("/grade/items")
def list_grade_items(
    semester: Optional[str] = Query(None),
    include_stale: bool = Query(False),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> dict:
    """读取已持久化的成绩条目。"""
    items = container.edu_connector.list_grade_items(
        user.id, semester=semester, include_stale=include_stale
    )
    return {
        "semester": semester,
        "items_count": len(items),
        "items": [
            {
                "id": it.id,
                "semester": it.semester,
                "course_code": it.course_code,
                "course_name": it.course_name,
                "credit": it.credit,
                "score": it.score,
                "grade_point": it.grade_point,
                "category": it.category,
                "status": it.status,
                "is_stale": it.is_stale,
                "last_seen_at": it.last_seen_at,
            }
            for it in items
        ],
    }


# ===== edu_systems (1:N) =====


def _system_to_out(row) -> EduSystemOut:
    try:
        features = json.loads(row.supported_features) if row.supported_features else []
    except (TypeError, ValueError):
        features = []
    return EduSystemOut(
        id=row.id,
        university_id=row.university_id,
        system_key=row.system_key,
        school_code=row.school_code,
        name=row.name,
        system_type=row.system_type,
        provider=row.provider,
        provider_version=row.provider_version,
        base_url=row.base_url,
        login_url=row.login_url,
        sso_url=row.sso_url,
        vpn_url=row.vpn_url,
        auth_type=row.auth_type,
        login_execution_mode=row.login_execution_mode,
        captcha_type=row.captcha_type,
        requires_campus_network=row.requires_campus_network,
        requires_vpn=row.requires_vpn,
        status=row.status,
        verification_status=row.verification_status,
        supported_features=features,
        last_verified_at=row.last_verified_at,
        source=row.source,
        notes=row.notes,
        is_mock=row.is_mock,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/systems/{university_id}", response_model=list[EduSystemOut])
def list_systems(
    university_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> list[EduSystemOut]:
    """列出学校的所有教务系统（1:N）。"""
    systems = container.edu_connector.list_systems(university_id)
    return [_system_to_out(s) for s in systems]


@router.post("/systems/{university_id}", response_model=EduSystemOut)
def upsert_system(
    university_id: str,
    request: EduSystemUpsert,
    user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> EduSystemOut:
    """管理员 upsert 教务系统。"""
    row = container.edu_connector.upsert_system(
        university_id=university_id,
        system_key=request.system_key,
        **request.model_dump(exclude={"system_key"}, exclude_none=True),
    )
    return _system_to_out(row)


# ===== edu_connections (状态机) =====


@router.post("/connections", response_model=EduConnectionOut)
def create_connection(
    request: EduConnectionCreate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduConnectionOut:
    """创建教务连接（返回 connection_id + 初始状态）。

    不默认上传账号密码。后续通过 /connections/{id}/continue 推进状态。
    """
    system = container.edu_connector.get_system_by_id(request.edu_system_id)
    if system is None:
        raise AppException(
            code="EDU_SYSTEM_NOT_FOUND",
            http_status=404,
            message="教务系统不存在",
        )
    if user.university_id is None:
        raise UniversityRequired()
    if system.university_id != user.university_id:
        raise Forbidden()
    detect = container.edu_connector.detect(system.university_id)
    conn = container.edu_connector.create_connection(
        user_id=user.id,
        edu_system_id=request.edu_system_id,
        university_id=system.university_id,
        provider=detect.provider,
        login_execution_mode=system.login_execution_mode,
    )
    return EduConnectionOut(
        id=conn.id,
        user_id=conn.user_id,
        edu_system_id=conn.edu_system_id,
        university_id=conn.university_id,
        state=conn.state,
        provider=conn.provider,
        login_execution_mode=conn.login_execution_mode,
        portal_url=conn.portal_url,
        external_student_id=conn.external_student_id,
        external_student_name=conn.external_student_name,
        error_code=conn.error_code,
        error_message=conn.error_message,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


@router.get("/connections/{connection_id}", response_model=EduConnectionOut)
def get_connection(
    connection_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduConnectionOut:
    conn = container.edu_connector.get_connection(connection_id)
    if conn is None:
        raise AppException(
            code="EDU_CONNECTION_NOT_FOUND",
            http_status=404,
            message="连接不存在",
        )
    if conn.user_id != user.id:
        raise Forbidden()
    return EduConnectionOut(
        id=conn.id,
        user_id=conn.user_id,
        edu_system_id=conn.edu_system_id,
        university_id=conn.university_id,
        state=conn.state,
        provider=conn.provider,
        login_execution_mode=conn.login_execution_mode,
        portal_url=conn.portal_url,
        external_student_id=conn.external_student_id,
        external_student_name=conn.external_student_name,
        error_code=conn.error_code,
        error_message=conn.error_message,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


@router.post("/connections/{connection_id}/pre-login", response_model=EduPreLoginResult)
async def pre_login(
    connection_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduPreLoginResult:
    """预登录：获取验证码图片等预登录数据。

    流程：
    1. 后端 GET 教务登录页，提取验证码图片
    2. 返回 pre_login_token + captcha_image_base64
    3. 客户端展示验证码图片，用户输入验证码
    4. 客户端调用 /continue(action=SUBMIT_WITH_CAPTCHA, pre_login_token, username, password, captcha)
    """
    conn = container.edu_connector.get_connection(connection_id)
    if conn is None:
        raise AppException(
            code="EDU_CONNECTION_NOT_FOUND",
            http_status=404,
            message="连接不存在",
        )
    if conn.user_id != user.id:
        raise Forbidden()
    result = await container.edu_connector.pre_login(connection_id=connection_id, user_id=user.id)
    return EduPreLoginResult(
        pre_login_token=result.get("pre_login_token") or "",
        verification_session_id=result.get("verification_session_id"),
        captcha_required=result.get("captcha_required", False),
        captcha_type=result.get("captcha_type", "none"),
        challenge_type=result.get("challenge_type", "none"),
        captcha_image_base64=result.get("captcha_image_base64"),
        captcha_mime_type=result.get("captcha_mime_type"),
        captcha_image_url=result.get("captcha_image_url"),
        expires_at=result.get("expires_at") or "",
    )


@router.post("/connections/{connection_id}/continue", response_model=EduConnectionOut)
async def continue_connection(
    connection_id: str,
    request: EduConnectionContinue,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduConnectionOut:
    """推进连接状态。

    支持两种路径：
    - server_credentials: username + password
    - client_webview: action=CLIENT_WEBVIEW_COMPLETE + cookies + current_url + user_agent
    - action=POLL: 轮询当前状态
    - action=CANCEL: 取消连接
    - action=SUBMIT_WITH_CAPTCHA: 携带验证码提交登录（需配合 pre_login_token + captcha）
    """
    conn = container.edu_connector.get_connection(connection_id)
    if conn is None:
        raise AppException(
            code="EDU_CONNECTION_NOT_FOUND",
            http_status=404,
            message="连接不存在",
        )
    if conn.user_id != user.id:
        raise Forbidden()
    new_state = await container.edu_connector.continue_connection(
        connection_id=connection_id,
        username=request.username,
        password=request.password.get_secret_value() if request.password else None,
        captcha=request.captcha,
        sms_code=request.sms_code,
        mfa_code=request.mfa_code,
        action=request.action,
        cookies=request.cookies,
        cookie_jar=[cookie.model_dump() for cookie in request.cookie_jar],
        current_url=request.current_url,
        user_agent=request.user_agent,
        pre_login_token=request.pre_login_token,
        verification_session_id=request.verification_session_id,
    )
    updated = container.edu_connector.get_connection(connection_id)
    return EduConnectionOut(
        id=updated.id,
        user_id=updated.user_id,
        edu_system_id=updated.edu_system_id,
        university_id=updated.university_id,
        state=updated.state,
        provider=updated.provider,
        login_execution_mode=updated.login_execution_mode,
        portal_url=updated.portal_url,
        external_student_id=updated.external_student_id,
        external_student_name=updated.external_student_name,
        error_code=updated.error_code,
        error_message=updated.error_message,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.post("/connections/from-url", response_model=EduConnectionOut)
async def create_connection_from_url(
    request: EduConnectionFromUrlRequest,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduConnectionOut:
    """从教务系统 URL 创建连接（便捷流程）。

    1. probe URL 检测 provider
    2. ensure_default_system 创建/复用 edu_system
    3. create_connection
    返回 connection（初始 state=idle），客户端再调 /continue 推进。
    """
    if not user.university_id:
        raise UniversityRequired()
    if request.university_id and request.university_id != user.university_id:
        raise Forbidden()
    university_id = user.university_id
    conn, system, probe = await container.edu_connector.create_connection_from_url(
        user_id=user.id,
        portal_url=request.portal_url,
        university_id=university_id,
    )
    return EduConnectionOut(
        id=conn.id,
        user_id=conn.user_id,
        edu_system_id=conn.edu_system_id,
        university_id=conn.university_id,
        state=conn.state,
        provider=conn.provider,
        login_execution_mode=conn.login_execution_mode,
        portal_url=conn.portal_url,
        external_student_id=conn.external_student_id,
        external_student_name=conn.external_student_name,
        error_code=conn.error_code,
        error_message=conn.error_message,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


@router.post("/discovery/probe", response_model=EduProbeResult)
async def discovery_probe(
    request: EduProbeRequest,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduProbeResult:
    """探测教务系统 URL（不需要 university_id）。

    只检测 provider/可达性/建议登录模式，不持久化任何数据。
    """
    result = await container.edu_connector.probe_portal(request.portal_url)
    return EduProbeResult(**result)


# ===== 教务系统发现（Discovery）=====

from ...services.edu.discovery_service import (
    submit_url as _discovery_submit_url,
    list_candidates as _discovery_list_candidates,
    review_candidate as _discovery_review_candidate,
    compute_stats as _discovery_compute_stats,
)


@router.post("/discovery/submit-url", response_model=EduDiscoverySubmitUrlResult)
async def discovery_submit_url(
    request: EduDiscoverySubmitUrlRequest,
    user: UserRow = Depends(current_user),
) -> EduDiscoverySubmitUrlResult:
    """用户手动提交教务系统 URL。

    检测 Provider → 尝试 HTTP 连接 → 保存为 USER_SUBMITTED 候选。
    不自动升级 VERIFIED，仅标 CANDIDATE（或 VERIFIED_LIVE 若检测到强信号）。
    """
    result = await _discovery_submit_url(
        university_id=request.university_id,
        candidate_url=request.candidate_url,
    )
    return EduDiscoverySubmitUrlResult(**result)


@router.get("/discovery/candidates", response_model=list[EduDiscoveryCandidateOut])
async def discovery_list_candidates(
    school_code: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    has_url: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: UserRow = Depends(require_role("admin")),
) -> list[EduDiscoveryCandidateOut]:
    """管理后台：列出候选（支持筛选与分页）。"""
    result = _discovery_list_candidates(
        school_code=school_code,
        status=status,
        provider=provider,
        has_url=has_url,
        page=page,
        page_size=page_size,
    )
    return [EduDiscoveryCandidateOut(**item) for item in result["items"]]


@router.post("/discovery/candidates/{school_code}/review")
async def discovery_review_candidate(
    school_code: str,
    request: EduDiscoveryReviewRequest,
    user: UserRow = Depends(require_role("admin")),
) -> dict:
    """管理后台：审核候选（confirm/reject/mark_historical/mark_intranet/reverify）。"""
    return _discovery_review_candidate(school_code, request.action)


@router.get("/discovery/stats", response_model=EduDiscoveryStatsOut)
async def discovery_stats(
    user: UserRow = Depends(require_role("admin")),
) -> EduDiscoveryStatsOut:
    """管理后台：发现统计。"""
    return EduDiscoveryStatsOut(**_discovery_compute_stats())


__all__ = ["router"]
