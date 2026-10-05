"""课程研究受控抓取器的出网安全回归测试。

覆盖:
- 校验通过后 DNS 变为私网（重绑定）时禁止连接
- 混合公网/私网解析结果直接拒绝
- 私网重定向在第二次请求前被拦截
- 无法取得可用解析结果时禁止连接
- 实际 TCP 连接使用校验过的 IP，Host / TLS SNI 仍用原域名
- 无 Content-Length 的超大响应在正文累积过程中被中止

全部使用模拟 DNS 与内存网络流，不请求真实私网或公网服务。
"""
from __future__ import annotations

import socket

import httpcore
import pytest

from app.services.course_research.source_fetcher import ControlledSourceFetcher, SSRFViolation
from app.services.edu.adapters import ssrf_guard

PUBLIC_IP = "93.184.216.34"
SECOND_PUBLIC_IP = "1.1.1.1"
PRIVATE_IP = "10.0.0.7"


def _dns(addresses: list[str]):
    return [
        (socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))
        for address in addresses
    ]


class ByteStream(httpcore.AsyncNetworkStream):
    """把一段原始 HTTP 响应按 max_bytes 分片返回，并记录实际发送字节数。"""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._offset = 0
        self.writes: list[bytes] = []
        self.tls_hosts: list[str | None] = []
        self.served = 0

    async def read(self, max_bytes, timeout=None):
        if self._offset >= len(self._payload):
            return b""
        chunk = self._payload[self._offset:self._offset + max_bytes]
        self._offset += len(chunk)
        self.served += len(chunk)
        return chunk

    async def write(self, buffer, timeout=None):
        self.writes.append(buffer)

    async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        assert ssl_context.verify_mode == __import__("ssl").CERT_REQUIRED
        assert ssl_context.check_hostname
        self.tls_hosts.append(server_hostname)
        return self

    def get_extra_info(self, info):
        return None

    async def aclose(self):
        pass


def _http_response(status: str, body: bytes, headers: dict[str, str]) -> bytes:
    head = [f"HTTP/1.1 {status}"]
    head.extend(f"{name}: {value}" for name, value in headers.items())
    return ("\r\n".join(head) + "\r\n\r\n").encode("ascii") + body


def _chunked_body(payload: bytes, chunk_size: int = 4096) -> bytes:
    parts = []
    for start in range(0, len(payload), chunk_size):
        piece = payload[start:start + chunk_size]
        parts.append(f"{len(piece):x}\r\n".encode("ascii") + piece + b"\r\n")
    parts.append(b"0\r\n\r\n")
    return b"".join(parts)


def _patch_dns(monkeypatch, answers):
    """按调用顺序返回解析结果。

    ``answers`` 可以是单个可调用对象，也可以是「每跳答案」的列表；列表元素
    既可以是地址列表，也可以是返回地址列表的可调用对象。
    """
    calls: list[tuple] = []

    if callable(answers):
        def resolve(*args, **kwargs):
            calls.append(args)
            return answers(*args, **kwargs)
    else:
        queue = list(answers)

        def resolve(*args, **kwargs):
            calls.append(args)
            if not queue:
                return []
            item = queue.pop(0)
            return item(*args, **kwargs) if callable(item) else item

    monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", resolve)
    return calls


def _patch_connect(monkeypatch, stream_factory, connected: list):
    async def connect(_self, host, port, **kwargs):
        connected.append((host, port))
        return stream_factory()

    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect)


@pytest.mark.asyncio
async def test_dns_rebinding_to_private_is_blocked_and_never_connects(monkeypatch):
    """validate_url 看到公网、连接层解析到私网时必须拒绝连接。"""
    _patch_dns(monkeypatch, [lambda *a, **k: _dns([PUBLIC_IP]), lambda *a, **k: _dns([PRIVATE_IP])])
    connected: list = []
    _patch_connect(monkeypatch, lambda: ByteStream(_http_response("200 OK", b"ok", {"Content-Length": "2"})), connected)

    fetcher = ControlledSourceFetcher()
    with pytest.raises(SSRFViolation):
        await fetcher.fetch("https://example.com/page")

    assert connected == []


@pytest.mark.asyncio
async def test_mixed_public_and_private_answers_are_rejected_before_connect(monkeypatch):
    _patch_dns(monkeypatch, lambda *a, **k: _dns([PUBLIC_IP, PRIVATE_IP]))
    connected: list = []
    _patch_connect(monkeypatch, lambda: ByteStream(b""), connected)

    fetcher = ControlledSourceFetcher()
    with pytest.raises(SSRFViolation, match="私网|本地"):
        await fetcher.fetch("https://example.com/page")

    assert connected == []


@pytest.mark.asyncio
async def test_private_redirect_is_blocked_before_second_request(monkeypatch):
    _patch_dns(monkeypatch, lambda *a, **k: _dns([PUBLIC_IP]))
    connected: list = []
    stream = ByteStream(_http_response(
        "302 Found", b"", {"Location": "http://127.0.0.1/internal", "Content-Length": "0"}
    ))
    _patch_connect(monkeypatch, lambda: stream, connected)

    fetcher = ControlledSourceFetcher()
    with pytest.raises(SSRFViolation, match="私网|本地"):
        await fetcher.fetch("https://example.com/start")

    # 只发生了第一次请求，且连接到的是校验过的公网 IP。
    assert connected == [(PUBLIC_IP, 443)]


@pytest.mark.asyncio
async def test_unresolvable_host_blocks_connection(monkeypatch):
    _patch_dns(monkeypatch, lambda *a, **k: [])
    connected: list = []
    _patch_connect(monkeypatch, lambda: ByteStream(b""), connected)

    fetcher = ControlledSourceFetcher()
    with pytest.raises(SSRFViolation):
        await fetcher.fetch("https://unresolved.example/page")

    assert connected == []


@pytest.mark.asyncio
async def test_connection_pins_validated_ip_and_preserves_host_and_sni(monkeypatch):
    _patch_dns(monkeypatch, lambda *a, **k: _dns([SECOND_PUBLIC_IP]))
    connected: list = []
    stream = ByteStream(_http_response(
        "200 OK", b"<html><title>Example</title></html>", {"Content-Type": "text/html", "Content-Length": "35"}
    ))
    _patch_connect(monkeypatch, lambda: stream, connected)

    fetcher = ControlledSourceFetcher()
    result = await fetcher.fetch("https://example.com/page")

    assert result.title == "Example"
    # TCP 只连到校验过的 IP；Host 与 TLS SNI 仍是原域名。
    assert connected == [(SECOND_PUBLIC_IP, 443)]
    assert stream.tls_hosts == ["example.com"]
    assert b"host: example.com" in b"".join(stream.writes).lower()


@pytest.mark.asyncio
async def test_oversized_response_without_content_length_is_aborted_while_accumulating(monkeypatch):
    """没有 Content-Length 的超大响应必须在累积过程中中止，而不是下载完再判断。"""
    _patch_dns(monkeypatch, lambda *a, **k: _dns([PUBLIC_IP]))
    payload = b"x" * (512 * 1024)
    stream = ByteStream(_http_response(
        "200 OK",
        _chunked_body(payload),
        {"Content-Type": "text/html", "Transfer-Encoding": "chunked"},
    ))
    connected: list = []
    _patch_connect(monkeypatch, lambda: stream, connected)

    fetcher = ControlledSourceFetcher(max_bytes=1024)
    with pytest.raises(SSRFViolation, match="响应过大"):
        await fetcher.fetch("https://example.com/big")

    assert connected == [(PUBLIC_IP, 443)]
    # 明确证明没有把整个响应读完。
    assert stream.served < len(payload)


@pytest.mark.asyncio
async def test_allow_web_false_never_touches_dns_or_network(monkeypatch):
    calls = _patch_dns(monkeypatch, lambda *a, **k: _dns([PUBLIC_IP]))
    connected: list = []
    _patch_connect(monkeypatch, lambda: ByteStream(b""), connected)

    from app.core.exceptions import AgentSourcePolicyViolation

    fetcher = ControlledSourceFetcher()
    with pytest.raises(AgentSourcePolicyViolation):
        await fetcher.fetch("https://example.com/page", allow_web=False)

    assert calls == []
    assert connected == []
