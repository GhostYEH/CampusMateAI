"""把上游返回的**自由文本**做脱敏，再下发给客户端。

为什么需要：`magicclassClient` 会把上游响应里的 `error` / `message` 原样取出来，
最终经由 `magicclassSessionOut.error` / `.message` 下发到学生客户端。上游文本**不可信**：

    {"success": false, "error": "connect ECONNREFUSED http://magicclass:3000/api/classroom"}

或者运维把 ACCESS_CODE 拼进了报错里。这类内容一旦下发，就同时泄露了内部拓扑与凭据。

因此：任何来自上游的自由文本，在下发前都必须经过本模块。
"""
from __future__ import annotations

import re
from typing import Any, Optional

#: 内部服务主机名（Docker 服务名）。即便换了端口/路径也必须遮掉。
_INTERNAL_HOST_RE = re.compile(
    r"https?://[A-Za-z0-9._-]*magicclass[A-Za-z0-9._-]*(?::\d+)?[^\s\"'<>]*",
    re.IGNORECASE,
)

#: Cookie / Authorization 这类凭据出现在文本里时一并遮掉。
#: 注意 `Bearer <token>` 是两段，必须连 token 一起吃掉，否则会留下半截凭据。
_CREDENTIAL_RE = re.compile(
    r"(?i)\b(cookie|set-cookie|authorization|access[_-]?code|api[_-]?key)\b\s*[:=]\s*"
    r"(?:bearer\s+)?[^\s;,\"']+"
)

#: 兜底：形如 `magicclass_access=<value>` 的 cookie 名
_COOKIE_NAME_RE = re.compile(r"(?i)\bmagicclass_access\s*=\s*\S+")

_REDACTED = "[已隐藏]"

#: 下发文本的长度上限（错误信息只需要可操作，不需要整段堆栈）
MAX_PUBLIC_TEXT = 300


def redact_public_text(text: Optional[Any], settings: Any = None) -> Optional[str]:
    """脱敏 + 截断。空值原样返回（None 保持 None，空串保持空串）。"""
    if text is None:
        return None
    out = str(text)
    if not out:
        return ""
    secrets = [
        getattr(settings, "magicclass_access_code", "") if settings is not None else "",
        getattr(settings, "magicclass_base_url", "") if settings is not None else "",
        getattr(settings, "magicclass_origin", "") if settings is not None else "",
        getattr(settings, "magicclass_public_origin", "") if settings is not None else "",
    ]
    for secret in secrets:
        value = str(secret or "")
        if value and len(value) >= 4:
            out = out.replace(value, _REDACTED)
    out = _INTERNAL_HOST_RE.sub(_REDACTED, out)
    out = _CREDENTIAL_RE.sub(lambda m: f"{m.group(1)}={_REDACTED}", out)
    out = _COOKIE_NAME_RE.sub(_REDACTED, out)
    return out[:MAX_PUBLIC_TEXT]


__all__ = ["MAX_PUBLIC_TEXT", "redact_public_text"]
