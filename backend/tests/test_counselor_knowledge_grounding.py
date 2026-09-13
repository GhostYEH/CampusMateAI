"""CPM 必须把知识库证据与世界模型上下文一起交给后端大模型。"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, List
from pathlib import Path
from types import SimpleNamespace

from app.core.config import Settings
from app.api.routes import counselor
from app.api.routes.counselor import _collect_learner_state_context
from app.database.sqlite_db import Database
from app.repositories.document_repository import DocumentRepository
from app.services.llm.base import LLMResponse
from app.services.rag_service import RagService
from app.services.retrieval_service import RetrievalService


class RecordingLLM:
    def __init__(self) -> None:
        self.messages: List[dict] = []

    @property
    def name(self) -> str:
        return "recording"

    @property
    def available(self) -> bool:
        return True

    async def stream_chat(self, messages: List[dict], **kwargs) -> AsyncIterator[str]:
        self.messages = messages
        yield "已根据资料和你的学习安排整理。"

    async def chat(self, messages: List[dict], **kwargs) -> LLMResponse:
        self.messages = messages
        return LLMResponse(content="已根据资料和你的学习安排整理。")


def _settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        llm_provider="openai_compatible",
        llm_base_url="http://localhost",
        llm_api_key="test-key",
        llm_model="test-model",
    )


def _collect(rag: RagService) -> list:
    async def run() -> list:
        return [
            event
            async for event in rag.stream_answer(
                "奖学金怎么申请",
                world_model_context="当前正在准备本学期材料，最近待办是整理成绩单",
            )
        ]

    return asyncio.run(run())


def test_cpm_combines_retrieved_policy_with_world_model_context() -> None:
    db = Database(None)
    repository = DocumentRepository(db)
    repository.add_document(
        title="本校奖学金正式通知",
        content_text=(
            "本校奖学金申请条件包括正式学籍和综合测评排名。"
            "奖学金申请须提交本学年成绩单、奖学金申请表，"
            "并在学生事务系统办理。"
        ),
        raw_text=(
            "本校奖学金申请条件包括正式学籍和综合测评排名。"
            "奖学金申请须提交本学年成绩单、奖学金申请表，"
            "并在学生事务系统办理。"
        ),
        source_department="学生资助中心",
        is_official=True,
    )
    repository.add_document(
        title="图书馆借阅规则",
        content_text="图书馆借阅证可借阅纸质图书。",
        raw_text="图书馆借阅证可借阅纸质图书。",
    )
    repository.add_document(
        title="实验室预约规则",
        content_text="实验室设备需要提前预约。",
        raw_text="实验室设备需要提前预约。",
    )
    repository.add_document(
        title="学生请假流程",
        content_text="学生请假需要提交请假申请。",
        raw_text="学生请假需要提交请假申请。",
    )
    retrieval = RetrievalService(repository)
    retrieval.rebuild()
    llm = RecordingLLM()
    rag = RagService(retrieval, llm, _settings(), repository)

    events = _collect(rag)
    final = events[-1]
    user_prompt = llm.messages[-1]["content"]

    assert final.mode == "llm"
    assert final.sources
    assert final.sources[0].title == "本校奖学金正式通知"
    assert "本学年成绩单" in user_prompt
    assert "当前正在准备本学期材料" in user_prompt


def test_demo_knowledge_directory_has_no_bundled_policy_files() -> None:
    demo_dir = Path(__file__).parents[1] / "data" / "knowledge_base" / "demo"
    assert not list(demo_dir.glob("*.md"))


def test_cpm_exposes_exact_assistant_chat_alias() -> None:
    paths = {route.path for route in counselor.router.routes}
    assert "/counselor/chat" in paths
    assert "/assistant/chat" in paths


def test_counselor_reads_current_learner_world_model_snapshots() -> None:
    snapshot = SimpleNamespace(
        state_type="workload_pressure",
        scope_type="USER",
        scope_id="user-1",
        value={"pressure_band": "HIGH", "task_count": 4},
        confidence=0.91,
        data_quality="verified",
    )
    snapshot_calls: list[dict] = []

    def list_all_current_snapshots(**kwargs):
        snapshot_calls.append(kwargs)
        return [snapshot]

    forecast = SimpleNamespace(
        forecast_type="UPCOMING_WORKLOAD",
        data_quality="verified",
        confidence=0.8,
        value=SimpleNamespace(pressure_band="HIGH", task_count=4),
    )
    plan = SimpleNamespace(
        status="PROPOSED",
        run=SimpleNamespace(valid_until="2099-01-01T00:00:00+00:00"),
        items=[SimpleNamespace(item_type="REVIEW_DEADLINE", estimated_minutes=30)],
    )
    container = SimpleNamespace(
        learner_state_repository=SimpleNamespace(
            list_all_current_snapshots=list_all_current_snapshots
        ),
        forecast_service=SimpleNamespace(
            list_forecasts=lambda **kwargs: ([forecast], 1)
        ),
        learning_plan_repository=SimpleNamespace(
            list_plans=lambda **kwargs: ([plan], 1)
        ),
    )

    context, count, warnings = _collect_learner_state_context(
        container,
        SimpleNamespace(id="user-1"),
    )

    assert count == 1
    assert "workload_pressure" in context
    assert "HIGH" in context
    assert snapshot_calls[0]["projection_kind"] == "WORLD"
    assert "预测摘要" in context
    assert "UPCOMING_WORKLOAD" in context
    assert "行动计划摘要" in context
    assert "PROPOSED" in context
    assert warnings == []
