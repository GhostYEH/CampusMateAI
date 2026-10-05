from collections import deque
import gzip
import socket
import ssl

import httpcore
import httpx
import pytest

from app.services.edu.adapters import ssrf_guard
from app.services.edu.adapters.ssrf_guard import SSRFBlockedError
from app.services.edu.adapters.ssrf_transport import (
    CompressedResponseError,
    PinnedNetworkBackend,
    SSRFSafeTransport,
)
from app.services.edu.adapters.zhengfang_http import ZhengfangHttpClient


def _dns(addresses):
    return [(socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))
            for address in addresses]


class MemoryStream(httpcore.AsyncNetworkStream):
    def __init__(self):
        self.responses = deque([b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"] * 2)
        self.writes = []
        self.tls_hosts = []

    async def read(self, max_bytes, timeout=None):
        return self.responses.popleft() if self.responses else b""

    async def write(self, buffer, timeout=None):
        self.writes.append(buffer)

    async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED
        assert ssl_context.check_hostname
        self.tls_hosts.append(server_hostname)
        return self

    def get_extra_info(self, info):
        return None

    async def aclose(self):
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("rebound", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1"])
async def test_school_request_blocks_dns_rebinding_before_connect(monkeypatch, method, rebound):
    lookups = []
    connected = []

    def resolve(*args, **kwargs):
        lookups.append(args[0])
        return _dns(["93.184.216.34"] if len(lookups) == 1 else [rebound])

    async def connect(_self, host, port, **kwargs):
        connected.append(host)
        return MemoryStream()

    monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", resolve)
    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect)
    client = ZhengfangHttpClient(base_url="https://school.example")
    try:
        with pytest.raises(SSRFBlockedError):
            await getattr(client, method)("/login")
    finally:
        await client.aclose()
    assert connected == []
    assert len(lookups) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("address", ["93.184.216.34", "2606:4700:4700::1111"])
async def test_transport_pins_tcp_ip_preserves_host_sni_cookies_and_pool(monkeypatch, address):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")
    monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", lambda *a, **kw: _dns([address]))
    stream = MemoryStream()
    connected = []

    async def connect(_self, host, port, **kwargs):
        connected.append((host, port))
        return stream

    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect)
    client = ZhengfangHttpClient(base_url="https://school.example")
    client.set_cookies({"sid": "test-session"})
    try:
        assert (await client.get("/first")).url == "https://school.example/first"
        assert (await client.post("/second", data={"field": "value"})).text == "ok"
    finally:
        await client.aclose()
    assert connected == [(address, 443)]
    assert stream.tls_hosts == ["school.example"]
    wire = b"".join(stream.writes).lower()
    assert wire.count(b"host: school.example") == 2
    assert wire.count(b"cookie: sid=test-session") == 2


@pytest.mark.asyncio
async def test_backend_rejects_mixed_dns_answers_and_unresolved_names(monkeypatch):
    monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", lambda *a, **kw: _dns(["93.184.216.34", "10.0.0.1"]))
    with pytest.raises(SSRFBlockedError):
        await PinnedNetworkBackend().connect_tcp("school.example", 443)
    monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", lambda *a, **kw: [])
    async with httpx.AsyncClient(transport=SSRFSafeTransport(), trust_env=False) as client:
        with pytest.raises(httpx.ConnectError, match="DNS"):
            await client.get("https://school.example/")


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [httpcore.ConnectError, httpcore.ConnectTimeout])
async def test_backend_falls_back_only_to_other_validated_ips(monkeypatch, failure):
    addresses = ["2606:4700:4700::1111", "1.1.1.1"]
    monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", lambda *a, **kw: _dns(addresses))
    attempts = []

    async def connect(_self, host, port, **kwargs):
        attempts.append(host)
        if len(attempts) == 1:
            raise failure("first address unavailable")
        return MemoryStream()

    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect)
    await PinnedNetworkBackend().connect_tcp("school.example", 443)
    assert attempts == addresses


class RawStream(httpcore.AsyncNetworkStream):
    """按 max_bytes 分片返回一段原始 HTTP 响应。"""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._offset = 0
        self.closed = False

    async def read(self, max_bytes, timeout=None):
        if self._offset >= len(self._payload):
            return b""
        chunk = self._payload[self._offset:self._offset + max_bytes]
        self._offset += len(chunk)
        return chunk

    async def write(self, buffer, timeout=None):
        pass

    async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        return self

    def get_extra_info(self, info):
        return None

    async def aclose(self):
        self.closed = True


def _raw_response(body: bytes, headers: dict[str, str]) -> bytes:
    head = ["HTTP/1.1 200 OK"]
    head.extend(f"{name}: {value}" for name, value in headers.items())
    return ("\r\n".join(head) + "\r\n\r\n").encode("ascii") + body


def _serve_once(monkeypatch, payload: bytes) -> RawStream:
    stream = RawStream(payload)
    monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", lambda *a, **kw: _dns(["93.184.216.34"]))

    async def connect(_self, host, port, **kwargs):
        return stream

    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect)
    return stream


def _count_httpx_decompression(monkeypatch) -> list[int]:
    from httpx import _decoders

    calls: list[int] = []
    original = _decoders.GZipDecoder.decode

    def decode(self, data: bytes) -> bytes:
        calls.append(len(data))
        return original(self, data)

    monkeypatch.setattr(_decoders.GZipDecoder, "decode", decode)
    return calls


@pytest.mark.asyncio
async def test_transport_without_budget_keeps_accepting_encoded_bodies(monkeypatch):
    """未配置预算的教务传输保持原行为：编码正文仍由 httpx 正常解码。"""
    body = b"school-payload " * 200
    compressed = gzip.compress(body, 9)
    _serve_once(monkeypatch, _raw_response(
        compressed,
        {"Content-Type": "text/html", "Content-Encoding": "gzip", "Content-Length": str(len(compressed))},
    ))

    async with httpx.AsyncClient(transport=SSRFSafeTransport(), trust_env=False) as client:
        response = await client.get("https://school.example/page")

    assert response.status_code == 200
    assert response.content == body


@pytest.mark.asyncio
async def test_transport_with_budget_rejects_encoded_body_before_response_is_built(monkeypatch):
    """启用预算时拒绝编码正文，且拒绝发生在 httpx 解码之前。"""
    body = b"school-payload " * 1000
    compressed = gzip.compress(body, 9)
    assert len(compressed) < 4096 < len(body)
    stream = _serve_once(monkeypatch, _raw_response(
        compressed,
        {"Content-Type": "text/html", "Content-Encoding": "gzip", "Content-Length": str(len(compressed))},
    ))
    decode_calls = _count_httpx_decompression(monkeypatch)

    async with httpx.AsyncClient(
        transport=SSRFSafeTransport(max_response_bytes=4096), trust_env=False
    ) as client:
        with pytest.raises(CompressedResponseError, match="content-encoded"):
            await client.get("https://school.example/page")

    assert decode_calls == []
    # 拒绝路径也要及时关闭上游响应，不能把连接挂在池里。
    assert stream.closed is True


@pytest.mark.asyncio
async def test_transport_with_budget_still_accepts_plain_bodies(monkeypatch):
    body = b"<html>plain</html>"
    _serve_once(monkeypatch, _raw_response(
        body, {"Content-Type": "text/html", "Content-Length": str(len(body))},
    ))

    async with httpx.AsyncClient(
        transport=SSRFSafeTransport(max_response_bytes=4096), trust_env=False
    ) as client:
        response = await client.get("https://school.example/page")

    assert response.content == body
