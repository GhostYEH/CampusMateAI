"""取消检查点与 run 终态保护(§5.6)。

取消是协作式的:置为 CANCELLED 后,后续模型/工具步骤必须自行停止,
不能继续消耗额度或产生新的写操作。
"""
from __future__ import annotations

import pytest

from app.core.exceptions import AgentRunCancelled, AgentRuntimeError
from app.services.agent_runtime.cancellation import ensure_run_active, is_run_cancelled
from app.services.agent_runtime.run_manager import RunManager


class _RunRepositoryStub:
    """最小 run 仓储:只服务取消语义用例。"""

    def __init__(self, status: str) -> None:
        self._run = {"run_id": "run_x", "status": status}

    def get_run(self, run_id: str):
        return self._run if run_id == "run_x" else None


@pytest.mark.parametrize("status", ["RUNNING", "QUEUED", "AWAITING_APPROVAL"])
def test_active_run_passes_checkpoint(status: str):
    repo = _RunRepositoryStub(status)
    assert is_run_cancelled(repo, "run_x") is False
    assert ensure_run_active(repo, "run_x")["status"] == status


def test_cancelled_run_raises_run_cancelled():
    repo = _RunRepositoryStub("CANCELLED")
    assert is_run_cancelled(repo, "run_x") is True
    with pytest.raises(AgentRunCancelled) as excinfo:
        ensure_run_active(repo, "run_x")
    assert excinfo.value.code == "AGENT_RUN_CANCELLED"


def test_terminal_run_cannot_advance():
    repo = _RunRepositoryStub("SUCCEEDED")
    with pytest.raises(AgentRuntimeError) as excinfo:
        ensure_run_active(repo, "run_x")
    assert excinfo.value.code == "AGENT_INVALID_STATE"


def test_missing_run_reports_not_found():
    repo = _RunRepositoryStub("RUNNING")
    with pytest.raises(AgentRuntimeError) as excinfo:
        ensure_run_active(repo, "run_missing")
    assert excinfo.value.code == "AGENT_RUN_NOT_FOUND"


def test_run_manager_checkpoint_delegates_to_cancellation_helper():
    manager = RunManager(_RunRepositoryStub("RUNNING"))
    assert manager.assert_active("run_x")["run_id"] == "run_x"

    cancelled = RunManager(_RunRepositoryStub("CANCELLED"))
    with pytest.raises(AgentRunCancelled):
        cancelled.assert_active("run_x")


def test_cancelled_run_rejects_further_transitions():
    """终态保护:CANCELLED 之后不能再转 SUCCEEDED。"""
    repo = _RunRepositoryStub("CANCELLED")
    manager = RunManager(repo)
    with pytest.raises(AgentRuntimeError) as excinfo:
        manager.transition("run_x", "SUCCEEDED", phase="IDLE")
    assert excinfo.value.code == "AGENT_INVALID_STATE"
