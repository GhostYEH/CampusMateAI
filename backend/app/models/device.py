from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DesktopDevice:
    id: str
    owner_user_id: str
    device_name: str
    platform: str
    hardware_model: Optional[str]
    app_version: Optional[str]
    status: str
    created_at: str
    bound_at: str
    last_heartbeat_at: Optional[str]
    revoked_at: Optional[str]
    capabilities: dict[str, bool] = field(default_factory=dict)
    model_versions: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DesktopDeviceBinding:
    id: str
    device_id: str
    bind_token_hash: str
    poll_token_hash: str
    status: str
    created_at: str
    expires_at: str
    confirmed_at: Optional[str]


@dataclass(frozen=True)
class DeviceEventReceipt:
    event_id: str
    payload_hash: str
    received_at: str


__all__ = ["DesktopDevice", "DesktopDeviceBinding", "DeviceEventReceipt"]
