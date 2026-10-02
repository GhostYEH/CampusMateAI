import threading
from types import SimpleNamespace

import pytest

from app.api.routes import knowledge


@pytest.mark.asyncio
async def test_index_rebuild_runs_outside_event_loop_thread(monkeypatch):
    calls = []

    def rebuild():
        calls.append(threading.get_ident())
        return 12

    container = SimpleNamespace(
        knowledge_ingestion=SimpleNamespace(rebuild_index=rebuild),
        document_repository=SimpleNamespace(count_documents=lambda: 3),
    )
    monkeypatch.setattr(knowledge, "get_container", lambda: container)
    result = await knowledge.rebuild_index(_=None)
    assert result.chunk_count == 12
    assert calls and calls[0] != threading.get_ident()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["delete_user_documents", "delete_all_documents"])
async def test_data_management_offloads_delete_and_rebuild(monkeypatch, action):
    calls = []

    def delete():
        calls.append(("delete", threading.get_ident()))
        return 2

    def rebuild():
        calls.append(("rebuild", threading.get_ident()))

    container = SimpleNamespace(
        knowledge_ingestion=SimpleNamespace(delete_all_user_documents=delete, delete_all_documents=delete),
        retrieval=SimpleNamespace(rebuild=rebuild),
    )
    monkeypatch.setattr(knowledge, "get_container", lambda: container)
    result = await knowledge.data_management(action, _=None)
    assert result.affected_count == 2
    assert [kind for kind, _ in calls] == ["delete", "rebuild"]
    assert all(thread_id != threading.get_ident() for _, thread_id in calls)
