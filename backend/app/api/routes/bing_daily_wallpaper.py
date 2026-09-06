"""UAPI 必应每日壁纸代理。

密钥只在后端读取，Web 客户端通过本地 API 获取元数据或图片，避免将
UAPI Bearer Key 暴露到浏览器。上游地址和参数严格对应 UAPI 文档。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, RedirectResponse, Response

from ...core.config import Settings
from ...core.exceptions import AppException
from ...core.logging import logger
from ..deps import get_settings_dep


UAPI_BING_DAILY_URL = "https://uapis.cn/api/v1/image/bing-daily"
UAPI_BING_DAILY_HISTORY_URL = "https://uapis.cn/api/v1/image/bing-daily/history"
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ALLOWED_RESOLUTIONS = {"4k", "1080"}
_ALLOWED_FORMATS = {"image", "json", "redirect"}

router = APIRouter(prefix="/wallpaper", tags=["wallpaper"])


def _error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    retry_after: str | None = None,
) -> JSONResponse:
    headers = {"Retry-After": retry_after} if retry_after else None
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "details": None},
        headers=headers,
    )


def _upstream_message(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except (TypeError, ValueError):
        return None
    if isinstance(payload, dict) and isinstance(payload.get("error"), str):
        return payload["error"].strip() or None
    return None


def _upstream_error(response: httpx.Response) -> JSONResponse:
    status_code = response.status_code
    known_statuses = {400, 404, 429, 500}
    output_status = status_code if status_code in known_statuses else 502
    code = {
        400: "UAPI_BAD_REQUEST",
        404: "UAPI_NOT_FOUND",
        429: "UAPI_RATE_LIMITED",
        500: "UAPI_SERVER_ERROR",
    }.get(status_code, "UAPI_UPSTREAM_ERROR")
    message = _upstream_message(response) or {
        400: "请求参数不正确",
        404: "没有找到对应日期的必应壁纸",
        429: "请求过于频繁，请稍后再试",
        500: "必应壁纸获取失败",
    }.get(status_code, "必应壁纸服务暂时不可用")
    retry_after = response.headers.get("retry-after") if status_code == 429 else None
    return _error_response(output_status, code, message, retry_after=retry_after)


def _validate_date(date: str | None) -> None:
    if date is not None:
        if not _DATE_PATTERN.fullmatch(date):
            raise AppException("date 格式必须是 YYYY-MM-DD", code="UAPI_BAD_REQUEST", http_status=400)
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError as exc:
            raise AppException("date 格式必须是有效的 YYYY-MM-DD 日期", code="UAPI_BAD_REQUEST", http_status=400) from exc


def _validate_resolution(resolution: str) -> None:
    if resolution not in _ALLOWED_RESOLUTIONS:
        raise AppException("resolution 只能传 4k 或 1080", code="UAPI_BAD_REQUEST", http_status=400)


def _validate_query(date: str | None, resolution: str, response_format: str, random: bool) -> None:
    _validate_date(date)
    if random and date is not None:
        raise AppException("random 不能和 date 同时使用", code="UAPI_BAD_REQUEST", http_status=400)
    _validate_resolution(resolution)
    if response_format not in _ALLOWED_FORMATS:
        raise AppException("format 只能传 image、json 或 redirect", code="UAPI_BAD_REQUEST", http_status=400)


def _request_params(date: str | None, random: bool, resolution: str, response_format: str) -> dict[str, Any]:
    params: dict[str, Any] = {"resolution": resolution, "format": response_format}
    if date is not None:
        params["date"] = date
    if random:
        params["random"] = True
    return params


def _timeout(settings: Settings) -> httpx.Timeout:
    seconds = max(1.0, min(float(settings.uapi_timeout_seconds), 60.0))
    return httpx.Timeout(seconds, connect=min(3.0, seconds))


def _require_key(settings: Settings) -> str | None:
    key = settings.uapi_api_key.strip()
    if not key:
        return None
    if not key.startswith("uapi-"):
        raise AppException("UAPI Key 格式无效，应以 uapi- 开头", code="UAPI_KEY_INVALID", http_status=503)
    return key


def _uapi_headers(key: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"} if key else {}


@router.get("/bing-daily")
async def get_bing_daily_wallpaper(
    date: str | None = Query(default=None),
    random: bool = Query(default=False),
    resolution: str = Query(default="4k"),
    format: str = Query(default="image"),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    """代理 UAPI 必应每日壁纸的 image/json/redirect 三种响应格式。"""
    _validate_query(date, resolution, format, random)
    key = _require_key(settings)
    params = _request_params(date, random, resolution, format)

    try:
        async with httpx.AsyncClient(timeout=_timeout(settings), follow_redirects=False) as client:
            upstream = await client.get(
                UAPI_BING_DAILY_URL,
                params=params,
                headers=_uapi_headers(key),
            )
    except httpx.TimeoutException:
        logger.warning("UAPI Bing daily wallpaper timed out")
        return _error_response(504, "UAPI_TIMEOUT", "必应壁纸服务请求超时，请稍后重试")
    except httpx.RequestError as exc:
        logger.warning("UAPI Bing daily wallpaper network error: {}", str(exc)[:160])
        return _error_response(502, "UAPI_NETWORK_ERROR", "必应壁纸服务暂时不可达，请稍后重试")

    if 300 <= upstream.status_code < 400:
        location = upstream.headers.get("location")
        if not location:
            return _error_response(502, "UAPI_INVALID_RESPONSE", "必应壁纸服务未返回图片地址")
        return RedirectResponse(url=location, status_code=upstream.status_code)
    if not 200 <= upstream.status_code < 300:
        return _upstream_error(upstream)

    if format == "json":
        try:
            payload = upstream.json()
        except (TypeError, ValueError):
            return _error_response(502, "UAPI_INVALID_RESPONSE", "必应壁纸服务返回了无法解析的数据")
        if not isinstance(payload, dict) or not isinstance(payload.get("image_url"), str) or not payload["image_url"].strip():
            return _error_response(502, "UAPI_INVALID_RESPONSE", "必应壁纸服务返回的数据缺少 image_url")
        return JSONResponse(content=payload, status_code=upstream.status_code)

    if format == "image":
        content_type = upstream.headers.get("content-type", "image/webp").split(";", 1)[0].strip()
        if not content_type.startswith("image/") or not upstream.content:
            return _error_response(502, "UAPI_INVALID_RESPONSE", "必应壁纸服务未返回有效图片")
        return Response(content=upstream.content, status_code=upstream.status_code, media_type=content_type)

    return _error_response(502, "UAPI_INVALID_RESPONSE", "必应壁纸服务未返回有效跳转地址")


@router.get("/bing-daily/history")
async def get_bing_daily_wallpaper_history(
    date: str | None = Query(default=None),
    resolution: str = Query(default="4k"),
    page: int = Query(default=1),
    page_size: int = Query(default=30),
    settings: Settings = Depends(get_settings_dep),
) -> JSONResponse:
    """代理 UAPI 必应壁纸历史列表，支持按日期精确查询。"""
    _validate_date(date)
    _validate_resolution(resolution)
    if page < 1:
        raise AppException("page 必须是正整数", code="UAPI_BAD_REQUEST", http_status=400)
    if page_size < 1 or page_size > 100:
        raise AppException("page_size 必须是 1 到 100 之间的正整数", code="UAPI_BAD_REQUEST", http_status=400)

    params: dict[str, Any] = {"resolution": resolution}
    if date is not None:
        params["date"] = date
    else:
        params.update({"page": page, "page_size": page_size})

    key = _require_key(settings)
    try:
        async with httpx.AsyncClient(timeout=_timeout(settings), follow_redirects=False) as client:
            upstream = await client.get(
                UAPI_BING_DAILY_HISTORY_URL,
                params=params,
                headers=_uapi_headers(key),
            )
    except httpx.TimeoutException:
        logger.warning("UAPI Bing daily wallpaper history timed out")
        return _error_response(504, "UAPI_TIMEOUT", "必应壁纸历史服务请求超时，请稍后重试")
    except httpx.RequestError as exc:
        logger.warning("UAPI Bing daily wallpaper history network error: {}", str(exc)[:160])
        return _error_response(502, "UAPI_NETWORK_ERROR", "必应壁纸历史服务暂时不可达，请稍后重试")

    if not 200 <= upstream.status_code < 300:
        return _upstream_error(upstream)

    try:
        payload = upstream.json()
    except (TypeError, ValueError):
        return _error_response(502, "UAPI_INVALID_RESPONSE", "必应壁纸历史服务返回了无法解析的数据")
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("items"), list)
        or not isinstance(payload.get("pagination"), dict)
    ):
        return _error_response(502, "UAPI_INVALID_RESPONSE", "必应壁纸历史服务返回的数据结构无效")
    return JSONResponse(content=payload, status_code=upstream.status_code)


__all__ = ["UAPI_BING_DAILY_URL", "UAPI_BING_DAILY_HISTORY_URL", "router"]
