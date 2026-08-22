"""QR payload 协议 — 跨端统一生成与解析。

二维码内容格式:
    campusmate://auth/web-login?v=1&sid=<session_id>&token=<scan_token>

安全:
- 二维码只包含随机一次性凭据(session_id + scan_token)，不含 JWT / userId / 密码。
- browser_token 不写入二维码。
- 解析时严格校验 scheme / host / version / 参数格式，拒绝任意 URL。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse

SCHEME = "campusmate"
HOST = "auth"
PATH = "/web-login"
VERSION = 1


@dataclass(frozen=True)
class QrPayload:
    session_id: str
    scan_token: str
    version: int = VERSION

    def to_string(self) -> str:
        params = urlencode({"v": self.version, "sid": self.session_id, "token": self.scan_token})
        return f"{SCHEME}://{HOST}{PATH}?{params}"


def build_qr_payload(session_id: str, scan_token: str) -> str:
    """生成二维码字符串。"""
    return QrPayload(session_id=session_id, scan_token=scan_token).to_string()


def parse_qr_payload(raw: str) -> Optional[QrPayload]:
    """解析并严格校验二维码字符串。

    返回 None 表示不是有效的 CampusMate 登录二维码。
    不抛异常，由调用方决定如何处理无效输入。
    """
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    if not raw.startswith(f"{SCHEME}://"):
        return None
    try:
        parsed = urlparse(raw)
    except Exception:
        return None
    if parsed.scheme != SCHEME:
        return None
    if parsed.netloc != HOST:
        return None
    if parsed.path != PATH:
        return None
    qs = parse_qs(parsed.query)
    version_list = qs.get("v", [])
    sid_list = qs.get("sid", [])
    token_list = qs.get("token", [])
    if not version_list or not sid_list or not token_list:
        return None
    try:
        version = int(version_list[0])
    except (ValueError, IndexError):
        return None
    if version != VERSION:
        return None
    session_id = sid_list[0]
    scan_token = token_list[0]
    if not session_id or not scan_token:
        return None
    # 基本长度 sanity check（session_id 至少 16，scan_token 至少 32）
    if len(session_id) < 16 or len(scan_token) < 32:
        return None
    return QrPayload(session_id=session_id, scan_token=scan_token, version=version)