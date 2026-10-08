from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .study import StudyBehaviorSummary


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class DeviceBindingCreate(StrictModel):
    device_name: str = Field(..., min_length=1, max_length=80)
    platform: Literal["android", "linux"]
    hardware_model: str | None = Field(None, max_length=120)
    app_version: str | None = Field(None, max_length=64)

    @field_validator("device_name")
    @classmethod
    def trim_device_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("device_name must not be blank")
        return normalized


class DeviceBindingCreateOut(StrictModel):
    binding_id: str
    qr_payload: str
    poll_token: str
    status: Literal["PENDING"]
    expires_at: datetime
    poll_interval_seconds: int = 2


class DeviceBindingConfirm(StrictModel):
    bind_token: str = Field(..., min_length=32, max_length=128)


class DeviceBindingPollOut(StrictModel):
    binding_id: str
    status: Literal["PENDING", "CONFIRMED", "EXPIRED", "REVOKED"]
    expires_at: datetime
    device_credential: str | None = None
    device_id: str | None = None


class DesktopDeviceOut(StrictModel):
    device_id: str
    device_name: str
    platform: str
    hardware_model: str | None = None
    app_version: str | None = None
    status: str
    created_at: datetime
    bound_at: datetime
    last_heartbeat_at: datetime | None = None


class DesktopDeviceListOut(StrictModel):
    items: list[DesktopDeviceOut]


class DeviceHeartbeat(StrictModel):
    app_version: str = Field(..., min_length=1, max_length=64)
    os_version: str | None = Field(None, max_length=64)
    network_state: Literal["online", "offline", "limited"]
    temperature_c: float | None = Field(None, ge=-20, le=120)
    free_storage_mb: int | None = Field(None, ge=0, le=2_000_000)
    capabilities: dict[str, bool] = Field(default_factory=dict, max_length=16)
    model_versions: dict[str, str] = Field(default_factory=dict, max_length=16)

    @field_validator("capabilities")
    @classmethod
    def validate_capability_keys(cls, value: dict[str, bool]) -> dict[str, bool]:
        allowed = {
            "camera",
            "microphone",
            "speaker",
            "display",
            "behavior_model",
            "expression_model",
        }
        if any(key not in allowed for key in value):
            raise ValueError("unsupported capability")
        return value

    @field_validator("model_versions")
    @classmethod
    def validate_model_keys(cls, value: dict[str, str]) -> dict[str, str]:
        allowed = {"behavior", "expression", "presence"}
        if any(
            key not in allowed or not item or len(item) > 128
            for key, item in value.items()
        ):
            raise ValueError("unsupported model kind")
        return value


class DeviceHeartbeatOut(StrictModel):
    accepted: bool = True
    received_at: datetime


class DeviceConfigOut(StrictModel):
    protocol_version: int = 1
    config_version: str
    vision_enabled: bool = True
    behavior_sample_interval_ms: int = Field(ge=250, le=10_000)
    expression_enabled: bool = True
    supports_session_control: bool = True
    supports_structured_event_upload: bool = True
    supports_ota: bool = False
    supports_realtime_voice: bool = False
    local_behavior_inference: bool
    local_expression_inference: bool
    hardware_acceleration_status: Literal["unverified"] = "unverified"
    preferences_configured: bool = False
    preferences_version: int = 0
    timezone: str = "Asia/Shanghai"
    daily_capacity_minutes: int = Field(default=240, ge=15, le=720)
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    preferences_updated_at: datetime | None = None
    updated_at: datetime


class DeviceFocusSessionCreate(StrictModel):
    planned_duration_seconds: int | None = Field(None, ge=300, le=14_400)
    goal: str | None = Field(None, max_length=500)


class DeviceFocusSessionActionOut(StrictModel):
    id: str
    mode: str
    started_at: datetime
    paused_at: datetime | None = None
    ended_at: datetime | None = None
    planned_duration_seconds: int
    duration_seconds: int
    pause_seconds: int
    status: str


class DeviceFocusSessionFinish(StrictModel):
    behavior_summary: StudyBehaviorSummary | None = None


class BehaviorStablePayload(StrictModel):
    label: Literal["READ", "WRITE", "PHONE_INTERACTION", "NO_VISIBLE_STUDY", "COMPUTER"]
    confidence: float = Field(ge=0, le=1)
    duration_seconds: int = Field(ge=0, le=86_400)


class PresenceChangedPayload(StrictModel):
    state: Literal["PRESENT", "OBSERVING", "ABSENT"]
    confidence: float = Field(ge=0, le=1)


class ExpressionStablePayload(StrictModel):
    label: Literal[
        "ANGRY",
        "DISGUST",
        "FEAR",
        "HAPPY",
        "NEUTRAL",
        "SAD",
        "SURPRISE",
        "UNKNOWN",
        "NO_FACE",
    ]
    confidence: float = Field(ge=0, le=1)


class DeviceEventBase(StrictModel):
    event_id: str = Field(..., min_length=1, max_length=64)
    session_id: str = Field(..., min_length=1, max_length=64)
    occurred_at: datetime
    model_version: str = Field(..., min_length=1, max_length=128)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must carry timezone")
        return value.astimezone(timezone.utc)


class BehaviorStableEvent(DeviceEventBase):
    event_type: Literal["behavior_stable"]
    payload: BehaviorStablePayload


class PresenceChangedEvent(DeviceEventBase):
    event_type: Literal["presence_changed"]
    payload: PresenceChangedPayload


class ExpressionStableEvent(DeviceEventBase):
    event_type: Literal["expression_stable"]
    payload: ExpressionStablePayload


DeviceEvent = Annotated[
    Union[BehaviorStableEvent, PresenceChangedEvent, ExpressionStableEvent],
    Field(discriminator="event_type"),
]


class DeviceEventBatch(StrictModel):
    events: list[DeviceEvent] = Field(..., min_length=1, max_length=100)

    @field_validator("events")
    @classmethod
    def unique_event_ids(cls, value: list[DeviceEvent]) -> list[DeviceEvent]:
        ids = [event.event_id for event in value]
        if len(ids) != len(set(ids)):
            raise ValueError("event_id must be unique within a batch")
        return value


class DeviceEventBatchOut(StrictModel):
    accepted_event_ids: list[str]
    duplicate_event_ids: list[str]
