"""Shared mechanics for the managed magic class HTTP gateways.

Route modules keep their dependency functions and operation-specific messages;
this module only owns client construction and conditional-write header parsing.
"""

from __future__ import annotations

from typing import Optional

from ..services.container import ServiceContainer
from ..services.magicclass.fusion_client import MagicClassFusionClient
from ..services.magicclass.fusion_errors import FusionInvalidRequest


def build_fusion_client(
    container: ServiceContainer,
    *,
    client_type: type[MagicClassFusionClient] = MagicClassFusionClient,
) -> MagicClassFusionClient:
    """Read configuration from the request container, including test overrides."""
    settings = container.settings
    return client_type(
        base_url=settings.magicclass_service_url,
        secret=settings.magicclass_internal_secret,
        timeout_seconds=settings.magicclass_service_timeout_seconds,
    )


def require_idempotency_key(
    value: Optional[str], *, missing_message: str, max_length: int
) -> str:
    key = (value or "").strip()
    if not key:
        raise FusionInvalidRequest(missing_message)
    if len(key) > max_length:
        raise FusionInvalidRequest("Idempotency-Key 过长")
    return key


def require_revision(
    value: Optional[str],
    *,
    missing_message: str = "写入请求必须携带 If-Match（当前 revision）",
) -> int:
    """Preserve the gateways' weak/quoted ETag handling and reject wildcards."""
    raw = (value or "").strip().replace("W/", "").replace('"', "")
    if not raw:
        raise FusionInvalidRequest(missing_message)
    if raw == "*":
        raise FusionInvalidRequest("If-Match 不接受 *，请传回你读到的 revision")
    try:
        revision = int(raw)
    except ValueError as exc:
        raise FusionInvalidRequest("If-Match 必须是正整数 revision") from exc
    if revision < 1:
        raise FusionInvalidRequest("If-Match 必须是正整数 revision")
    return revision
