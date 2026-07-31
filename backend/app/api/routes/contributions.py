"""用户主动参与 CNN 表情样本共建的接口。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from ...core.exceptions import AppException, Forbidden
from ...core.config import get_settings
from ...models.multi_role import UserRow
from ..deps import current_user

router = APIRouter()

_ALLOWED_LABELS = {
    "HAPPY", "NEUTRAL", "SAD", "ANGRY", "FEAR", "SURPRISE", "DISGUST",
}
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}


class ExpressionContributionResponse(BaseModel):
    sample_id: str
    label: str
    status: str
    message: str


def _storage_dir() -> Path:
    settings = get_settings()
    path = Path(settings.expression_contribution_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _metadata_path(sample_id: str) -> Path:
    return _storage_dir() / f"{sample_id}.json"


@router.post(
    "/contributions/expression-samples",
    response_model=ExpressionContributionResponse,
)
async def upload_expression_sample(
    image: UploadFile = File(...),
    label: str = Form(...),
    consent: bool = Form(...),
    model_version: str = Form("unknown"),
    user: UserRow = Depends(current_user),
) -> ExpressionContributionResponse:
    """接收用户明确同意后上传的一张已打标图片。"""
    normalized_label = label.strip().upper()
    if normalized_label not in _ALLOWED_LABELS:
        raise AppException("表情标签无效", code="EXPRESSION_LABEL_INVALID", http_status=422)
    if not consent:
        raise AppException("未获得样本共建同意", code="CONTRIBUTION_CONSENT_REQUIRED", http_status=403)
    if image.content_type not in _ALLOWED_CONTENT_TYPES:
        raise AppException("仅支持 JPG 或 PNG 图片", code="EXPRESSION_IMAGE_TYPE_INVALID", http_status=415)

    settings = get_settings()
    max_bytes = settings.max_expression_contribution_mb * 1024 * 1024
    sample_id = uuid.uuid4().hex
    extension = ".png" if image.content_type == "image/png" else ".jpg"
    image_path = _storage_dir() / f"{sample_id}{extension}"
    total = 0
    try:
        with image_path.open("wb") as output:
            while True:
                chunk = await image.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise AppException(
                        f"图片超过 {settings.max_expression_contribution_mb} MB 上限",
                        code="EXPRESSION_IMAGE_TOO_LARGE",
                        http_status=413,
                    )
                output.write(chunk)

        metadata: Dict[str, str] = {
            "sample_id": sample_id,
            "owner_id": user.id,
            "label": normalized_label,
            "model_version": model_version.strip()[:80] or "unknown",
            "content_type": image.content_type,
            "size_bytes": str(total),
            "consent": "true",
            "consent_version": "expression-contribution-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _metadata_path(sample_id).write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except AppException:
        image_path.unlink(missing_ok=True)
        raise
    except Exception as error:
        image_path.unlink(missing_ok=True)
        raise AppException(
            "样本保存失败，请稍后重试",
            code="EXPRESSION_SAMPLE_SAVE_FAILED",
            http_status=500,
        ) from error

    return ExpressionContributionResponse(
        sample_id=sample_id,
        label=normalized_label,
        status="accepted",
        message="样本已接收，将用于后续人工复核与模型优化",
    )


@router.delete(
    "/contributions/expression-samples/{sample_id}",
    response_model=ExpressionContributionResponse,
)
async def delete_expression_sample(
    sample_id: str,
    user: UserRow = Depends(current_user),
) -> ExpressionContributionResponse:
    """允许贡献者删除自己上传的样本及其元数据。"""
    if not sample_id.isalnum() or len(sample_id) != 32:
        raise AppException("样本编号无效", code="EXPRESSION_SAMPLE_ID_INVALID", http_status=422)
    metadata_path = _metadata_path(sample_id)
    if not metadata_path.exists():
        raise AppException("样本不存在", code="EXPRESSION_SAMPLE_NOT_FOUND", http_status=404)
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AppException("样本元数据不可读", code="EXPRESSION_METADATA_INVALID", http_status=500) from error
    if metadata.get("owner_id") != user.id:
        raise Forbidden("无权删除该样本")

    for extension in (".jpg", ".png"):
        (_storage_dir() / f"{sample_id}{extension}").unlink(missing_ok=True)
    metadata_path.unlink(missing_ok=True)
    return ExpressionContributionResponse(
        sample_id=sample_id,
        label=str(metadata.get("label", "UNKNOWN")),
        status="deleted",
        message="样本及其元数据已删除",
    )


__all__ = ["router"]
