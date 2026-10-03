import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.config import Settings
from app.models.document import ChunkRow, DocumentRow
from app.services.rag_service import RagService
from app.services.retrieval_service import RetrievalService


@pytest.mark.asyncio
async def test_slow_retrieval_does_not_block_other_async_requests():
    entered = threading.Event()
    release = threading.Event()

    def search(*args, **kwargs):
        entered.set()
        assert release.wait(2), "event loop did not release the retrieval worker"
        return []

    service = RagService(Mock(search=search), None, Settings(llm_provider="none"), Mock())
    response = asyncio.create_task(service.answer("奖学金申请有哪些材料？"))
    try:
        for _ in range(100):
            if entered.is_set():
                break
            await asyncio.sleep(0.005)
        assert entered.is_set()
        assert not response.done()
    finally:
        release.set()
    result = await response
    assert result.answer


def test_global_vocabulary_rebuilds_once_and_refreshes_after_document_changes():
    doc = DocumentRow(document_id="doc", title="奖学金申请", content_hash="hash", content_text="材料", raw_text="材料", is_official=True)
    documents = [doc] + [
        DocumentRow(document_id=f"other{i}", title=title, content_hash=str(i), content_text=title, raw_text=title)
        for i, title in enumerate(["校园食堂菜单", "运动场馆开放时间"])
    ]
    chunks = [ChunkRow(chunk_id=f"c{i}", document_id=row.document_id, section=None, position=0, content=row.title + row.content_text) for i, row in enumerate(documents)]
    repository = SimpleNamespace(
        list_documents=Mock(return_value=documents),
        list_chunks=Mock(return_value=chunks),
    )
    service = RetrievalService(repository)
    service.rebuild()
    vocabulary = service._global_token_set
    original = service.search("奖学金申请", k=1, min_absolute_score=0.01)
    assert original
    service.search("奖学金申请", k=1, min_absolute_score=0.01)
    assert service._global_token_set is vocabulary
    assert repository.list_chunks.call_count == 1
    repository.list_chunks.return_value = []
    repository.list_documents.return_value = []
    service.mark_stale()
    assert service.search("奖学金申请") == []
    assert service._global_token_set == frozenset()
    repository.list_chunks.return_value = chunks
    repository.list_documents.return_value = documents
    service.mark_stale()
    assert service.search("奖学金申请", k=1, min_absolute_score=0.01) == original
    assert service._global_token_set == vocabulary
