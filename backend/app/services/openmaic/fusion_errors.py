"""Failures the fusion gateway can report to a CampusMate client.

Every one of these is a *translated* failure: the managed service answered, and
the gateway restated the answer in CampusMate's own error vocabulary. None of
them carries the internal address, the assertion, or the service's raw body —
the browser is told what it can act on and nothing else.

The status codes are chosen for the browser, not copied from the wire. The
service answers a failed `If-Match` with 412 because that is the correct HTTP
semantics for a conditional request; the client cannot act on the difference
between 412 and 409, and 409 is what "someone else changed this" means to it.
"""

from __future__ import annotations

from typing import Any, Optional

from ...core.exceptions import AppException


class FusionUnavailable(AppException):
    """The managed service is off, unreachable, or refused our assertion."""

    code = "OPENMAIC_FUSION_UNAVAILABLE"
    http_status = 503
    message = "受管 OpenMAIC 服务当前不可用，请稍后重试"


class FusionInvalidRequest(AppException):
    code = "OPENMAIC_INVALID_REQUEST"
    http_status = 400
    message = "请求参数不合法"


class FusionWorkspaceNotFound(AppException):
    """Also used for another user's row: existence is not confirmed to strangers."""

    code = "OPENMAIC_WORKSPACE_NOT_FOUND"
    http_status = 404
    message = "未找到该学习工作台"


class FusionRevisionConflict(AppException):
    code = "OPENMAIC_REVISION_CONFLICT"
    http_status = 409
    message = "内容已被其他操作更新，请重新读取后再提交"


class FusionIdempotencyConflict(AppException):
    code = "OPENMAIC_IDEMPOTENCY_CONFLICT"
    http_status = 409
    message = "同一个幂等键被用于了不同的请求"


class FusionDocumentRejected(AppException):
    """The DSL write path refused the document; `details` carries its issues."""

    code = "OPENMAIC_DOCUMENT_REJECTED"
    http_status = 422
    message = "内容未通过校验，未保存"


__all__ = [
    "FusionUnavailable",
    "FusionInvalidRequest",
    "FusionWorkspaceNotFound",
    "FusionRevisionConflict",
    "FusionIdempotencyConflict",
    "FusionDocumentRejected",
]


def raise_for_service_error(status_code: int, body: Optional[Any]) -> None:
    """Translate one service response into the matching CampusMate failure.

    Unmapped statuses become {@link FusionUnavailable}: an answer we did not
    expect means the two sides have drifted, which is a deployment problem rather
    than something the caller can fix by changing the request.
    """
    payload = body if isinstance(body, dict) else {}
    error_code = str(payload.get("error") or "")
    message = str(payload.get("message") or "")

    if status_code == 404:
        raise FusionWorkspaceNotFound()
    if status_code == 412:
        raise FusionRevisionConflict()
    if status_code == 409:
        if error_code == "idempotency_conflict":
            raise FusionIdempotencyConflict()
        raise FusionRevisionConflict()
    if status_code == 422:
        details: dict[str, Any] = {}
        if isinstance(payload.get("issues"), list):
            details["issues"] = payload["issues"]
        if isinstance(payload.get("limit"), str):
            details["limit"] = payload["limit"]
        raise FusionDocumentRejected(details=details or None)
    if status_code == 400:
        raise FusionInvalidRequest(message or None)
    raise FusionUnavailable()
