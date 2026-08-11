"""日志配置 — 使用 loguru，禁止记录 API Key / 对话隐私 / 摄像头数据。"""
from __future__ import annotations

import logging
import sys
from typing import Any

from loguru import logger

from .config import Settings


class _InterceptHandler(logging.Handler):
    """把标准 logging 桥接到 loguru，便于 uvicorn 等库日志统一。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _redact_filter(record: Any) -> None:
    """脱敏：把记录中可能存在的敏感字段替换为 ***。"""
    msg = record.get("message", "")
    lower = msg.lower()
    sensitive_markers = ("api_key", "apikey", "authorization", "password", "token")
    if any(m in lower for m in sensitive_markers):
        record["message"] = "[redacted: 含敏感字段，已脱敏]"


def configure_logging(settings: Settings) -> None:
    """根据 Settings 配置全局 loguru 与标准 logging 桥接。

    注意：不要在运行时 force=True 覆盖 uvicorn 已安装的 logging handlers，
    否则 uvicorn 在 lifespan yield 后输出 "Application startup complete"
    会走 _InterceptHandler → loguru → stdout，在事件循环里阻塞，
    导致端口虽 LISTEN 但不响应任何 HTTP 请求。
    这里仅配置 loguru，并把标准 logging 桥接到 loguru，但不强制移除
    uvicorn/fastapi 自己的 handler，避免干扰其事件循环。
    """
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level,
        filter=_redact_filter,
        backtrace=False,
        diagnose=False,
        enqueue=False,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        ),
    )

    # 桥接标准 logging(不 force,不覆盖 uvicorn 已有 handler)
    root = logging.getLogger()
    if not any(isinstance(h, _InterceptHandler) for h in root.handlers):
        root.addHandler(_InterceptHandler())
    root.setLevel(settings.log_level.upper())

    # 降低 uvicorn access 噪音
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


__all__ = ["configure_logging", "logger"]
