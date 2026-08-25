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
from http.cookiejar import Cookie, DefaultCookiePolicy
from typing import Optional
from urllib.parse import urljoin, urlsplit

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
    content: bytes = b""

    @property
    def content_type(self) -> Optional[str]:
        """Return a normalized media type without untrusted parameters."""
        value = next(
            (
                candidate
                for key, candidate in self.headers.items()
                if isinstance(key, str) and key.lower() == "content-type"
            ),
            None,
        )
        if not isinstance(value, str):
            return None
        media_type = value.split(";", 1)[0].strip().lower()
        if media_type.count("/") != 1 or any(
            not (char.isalnum() or char in "!#$&^_.+-/") for char in media_type
        ):
            return None
        return media_type


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
        self._cookies = httpx.Cookies()

    @property
    def cookies(self) -> dict:
        result: dict[str, str] = {}
        for cookie in self._cookies.jar:
            result.setdefault(cookie.name, cookie.value)
        return result

    @property
    def cookie_jar(self) -> list[dict]:
        """Return every scoped cookie; unlike a dict, duplicate names survive."""
        result: list[dict] = []
        for cookie in sorted(self._cookies.jar, key=lambda item: (item.domain, item.path, item.name, item.value)):
            rest = {str(key).lower(): value for key, value in (cookie._rest or {}).items()}
            result.append({
                "name": cookie.name,
                "value": cookie.value,
                "domain": None if rest.get("_campusmate_domain_unknown") else cookie.domain,
                "source_url": rest.get("_campusmate_source_url"),
                "host_only": True if rest.get("_campusmate_host_only") else None,
                "path": None if rest.get("_campusmate_path_unknown") else cookie.path,
                "secure": None if rest.get("_campusmate_secure_unknown") else cookie.secure,
                "http_only": True if "httponly" in rest else None,
                "same_site": rest.get("samesite"),
                "expires": cookie.expires,
            })
        return result

    def set_cookies(self, cookies: dict) -> None:
        if not isinstance(cookies, dict):
            raise ValueError("cookies must be a dict")
        self.set_cookie_jar([
            {
                "name": name,
                "value": value,
                "domain": None,
                "source_url": self._base_url,
                "host_only": True,
                "path": None,
                "secure": None,
                "http_only": None,
                "same_site": None,
                "expires": None,
            }
            for name, value in cookies.items()
        ])

    def set_cookie_jar(self, cookies: list[dict], *, allowed_origins: Optional[list[str]] = None) -> None:
        if not isinstance(cookies, list):
            raise ValueError("cookie_jar must be a list")
        jar = httpx.Cookies()
        jar.jar.set_policy(DefaultCookiePolicy(strict_ns_domain=DefaultCookiePolicy.DomainStrictNonDomain))
        allowed = allowed_origins or [self._base_url]
        allowed_hosts: set[str] = set()
        for origin in allowed:
            parsed = urlsplit(origin)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("allowed cookie origin must be exact https origin")
            allowed_hosts.add(parsed.hostname.lower())
        for item in cookies:
            if not isinstance(item, dict):
                raise ValueError("cookie entry must be an object")
            name = item.get("name")
            value = item.get("value")
            domain = item.get("domain")
            path = item.get("path")
            source_url = item.get("source_url")
            host_only = item.get("host_only")
            if not isinstance(name, str) or not name or not isinstance(value, str):
                raise ValueError("cookie name and value are required strings")
            if any(ord(char) < 32 or ord(char) == 127 for char in name + value) or any(char in value for char in ';,\\\"'):
                raise ValueError("cookie contains control characters")
            if domain is not None and not isinstance(domain, str):
                raise ValueError("cookie domain must be a string or null")
            if path is not None and not isinstance(path, str):
                raise ValueError("cookie path must be a string or null")
            if source_url is not None and not isinstance(source_url, str):
                raise ValueError("cookie source_url must be a string or null")
            if host_only is not None and not isinstance(host_only, bool):
                raise ValueError("cookie host_only must be a boolean or null")
            source_host: Optional[str] = None
            if source_url is not None:
                source = urlsplit(source_url)
                if source.scheme != "https" or not source.hostname or source.username or source.password:
                    raise ValueError("cookie source_url must be exact https")
                source_host = source.hostname.lower()
                if source_host not in allowed_hosts:
                    raise ValueError("cookie source_url is outside allowed origins")
            elif domain is not None and domain.lower().lstrip(".") in allowed_hosts:
                # Old structured clients lacked source metadata: keep the scope host-only.
                source_host = domain.lower().lstrip(".")
                host_only = True
            else:
                raise ValueError("cookie source_url is required for unknown scope")
            normalized_domain = (domain or source_host).lower().lstrip(".")
            if normalized_domain not in allowed_hosts or normalized_domain != source_host:
                raise ValueError("cookie domain is outside the source origin")
            if host_only is None:
                host_only = domain is None
            rest: dict[str, object] = {}
            if item.get("http_only") is True:
                rest["HttpOnly"] = None
            if item.get("same_site") is not None:
                rest["SameSite"] = item["same_site"]
            if host_only:
                rest["_campusmate_host_only"] = "1"
            if source_url is not None:
                rest["_campusmate_source_url"] = source_url
            if path is None:
                rest["_campusmate_path_unknown"] = "1"
            if item.get("secure") is None:
                rest["_campusmate_secure_unknown"] = "1"
            normalized_path = path or "/"
            expires = item.get("expires")
            if expires is not None and (not isinstance(expires, int) or isinstance(expires, bool) or expires < 0):
                raise ValueError("cookie expires must be a non-negative integer or null")
            jar.jar.set_cookie(Cookie(
                version=0,
                name=name,
                value=value,
                port=None,
                port_specified=False,
                domain=normalized_domain,
                domain_specified=not host_only,
                domain_initial_dot=False,
                path=normalized_path,
                path_specified=path is not None,
                secure=True if item.get("secure") is None else bool(item.get("secure")),
                expires=expires,
                discard=expires is None,
                comment=None,
                comment_url=None,
                rest=rest,
                rfc2109=False,
            ))
        self._cookies = jar

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
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=False, cookies=self._cookies) as client:
                resp = await client.get(url, params=params, headers=self._build_headers(referer=referer))
                self._validate_redirect_target(resp, url)
                self._cookies.update(resp.cookies)
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
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=False, cookies=self._cookies) as client:
                resp = await client.post(
                    url,
                    data=data,
                    params=params,
                    headers=self._build_headers(referer=referer, form_post=form_post),
                )
                self._validate_redirect_target(resp, url)
                self._cookies.update(resp.cookies)
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
        content = bytes(resp.content)
        try:
            text = content.decode(self._encoding or "utf-8", errors="replace")
        except (LookupError, UnicodeDecodeError):
            text = resp.text
        return HttpResponse(
            status=status,
            text=text,
            url=str(resp.url),
            headers=dict(resp.headers),
            content=content,
        )

    @staticmethod
    def _validate_redirect_target(resp: httpx.Response, request_url: str) -> None:
        location = resp.headers.get("location")
        if location:
            assert_safe_url(urljoin(request_url, location))


__all__ = [
    "EduAdapterError",
    "NeedUserAction",
    "HttpResponse",
    "ZhengfangHttpClient",
]
