"""知识库导入服务 — 解析文档 → 分块 → 入库 → 重建索引。"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..core.exceptions import (
    DocumentAlreadyExists,
    FileTooLarge,
    FileNameUnsafe,
    FileTypeNotAllowed,
)
from ..core.security import is_path_traversal, sanitize_filename
from ..core.config import Settings
from ..repositories.document_repository import DocumentRepository, compute_content_hash
from ..utils.file_parsers import parse_file
from ..utils.text_utils import normalize_text
from .retrieval_service import RetrievalService


def _is_expired(effective_to: Optional[str]) -> bool:
    """如果 effective_to 早于当前时间，标记为过期。"""
    if not effective_to:
        return False
    try:
        dt = datetime.fromisoformat(effective_to.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt < datetime.now(timezone.utc)
    except ValueError:
        return False


class KnowledgeIngestionService:
    """文档导入、解析、入库、索引重建。"""

    def __init__(
        self,
        repository: DocumentRepository,
        retrieval: RetrievalService,
        settings: Settings,
    ) -> None:
        self._repo = repository
        self._retrieval = retrieval
        self._settings = settings
        # 确保知识库目录存在
        self._settings.knowledge_base_dir.mkdir(parents=True, exist_ok=True)

    def import_file(
        self,
        file_path: Path,
        *,
        original_filename: Optional[str] = None,
        source_department: Optional[str] = None,
        source_type: Optional[str] = None,
        published_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        effective_from: Optional[str] = None,
        effective_to: Optional[str] = None,
        version: Optional[str] = None,
        applicable_students: Optional[str] = None,
        is_official: bool = False,
        is_demo: bool = False,
    ):
        """导入文件，返回 (document_row, created)。"""
        # 1. 安全检查
        ext = file_path.suffix.lstrip(".").lower()
        if ext not in self._settings.allowed_extensions_list:
            raise FileTypeNotAllowed(
                f"仅允许 {','.join(self._settings.allowed_extensions_list)} 类型"
            )
        size = file_path.stat().st_size
        if size > self._settings.max_upload_mb * 1024 * 1024:
            raise FileTooLarge(
                f"文件超过 {self._settings.max_upload_mb} MB 上限"
            )
        if size == 0:
            raise FileTypeNotAllowed("文件为空")

        if original_filename:
            safe_name = sanitize_filename(original_filename)
        else:
            safe_name = sanitize_filename(file_path.name)
        # 路径穿越检查仅用于"从知识库目录读取"的场景；
        # 上传文件位于临时目录，不需要也不应位于 knowledge_base_dir 下。

        # 2. 解析
        try:
            content = parse_file(file_path)
        except ValueError as e:
            raise FileTypeNotAllowed(str(e))
        content = normalize_text(content)
        if not content.strip():
            raise FileTypeNotAllowed("解析后内容为空")

        # 3. 推断标题与元数据
        content_hash = compute_content_hash(content)
        existing = self._repo.get_document_by_hash(content_hash)
        if existing is not None:
            raise DocumentAlreadyExists(
                f"文档已存在(哈希重复): {existing.title}",
                details={"document_id": existing.document_id},
            )

        title = self._repo.infer_title_from_content(content, fallback_filename=safe_name)
        is_expired = _is_expired(effective_to)

        # 4. 入库
        row, created = self._repo.add_document(
            title=title,
            content_text=content,
            raw_text=content,
            content_hash=content_hash,
            source_department=source_department,
            source_type=source_type,
            original_filename=safe_name,
            published_at=published_at,
            updated_at=updated_at,
            effective_from=effective_from,
            effective_to=effective_to,
            version=version,
            applicable_students=applicable_students,
            is_official=is_official,
            is_expired=is_expired,
            is_demo=is_demo,
            file_size=size,
            file_ext=ext,
        )
        # 5. 重建索引
        self._retrieval.mark_stale()
        return row, created

    def import_text(
        self,
        *,
        content: str,
        title: str,
        source_department: Optional[str] = None,
        source_type: Optional[str] = None,
        original_filename: Optional[str] = None,
        published_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        effective_from: Optional[str] = None,
        effective_to: Optional[str] = None,
        version: Optional[str] = None,
        applicable_students: Optional[str] = None,
        is_official: bool = False,
        is_demo: bool = False,
    ):
        """直接以文本形式导入(用于演示资料)。"""
        content = normalize_text(content)
        if not content.strip():
            raise FileTypeNotAllowed("内容为空")
        content_hash = compute_content_hash(content)
        existing = self._repo.get_document_by_hash(content_hash)
        if existing is not None:
            raise DocumentAlreadyExists(
                f"文档已存在(哈希重复): {existing.title}",
                details={"document_id": existing.document_id},
            )
        is_expired = _is_expired(effective_to)
        row, created = self._repo.add_document(
            title=title,
            content_text=content,
            raw_text=content,
            content_hash=content_hash,
            source_department=source_department,
            source_type=source_type,
            original_filename=original_filename,
            published_at=published_at,
            updated_at=updated_at,
            effective_from=effective_from,
            effective_to=effective_to,
            version=version,
            applicable_students=applicable_students,
            is_official=is_official,
            is_expired=is_expired,
            is_demo=is_demo,
        )
        self._retrieval.mark_stale()
        return row, created

    def delete_document(self, document_id: str) -> bool:
        deleted = self._repo.delete_document(document_id)
        if deleted:
            self._retrieval.mark_stale()
        return deleted

    def rebuild_index(self) -> int:
        return self._retrieval.rebuild()

    def import_demo_documents(self) -> int:
        """导入内置测试环境资料(若尚未导入)。返回新增数量。

        说明:
        - 测试环境资料明确标注 is_demo=True,用于在 dev/test 环境快速验证检索/RAG 链路。
        - 资料内容为"仿真校园制度文档",不代表任何真实学校制度。
        - production 环境下 Settings 校验已禁止 AUTO_IMPORT_DEMO=True,
          因此本方法在生产路径中不会被调用。
        """
        demo_dir = self._settings.knowledge_base_dir / "demo"
        if not demo_dir.exists():
            return 0
        added = 0
        for md_file in sorted(demo_dir.glob("*.md")):
            try:
                self.import_file(
                    md_file,
                    original_filename=md_file.name,
                    source_type="demo",
                    source_department="测试环境资料(仿真校园)",
                    is_official=True,
                    is_demo=True,
                )
                added += 1
            except (DocumentAlreadyExists, FileTypeNotAllowed, FileTooLarge, FileNameUnsafe):
                continue
        return added

    def delete_all_user_documents(self) -> int:
        """删除所有用户导入文档(is_demo=0),保留测试环境资料。"""
        n = self._repo.delete_all_user_documents()
        if n > 0:
            self._retrieval.mark_stale()
        return n

    def delete_all_documents(self) -> int:
        """删除所有文档(包括演示资料)。"""
        n = self._repo.delete_all_documents()
        if n > 0:
            self._retrieval.mark_stale()
        return n


__all__ = ["KnowledgeIngestionService"]
