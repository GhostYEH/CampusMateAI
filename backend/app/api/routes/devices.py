"""Desktop companion device binding and structured event APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ...core.exceptions import DeviceBindingInvalid
from ...core.rate_limit import check_request_rate
from ...models.device import DesktopDevice
from ...models.multi_role import UserRow
from ...schemas.device import (
    DesktopDeviceListOut,
    DesktopDeviceOut,
    DeviceBindingConfirm,
    DeviceBindingCreate,
    DeviceBindingCreateOut,
    DeviceBindingPollOut,
    DeviceConfigOut,
    DeviceEventBatch,
    DeviceEventBatchOut,
    DeviceFocusSessionActionOut,
    DeviceFocusSessionCreate,
    DeviceFocusSessionFinish,
    DeviceHeartbeat,
    DeviceHeartbeatOut,
)
from ...services.container import ServiceContainer, get_container
from ..deps import student_only

router = APIRouter(prefix="/devices", tags=["桌面设备"])
_device_bearer = HTTPBearer(auto_error=False, scheme_name="DesktopDeviceBearer")


def _container() -> ServiceContainer:
    return get_container()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _device_out(device: DesktopDevice) -> DesktopDeviceOut:
    return DesktopDeviceOut(
        device_id=device.id,
        device_name=device.device_name,
        platform=device.platform,
        hardware_model=device.hardware_model,
        app_version=device.app_version,
        status=device.status,
        created_at=device.created_at,
        bound_at=device.bound_at,
        last_heartbeat_at=device.last_heartbeat_at,
    )


def _session_out(session) -> DeviceFocusSessionActionOut:
    return DeviceFocusSessionActionOut(**session)


def current_device(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_device_bearer)
    ],
    container: ServiceContainer = Depends(_container),
) -> DesktopDevice:
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials
    ):
        raise DeviceBindingInvalid("缺少桌面设备凭据")
    return container.desktop_device_service.authenticate(credentials.credentials)


@router.post(
    "/bindings",
    response_model=DeviceBindingCreateOut,
    status_code=status.HTTP_201_CREATED,
    summary="申请桌面设备二维码绑定",
)
def create_binding(
    req: DeviceBindingCreate,
    request: Request,
    container: ServiceContainer = Depends(_container),
) -> DeviceBindingCreateOut:
    check_request_rate(request, "desktop_device_binding", limit=3, window=60)
    return DeviceBindingCreateOut(
        **container.desktop_device_service.create_binding(
            device_name=req.device_name,
            platform=req.platform,
            hardware_model=req.hardware_model,
            app_version=req.app_version,
            now=_now(),
        )
    )


@router.post(
    "/bindings/{binding_id}/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="由已登录用户确认桌面设备绑定",
)
def confirm_binding(
    binding_id: str,
    req: DeviceBindingConfirm,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> Response:
    container.desktop_device_service.confirm_binding(
        binding_id=binding_id,
        bind_token=req.bind_token,
        owner_user_id=user.id,
        now=_now(),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/bindings/{binding_id}/result",
    response_model=DeviceBindingPollOut,
    summary="设备轮询绑定结果并领取设备凭据",
)
def poll_binding(
    binding_id: str,
    poll_token: Annotated[
        str, Header(alias="X-Device-Poll-Token", min_length=32, max_length=128)
    ],
    container: ServiceContainer = Depends(_container),
) -> DeviceBindingPollOut:
    return DeviceBindingPollOut(
        **container.desktop_device_service.poll_binding(
            binding_id=binding_id,
            poll_token=poll_token,
            now=_now(),
        )
    )


@router.get("", response_model=DesktopDeviceListOut, summary="列出当前账号的桌面设备")
def list_devices(
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> DesktopDeviceListOut:
    return DesktopDeviceListOut(
        items=[
            _device_out(row)
            for row in container.desktop_device_service.list_devices(user.id)
        ]
    )


@router.delete(
    "/{device_id}", status_code=status.HTTP_204_NO_CONTENT, summary="撤销本人桌面设备"
)
def revoke_device(
    device_id: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> Response:
    container.desktop_device_service.revoke_device(
        device_id=device_id, owner_user_id=user.id, now=_now()
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/me/heartbeat",
    response_model=DeviceHeartbeatOut,
    summary="上报桌面设备心跳和诊断状态",
)
def heartbeat(
    req: DeviceHeartbeat,
    device: DesktopDevice = Depends(current_device),
    container: ServiceContainer = Depends(_container),
) -> DeviceHeartbeatOut:
    received = container.desktop_device_service.heartbeat(
        device=device, body=req, now=_now()
    )
    return DeviceHeartbeatOut(received_at=received)


@router.get(
    "/me/config",
    response_model=DeviceConfigOut,
    summary="读取桌面设备观察配置与用户偏好",
)
def get_config(
    device: DesktopDevice = Depends(current_device),
    container: ServiceContainer = Depends(_container),
) -> DeviceConfigOut:
    return DeviceConfigOut(
        **container.desktop_device_service.config(device=device, now=_now())
    )


@router.post(
    "/me/focus-sessions",
    response_model=DeviceFocusSessionActionOut,
    status_code=status.HTTP_201_CREATED,
    summary="由桌面设备开始本人专注会话",
)
def create_focus_session(
    req: DeviceFocusSessionCreate,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
    device: DesktopDevice = Depends(current_device),
    container: ServiceContainer = Depends(_container),
) -> DeviceFocusSessionActionOut:
    session = container.desktop_device_service.create_focus_session(
        device=device,
        planned_duration_seconds=req.planned_duration_seconds,
        goal=req.goal,
        idempotency_key=idempotency_key,
    )
    return _session_out(session)


@router.post(
    "/me/focus-sessions/{session_id}/pause",
    response_model=DeviceFocusSessionActionOut,
    summary="暂停本人专注会话",
)
def pause_focus_session(
    session_id: str,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
    device: DesktopDevice = Depends(current_device),
    container: ServiceContainer = Depends(_container),
) -> DeviceFocusSessionActionOut:
    return _session_out(
        container.desktop_device_service.pause_focus_session(
            device=device,
            session_id=session_id,
            idempotency_key=idempotency_key,
        )
    )


@router.post(
    "/me/focus-sessions/{session_id}/resume",
    response_model=DeviceFocusSessionActionOut,
    summary="恢复本人专注会话",
)
def resume_focus_session(
    session_id: str,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
    device: DesktopDevice = Depends(current_device),
    container: ServiceContainer = Depends(_container),
) -> DeviceFocusSessionActionOut:
    return _session_out(
        container.desktop_device_service.resume_focus_session(
            device=device,
            session_id=session_id,
            idempotency_key=idempotency_key,
        )
    )


@router.post(
    "/me/focus-sessions/{session_id}/finish",
    response_model=DeviceFocusSessionActionOut,
    summary="结束本人专注会话",
)
def finish_focus_session(
    session_id: str,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
    req: Annotated[DeviceFocusSessionFinish, Body()],
    device: DesktopDevice = Depends(current_device),
    container: ServiceContainer = Depends(_container),
) -> DeviceFocusSessionActionOut:
    summary = (
        req.behavior_summary.model_dump(mode="json") if req.behavior_summary else None
    )
    session = container.desktop_device_service.finish_focus_session(
        device=device,
        session_id=session_id,
        behavior_summary=summary,
        idempotency_key=idempotency_key,
    )
    return _session_out(session)


@router.post(
    "/me/events:batch",
    response_model=DeviceEventBatchOut,
    summary="批量幂等接收端侧结构化事件",
)
def append_events(
    req: DeviceEventBatch,
    device: DesktopDevice = Depends(current_device),
    container: ServiceContainer = Depends(_container),
) -> DeviceEventBatchOut:
    accepted, duplicates = container.desktop_device_service.validate_events(
        device=device,
        events=req.events,
        now=_now(),
    )
    return DeviceEventBatchOut(
        accepted_event_ids=accepted, duplicate_event_ids=duplicates
    )


__all__ = ["router"]
