"""知识库导入/检索/删除测试。"""
from __future__ import annotations

import io
from pathlib import Path


def test_knowledge_status_empty(empty_app_client):
    resp = empty_app_client.get("/api/v1/knowledge/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_count"] == 0
    assert body["chunk_count"] == 0
    assert body["is_available"] is False
    assert body["index_status"] == "empty"
    assert body["retrieval_method"] == "bm25"


def test_knowledge_status_after_demo_import(app_client):
    """app_client fixture 已导入演示资料。"""
    resp = app_client.get("/api/v1/knowledge/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_count"] >= 5  # 至少 5 份演示资料
    assert body["chunk_count"] > 0
    assert body["is_available"] is True
    assert body["index_status"] == "ready"


def test_list_documents(app_client):
    resp = app_client.get("/api/v1/knowledge/documents")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 5
    # 每份文档有元数据
    first = body[0]
    assert "document_id" in first
    assert "title" in first
    assert "content_hash" in first
    assert "is_official" in first
    assert "is_expired" in first


def test_upload_markdown_document(empty_app_client):
    """上传一份 Markdown 文档。"""
    content = "# 测试文档\n\n这是测试内容，包含社会实践学分申请相关信息。"
    resp = empty_app_client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("test.md", io.BytesIO(content.encode("utf-8")), "text/markdown")},
        data={
            "title": "测试文档",
            "source_department": "测试学院",
            "source_type": "test",
            "is_official": "true",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "测试文档"
    assert body["source_department"] == "测试学院"
    assert body["is_official"] is True
    assert body["document_id"].startswith("doc_")
    # 应可查询
    resp2 = empty_app_client.get("/api/v1/knowledge/status")
    assert resp2.json()["document_count"] == 1


def test_upload_duplicate_returns_409(empty_app_client):
    """重复内容应返回 409。"""
    content = "# 重复测试\n\n相同内容。"
    files_args = {
        "file": ("dup.md", io.BytesIO(content.encode("utf-8")), "text/markdown"),
    }
    resp1 = empty_app_client.post("/api/v1/knowledge/documents", files=files_args)
    assert resp1.status_code == 200
    # 重新构造 BytesIO (已被读取)
    files_args2 = {
        "file": ("dup2.md", io.BytesIO(content.encode("utf-8")), "text/markdown"),
    }
    resp2 = empty_app_client.post("/api/v1/knowledge/documents", files=files_args2)
    assert resp2.status_code == 409
    body = resp2.json()
    assert body["code"] == "DOCUMENT_ALREADY_EXISTS"


def test_upload_unsupported_type_rejected(empty_app_client):
    """不支持文件类型应被拒绝。"""
    content = b"binary data"
    resp = empty_app_client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("test.exe", io.BytesIO(content), "application/octet-stream")},
    )
    assert resp.status_code == 415
    body = resp.json()
    assert body["code"] == "FILE_TYPE_NOT_ALLOWED"


def test_upload_oversized_file_rejected(empty_app_client):
    """超大文件应被拒绝。"""
    # 构造一个大于 10MB 的内容
    big = b"x" * (11 * 1024 * 1024)
    resp = empty_app_client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("big.txt", io.BytesIO(big), "text/plain")},
    )
    assert resp.status_code == 413
    body = resp.json()
    assert body["code"] == "FILE_TOO_LARGE"


def test_upload_empty_file_rejected(empty_app_client):
    """空文件应被拒绝。"""
    resp = empty_app_client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
    )
    assert resp.status_code == 415
    body = resp.json()
    assert body["code"] == "FILE_TYPE_NOT_ALLOWED"


def test_delete_document(empty_app_client):
    """删除文档后应不再出现在列表中。"""
    content = "# 删除测试\n\n内容。"
    upload_resp = empty_app_client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("del.md", io.BytesIO(content.encode("utf-8")), "text/markdown")},
    )
    doc_id = upload_resp.json()["document_id"]

    del_resp = empty_app_client.delete(f"/api/v1/knowledge/documents/{doc_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # 列表中应不再有
    list_resp = empty_app_client.get("/api/v1/knowledge/documents")
    ids = [d["document_id"] for d in list_resp.json()]
    assert doc_id not in ids


def test_delete_nonexistent_returns_404(empty_app_client):
    resp = empty_app_client.delete("/api/v1/knowledge/documents/doc_notexist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "DOCUMENT_NOT_FOUND"


def test_rebuild_index(app_client):
    resp = app_client.post("/api/v1/knowledge/rebuild")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["document_count"] >= 5
    assert body["chunk_count"] > 0
