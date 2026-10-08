from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode

from ..core.exceptions import (
    DeviceBindingInvalid,
    DeviceEventConflict,
    DeviceNotFound,
    StudySessionNotFound,
    ValidationFailed,
)
from ..core.security import hash_token
from ..models.device import DesktopDevice
from ..repositories.device_repository import DesktopDeviceRepository
from ..repositories.study_session_repository import StudySessionRepository
from ..repositories.learner_control_repository import LearnerControlRepository
from ..repositories.user_repository import UserRepository
from ..services.learner_event_service import LearnerEventService
from ..schemas.learner_preferences import LearnerPreferences
from ..schemas.device import DeviceEvent
from .focus_realtime_voice_service import get_focus_realtime_voice_service

UTC = timezone.utc
BINDING_TTL = timedelta(minutes=5)
EVENT_MAX_AGE = timedelta(days=7)
EVENT_FUTURE_TOLERANCE = timedelta(minutes=5)


def _device_credential(binding_id: str, poll_token: str) -> str:
    material = (
        b"CampusMateAI:desktop-device-credential:v1\0"
        + binding_id.encode()
        + b"\0"
        + poll_token.encode()
    )
    return "dvc_" + hashlib.sha256(material).hexdigest()


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class DesktopDeviceService:
    def __init__(
        self,
        repository: DesktopDeviceRepository,
        study_repository: StudySessionRepository,
        learner_preferences: LearnerControlRepository,
        learner_event_service: LearnerEventService,
        user_repository: UserRepository,
    ) -> None:
        self._repo = repository
        self._study = study_repository
        self._learner_preferences = learner_preferences
        self._learner_event_service = learner_event_service
        self._users = user_repository

    @staticmethod
    def credential_hash(credential: str) -> str:
        return hash_token(credential)

    def authenticate(self, credential: str) -> DesktopDevice:
        device = self._repo.get_device_by_credential_hash(hash_token(credential))
        if device is None:
            raise DeviceBindingInvalid("设备凭据无效或已撤销")
        user = self._users.get_user_by_id(device.owner_user_id)
        if (
            user is None
            or not user.is_active
            or user.role != "student"
            or user.original_role == "teacher"
        ):
            raise DeviceBindingInvalid("绑定账号已停用或不允许桌面设备访问")
        return device

    def create_binding(
        self,
        *,
        device_name: str,
        platform: str,
        hardware_model: Optional[str],
        app_version: Optional[str],
        now: datetime,
    ) -> dict[str, Any]:
        bind_token = secrets.token_urlsafe(32)
        poll_token = secrets.token_urlsafe(32)
        expires_at = now.astimezone(UTC) + BINDING_TTL
        binding_id, _ = self._repo.create_binding(
            device_name=device_name.strip(),
            platform=platform,
            hardware_model=hardware_model,
            app_version=app_version,
            bind_token_hash=hash_token(bind_token),
            poll_token_hash=hash_token(poll_token),
            expires_at=expires_at.isoformat(),
        )
        qr_payload = "campusmate://device/bind?" + urlencode(
            {"v": 1, "sid": binding_id, "token": bind_token}
        )
        return {
            "binding_id": binding_id,
            "qr_payload": qr_payload,
            "poll_token": poll_token,
            "status": "PENDING",
            "expires_at": expires_at,
            "poll_interval_seconds": 2,
        }

    def confirm_binding(
        self, *, binding_id: str, bind_token: str, owner_user_id: str, now: datetime
    ) -> None:
        binding = self._repo.get_binding(binding_id)
        if binding is None or not secrets.compare_digest(
            binding["bind_token_hash"], hash_token(bind_token)
        ):
            raise DeviceBindingInvalid()
        if _datetime(binding["expires_at"]) <= now.astimezone(UTC):
            raise DeviceBindingInvalid("设备绑定二维码已过期")
        if binding["status"] == "CONFIRMED":
            if (
                binding["owner_user_id"] == owner_user_id
                and binding["device_status"] == "ACTIVE"
            ):
                return
            raise DeviceBindingInvalid("绑定会话已被使用")
        if binding["status"] != "PENDING":
            raise DeviceBindingInvalid()
        # 派生凭据只会在本机持有 poll token 的客户端可重建；二维码中的 bind token 不足以登录设备。
        # 确认接口本身不能取得 poll token，故 credential hash 在确认时延迟到结果轮询兑换。
        confirmed = self._repo.confirm_binding(
            binding_id=binding_id,
            bind_token_hash=hash_token(bind_token),
            owner_user_id=owner_user_id,
            now=now,
        )
        if confirmed is None:
            raise DeviceBindingInvalid("绑定会话已过期或已被使用")

    def poll_binding(
        self, *, binding_id: str, poll_token: str, now: datetime
    ) -> dict[str, Any]:
        binding = self._repo.poll_binding(
            binding_id=binding_id, poll_token_hash=hash_token(poll_token)
        )
        if binding is None:
            raise DeviceBindingInvalid("绑定轮询凭据无效")
        expires_at = _datetime(binding["expires_at"])
        if expires_at <= now.astimezone(UTC):
            return {
                "binding_id": binding_id,
                "status": "EXPIRED",
                "expires_at": expires_at,
            }
        if binding["status"] == "PENDING":
            return {
                "binding_id": binding_id,
                "status": "PENDING",
                "expires_at": expires_at,
            }
        if binding["status"] != "CONFIRMED" or binding["device_status"] != "ACTIVE":
            return {
                "binding_id": binding_id,
                "status": "REVOKED",
                "expires_at": expires_at,
            }
        owner = self._users.get_user_by_id(binding["owner_user_id"])
        if (
            owner is None
            or not owner.is_active
            or owner.role != "student"
            or owner.original_role == "teacher"
        ):
            return {
                "binding_id": binding_id,
                "status": "REVOKED",
                "expires_at": expires_at,
            }
        credential = _device_credential(binding_id, poll_token)
        if not self._repo.set_derived_credential_hash(
            binding["device_id"], hash_token(credential)
        ):
            return {
                "binding_id": binding_id,
                "status": "REVOKED",
                "expires_at": expires_at,
            }
        return {
            "binding_id": binding_id,
            "status": "CONFIRMED",
            "expires_at": expires_at,
            "device_credential": credential,
            "device_id": binding["device_id"],
        }

    def list_devices(self, owner_user_id: str) -> list[DesktopDevice]:
        return self._repo.list_devices(owner_user_id)

    def revoke_device(
        self, *, device_id: str, owner_user_id: str, now: datetime
    ) -> None:
        if not self._repo.revoke_device(
            device_id=device_id, owner_user_id=owner_user_id, now=now
        ):
            raise DeviceNotFound()

    def heartbeat(self, *, device: DesktopDevice, body: Any, now: datetime) -> datetime:
        received_at = now.astimezone(UTC)
        if not self._repo.update_heartbeat(
            device_id=device.id,
            app_version=body.app_version,
            os_version=body.os_version,
            network_state=body.network_state,
            temperature_c=body.temperature_c,
            free_storage_mb=body.free_storage_mb,
            capabilities=body.capabilities,
            model_versions=body.model_versions,
            now=received_at,
        ):
            raise DeviceBindingInvalid("设备已撤销")
        return received_at

    def config(self, *, device: DesktopDevice, now: datetime) -> dict[str, Any]:
        preferences = self._learner_preferences.get_preferences(
            user_id=device.owner_user_id
        )
        if preferences is None:
            preference_values = LearnerPreferences().model_dump(mode="json")
            configured = False
            version = 0
            updated_at = None
        else:
            preference_values = preferences
            configured = True
            version = int(preferences.get("version", 0))
            updated_at = preferences.get("updated_at")
        return {
            "protocol_version": 1,
            "config_version": "desktop-v1",
            "vision_enabled": bool(device.capabilities.get("camera", False)),
            "behavior_sample_interval_ms": 500,
            "expression_enabled": bool(
                device.capabilities.get("camera", False)
                and device.capabilities.get("expression_model", False)
            ),
            "supports_session_control": True,
            "supports_structured_event_upload": True,
            "supports_ota": False,
            "supports_realtime_voice": get_focus_realtime_voice_service()._settings.realtime_voice_available,
            "local_behavior_inference": bool(
                device.capabilities.get("behavior_model", False)
                and device.model_versions.get("behavior")
            ),
            "local_expression_inference": bool(
                device.capabilities.get("expression_model", False)
                and device.model_versions.get("expression")
            ),
            "hardware_acceleration_status": "unverified",
            "preferences_configured": configured,
            "preferences_version": version,
            "timezone": preference_values["timezone"],
            "daily_capacity_minutes": preference_values["daily_capacity_minutes"],
            "quiet_hours_start": preference_values["quiet_hours_start"],
            "quiet_hours_end": preference_values["quiet_hours_end"],
            "preferences_updated_at": updated_at,
            "updated_at": now.astimezone(UTC),
        }

    def validate_events(
        self,
        *,
        device: DesktopDevice,
        events: list[DeviceEvent],
        now: datetime,
    ) -> tuple[list[str], list[str]]:
        current = now.astimezone(UTC)
        rows: list[dict[str, Any]] = []
        for item in events:
            session = self._repo.get_session_for_owner(
                session_id=item.session_id,
                owner_user_id=device.owner_user_id,
            )
            if (
                session is None
                or session["mode"] != "focus"
                or not self._repo.device_owns_session(
                    device_id=device.id, session_id=item.session_id
                )
            ):
                raise StudySessionNotFound()
            occurred = item.occurred_at.astimezone(UTC)
            started = _datetime(session["started_at"])
            if (
                occurred < current - EVENT_MAX_AGE
                or occurred > current + EVENT_FUTURE_TOLERANCE
            ):
                raise ValidationFailed("事件时间超出允许范围")
            if occurred < started - EVENT_FUTURE_TOLERANCE:
                raise ValidationFailed("事件时间早于专注会话")
            if session["ended_at"]:
                ended = _datetime(session["ended_at"])
                if (
                    session["status"] != "completed"
                    or current - ended > EVENT_MAX_AGE
                    or occurred > ended + EVENT_FUTURE_TOLERANCE
                ):
                    raise ValidationFailed(
                        "结束会话仅接受结束后 7 天内、会话时间范围内的离线事件"
                    )
            elif session["status"] not in {"active", "paused"}:
                raise ValidationFailed("专注会话当前状态不接受事件")
            encoded = json.dumps(
                item.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            rows.append(
                {
                    "event_id": item.event_id,
                    "session_id": item.session_id,
                    "event_type": item.event_type,
                    "occurred_at": occurred.isoformat(),
                    "model_version": item.model_version,
                    "payload_json": json.dumps(
                        item.payload.model_dump(mode="json"),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "payload_hash": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
                }
            )
        try:
            return self._repo.append_event_batch(
                device_id=device.id, events=rows, received_at=current
            )
        except ValueError as exc:
            raise DeviceEventConflict() from exc

    @staticmethod
    def _session_response(session: Any) -> dict[str, Any]:
        return {
            "id": session.id,
            "mode": session.mode,
            "started_at": session.started_at,
            "paused_at": session.paused_at,
            "ended_at": session.ended_at,
            "planned_duration_seconds": session.planned_duration_seconds,
            "duration_seconds": session.duration_seconds,
            "pause_seconds": session.pause_seconds,
            "status": session.status,
        }

    def _run_session_command(
        self,
        *,
        device: DesktopDevice,
        idempotency_key: str,
        action: str,
        request: dict[str, Any],
        execute,
    ) -> dict[str, Any]:
        encoded = json.dumps(
            {"action": action, "request": request},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        request_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        response, _replayed = self._repo.execute_session_command(
            device_id=device.id,
            idempotency_key=idempotency_key,
            action=action,
            request_hash=request_hash,
            execute=lambda: self._session_response(execute()),
        )
        return response

    def create_focus_session(
        self,
        *,
        device: DesktopDevice,
        planned_duration_seconds: Optional[int],
        goal: Optional[str],
        idempotency_key: str,
    ) -> dict[str, Any]:
        if goal is not None and not goal.strip():
            raise ValidationFailed("goal 不能为空白字符串")
        normalized_goal = goal.strip() if goal else None

        def execute():
            session = self._study.create_session(
                user_id=device.owner_user_id,
                mode="focus",
                experience_mode="SMART_GUARD",
                planned_duration_seconds=planned_duration_seconds,
                goal=normalized_goal,
            )
            self._repo.link_device_session(
                device_id=device.id, session_id=session.id, created_at=datetime.now(UTC)
            )
            return session

        return self._run_session_command(
            device=device,
            idempotency_key=idempotency_key,
            action="create",
            request={
                "planned_duration_seconds": planned_duration_seconds,
                "goal": normalized_goal,
            },
            execute=execute,
        )

    def _assert_device_session(self, *, device: DesktopDevice, session_id: str) -> None:
        if not self._repo.device_owns_session(
            device_id=device.id, session_id=session_id
        ):
            raise StudySessionNotFound()

    def pause_focus_session(
        self, *, device: DesktopDevice, session_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        def execute():
            self._assert_device_session(device=device, session_id=session_id)
            return self._study.pause(
                session_id, user_id=device.owner_user_id, reason="桌面设备暂停"
            )

        return self._run_session_command(
            device=device,
            idempotency_key=idempotency_key,
            action="pause",
            request={"session_id": session_id},
            execute=execute,
        )

    def resume_focus_session(
        self, *, device: DesktopDevice, session_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        def execute():
            self._assert_device_session(device=device, session_id=session_id)
            return self._study.resume(session_id, user_id=device.owner_user_id)

        return self._run_session_command(
            device=device,
            idempotency_key=idempotency_key,
            action="resume",
            request={"session_id": session_id},
            execute=execute,
        )

    def finish_focus_session(
        self,
        *,
        device: DesktopDevice,
        session_id: str,
        behavior_summary: Optional[dict[str, Any]],
        idempotency_key: str,
    ) -> dict[str, Any]:
        def execute():
            self._assert_device_session(device=device, session_id=session_id)
            session = self._study.finish(
                session_id,
                user_id=device.owner_user_id,
                behavior_summary=behavior_summary,
            )
            self._learner_event_service.record_study_session_finished(session)
            return session

        return self._run_session_command(
            device=device,
            idempotency_key=idempotency_key,
            action="finish",
            request={"session_id": session_id, "behavior_summary": behavior_summary},
            execute=execute,
        )


__all__ = ["DesktopDeviceService"]
