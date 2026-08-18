"""QR 扫码登录与可信设备数据行模型。

所有 token 字段仅保存哈希(SHA-256)，不保存明文。
所有时间字段以 ISO 8601 字符串存储(带时区)。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class QrLoginSessionRow:
    id: str
    scan_token_hash: str
    browser_token_hash: str
    status: str = "PENDING"  # PENDING / SCANNED / CONFIRMED / CONSUMED / EXPIRED / CANCELLED
    user_id: Optional[str] = None
    device_id: Optional[str] = None
    browser_name: Optional[str] = None
    os_name: Optional[str] = None
    device_label: Optional[str] = None
    user_agent: Optional[str] = None
    trust_device: bool = False
    created_at: str = ""
    expires_at: str = ""
    scanned_at: Optional[str] = None
    confirmed_at: Optional[str] = None
    consumed_at: Optional[str] = None
    cancelled_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "QrLoginSessionRow":
        return cls(
            id=row["id"],
            scan_token_hash=row["scan_token_hash"],
            browser_token_hash=row["browser_token_hash"],
            status=row["status"],
            user_id=row["user_id"],
            device_id=row["device_id"],
            browser_name=row["browser_name"],
            os_name=row["os_name"],
            device_label=row["device_label"],
            user_agent=row["user_agent"],
            trust_device=bool(row["trust_device"]),
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            scanned_at=row["scanned_at"],
            confirmed_at=row["confirmed_at"],
            consumed_at=row["consumed_at"],
            cancelled_at=row["cancelled_at"],
        )


@dataclass
class TrustedDeviceRow:
    id: str
    user_id: str
    device_id: str
    token_hash: str
    device_name: Optional[str] = None
    browser_name: Optional[str] = None
    os_name: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: str = ""
    last_used_at: Optional[str] = None
    expires_at: str = ""
    revoked_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "TrustedDeviceRow":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            device_id=row["device_id"],
            token_hash=row["token_hash"],
            device_name=row["device_name"],
            browser_name=row["browser_name"],
            os_name=row["os_name"],
            user_agent=row["user_agent"],
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
        )