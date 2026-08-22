"""统一异常处理与结构化错误响应。"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(Exception):
    """业务异常基类，附带稳定错误码与可读 message。"""

    code: str = "INTERNAL_ERROR"
    http_status: int = 500
    message: str = "服务器内部错误"
    details: Optional[Any] = None

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        code: Optional[str] = None,
        http_status: Optional[int] = None,
        details: Optional[Any] = None,
    ) -> None:
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        if details is not None:
            self.details = details
        super().__init__(self.message)


# ===== 常用错误码 =====


class ValidationFailed(AppException):
    code = "VALIDATION_FAILED"
    http_status = 422
    message = "请求参数校验失败"


class NoticeEmpty(AppException):
    code = "NOTICE_EMPTY"
    http_status = 400
    message = "通知文本为空，无法提取。"


class NoticeTooLong(AppException):
    code = "NOTICE_TOO_LONG"
    http_status = 400
    message = "通知文本过长，请控制在 5000 字以内。"


class NoticeUnparseable(AppException):
    code = "NOTICE_UNPARSEABLE"
    http_status = 422
    message = "无法识别为通知文本，请粘贴真实校园通知。"


class KnowledgeBaseEmpty(AppException):
    code = "KNOWLEDGE_BASE_EMPTY"
    http_status = 200  # 业务上属于"无可答资料"，不是 HTTP 错误
    message = "当前知识库中没有可用于回答该问题的资料。"


class DocumentNotFound(AppException):
    code = "DOCUMENT_NOT_FOUND"
    http_status = 404
    message = "文档不存在。"


class NotFoundError(AppException):
    """通用资源不存在(用于附件等未在 AppException 子类中专门建模的资源)。"""

    code = "NOT_FOUND"
    http_status = 404
    message = "资源不存在。"


class DocumentAlreadyExists(AppException):
    code = "DOCUMENT_ALREADY_EXISTS"
    http_status = 409
    message = "相同内容哈希的文档已存在。"


class FileTooLarge(AppException):
    code = "FILE_TOO_LARGE"
    http_status = 413
    message = "文件过大。"


class FileTypeNotAllowed(AppException):
    code = "FILE_TYPE_NOT_ALLOWED"
    http_status = 415
    message = "不支持的文件类型。"


class FileNameUnsafe(AppException):
    code = "FILE_NAME_UNSAFE"
    http_status = 400
    message = "文件名不合法，可能包含路径穿越字符。"


class LLMUnavailable(AppException):
    code = "LLM_UNAVAILABLE"
    http_status = 200
    message = "LLM 暂不可用，已切换到检索摘要模式。"


class EmptyQuestion(AppException):
    code = "EMPTY_QUESTION"
    http_status = 400
    message = "问题为空，无法回答。"


# ===== 鉴权与权限 =====

class Unauthorized(AppException):
    code = "UNAUTHORIZED"
    http_status = 401
    message = "未认证或认证已失效。"


class Forbidden(AppException):
    code = "FORBIDDEN"
    http_status = 403
    message = "无权访问该资源。"


class UserNotFound(AppException):
    code = "USER_NOT_FOUND"
    http_status = 404
    message = "用户不存在。"


class UsernameExists(AppException):
    code = "USERNAME_EXISTS"
    http_status = 409
    message = "用户名已被占用。"


class StudentNumberExists(AppException):
    code = "STUDENT_NUMBER_EXISTS"
    http_status = 409
    message = "学号已被占用。"


class TeacherNumberExists(AppException):
    code = "TEACHER_NUMBER_EXISTS"
    http_status = 409
    message = "工号已被占用。"


class InvalidCredentials(AppException):
    code = "INVALID_CREDENTIALS"
    http_status = 401
    message = "用户名或密码错误。"


class InvalidInviteCode(AppException):
    code = "INVALID_INVITE_CODE"
    http_status = 404
    message = "邀请码无效或班级不存在。"


class ClassGroupFull(AppException):
    code = "CLASS_GROUP_FULL"
    http_status = 409
    message = "班级已满员。"


class AlreadyEnrolled(AppException):
    code = "ALREADY_ENROLLED"
    http_status = 409
    message = "该学生已加入此班级。"


class CourseNotFound(AppException):
    code = "COURSE_NOT_FOUND"
    http_status = 404
    message = "课程不存在。"


class ClassGroupNotFound(AppException):
    code = "CLASS_GROUP_NOT_FOUND"
    http_status = 404
    message = "班级不存在。"


class AnnouncementNotFound(AppException):
    code = "ANNOUNCEMENT_NOT_FOUND"
    http_status = 404
    message = "通知不存在。"


class AssignmentNotFound(AppException):
    code = "ASSIGNMENT_NOT_FOUND"
    http_status = 404
    message = "任务不存在。"


class SubmissionNotFound(AppException):
    code = "SUBMISSION_NOT_FOUND"
    http_status = 404
    message = "提交不存在。"


class AssignmentClosed(AppException):
    code = "ASSIGNMENT_CLOSED"
    http_status = 409
    message = "任务已截止提交。"


class ResubmitNotAllowed(AppException):
    code = "RESUBMIT_NOT_ALLOWED"
    http_status = 409
    message = "该任务不允许重新提交。"


class AttachmentTooLarge(AppException):
    code = "ATTACHMENT_TOO_LARGE"
    http_status = 413
    message = "附件过大。"


class AttachmentTypeNotAllowed(AppException):
    code = "ATTACHMENT_TYPE_NOT_ALLOWED"
    http_status = 415
    message = "附件类型不被允许。"


class InvalidTransition(AppException):
    code = "INVALID_TRANSITION"
    http_status = 409
    message = "状态转换不被允许。"


class StudySessionNotFound(AppException):
    code = "STUDY_SESSION_NOT_FOUND"
    http_status = 404
    message = "学习会话不存在。"


class StudyBreakNotFound(AppException):
    code = "STUDY_BREAK_NOT_FOUND"
    http_status = 404
    message = "休息记录不存在。"


class PersonalTaskNotFound(AppException):
    code = "PERSONAL_TASK_NOT_FOUND"
    http_status = 404
    message = "个人待办不存在。"


class PersonalTaskConflict(AppException):
    """个人待办状态冲突(如已完成/已删除的任务再次操作)。"""

    code = "PERSONAL_TASK_CONFLICT"
    http_status = 409
    message = "个人待办当前状态不允许该操作。"


# ===== QR 扫码登录 =====


class QrInvalid(AppException):
    code = "QR_INVALID"
    http_status = 400
    message = "二维码无效。"


class QrExpired(AppException):
    code = "QR_EXPIRED"
    http_status = 410
    message = "二维码已过期。"


class QrAlreadyScanned(AppException):
    code = "QR_ALREADY_SCANNED"
    http_status = 409
    message = "二维码已被扫描。"


class QrAlreadyConfirmed(AppException):
    code = "QR_ALREADY_CONFIRMED"
    http_status = 409
    message = "二维码已确认。"


class QrAlreadyConsumed(AppException):
    code = "QR_ALREADY_CONSUMED"
    http_status = 409
    message = "二维码已使用，不能重复兑换。"


class QrCancelled(AppException):
    code = "QR_CANCELLED"
    http_status = 409
    message = "二维码已取消。"


class QrUserMismatch(AppException):
    code = "QR_USER_MISMATCH"
    http_status = 403
    message = "确认用户与扫描用户不一致。"


class QrBrowserTokenInvalid(AppException):
    code = "QR_BROWSER_TOKEN_INVALID"
    http_status = 401
    message = "浏览器凭据无效。"


class QrNotConfirmed(AppException):
    code = "QR_NOT_CONFIRMED"
    http_status = 409
    message = "二维码尚未确认，不能兑换。"


class QrRateLimited(AppException):
    code = "QR_RATE_LIMITED"
    http_status = 429
    message = "创建二维码过于频繁，请稍后再试。"


# ===== Trusted Device（可信设备）=====


class TrustedDeviceInvalid(AppException):
    code = "TRUSTED_DEVICE_INVALID"
    http_status = 401
    message = "可信设备凭据无效。"


class TrustedDeviceExpired(AppException):
    code = "TRUSTED_DEVICE_EXPIRED"
    http_status = 401
    message = "可信设备凭据已过期。"


class TrustedDeviceRevoked(AppException):
    code = "TRUSTED_DEVICE_REVOKED"
    http_status = 401
    message = "可信设备已被撤销。"


def _build_error_body(
    code: str,
    message: str,
    details: Optional[Any] = None,
) -> dict:
    body = {"code": code, "message": message, "details": details}
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器，输出统一结构。"""

    @app.exception_handler(AppException)
    async def _app_exception_handler(_: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.http_status,
            content=_build_error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError):
        # Pydantic 自定义校验器的 ctx 可能携带 ValueError 实例；先做
        # JSON 安全转换，保证所有校验失败都稳定返回 422。
        details = jsonable_encoder(
            exc.errors(), custom_encoder={Exception: str}
        )
        return JSONResponse(
            status_code=422,
            content=_build_error_body(
                "VALIDATION_FAILED",
                "请求参数校验失败",
                details=details if isinstance(details, list) else None,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(_: Request, exc: StarletteHTTPException):
        # 把 404 / 405 等也包装成统一结构
        code_map = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 500: "INTERNAL_ERROR"}
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_body(
                code_map.get(exc.status_code, "HTTP_ERROR"),
                str(exc.detail) if exc.detail else "请求错误",
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(_: Request, exc: Exception):
        # 不向客户端暴露内部堆栈，仅返回通用错误
        return JSONResponse(
            status_code=500,
            content=_build_error_body(
                "INTERNAL_ERROR",
                "服务器内部错误，请稍后重试。",
            ),
        )


__all__ = [
    "AppException",
    "ValidationFailed",
    "NoticeEmpty",
    "NoticeTooLong",
    "NoticeUnparseable",
    "KnowledgeBaseEmpty",
    "DocumentNotFound",
    "NotFoundError",
    "DocumentAlreadyExists",
    "FileTooLarge",
    "FileTypeNotAllowed",
    "FileNameUnsafe",
    "LLMUnavailable",
    "EmptyQuestion",
    "Unauthorized",
    "Forbidden",
    "UserNotFound",
    "UsernameExists",
    "StudentNumberExists",
    "TeacherNumberExists",
    "InvalidCredentials",
    "InvalidInviteCode",
    "ClassGroupFull",
    "AlreadyEnrolled",
    "CourseNotFound",
    "ClassGroupNotFound",
    "AnnouncementNotFound",
    "AssignmentNotFound",
    "SubmissionNotFound",
    "AssignmentClosed",
    "ResubmitNotAllowed",
    "AttachmentTooLarge",
    "AttachmentTypeNotAllowed",
    "InvalidTransition",
    "StudySessionNotFound",
    "StudyBreakNotFound",
    "PersonalTaskNotFound",
    "PersonalTaskConflict",
    "register_exception_handlers",
]
