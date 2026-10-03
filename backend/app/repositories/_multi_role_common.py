"""Identifiers, timestamps and invite codes shared by the multi-role repositories."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _generate_invite_code() -> str:
    """生成 8 位邀请码(数字 + 大写字母,去除易混淆字符)。"""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去掉 I/O/0/1
    return "".join(secrets.choice(alphabet) for _ in range(8))
