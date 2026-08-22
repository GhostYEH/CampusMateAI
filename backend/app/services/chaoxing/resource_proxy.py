from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx


class CourseResourceProxyError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ChaoxingResourceProxy:
    ALLOWED_HOSTS = {
        "chaoxing.com", "ananas.chaoxing.com", "pan-yz.chaoxing.com",
        "p.ananas.chaoxing.com", "d0.ananas.chaoxing.com",
        "mooc1-api.chaoxing.com", "mooc1.chaoxing.com",
        "cldisk.com", "d0.cldisk.com", "s3.cldisk.com",
    }

    STREAMING_KINDS = {"video", "audio"}

    def __init__(self, *, settings, repository, credentials: dict) -> None:
        self.settings = settings
        self.repository = repository
        self.credentials = credentials

    @classmethod
    def validate_url(cls, url: str) -> str:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host:
            raise CourseResourceProxyError("resource_host_not_allowed")
        allowed = any(host == suffix or host.endswith(f".{suffix}") for suffix in cls.ALLOWED_HOSTS)
        if not allowed:
            raise CourseResourceProxyError("resource_host_not_allowed")
        return url

    @staticmethod
    def safe_filename(title: str, mime_type: str | None = None) -> str:
        name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", title).strip(" ._") or "resource"
        return name[:180]

    @staticmethod
    def _mobile_ua() -> str:
        return (
            "Dalvik/2.1.0 (Linux; U; Android 12) Language/zh_CN "
            "com.chaoxing.mobile/ChaoXingStudy_3_6.3.7_android_phone"
        )

    async def _resolve_download_url(self, item) -> str:
        source_url = item.source_url
        if item.remote_object_id:
            status_url = (
                "https://mooc1.chaoxing.com/ananas/status/"
                f"{item.remote_object_id}?flag=normal"
            )
            try:
                async with httpx.AsyncClient(
                    cookies=self.credentials, timeout=httpx.Timeout(30, connect=10)
                ) as status_client:
                    status_response = await status_client.get(
                        status_url,
                        headers={
                            "Referer": item.source_url or "https://mooc1.chaoxing.com/",
                            "User-Agent": self._mobile_ua(),
                        },
                    )
                    if status_response.status_code in (401, 403):
                        raise CourseResourceProxyError("chaoxing_session_expired")
                    status_response.raise_for_status()
                    status_data = status_response.json()
            except CourseResourceProxyError:
                raise
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError, TypeError) as error:
                raise CourseResourceProxyError("resource_metadata_error") from error
            if status_data.get("status") != "success" or not status_data.get("download"):
                raise CourseResourceProxyError("resource_metadata_error")
            source_url = str(status_data["download"])
            if source_url.startswith("http://"):
                source_url = "https://" + source_url[len("http://"):]
        if not source_url:
            raise CourseResourceProxyError("resource_url_missing")
        return self.validate_url(source_url)

    async def stream_file(self, *, item, range_header: str | None = None) -> dict:
        """流式代理视频/音频资源，支持 HTTP Range/206。

        不将完整内容写入本地缓存，直接将上游响应流式转发给客户端。
        需要真实学习通账号验证 Range 转发与 206 响应。
        """
        current_url = await self._resolve_download_url(item)
        headers = {
            "Referer": item.source_url or "https://mooc1.chaoxing.com/",
            "User-Agent": self._mobile_ua(),
        }
        if range_header:
            headers["Range"] = range_header
        client = httpx.AsyncClient(
            cookies=self.credentials,
            timeout=httpx.Timeout(60, connect=10),
            headers=headers,
        )
        try:
            request = client.build_request("GET", current_url)
            response = await client.send(request, stream=True, follow_redirects=False)
            redirects = 0
            while response.status_code in (301, 302, 303, 307, 308) and redirects < 6:
                location = response.headers.get("location")
                await response.aclose()
                if not location:
                    raise CourseResourceProxyError("resource_redirect_invalid")
                current_url = self.validate_url(urljoin(current_url, location))
                request = client.build_request("GET", current_url)
                response = await client.send(request, stream=True, follow_redirects=False)
                redirects += 1
            if response.status_code in (401, 403):
                await response.aclose()
                raise CourseResourceProxyError("chaoxing_session_expired")
            if response.status_code == 404:
                await response.aclose()
                raise CourseResourceProxyError("resource_not_found")
            if response.status_code >= 400:
                await response.aclose()
                raise CourseResourceProxyError(f"http_error_{response.status_code}")
        except CourseResourceProxyError:
            await client.aclose()
            raise
        except httpx.RequestError as error:
            await client.aclose()
            raise CourseResourceProxyError("resource_network_error") from error

        mime_type = response.headers.get("content-type")
        content_length = response.headers.get("content-length")
        content_range = response.headers.get("content-range")
        status_code = response.status_code

        async def stream_generator():
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        response_headers: dict[str, str | None] = {
            "content-length": content_length,
            "content-range": content_range,
            "accept-ranges": "bytes",
        }
        return {
            "stream": stream_generator(),
            "mime_type": mime_type,
            "filename": self.safe_filename(item.title, mime_type),
            "status_code": status_code,
            "headers": response_headers,
        }

    async def get_file(self, *, item) -> tuple[Path, str | None, str]:
        cache_dir = self.settings.chaoxing_cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached = self.repository.get_cache(item_id=item.id, user_id=item.user_id)
        if cached:
            path = (cache_dir / cached["relative_path"]).resolve()
            mime_type = (cached.get("mime_type") or "").lower()
            valid_type = "application/json" not in mime_type and "text/html" not in mime_type
            valid_size = int(cached.get("file_size") or 0) > 0
            if path.is_file() and cache_dir.resolve() in path.parents and valid_type and valid_size:
                return path, cached.get("mime_type"), self.safe_filename(item.title)
            stale_relative_path = self.repository.delete_cache(item_id=item.id, user_id=item.user_id)
            if stale_relative_path:
                stale_path = (cache_dir / stale_relative_path).resolve()
                if cache_dir.resolve() in stale_path.parents:
                    stale_path.unlink(missing_ok=True)

        current_url = await self._resolve_download_url(item)
        max_bytes = int(self.settings.chaoxing_cache_file_max_mb) * 1024 * 1024
        client = httpx.AsyncClient(
            cookies=self.credentials,
            timeout=httpx.Timeout(60, connect=10),
            headers={
                "Referer": item.source_url or "https://mooc1.chaoxing.com/",
                "User-Agent": self._mobile_ua(),
            },
        )
        tmp_path = cache_dir / f".{item.id}.{os.getpid()}.part"
        digest = hashlib.sha256()
        size = 0
        try:
            for _ in range(6):
                async with client.stream("GET", current_url, follow_redirects=False) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location:
                            raise CourseResourceProxyError("resource_redirect_invalid")
                        current_url = self.validate_url(urljoin(current_url, location))
                        continue
                    if response.status_code in (401, 403):
                        raise CourseResourceProxyError("chaoxing_session_expired")
                    if response.status_code == 404:
                        raise CourseResourceProxyError("resource_not_found")
                    response.raise_for_status()
                    content_type = (response.headers.get("content-type") or "").lower()
                    if "application/json" in content_type or "text/html" in content_type:
                        raise CourseResourceProxyError("resource_invalid_payload")
                    length = response.headers.get("content-length")
                    if length and int(length) > max_bytes:
                        raise CourseResourceProxyError("resource_too_large")
                    with tmp_path.open("wb") as output:
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > max_bytes:
                                raise CourseResourceProxyError("resource_too_large")
                            digest.update(chunk)
                            output.write(chunk)
                    content_hash = digest.hexdigest()
                    final_path = cache_dir / content_hash[:2] / content_hash
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                    if not final_path.exists():
                        tmp_path.replace(final_path)
                    else:
                        tmp_path.unlink(missing_ok=True)
                    mime_type = response.headers.get("content-type")
                    relative_path = final_path.relative_to(cache_dir).as_posix()
                    self.repository.upsert_cache(
                        item_id=item.id, user_id=item.user_id, course_id=item.course_id,
                        relative_path=relative_path, content_hash=content_hash,
                        mime_type=mime_type, file_size=size,
                    )
                    max_cache_bytes = int(self.settings.chaoxing_cache_max_mb) * 1024 * 1024
                    for stale_relative_path in self.repository.prune_cache(max_bytes=max_cache_bytes):
                        stale_path = (cache_dir / stale_relative_path).resolve()
                        if cache_dir.resolve() in stale_path.parents:
                            stale_path.unlink(missing_ok=True)
                    return final_path, mime_type, self.safe_filename(item.title, mime_type)
            raise CourseResourceProxyError("resource_redirect_limit")
        except httpx.RequestError as error:
            raise CourseResourceProxyError("resource_network_error") from error
        finally:
            tmp_path.unlink(missing_ok=True)
            await client.aclose()
