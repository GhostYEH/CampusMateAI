"""健康检查测试。"""
from __future__ import annotations


def test_health_returns_ok(app_client):
    resp = app_client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["mode"] == "real_backend"
    assert "version" in body
    assert "knowledge_base_initialized" in body
    assert "document_count" in body
    assert "chunk_count" in body
    assert "llm_available" in body
    assert body["retrieval_method"] == "bm25"


def test_health_empty_kb(empty_app_client):
    resp = empty_app_client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_count"] == 0
    assert body["chunk_count"] == 0
    assert body["knowledge_base_initialized"] is False


def test_root_endpoint(app_client):
    resp = app_client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert "name" in body
    assert "version" in body


def test_404_returns_structured_error(app_client):
    resp = app_client.get("/api/v1/nonexistent")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "NOT_FOUND"
    assert "message" in body
