"""CampusMate EduConnector API 路由。

统一教务连接层端点：

- GET  /edu/detect?university_id=...           探测学校教务厂商
- GET  /edu/config/{university_id}             获取学校教务系统配置
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
import logging
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Query, Response

from ...core.exceptions import AppException, Forbidden
from ...models.edu import (
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
    EduDiscoverySubmitUrlRequest,
    EduDiscoverySubmitUrlResult,
    EduPreLoginResult,
    EduProbeRequest,
    EduProbeResult,
    EduSyncRecordOut,
    EduSyncResult,
    EduSystemConfigOut,
    EduSystemOut,
)

logger = logging.getLogger(__name__)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user


router = APIRouter(prefix="/edu", tags=["教务"])


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


def _connection_to_out(conn, container: ServiceContainer) -> EduConnectionOut:
    return EduConnectionOut(
        id=conn.id,
        user_id=conn.user_id,
        edu_system_id=conn.edu_system_id,
        university_id=conn.university_id,
        state=conn.state,
        provider=conn.provider,
        login_execution_mode=conn.login_execution_mode,
        portal_url=conn.portal_url,
        allowed_origins=container.edu_connector.allowed_origins_for_connection(conn.id),
        external_student_id=conn.external_student_id,
        external_student_name=conn.external_student_name,
        error_code=conn.error_code,
        error_message=conn.error_message,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
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


@router.get(
    "/detect",
    response_model=EduDetectResult,
    summary="探测学校教务厂商",
    responses={
        200: {
            "description": "教务厂商与系统类型探测结果（不编造 URL）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "命中已配置教务系统",
                            "value": {
                                "university_id": "uni_4111010001",
                                "provider": "zhengfang",
                                "system_type": "undergrad",
                                "detected": True,
                                "confidence": 0.86,
                                "evidence": [
                                    {
                                        "source": "CONFIG",
                                        "detail": "edu_systems 命中已配置系统",
                                        "weight": 0.6,
                                    }
                                ],
                                "detection_source": "CONFIG",
                                "reason": "命中已配置的教务系统",
                            },
                        }
                    }
                }
            },
        }
    },
)
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


@router.get(
    "/config/{university_id}",
    response_model=EduSystemConfigOut,
    summary="获取教务系统配置",
    responses={
        200: {
            "description": "学校教务系统配置；不存在时自动创建默认配置",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "已发现部分 URL 的配置",
                            "value": {
                                "id": "cfg_uni_4111010001",
                                "university_id": "uni_4111010001",
                                "provider": "zhengfang",
                                "system_type": "undergrad",
                                "academic_system_url": "https://dean.pku.edu.cn/",
                                "academic_system_url_status": "verified",
                                "sso_url": "https://portal.pku.edu.cn/",
                                "sso_url_status": "verified",
                                "login_method": "sso",
                                "captcha_type": "none",
                                "supported_features": ["schedule", "grade", "exam"],
                                "school_code": "4111010001",
                                "data_source": "curated",
                                "created_at": "2026-09-01T08:00:00+00:00",
                                "updated_at": "2026-10-01T08:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
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


# ===== 绑定 =====


@router.get(
    "/binding",
    response_model=Optional[EduBindingOut],
    summary="获取教务绑定",
    responses={
        200: {
            "description": "当前用户教务绑定；未绑定时为 null",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "已绑定教务账号",
                            "value": {
                                "id": "bind_0001",
                                "user_id": "u_demo",
                                "university_id": "uni_4111010001",
                                "provider": "zhengfang",
                                "supported_features": ["schedule", "grade", "exam"],
                                "system_type": "undergrad",
                                "external_student_id": "20240001",
                                "external_student_name": "演示学生",
                                "connection_status": "active",
                                "session_type": "backend_cookie",
                                "last_synced_at": "2026-10-06T09:30:00+00:00",
                                "last_sync_status": "success",
                                "last_error": None,
                                "created_at": "2026-09-01T08:00:00+00:00",
                                "updated_at": "2026-10-06T09:30:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
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


@router.post(
    "/bind",
    response_model=EduBindingOut,
    summary="兼容旧版绑定接口",
    responses={
        200: {
            "description": "教务账号绑定成功（不含凭证）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "绑定成功",
                            "value": {
                                "id": "bind_0001",
                                "user_id": "u_demo",
                                "university_id": "uni_4111010001",
                                "provider": "zhengfang",
                                "supported_features": ["schedule", "grade", "exam"],
                                "system_type": "undergrad",
                                "external_student_id": "20240001",
                                "external_student_name": "演示学生",
                                "connection_status": "active",
                                "session_type": "backend_cookie",
                                "last_synced_at": None,
                                "last_sync_status": None,
                                "last_error": None,
                                "created_at": "2026-10-06T09:40:00+00:00",
                                "updated_at": "2026-10-06T09:40:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def bind(
    request: Annotated[
        EduBindRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "使用学号绑定本科教务",
                    "value": {
                        "username": "20240001",
                        "password": "EduDemo123456",
                        "system_type": "undergrad",
                    },
                }
            }
        ),
    ],
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


@router.delete(
    "/binding",
    summary="解绑教务账号",
    responses={
        200: {
            "description": "已解除当前用户的教务绑定",
            "content": {
                "application/json": {
                    "examples": {"成功": {"summary": "解绑成功", "value": {"ok": True}}}
                }
            },
        }
    },
)
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


def _project_sync_events_safely(
    *, user_id: str, binding, result: EduSyncResult, container: ServiceContainer
) -> None:
    """Project only persisted, structured sync facts; never fail the sync response."""
    if result.status != "success" or not result.persisted or not result.sync_batch_id:
        return
    observed_at = datetime.now(timezone.utc)
    try:
        if result.sync_type == "schedule":
            container.learner_event_service.record_edu_schedule_synced(
                user_id=user_id,
                binding_id=binding.id,
                semester=result.semester,
                scheduled_item_count=result.items_count,
                observed_at=observed_at,
                sync_batch_id=result.sync_batch_id,
            )
        elif result.sync_type == "grade":
            for item in container.edu_connector.list_grade_items(
                user_id, semester=result.semester, include_stale=False
            ):
                container.learner_event_service.record_edu_grade_observed(
                    user_id=user_id,
                    binding_id=binding.id,
                    semester=item.semester,
                    course_code=item.course_code,
                    credit_value=item.credit,
                    score=item.score,
                    assessment_category=item.category,
                    grade_id=item.id,
                    observed_at=observed_at,
                )
        elif result.sync_type == "exam":
            for item in container.edu_connector.list_exam_items(
                user_id, semester=result.semester, include_stale=False
            ):
                container.learner_event_service.record_edu_exam_discovered(
                    user_id=user_id,
                    binding_id=binding.id,
                    semester=item.semester,
                    course_code=item.course_code,
                    exam_id=item.id,
                    starts_at=item.starts_at,
                    observed_at=observed_at,
                )
    except Exception as exc:  # event projection is deliberately best-effort
        logger.warning(
            "learner_event_projection_failed user_id=%s action=%s exception_type=%s",
            user_id,
            result.sync_type,
            type(exc).__name__,
        )


@router.post(
    "/sync/profile",
    response_model=EduSyncResult,
    summary="同步学生基本信息",
    responses={
        200: {
            "description": "同步学生基本信息结果；未绑定时 status=failed（仍为 HTTP 200）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "同步成功",
                            "value": {
                                "sync_type": "profile",
                                "status": "success",
                                "items_count": 1,
                                "error_message": None,
                                "profile": {
                                    "external_student_id": "20240001",
                                    "name": "演示学生",
                                    "college": "信息科学技术学院",
                                    "major": "计算机科学与技术",
                                    "grade": "2024",
                                    "class_name": "计算机 2024 级 1 班",
                                },
                                "inserted": 0,
                                "updated": 1,
                                "unchanged": 0,
                                "removed": 0,
                                "failed": 0,
                                "sync_batch_id": "sync_20261006_093000",
                                "semester": None,
                                "persisted": True,
                                "stage": "completed",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def sync_profile(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduSyncResult:
    """同步学生基本信息。

    - 未绑定教务账号时不返回 404：仍是 HTTP 200，status=failed，客户端须检查业务 status。
    """
    if _require_binding_or_failed(user, container) is None:
        return EduSyncResult(sync_type="profile", status="failed", error_message="未绑定教务账号")
    return await container.edu_connector.sync_profile(user.id)


@router.post(
    "/sync/schedule",
    response_model=EduSyncResult,
    summary="同步教务课表",
    responses={
        200: {
            "description": "课表同步结果；未绑定时 status=failed（仍为 HTTP 200）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "同步成功",
                            "value": {
                                "sync_type": "schedule",
                                "status": "success",
                                "items_count": 12,
                                "error_message": None,
                                "inserted": 10,
                                "updated": 2,
                                "unchanged": 0,
                                "removed": 0,
                                "failed": 0,
                                "sync_batch_id": "sync_20261006_093100",
                                "semester": "2025-2026-1",
                                "persisted": True,
                                "stage": "completed",
                                "previous_schedule_preserved": False,
                                "protocol_source": "zhengfang_jwgl2",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def sync_schedule(
    semester: Optional[str] = Query(None, max_length=64),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduSyncResult:
    """同步课表，可按学期过滤。

    - 未绑定教务账号时不返回 404：仍是 HTTP 200，status=failed。
    """
    binding = _require_binding_or_failed(user, container)
    if binding is None:
        return EduSyncResult(sync_type="schedule", status="failed", error_message="未绑定教务账号")
    result = await container.edu_connector.sync_schedule(user.id, semester=semester)
    _project_sync_events_safely(user_id=user.id, binding=binding, result=result, container=container)
    return result


@router.post(
    "/sync/grade",
    response_model=EduSyncResult,
    summary="同步教务成绩",
    responses={
        200: {
            "description": "成绩同步结果；未绑定时 status=failed（仍为 HTTP 200）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "同步成功",
                            "value": {
                                "sync_type": "grade",
                                "status": "success",
                                "items_count": 24,
                                "error_message": None,
                                "inserted": 8,
                                "updated": 16,
                                "unchanged": 0,
                                "removed": 0,
                                "failed": 0,
                                "sync_batch_id": "sync_20261006_093200",
                                "semester": "2025-2026-1",
                                "persisted": True,
                                "stage": "completed",
                                "protocol_source": "zhengfang_jwgl2",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def sync_grade(
    semester: Optional[str] = Query(None, max_length=64),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduSyncResult:
    """同步成绩，可按学期过滤。

    - 未绑定教务账号时不返回 404：仍是 HTTP 200，status=failed。
    """
    binding = _require_binding_or_failed(user, container)
    if binding is None:
        return EduSyncResult(sync_type="grade", status="failed", error_message="未绑定教务账号")
    result = await container.edu_connector.sync_grade(user.id, semester=semester)
    _project_sync_events_safely(user_id=user.id, binding=binding, result=result, container=container)
    return result


@router.post(
    "/sync/exam",
    response_model=EduSyncResult,
    summary="同步考试安排",
    responses={
        200: {
            "description": "考试安排同步结果；未绑定时 status=failed（仍为 HTTP 200）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "同步成功",
                            "value": {
                                "sync_type": "exam",
                                "status": "success",
                                "items_count": 2,
                                "error_message": None,
                                "inserted": 2,
                                "updated": 0,
                                "unchanged": 0,
                                "removed": 0,
                                "failed": 0,
                                "sync_batch_id": "sync_20261006_093300",
                                "semester": "2025-2026-1",
                                "persisted": True,
                                "stage": "completed",
                                "protocol_source": "zhengfang_jwgl2",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def sync_exam(
    semester: Optional[str] = Query(None, max_length=64),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduSyncResult:
    """同步考试安排，可按学期过滤。

    - 未绑定教务账号时不返回 404：仍是 HTTP 200，status=failed。
    """
    binding = _require_binding_or_failed(user, container)
    if binding is None:
        return EduSyncResult(sync_type="exam", status="failed", error_message="未绑定教务账号")
    result = await container.edu_connector.sync_exam(user.id, semester=semester)
    _project_sync_events_safely(user_id=user.id, binding=binding, result=result, container=container)
    return result


@router.get(
    "/sync/records",
    response_model=list[EduSyncRecordOut],
    summary="列出同步记录",
    responses={
        200: {
            "description": "当前用户的教务同步记录列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "返回最近一次课表同步记录",
                            "value": [
                                {
                                    "id": "rec_0001",
                                    "binding_id": "bind_0001",
                                    "sync_type": "schedule",
                                    "status": "success",
                                    "items_count": 12,
                                    "error_message": None,
                                    "started_at": "2026-10-06T09:31:00+00:00",
                                    "finished_at": "2026-10-06T09:31:05+00:00",
                                }
                            ],
                        }
                    }
                }
            },
        }
    },
)
def list_sync_records(
    limit: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> list[EduSyncRecordOut]:
    """列出当前用户的教务同步记录，limit 控制返回条数。"""
    records = container.edu_connector.list_sync_records(user.id, limit=limit)
    return [_sync_record_to_out(r) for r in records]


# ===== 持久化教务数据读取（供三端展示真实课表/成绩）=====


@router.get(
    "/schedule/semesters",
    response_model=list[str],
    summary="列出课表学期",
    responses={
        200: {
            "description": "已同步课表的学期列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "返回两个学期",
                            "value": ["2025-2026-1", "2024-2025-2"],
                        }
                    }
                }
            },
        }
    },
)
def list_schedule_semesters(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> list[str]:
    """列出已同步课表的所有学期。"""
    return container.edu_connector.list_schedule_semesters(user.id)


@router.get(
    "/schedule/items",
    summary="读取课表条目",
    responses={
        200: {
            "description": "已持久化的课表条目",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "返回一条课表条目",
                            "value": {
                                "semester": "2025-2026-1",
                                "items_count": 1,
                                "items": [
                                    {
                                        "id": "sched_0001",
                                        "semester": "2025-2026-1",
                                        "course_code": "04830100",
                                        "course_name": "数据结构与算法",
                                        "teacher": "王老师",
                                        "location": "理科教学楼 305",
                                        "weekday": 1,
                                        "start_section": 1,
                                        "end_section": 2,
                                        "start_time": "08:00",
                                        "end_time": "09:40",
                                        "weeks": "1-16",
                                        "credit": 3.0,
                                        "is_stale": False,
                                        "last_seen_at": "2026-10-06T09:31:00+00:00",
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        }
    },
)
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


@router.get(
    "/grade/semesters",
    response_model=list[str],
    summary="列出成绩学期",
    responses={
        200: {
            "description": "已同步成绩的学期列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "返回一个学期",
                            "value": ["2025-2026-1"],
                        }
                    }
                }
            },
        }
    },
)
def list_grade_semesters(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> list[str]:
    """列出已同步成绩的所有学期。"""
    return container.edu_connector.list_grade_semesters(user.id)


@router.get(
    "/grade/items",
    summary="读取成绩条目",
    responses={
        200: {
            "description": "已持久化的成绩条目",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "返回一条成绩条目",
                            "value": {
                                "semester": "2025-2026-1",
                                "items_count": 1,
                                "items": [
                                    {
                                        "id": "grade_0001",
                                        "semester": "2025-2026-1",
                                        "course_code": "04830100",
                                        "course_name": "数据结构与算法",
                                        "credit": 3.0,
                                        "score": "92",
                                        "grade_point": 4.0,
                                        "category": "专业课",
                                        "status": "normal",
                                        "is_stale": False,
                                        "last_seen_at": "2026-10-06T09:32:00+00:00",
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        }
    },
)
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


@router.get(
    "/exam/semesters",
    response_model=list[str],
    summary="列出考试学期",
    responses={
        200: {
            "description": "已同步考试安排的学期列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "返回一个学期",
                            "value": ["2025-2026-1"],
                        }
                    }
                }
            },
        }
    },
)
def list_exam_semesters(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> list[str]:
    """列出已同步考试安排的所有学期。"""
    return container.edu_connector.list_exam_semesters(user.id)


@router.get(
    "/exam/items",
    summary="读取考试安排",
    responses={
        200: {
            "description": "已持久化的考试安排，补考通过 exam_type 区分",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "返回一条考试安排",
                            "value": {
                                "semester": "2025-2026-1",
                                "items_count": 1,
                                "items": [
                                    {
                                        "id": "exam_0001",
                                        "semester": "2025-2026-1",
                                        "course_code": "04830100",
                                        "course_name": "数据结构与算法",
                                        "exam_type": "final",
                                        "location": "理科教学楼 305",
                                        "seat": "12",
                                        "starts_at": "2026-01-10T09:00:00+08:00",
                                        "ends_at": "2026-01-10T11:00:00+08:00",
                                        "notes": None,
                                        "is_stale": False,
                                        "last_seen_at": "2026-10-06T09:33:00+00:00",
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        }
    },
)
def list_exam_items(
    semester: Optional[str] = Query(None),
    include_stale: bool = Query(False),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> dict:
    """读取已持久化的考试安排，补考通过 exam_type 区分。"""
    items = container.edu_connector.list_exam_items(
        user.id, semester=semester, include_stale=include_stale
    )
    return {
        "semester": semester,
        "items_count": len(items),
        "items": [
            {
                "id": item.id,
                "semester": item.semester,
                "course_code": item.course_code,
                "course_name": item.course_name,
                "exam_type": item.exam_type,
                "location": item.location,
                "seat": item.seat,
                "starts_at": item.starts_at,
                "ends_at": item.ends_at,
                "notes": item.notes,
                "is_stale": item.is_stale,
                "last_seen_at": item.last_seen_at,
            }
            for item in items
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


@router.get(
    "/systems/{university_id}",
    response_model=list[EduSystemOut],
    summary="列出学校教务系统",
    responses={
        200: {
            "description": "学校的教务系统列表（1:N）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "返回一个已核验系统",
                            "value": [
                                {
                                    "id": "sys_0001",
                                    "university_id": "uni_4111010001",
                                    "system_key": "undergraduate-main",
                                    "name": "北京大学本科教务系统",
                                    "system_type": "undergrad",
                                    "provider": "zhengfang",
                                    "login_url": "https://dean.pku.edu.cn/login",
                                    "auth_type": "sso",
                                    "login_execution_mode": "backend_http",
                                    "captcha_type": "none",
                                    "status": "active",
                                    "verification_status": "verified",
                                    "supported_features": ["schedule", "grade", "exam"],
                                    "source": "curated",
                                    "updated_at": "2026-10-01T08:00:00+00:00",
                                }
                            ],
                        }
                    }
                }
            },
        }
    },
)
def list_systems(
    university_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> list[EduSystemOut]:
    """列出学校的所有教务系统（1:N）。"""
    systems = container.edu_connector.list_systems(university_id)
    return [_system_to_out(s) for s in systems]


# ===== edu_connections (状态机) =====


@router.post(
    "/connections",
    response_model=EduConnectionOut,
    summary="创建教务连接",
    responses={
        200: {
            "description": "已创建连接，返回 connection_id 与初始状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "创建后处于 idle 状态",
                            "value": {
                                "id": "conn_0001",
                                "user_id": "u_demo",
                                "edu_system_id": "sys_0001",
                                "university_id": "uni_4111010001",
                                "state": "idle",
                                "provider": "zhengfang",
                                "login_execution_mode": "backend_http",
                                "portal_url": "https://dean.pku.edu.cn/",
                                "allowed_origins": ["https://dean.pku.edu.cn"],
                                "external_student_id": None,
                                "external_student_name": None,
                                "error_code": None,
                                "error_message": None,
                                "created_at": "2026-10-06T09:40:00+00:00",
                                "updated_at": "2026-10-06T09:40:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def create_connection(
    request: Annotated[
        EduConnectionCreate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "按教务系统 ID 创建连接",
                    "value": {"edu_system_id": "sys_0001"},
                }
            }
        ),
    ],
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
    return _connection_to_out(conn, container)


@router.get(
    "/connections/{connection_id}",
    response_model=EduConnectionOut,
    summary="读取教务连接",
    responses={
        200: {
            "description": "教务连接的当前状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "已连接并识别到学生",
                            "value": {
                                "id": "conn_0001",
                                "user_id": "u_demo",
                                "edu_system_id": "sys_0001",
                                "university_id": "uni_4111010001",
                                "state": "connected",
                                "provider": "zhengfang",
                                "login_execution_mode": "backend_http",
                                "portal_url": "https://dean.pku.edu.cn/",
                                "allowed_origins": ["https://dean.pku.edu.cn"],
                                "external_student_id": "20240001",
                                "external_student_name": "演示学生",
                                "error_code": None,
                                "error_message": None,
                                "created_at": "2026-10-06T09:40:00+00:00",
                                "updated_at": "2026-10-06T09:41:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def get_connection(
    connection_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduConnectionOut:
    """读取指定教务连接的当前状态；不存在返回 404，非本人返回 403。"""
    conn = container.edu_connector.get_connection(connection_id)
    if conn is None:
        raise AppException(
            code="EDU_CONNECTION_NOT_FOUND",
            http_status=404,
            message="连接不存在",
        )
    if conn.user_id != user.id:
        raise Forbidden()
    return _connection_to_out(conn, container)


@router.post(
    "/connections/{connection_id}/pre-login",
    response_model=EduPreLoginResult,
    summary="获取预登录验证码",
)
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


@router.post(
    "/connections/{connection_id}/continue",
    response_model=EduConnectionOut,
    summary="推进连接状态",
    responses={
        200: {
            "description": "推进后的教务连接状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "验证码提交后认证成功",
                            "value": {
                                "id": "conn_0001",
                                "user_id": "u_demo",
                                "edu_system_id": "sys_0001",
                                "university_id": "uni_4111010001",
                                "state": "authenticated",
                                "provider": "zhengfang",
                                "login_execution_mode": "backend_http",
                                "portal_url": "https://dean.pku.edu.cn/",
                                "allowed_origins": ["https://dean.pku.edu.cn"],
                                "external_student_id": "20240001",
                                "external_student_name": "演示学生",
                                "error_code": None,
                                "error_message": None,
                                "created_at": "2026-10-06T09:40:00+00:00",
                                "updated_at": "2026-10-06T09:41:30+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def continue_connection(
    connection_id: str,
    request: Annotated[
        EduConnectionContinue,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "携带验证码提交登录",
                    "value": {
                        "action": "SUBMIT_WITH_CAPTCHA",
                        "username": "20240001",
                        "password": "EduDemo123456",
                        "captcha": "8A6F",
                        "pre_login_token": "plt_9f2c4e7a1b",
                    },
                }
            }
        ),
    ],
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
    return _connection_to_out(updated, container)


@router.post(
    "/connections/from-url",
    response_model=EduConnectionOut,
    summary="从URL创建教务连接",
    responses={
        200: {
            "description": "已按 URL 探测并创建连接，返回初始状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "按门户 URL 创建后处于 idle 状态",
                            "value": {
                                "id": "conn_0002",
                                "user_id": "u_demo",
                                "edu_system_id": "sys_0001",
                                "university_id": "uni_4111010001",
                                "state": "idle",
                                "provider": "zhengfang",
                                "login_execution_mode": "backend_http",
                                "portal_url": "https://dean.pku.edu.cn/",
                                "allowed_origins": ["https://dean.pku.edu.cn"],
                                "external_student_id": None,
                                "external_student_name": None,
                                "error_code": None,
                                "error_message": None,
                                "created_at": "2026-10-06T09:42:00+00:00",
                                "updated_at": "2026-10-06T09:42:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def create_connection_from_url(
    request: Annotated[
        EduConnectionFromUrlRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "按门户 URL 创建连接",
                    "value": {
                        "portal_url": "https://dean.pku.edu.cn/",
                        "university_id": "uni_4111010001",
                    },
                }
            }
        ),
    ],
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
    return _connection_to_out(conn, container)


@router.post(
    "/discovery/probe",
    response_model=EduProbeResult,
    summary="探测教务系统URL",
    responses={
        200: {
            "description": "URL 探测结果（不持久化任何数据）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "可达且识别为正方教务",
                            "value": {
                                "portal_url": "https://dean.pku.edu.cn/",
                                "provider": "ZHENGFANG",
                                "provider_confidence": 0.9,
                                "reachable": True,
                                "http_status": 200,
                                "final_url": "https://dean.pku.edu.cn/",
                                "title": "北京大学教务部",
                                "is_edu_page": True,
                                "suggested_login_mode": "backend_http",
                                "challenge_type": "none",
                                "evidence": [
                                    {
                                        "dimension": "url",
                                        "detail": "命中正方教务特征路径",
                                    }
                                ],
                                "error": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def discovery_probe(
    request: Annotated[
        EduProbeRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "探测北大教务门户",
                    "value": {"portal_url": "https://dean.pku.edu.cn/"},
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> EduProbeResult:
    """探测教务系统 URL（不需要 university_id）。

    只检测 provider/可达性/建议登录模式，不持久化任何数据。
    """
    result = await container.edu_connector.probe_portal(request.portal_url)
    return EduProbeResult(**result)


# ===== 教务系统发现（Discovery）=====

from ...services.edu.discovery_service import submit_url as _discovery_submit_url


@router.post(
    "/discovery/submit-url",
    response_model=EduDiscoverySubmitUrlResult,
    summary="提交教务系统URL",
    responses={
        200: {
            "description": "URL 检测与候选保存结果",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "保存为候选",
                            "value": {
                                "school_code": "4111010001",
                                "school_name": "北京大学",
                                "candidate_url": "https://dean.pku.edu.cn/",
                                "provider": "ZHENGFANG",
                                "provider_confidence": 0.9,
                                "reachable": True,
                                "http_status": 200,
                                "final_url": "https://dean.pku.edu.cn/",
                                "title": "北京大学教务部",
                                "is_edu_page": True,
                                "evidence": [
                                    {
                                        "dimension": "url",
                                        "detail": "命中正方教务特征路径",
                                    }
                                ],
                                "verification_status": "CANDIDATE",
                                "saved": True,
                                "error": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def discovery_submit_url(
    request: Annotated[
        EduDiscoverySubmitUrlRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "提交北大教务门户 URL",
                    "value": {
                        "university_id": "uni_4111010001",
                        "candidate_url": "https://dean.pku.edu.cn/",
                    },
                }
            }
        ),
    ],
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


__all__ = ["router"]
