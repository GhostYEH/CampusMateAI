"""SSRF 防护与 HTTP 工具。

EduConnector 在 backend 模式下会请求学校教务系统 URL，必须严格校验目标地址，
拒绝 localhost / 内网 / file:// / ftp:// 等危险目标。

某些学校系统真实属于校内网（requires_campus_network=true），
此类不删除数据，但禁止 backend_http 模式，强制走 client_webview。
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


class SSRFBlockedError(Exception):
    """目标 URL 被 SSRF 防护拒绝。"""


@dataclass
class UrlSafetyReport:
    allowed: bool
    reason: Optional[str] = None
    final_host: Optional[str] = None
    is_private: bool = False


def check_url_safety(url: str, *, allow_private: bool = False) -> UrlSafetyReport:
    """校验 URL 是否安全可请求。

    - 拒绝非 http/https
    - 拒绝 localhost / 127.0.0.1 / 0.0.0.0 / ::1
    - 拒绝 169.254.0.0/16（链路本地）
    - 默认拒绝 RFC1918 内网（除非 allow_private=True）
    - 不解析 DNS（避免 DNS rebinding 复杂度），只校验字面 host
    """
    if not url or not isinstance(url, str):
        return UrlSafetyReport(allowed=False, reason="empty url")
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return UrlSafetyReport(allowed=False, reason=f"scheme {scheme!r} not allowed")
    host = (parsed.hostname or "").lower()
    if not host:
        return UrlSafetyReport(allowed=False, reason="missing host")
    if host in ("localhost", "ip6-localhost", "ip6-loopback"):
        return UrlSafetyReport(allowed=False, reason="localhost blocked")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        if ip.is_loopback:
            return UrlSafetyReport(allowed=False, reason="loopback ip blocked")
        if ip.is_link_local:
            return UrlSafetyReport(allowed=False, reason="link-local blocked")
        if ip.is_multicast:
            return UrlSafetyReport(allowed=False, reason="multicast blocked")
        if ip.is_reserved:
            return UrlSafetyReport(allowed=False, reason="reserved ip blocked")
        if ip.is_private and not allow_private:
            return UrlSafetyReport(
                allowed=False, reason="private ip blocked (requires_campus_network should use client_webview)",
                is_private=True,
            )
        if ip.is_private and allow_private:
            return UrlSafetyReport(allowed=True, final_host=host, is_private=True)
    return UrlSafetyReport(allowed=True, final_host=host)


def assert_safe_url(url: str, *, allow_private: bool = False) -> None:
    report = check_url_safety(url, allow_private=allow_private)
    if not report.allowed:
        raise SSRFBlockedError(f"URL blocked: {url!r} -> {report.reason}")


def safe_join_url(base: str, path: str) -> str:
    """拼接 base_url + path，处理首尾斜杠。"""
    if not path:
        return base
    if path.startswith(("http://", "https://")):
        return path
    return base.rstrip("/") + ("" if path.startswith("/") else "/") + path


__all__ = [
    "SSRFBlockedError",
    "UrlSafetyReport",
    "check_url_safety",
    "assert_safe_url",
    "safe_join_url",
]