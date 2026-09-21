"""浏览器公开课堂地址的构造与校验。

背景：生产部署下 magicclass 的**内部**服务地址与**浏览器公开**地址必然不同。

    MAGICCLASS_BASE_URL     = http://magicclass:3000            （内部，Docker 网络）
    MAGICCLASS_EMBED_ORIGIN = https://classroom.example.edu    （浏览器公开）

上游 `/api/generate-classroom` 返回的 `result.url` 永远是内部地址。若把它原样写进
session / 历史 / API 响应，会造成两个后果：内部拓扑泄露，且客户端只信任公开 Origin
导致课堂一律打不开。

因此领域层只保存**经过校验的 classroom_id**，公开地址一律由本模块按公开 Origin 现场构造。
"""
from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlparse

# 与 magic class 的 `isValidClassroomId` 保持一致（/^[a-zA-Z0-9_-]+$/），另加长度上限
CLASSROOM_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,192}$")


def is_valid_classroom_id(classroom_id: Any) -> bool:
    return isinstance(classroom_id, str) and bool(CLASSROOM_ID_RE.match(classroom_id))


def build_public_classroom_url(
    *,
    public_origin: str,
    classroom_id: Any,
    require_https: bool = True,
) -> Optional[str]:
    """按公开 Origin 构造 `/classroom/{id}`。任一条不满足即返回 None（fail-closed）。

    - classroom_id 必须符合白名单；
    - 公开 Origin 必须是裸 origin：http(s)、有 netloc、无凭据/query/fragment/路径；
    - `require_https=True`（生产）时强制 HTTPS。
    """
    if not public_origin or not is_valid_classroom_id(classroom_id):
        return None
    parsed = urlparse(str(public_origin))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None
    if parsed.path not in ("", "/"):
        return None
    if require_https and parsed.scheme != "https":
        return None
    return f"{parsed.scheme}://{parsed.netloc}/classroom/{classroom_id}"


def resolve_public_classroom_url(settings: Any, classroom_id: Any) -> Optional[str]:
    """从 Settings 解析公开课堂地址；未配置公开 Origin 时返回 None。"""
    return build_public_classroom_url(
        public_origin=getattr(settings, "magicclass_public_origin", "") or "",
        classroom_id=classroom_id,
        require_https=getattr(settings, "app_env", "development") == "production",
    )


def public_classroom_url_for_session(settings: Any, session: Any) -> Optional[str]:
    """读取历史 session 的公开地址。

    - 有可信 `classroom_id` → 用公开 Origin **重新构造**（旧数据里的内部 URL 就此被替换，
      且不做破坏性迁移：落盘文件保持原样）；
    - 没有可信 `classroom_id` → 返回 None，绝不回落旧 URL。
    """
    return resolve_public_classroom_url(settings, getattr(session, "classroom_id", None))


def public_url_unavailable_reason(session: Any) -> Optional[str]:
    """无法构造公开地址时的**可操作**原因（不含任何内部地址/凭据）。"""
    if not getattr(session, "classroom_id", None):
        return "该课堂缺少可验证的课堂标识，无法构造安全地址"
    return "当前部署未开放浏览器访问（未配置公开课堂地址）"


def project_session_url(settings: Any, session: Any) -> tuple[Optional[str], Optional[str]]:
    """**唯一**的公开课堂地址投影入口：返回 (url, unavailable_reason)。

    约定（任何下发课堂地址的响应都必须经过这里）：

    * `classroom_id` 是课堂身份的**权威**字段；
    * 数据库里历史保存的 `classroom_url` **永不**被信任，也永不直接下发；
    * 公开 Origin 未配置 / classroom_id 非法 → `(None, reason)`，fail-closed。
    """
    url = public_classroom_url_for_session(settings, session)
    return url, (None if url else public_url_unavailable_reason(session))


def is_internal_url_leaked(url: Optional[str], settings: Any) -> bool:
    """诊断辅助：url 是否指向内部服务 Origin。"""
    if not url:
        return False
    internal = getattr(settings, "magicclass_origin", "") or ""
    if not internal:
        return False
    return str(url).startswith(internal)


__all__ = [
    "CLASSROOM_ID_RE",
    "is_valid_classroom_id",
    "build_public_classroom_url",
    "resolve_public_classroom_url",
    "public_classroom_url_for_session",
    "public_url_unavailable_reason",
    "project_session_url",
    "is_internal_url_leaked",
]
