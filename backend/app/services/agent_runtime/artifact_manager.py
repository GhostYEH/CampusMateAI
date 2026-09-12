"""Artifact 管理器 —— 原子写入 + 所有权校验。

JSON / Markdown 写入受控目录。每次读取重新校验所有权。
"""
from __future__ import annotations

from typing import Optional

from ...repositories.agent_artifact_repository import AgentArtifactRepository


class ArtifactManager:
    """Artifact 管理器。"""

    def __init__(self, repository: AgentArtifactRepository) -> None:
        self._repo = repository

    def create(
        self,
        *,
        run_id: str,
        user_id: str,
        artifact_type: str,
        content: dict | str,
        mime_type: str = "application/json",
        version: int = 1,
    ) -> str:
        return self._repo.create_artifact(
            run_id=run_id,
            user_id=user_id,
            artifact_type=artifact_type,
            content=content,
            mime_type=mime_type,
            version=version,
        )

    def get(self, artifact_id: str, user_id: str) -> Optional[dict]:
        return self._repo.get_artifact(artifact_id, user_id)

    def read_content(self, artifact_id: str, user_id: str) -> Optional[str]:
        return self._repo.read_content(artifact_id, user_id)

    def list_by_run(self, run_id: str, user_id: str) -> list[dict]:
        return self._repo.list_artifacts_by_run(run_id, user_id)


__all__ = ["ArtifactManager"]