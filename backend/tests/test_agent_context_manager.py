from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import AppException
from app.services.agent_runtime.context_manager import ContextManager


def test_context_snapshot_is_bounded_immutable_and_expires():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    snapshot = ContextManager(max_rows=2, max_chars=1000).build(
        user_id="u", scope={"course_ids": ["c"]},
        facts={"tasks": [{"id": "1"}, {"id": "2"}, {"id": "3"}]},
        source_refs=["tasks"], now=now,
    )
    assert len(snapshot.facts["tasks"]) == 2
    assert snapshot.truncated_sources == ("tasks",)
    with pytest.raises(TypeError):
        snapshot.facts["tasks"] = []
    with pytest.raises(AppException) as exc:
        ContextManager.require_fresh(snapshot, now + timedelta(hours=1))
    assert exc.value.code == "AGENT_CONTEXT_EXPIRED"
