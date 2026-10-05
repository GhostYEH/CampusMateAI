"""Connect only to validated IPs while retaining the origin for HTTP and TLS."""
from __future__ import annotations

from contextlib import contextmanager
from functools import partial
import ssl
import time

import anyio
import httpcore
import httpx

from .ssrf_guard import SSRFBlockedError, check_url_safety


class ResponseTooLargeError(Exception):
    """Upstream body exceeded the caller's hard byte budget.

    Raised while the body is still being accumulated, so a caller with a size
    limit never has to download a whole oversized response first.
    """


class PinnedNetworkBackend(httpcore.AnyIOBackend):
    def __init__(self, *, allow_private: bool = False) -> None:
        self._allow_private = allow_private

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        try:
            # Bound DNS and all address attempts by the connection timeout.
            with anyio.fail_after(timeout):
                url_host = f"[{host}]" if ":" in host else host
                report = await anyio.to_thread.run_sync(
                    partial(check_url_safety, f"https://{url_host}:{port}/", allow_private=self._allow_private),
                    abandon_on_cancel=True,
                )
                if not report.allowed:
                    raise SSRFBlockedError(f"Connection blocked: {report.reason}")
                if not report.resolved_addresses:
                    raise httpcore.ConnectError("DNS returned no usable addresses")
                last_error = None
                for index, address in enumerate(report.resolved_addresses):
                    attempt_timeout = None if deadline is None else max(
                        0, (deadline - time.monotonic()) / (len(report.resolved_addresses) - index)
                    )
                    try:
                        # A literal IP cannot undergo another hostname lookup.
                        # httpcore still uses the original host for SNI/certificates.
                        return await super().connect_tcp(
                            address, port, timeout=attempt_timeout, local_address=local_address,
                            socket_options=socket_options,
                        )
                    except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                        last_error = exc
                raise last_error
        except TimeoutError as exc:
            raise httpcore.ConnectTimeout("Connection timed out") from exc


_ERROR_TYPES = (
    "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout",
    "ConnectError", "ReadError", "WriteError", "RemoteProtocolError",
    "LocalProtocolError", "ProxyError", "UnsupportedProtocol",
)
_ERROR_MAP = {getattr(httpcore, name): getattr(httpx, name) for name in _ERROR_TYPES}


@contextmanager
def _map_errors():
    try:
        yield
    except tuple(_ERROR_MAP) as exc:
        for source, target in _ERROR_MAP.items():
            if isinstance(exc, source):
                raise target(str(exc)) from exc
        raise


class SSRFSafeTransport(httpx.AsyncBaseTransport):
    """Direct, pooled transport for buffered school HTTP requests; no proxies.

    ``max_response_bytes`` is opt-in. When set, the body is read incrementally
    and the request is aborted as soon as the running total exceeds the budget,
    instead of buffering everything and rejecting it afterwards.
    """

    def __init__(
        self,
        *,
        allow_private: bool = False,
        verify: bool | ssl.SSLContext = True,
        max_response_bytes: int | None = None,
    ) -> None:
        context = verify if isinstance(verify, ssl.SSLContext) else httpcore.default_ssl_context()
        if verify is False:
            # Only callers with the existing non-production opt-in use this.
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        self._max_response_bytes = max_response_bytes
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=context,
            max_connections=100, max_keepalive_connections=20, keepalive_expiry=5,
            network_backend=PinnedNetworkBackend(allow_private=allow_private),
        )

    async def _read_body(self, response: httpcore.Response) -> bytes:
        if self._max_response_bytes is None:
            return await response.aread()
        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_stream():
            total += len(chunk)
            if total > self._max_response_bytes:
                raise ResponseTooLargeError(
                    f"upstream body exceeded {self._max_response_bytes} bytes"
                )
            chunks.append(chunk)
        return b"".join(chunks)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        core_request = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme, host=request.url.raw_host,
                port=request.url.port, target=request.url.raw_path,
            ),
            headers=request.headers.raw, content=request.stream, extensions=request.extensions,
        )
        with _map_errors():
            response = await self._pool.handle_async_request(core_request)
            try:
                content = await self._read_body(response)
            finally:
                await response.aclose()
        return httpx.Response(
            response.status, headers=response.headers, content=content, extensions=response.extensions,
        )

    async def aclose(self) -> None:
        with _map_errors():
            await self._pool.aclose()
