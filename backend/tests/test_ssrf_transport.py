from collections import deque
import socket
import ssl

import httpcore
import httpx
import pytest

from app.services.edu.adapters import ssrf_guard
from app.services.edu.adapters.ssrf_guard import SSRFBlockedError
from app.services.edu.adapters.ssrf_transport import PinnedNetworkBackend, SSRFSafeTransport
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
