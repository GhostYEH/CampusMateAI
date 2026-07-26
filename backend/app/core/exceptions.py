"""统一异常处理与结构化错误响应。"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, Request
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
        return JSONResponse(
            status_code=422,
            content=_build_error_body(
                "VALIDATION_FAILED",
                "请求参数校验失败",
                details=exc.errors() if isinstance(exc.errors(), list) else None,
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
    "DocumentAlreadyExists",
    "FileTooLarge",
    "FileTypeNotAllowed",
    "FileNameUnsafe",
    "LLMUnavailable",
    "EmptyQuestion",
    "register_exception_handlers",
]
