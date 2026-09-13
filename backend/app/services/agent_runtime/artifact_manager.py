from __future__ import annotations

import hashlib
from pathlib import Path

from ...core.exceptions import AppException
from ...models.agent_runtime import AgentArtifactRow
from ...repositories.agent_artifact_repository import AgentArtifactRepository


class ArtifactManager:
    def __init__(self, repository: AgentArtifactRepository, root: Path) -> None:
        self._repository = repository
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, content_ref: str) -> Path:
        candidate = (self._root / content_ref).resolve()
        if candidate == self._root or self._root not in candidate.parents:
            raise AppException(code="AGENT_TOOL_REJECTED", http_status=400, message="Artifact 路径不安全")
        return candidate

    def create(self, *, user_id: str, run_id: str, artifact_type: str, version: int,
               mime_type: str, content: bytes) -> AgentArtifactRow:
        if len(content) > 2 * 1024 * 1024:
            raise AppException(code="AGENT_TOOL_REJECTED", http_status=413, message="Artifact 超出大小限制")
        digest = hashlib.sha256(content).hexdigest()
        content_ref = f"{user_id}/{run_id}/{artifact_type.lower()}-v{version}-{digest[:12]}.bin"
        target = self._resolve(content_ref)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        try:
            return self._repository.create(
                user_id=user_id, run_id=run_id, artifact_type=artifact_type,
                content_ref=content_ref, content_hash=digest, version=version,
                mime_type=mime_type, size_bytes=len(content),
            )
        except Exception:
            target.unlink(missing_ok=True)
            raise

    def read(self, *, artifact_id: str, user_id: str) -> bytes:
        artifact = self._repository.get(artifact_id=artifact_id, user_id=user_id)
        if artifact is None:
            raise AppException(code="AGENT_PERMISSION_DENIED", http_status=404, message="Artifact 不存在")
        target = self._resolve(artifact.content_ref)
        if not target.is_file():
            raise AppException(code="AGENT_INVALID_STATE", http_status=404, message="Artifact 内容不可用")
        content = target.read_bytes()
        if hashlib.sha256(content).hexdigest() != artifact.content_hash:
            raise AppException(code="AGENT_INVALID_STATE", http_status=409, message="Artifact 完整性校验失败")
        return content
