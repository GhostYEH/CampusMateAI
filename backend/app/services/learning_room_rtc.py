"""Room-scoped credentials for native classroom audio/video.

Wire format: Volcengine AccessToken v001, little-endian length-prefixed fields.
Reference (pinned): https://github.com/volcengine/VolcEngineRTC/tree/
30a9b7352a258368238f407052ce656d7b331035/Android/APIExample/app/src/main/java/
rtc/volcengine/apiexample/common/accesstoken
Media travels through RTC, never through FastAPI or SQLite.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import re
import secrets
import struct
import time
import zipfile

from ..core.config import Settings
from ..core.exceptions import AppException
from ..repositories.learning_room_repository import LearningRoomRepository

TOKEN_TTL_SECONDS = 120
REFRESH_AFTER_SECONDS = 60


def rtc_available(settings: Settings) -> bool:
    return bool(
        re.fullmatch(r"[a-zA-Z0-9]{24}", settings.volc_rtc_app_id)
        and settings.volc_rtc_app_key.strip()
    )


def _pack_bytes(value: bytes) -> bytes:
    return struct.pack("<H", len(value)) + value


def issue_room_token(
    settings: Settings, repo: LearningRoomRepository, room_id: str, user_id: str
) -> dict:
    # Check membership even when RTC is disabled; never disclose another room.
    repo.get(room_id, user_id)
    if not rtc_available(settings):
        raise AppException(
            "课堂音视频尚未配置，请联系服务维护者",
            code="CLASSROOM_RTC_UNAVAILABLE",
            http_status=503,
        )
    now = int(time.time())
    expires = now + TOKEN_TTL_SECONDS
    # Namespace avoids collisions with Focus AI and other uses of the RTC app.
    rtc_room = "class_" + hashlib.sha256(room_id.encode()).hexdigest()[:40]
    message = (
        struct.pack("<III", secrets.randbits(32), now, expires)
        + _pack_bytes(rtc_room.encode())
        + _pack_bytes(user_id.encode())
        + struct.pack("<H", 5)
        + b"".join(struct.pack("<HI", privilege, expires) for privilege in range(5))
    )
    signature = hmac.digest(settings.volc_rtc_app_key.encode(), message, "sha256")
    token = (
        "001"
        + settings.volc_rtc_app_id
        + base64.b64encode(_pack_bytes(message) + _pack_bytes(signature)).decode(
            "ascii"
        )
    )
    return {
        "provider": "volcengine",
        "app_id": settings.volc_rtc_app_id,
        "room_id": rtc_room,
        "user_id": user_id,
        "token": token,
        "expires_at": expires,
        "refresh_after_seconds": REFRESH_AFTER_SECONDS,
    }


def create_native_room(repo: LearningRoomRepository, user_id: str, title: str) -> dict:
    """Use the existing portable room format; no parallel membership store."""
    manifest = {
        "formatVersion": 1,
        "exportedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "appVersion": "1.0.3",
        "stage": {"name": title},
        "agents": [],
        "mediaIndex": {},
        "scenes": [
            {
                "type": "slide",
                "title": title,
                "order": 0,
                "content": {
                    "type": "slide",
                    "canvas": {
                        "id": "native-discussion",
                        "viewportSize": 1000,
                        "viewportRatio": 0.5625,
                        "theme": {
                            "backgroundColor": "#FFFFFF",
                            "themeColors": ["#4F6BED"],
                            "fontColor": "#222222",
                            "fontName": "Arial",
                        },
                        "elements": [],
                    },
                },
            }
        ],
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
    return repo.create(user_id, title, "native-discussion", output.getvalue(), 1)
