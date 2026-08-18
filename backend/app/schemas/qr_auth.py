"""QR 扫码登录与可信设备 Pydantic schema。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ===== QR Create =====


class QrCreateRequest(BaseModel):
    device_id: Optional[str] = Field(None, max_length=128, description="浏览器生成的设备标识")
    browser_name: Optional[str] = Field(None, max_length=64)
    os_name: Optional[str] = Field(None, max_length=64)


class QrCreateResponse(BaseModel):
    session_id: str
    qr_payload: str = Field(description="二维码内容字符串")
    browser_token: str = Field(description="浏览器兑换凭据，不写入二维码")
    status: str = "PENDING"
    expires_at: str
    expires_in: int = Field(description="剩余有效期(秒)")


# ===== QR Scan =====


class QrScanRequest(BaseModel):
    session_id: str = Field(..., min_length=16, max_length=64)
    scan_token: str = Field(..., min_length=32, max_length=128)


class QrScanResponse(BaseModel):
    session_id: str
    browser_name: Optional[str] = None
    os_name: Optional[str] = None
    device_label: Optional[str] = None
    expires_at: str
    status: str = "SCANNED"


# ===== QR Confirm =====


class QrConfirmRequest(BaseModel):
    session_id: str = Field(..., min_length=16, max_length=64)
    scan_token: str = Field(..., min_length=32, max_length=128)
    trust_device: bool = False


class QrConfirmResponse(BaseModel):
    session_id: str
    status: str = "CONFIRMED"
    trust_device: bool


# ===== QR Cancel =====


class QrCancelRequest(BaseModel):
    session_id: str = Field(..., min_length=16, max_length=64)
    scan_token: str = Field(..., min_length=32, max_length=128)


# ===== QR Status =====


class QrStatusResponse(BaseModel):
    session_id: str
    status: str
    expires_at: str


# ===== QR Exchange =====


class QrExchangeRequest(BaseModel):
    session_id: str = Field(..., min_length=16, max_length=64)
    browser_token: str = Field(..., min_length=32, max_length=128)


# ===== Trusted Device Auto Login =====


class TrustedDeviceAutoLoginRequest(BaseModel):
    device_id: Optional[str] = Field(None, max_length=128)


class TrustedDeviceRevokeRequest(BaseModel):
    device_id: Optional[str] = Field(None, max_length=128)


class TrustedDeviceListItem(BaseModel):
    id: str
    device_id: str
    device_name: Optional[str] = None
    browser_name: Optional[str] = None
    os_name: Optional[str] = None
    created_at: str
    last_used_at: Optional[str] = None
    expires_at: str
    is_current: bool = False


class TrustedDeviceListResponse(BaseModel):
    devices: list[TrustedDeviceListItem] = Field(default_factory=list)