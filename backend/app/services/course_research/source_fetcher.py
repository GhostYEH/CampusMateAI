"""受控检索工具(§8.2、§11)。

公共 Web 访问必须走本模块,执行 SSRF 防护:
- 私网/本地/loopback/link-local 拒绝
- 协议/主机检查(仅 HTTP/HTTPS)
- 超时和内容大小限制
- 重定向逃逸检查
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

from ...core.exceptions import AgentSourcePolicyViolation


@dataclass(frozen=True)
class FetchedSource:
    """受控检索结果。"""

    url: str
    title: str
    snippet: str
    accessed_at: str
    status_code: int
    content_type: Optional[str] = None


class SSRFViolation(Exception):
    """SSRF 防护拒绝。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# 私网/保留地址检查
def _is_private_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_url(
    url: str,
    *,
    allowed_schemes: tuple[str, ...] = ("http", "https"),
) -> str:
    """校验 URL 安全性。返回规范化后的 URL。

    拒绝:
    - 非 HTTP(S) 协议
    - 私网/本地/loopback/link-local 地址
    - 无主机
    - IP 字面量解析为私网
    - 主机名解析为私网(尽力解析)
    """
    if not url or not isinstance(url, str):
        raise SSRFViolation("URL 为空")
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in allowed_schemes:
        raise SSRFViolation(f"协议不被允许: {scheme}")
    host = parsed.hostname
    if not host:
        raise SSRFViolation("URL 缺少主机")
    # 显式 IP 字面量
    try:
        ip = ipaddress.ip_address(host)
        if _is_private_ip(ip):
            raise SSRFViolation(f"目标地址为私网/本地: {host}")
        return url
    except ValueError:
        pass
    # 主机名:解析并检查所有 A/AAAA 记录
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        # 无法解析:允许通过(可能在 fetch 时失败),但记录
        return url
    for family, _, _, _, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
            if _is_private_ip(ip):
                raise SSRFViolation(f"主机 {host} 解析到私网地址: {ip_str}")
        except ValueError:
            continue
    return url


class ControlledSourceFetcher:
    """受控检索工具。

    公共 Web 访问必须经过 SSRF 防护。课程资料检索不走本工具,
    直接通过 CourseContentRepository / RetrievalService。
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        max_bytes: int = 1024 * 1024,  # 1 MiB
        max_redirects: int = 3,
        transport=None,
    ) -> None:
        self._timeout = timeout_seconds
        self._max_bytes = max_bytes
        self._max_redirects = max_redirects
        self._transport = transport

    def validate(self, url: str) -> str:
        """仅校验,不发起请求。"""
        return validate_url(url)

    async def fetch(
        self,
        url: str,
        *,
        allow_web: bool = True,
    ) -> FetchedSource:
        """受控 fetch。

        - allow_web=False 时直接拒绝(硬约束)
        - SSRF 校验
        - 超时、大小、重定向限制
        """
        if not allow_web:
            raise AgentSourcePolicyViolation(
                "来源策略禁止公共 Web 检索",
                code="AGENT_SOURCE_POLICY_VIOLATION",
                http_status=403,
            )
        validated = validate_url(url)
        # 延迟导入 httpx,避免在纯单元测试中强制依赖网络
        import httpx
        from datetime import datetime, timezone

        async with httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=False,
            transport=self._transport,
        ) as client:
            try:
                current_url = validated
                for redirect_count in range(self._max_redirects + 1):
                    # Validate every hop before sending it. Validating only resp.url
                    # after automatic redirects is too late: the private request has
                    # already happened at that point.
                    validate_url(current_url)
                    resp = await client.get(current_url)
                    if resp.status_code not in (301, 302, 303, 307, 308):
                        break
                    location = resp.headers.get("location")
                    if not location:
                        break
                    if redirect_count >= self._max_redirects:
                        raise SSRFViolation("重定向次数过多")
                    current_url = urljoin(current_url, location)
                else:  # pragma: no cover - loop always exits or raises
                    raise SSRFViolation("重定向次数过多")
            except httpx.TimeoutException as e:
                raise SSRFViolation(f"请求超时: {e}") from e
            except (httpx.HTTPError, OSError) as e:
                raise SSRFViolation(f"请求失败: {type(e).__name__}") from e
            final_url = str(resp.url)
            validate_url(final_url)
            # 大小限制
            content_length = int(resp.headers.get("content-length", 0))
            if content_length and content_length > self._max_bytes:
                raise SSRFViolation("响应过大")
            body = resp.text
            if len(body.encode("utf-8")) > self._max_bytes:
                raise SSRFViolation("响应过大")
            # 提取 title
            title = _extract_title(body) or final_url
            snippet = body[:500]
            return FetchedSource(
                url=final_url,
                title=title,
                snippet=snippet,
                accessed_at=datetime.now(timezone.utc).isoformat(),
                status_code=resp.status_code,
                content_type=resp.headers.get("content-type"),
            )


def _extract_title(html: str) -> Optional[str]:
    """从 HTML 中提取 <title>。"""
    import re

    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()[:256]
    return None


__all__ = [
    "ControlledSourceFetcher",
    "FetchedSource",
    "SSRFViolation",
    "validate_url",
]
