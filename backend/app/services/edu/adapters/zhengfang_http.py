"""ZhengfangHttpClient — 正方教务系统 HTTP 客户端。

封装 httpx，处理：
- SSRF 防护
- cookie 透传
- 编码（部分旧版系统使用 GBK）
- 超时 / 网络异常 → 统一 EduAdapterError
- 401/403/404/429/500 → 统一错误码

不保存任何密码。登录后只保留 cookie 在内存 session。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from .ssrf_guard import SSRFBlockedError, assert_safe_url, safe_join_url


class EduAdapterError(Exception):
    """Adapter 层统一错误。"""

    def __init__(self, code: str, message: str, *, http_status: Optional[int] = None) -> None:
        self.code = code
        self.http_status = http_status
        super().__init__(f"[{code}] {message}")


class NeedUserAction(Exception):
    """登录流程需要用户人工操作（验证码 / 滑块 / 短信 / MFA）。

    不绕过、不破解。返回状态码由 connector 状态机推进。
    """

    def __init__(self, action: str, *, detail: Optional[str] = None, captcha_url: Optional[str] = None) -> None:
        self.action = action
        self.detail = detail
        self.captcha_url = captcha_url
        super().__init__(f"NEED_USER_ACTION: {action}")


@dataclass
class HttpResponse:
    status: int
    text: str
    url: str
    headers: dict


class ZhengfangHttpClient:
    """正方教务系统 HTTP 客户端。"""

    DEFAULT_TIMEOUT = 20.0

    def __init__(
        self,
        *,
        base_url: str,
        encoding: str = "utf-8",
        timeout: float = DEFAULT_TIMEOUT,
        allow_private: bool = False,
        extra_headers: Optional[dict] = None,
    ) -> None:
        self._base_url = base_url
        self._encoding = encoding
        self._timeout = timeout
        self._allow_private = allow_private
        self._extra_headers = extra_headers or {}
        self._cookies: dict = {}

    @property
    def cookies(self) -> dict:
        return dict(self._cookies)

    def set_cookies(self, cookies: dict) -> None:
        self._cookies = dict(cookies)

    def _build_headers(self, *, referer: Optional[str] = None, form_post: bool = False) -> dict:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; CampusMateEduConnector) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
            ),
            "Accept": "application/json, text/html, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if form_post:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            headers["X-Requested-With"] = "XMLHttpRequest"
        if referer:
            headers["Referer"] = referer
        headers.update(self._extra_headers)
        return headers

    async def get(self, path_or_url: str, *, params: Optional[dict] = None, referer: Optional[str] = None) -> HttpResponse:
        url = safe_join_url(self._base_url, path_or_url) if not path_or_url.startswith(("http://", "https://")) else path_or_url
        assert_safe_url(url, allow_private=self._allow_private)
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True, cookies=self._cookies) as client:
                resp = await client.get(url, params=params, headers=self._build_headers(referer=referer))
                self._cookies.update(dict(resp.cookies))
                return self._wrap(resp, url)
        except httpx.TimeoutException as e:
            raise EduAdapterError("NETWORK_TIMEOUT", f"请求超时: {e}") from e
        except httpx.ConnectError as e:
            raise EduAdapterError("NETWORK_ERROR", f"连接失败: {e}") from e
        except (httpx.ReadError, httpx.RemoteProtocolError) as e:
            raise EduAdapterError("NETWORK_ERROR", f"读取失败: {e}") from e
        except SSRFBlockedError:
            raise
        except httpx.HTTPError as e:
            raise EduAdapterError("NETWORK_ERROR", f"HTTP 错误: {e}") from e

    async def post(
        self,
        path_or_url: str,
        *,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
        referer: Optional[str] = None,
        form_post: bool = True,
    ) -> HttpResponse:
        url = safe_join_url(self._base_url, path_or_url) if not path_or_url.startswith(("http://", "https://")) else path_or_url
        assert_safe_url(url, allow_private=self._allow_private)
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True, cookies=self._cookies) as client:
                resp = await client.post(
                    url,
                    data=data,
                    params=params,
                    headers=self._build_headers(referer=referer, form_post=form_post),
                )
                self._cookies.update(dict(resp.cookies))
                return self._wrap(resp, url)
        except httpx.TimeoutException as e:
            raise EduAdapterError("NETWORK_TIMEOUT", f"请求超时: {e}") from e
        except httpx.ConnectError as e:
            raise EduAdapterError("NETWORK_ERROR", f"连接失败: {e}") from e
        except (httpx.ReadError, httpx.RemoteProtocolError) as e:
            raise EduAdapterError("NETWORK_ERROR", f"读取失败: {e}") from e
        except SSRFBlockedError:
            raise
        except httpx.HTTPError as e:
            raise EduAdapterError("NETWORK_ERROR", f"HTTP 错误: {e}") from e

    def _wrap(self, resp: httpx.Response, url: str) -> HttpResponse:
        status = resp.status_code
        if status in (401, 403):
            raise EduAdapterError("AUTH_FAILED", f"认证失败或会话过期 (HTTP {status})", http_status=status)
        if status == 404:
            raise EduAdapterError("SYSTEM_UNAVAILABLE", f"接口不存在 (HTTP 404)", http_status=status)
        if status == 429:
            raise EduAdapterError("RATE_LIMITED", "请求过于频繁，已被限流", http_status=status)
        if status >= 500:
            raise EduAdapterError("SYSTEM_UNAVAILABLE", f"教务系统异常 (HTTP {status})", http_status=status)
        try:
            text = resp.content.decode(self._encoding or "utf-8", errors="replace")
        except (LookupError, UnicodeDecodeError):
            text = resp.text
        return HttpResponse(status=status, text=text, url=str(resp.url), headers=dict(resp.headers))


__all__ = [
    "EduAdapterError",
    "NeedUserAction",
    "HttpResponse",
    "ZhengfangHttpClient",
]