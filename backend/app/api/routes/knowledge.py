"""知识库管理路由。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from ...core.exceptions import AppException, DocumentNotFound, FileNameUnsafe
from ...core.logging import logger
from ...core.security import sanitize_filename
from ...schemas.knowledge import (
    DataManagementResponse,
    DeleteResponse,
    DocumentMetadata,
    DocumentSummary,
    KnowledgeStatus,
    RebuildResponse,
)
from ...services.container import get_container

router = APIRouter()


def _determine_knowledge_base_type(
    demo_count: int, user_count: int
) -> str:
    """根据演示/用户文档数量判定知识库类型。"""
    if demo_count == 0 and user_count == 0:
        return "empty"
    if demo_count > 0 and user_count == 0:
        return "demo"
    if demo_count == 0 and user_count > 0:
        return "user"
    return "hybrid"


def _determine_qa_mode(
    *, llm_available: bool, is_available: bool
) -> str:
    """根据 LLM 与知识库可用性判定问答模式。"""
    if not is_available:
        return "no_knowledge"
    if llm_available:
        return "llm_rag"
    return "retrieval_summary"


@router.get("/knowledge/status", response_model=KnowledgeStatus)
async def knowledge_status() -> KnowledgeStatus:
    container = get_container()
    container.retrieval.rebuild()
    last_imported = container.document_repository.latest_imported_at()
    chunk_count = container.retrieval.chunk_count
    doc_count = container.document_repository.count_documents()
    demo_count = container.document_repository.count_demo_documents()
    user_count = container.document_repository.count_user_documents()
    is_available = chunk_count > 0
    kb_type = _determine_knowledge_base_type(demo_count, user_count)
    llm_available = (
        container.llm is not None and container.settings.llm_available
    )
    qa_mode = _determine_qa_mode(
        llm_available=llm_available, is_available=is_available
    )
    return KnowledgeStatus(
        document_count=doc_count,
        chunk_count=chunk_count,
        last_updated=last_imported,
        index_status="ready" if is_available else "empty",
        retrieval_method="bm25",
        is_available=is_available,
        knowledge_base_path=str(container.settings.knowledge_base_dir),
        knowledge_base_type=kb_type,
        demo_document_count=demo_count,
        user_document_count=user_count,
        llm_available=llm_available,
        qa_mode=qa_mode,
    )


@router.get("/knowledge/documents", response_model=List[DocumentSummary])
async def list_documents() -> List[DocumentSummary]:
    container = get_container()
    docs = container.document_repository.list_documents()
    return [
        DocumentSummary(
            document_id=d.document_id,
            title=d.title,
            source_department=d.source_department,
            source_type=d.source_type,
            original_filename=d.original_filename,
            content_hash=d.content_hash,
            published_at=_parse_dt(d.published_at),
            updated_at=_parse_dt(d.updated_at),
            effective_from=_parse_dt(d.effective_from),
            effective_to=_parse_dt(d.effective_to),
            version=d.version,
            applicable_students=d.applicable_students,
            is_official=d.is_official,
            is_expired=d.is_expired,
            is_demo=d.is_demo,
            file_size=d.file_size,
            file_ext=d.file_ext,
            imported_at=_parse_dt(d.imported_at),
        )
        for d in docs
    ]


def _parse_dt(s: Optional[str]):
    if not s:
        return None
    from datetime import datetime
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.post("/knowledge/documents", response_model=DocumentSummary)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    source_department: Optional[str] = Form(None),
    source_type: Optional[str] = Form(None),
    published_at: Optional[str] = Form(None),
    updated_at: Optional[str] = Form(None),
    effective_from: Optional[str] = Form(None),
    effective_to: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
    applicable_students: Optional[str] = Form(None),
    is_official: bool = Form(False),
) -> DocumentSummary:
    """上传文档到知识库。

    使用 multipart/form-data 上传文件，元数据通过 Form 字段提供。
    上传的文档默认 is_demo=False(用户导入资料)。
    """
    container = get_container()
    # 校验文件名(防止路径穿越、特殊字符)
    original_filename = file.filename or "upload"
    try:
        safe_filename = sanitize_filename(original_filename)
    except ValueError as e:
        raise AppException(
            str(e),
            code="FILE_NAME_UNSAFE",
            http_status=400,
        )
    # sanitize_filename 已剥离路径,用安全名重新取扩展名
    ext = Path(safe_filename).suffix.lstrip(".").lower()
    if ext not in container.settings.allowed_extensions_list:
        raise AppException(
            f"仅允许 {','.join(container.settings.allowed_extensions_list)} 类型",
            code="FILE_TYPE_NOT_ALLOWED",
            http_status=415,
        )
    # 读取到临时文件
    suffix = f".{ext}"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        total = 0
        max_bytes = container.settings.max_upload_mb * 1024 * 1024
        while True:
            buf = await file.read(64 * 1024)
            if not buf:
                break
            total += len(buf)
            if total > max_bytes:
                tmp.close()
                os.unlink(tmp.name)
                raise AppException(
                    f"文件超过 {container.settings.max_upload_mb} MB 上限",
                    code="FILE_TOO_LARGE",
                    http_status=413,
                )
            tmp.write(buf)
        tmp.close()
        row, created = container.knowledge_ingestion.import_file(
            Path(tmp.name),
            original_filename=original_filename,
            source_department=source_department,
            source_type=source_type,
            published_at=published_at,
            updated_at=updated_at,
            effective_from=effective_from,
            effective_to=effective_to,
            version=version,
            applicable_students=applicable_students,
            is_official=is_official,
            is_demo=False,  # 上传的文档默认是用户导入,非演示资料
        )
        if not created:
            raise AppException(
                "文档已存在(哈希重复)",
                code="DOCUMENT_ALREADY_EXISTS",
                http_status=409,
                details={"document_id": row.document_id, "title": row.title},
            )
        # 若上传时未提供 title，使用文件推断的
        final_title = title or row.title
        # 重建索引
        container.retrieval.rebuild()
        return DocumentSummary(
            document_id=row.document_id,
            title=final_title,
            source_department=row.source_department,
            source_type=row.source_type,
            original_filename=row.original_filename,
            content_hash=row.content_hash,
            published_at=_parse_dt(row.published_at),
            updated_at=_parse_dt(row.updated_at),
            effective_from=_parse_dt(row.effective_from),
            effective_to=_parse_dt(row.effective_to),
            version=row.version,
            applicable_students=row.applicable_students,
            is_official=row.is_official,
            is_expired=row.is_expired,
            is_demo=row.is_demo,
            file_size=row.file_size,
            file_ext=row.file_ext,
            imported_at=_parse_dt(row.imported_at),
        )
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


@router.delete("/knowledge/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(document_id: str) -> DeleteResponse:
    container = get_container()
    deleted = container.knowledge_ingestion.delete_document(document_id)
    if not deleted:
        raise DocumentNotFound(f"文档 {document_id} 不存在")
    container.retrieval.rebuild()
    return DeleteResponse(success=True, document_id=document_id)


@router.post("/knowledge/rebuild", response_model=RebuildResponse)
async def rebuild_index() -> RebuildResponse:
    container = get_container()
    n = container.knowledge_ingestion.rebuild_index()
    return RebuildResponse(
        success=True,
        document_count=container.document_repository.count_documents(),
        chunk_count=n,
        message="索引已重建",
    )


@router.post("/knowledge/manage/{action}", response_model=DataManagementResponse)
async def data_management(action: str) -> DataManagementResponse:
    """数据管理操作。

    支持的 action:
    - delete_user_documents: 删除所有用户导入的知识库文档(保留测试环境资料)
    - delete_all_documents: 删除所有知识库文档(包括测试环境资料)

    备注:
    - 不再提供"恢复演示资料 / 一键重置演示数据"等生产接口;
      测试环境资料仅在 dev/test 启动时通过 AUTO_IMPORT_DEMO 导入,
      production 已被 config 校验拦截。
    """
    container = get_container()
    action = action.strip().lower()
    if action == "delete_user_documents":
        n = container.knowledge_ingestion.delete_all_user_documents()
        container.retrieval.rebuild()
        return DataManagementResponse(
            success=True,
            action=action,
            affected_count=n,
            message=(
                f"已删除 {n} 份用户导入文档,测试环境资料保留。"
                if n > 0
                else "没有用户导入文档可删除。"
            ),
        )
    if action == "delete_all_documents":
        n = container.knowledge_ingestion.delete_all_documents()
        container.retrieval.rebuild()
        return DataManagementResponse(
            success=True,
            action=action,
            affected_count=n,
            message=f"已删除全部 {n} 份知识库文档(包括测试环境资料)。",
        )
    raise AppException(
        f"不支持的数据管理操作: {action}",
        code="INVALID_ACTION",
        http_status=400,
    )
