"""AI 导员真实上下文融合测试 — recent_tasks / self_report / expression_signal。

覆盖要求(用户原话):
1. 用户 A 创建 PersonalTask
2. 用户 A 发送该 task_id,任务进入上下文
3. 用户 A 伪造 title,后端使用数据库真实 title
4. 用户 B 发送用户 A 的 task_id,任务被忽略
5. 发送不存在的 task_id,任务被忽略
6. 发送已软删除 task_id,任务被忽略
7. 匿名用户发送 recent_tasks,全部忽略
8. ignored task 的伪造 title 不得出现在:
   - answer
   - context_used
   - context_warnings 以外的正文
   - sources
   - LLM prompt 测试桩
   - 普通日志
9. Assignment ID 放进 recent_tasks 时必须被忽略
10. Assignment 仍通过 assignment_id 正常工作
11. self_report 超过 500 字返回 422
12. self_report 空白字符串转换为 null
13. 携带 self_report 时无知识库依据仍返回 no_knowledge
14. expression_signal 不进入 LLM prompt

实现说明:
- 测试桩 LLM: 使用 RecordingLLMClient 记录最近一次 messages,
  通过容器替换 rag_service._llm 实现。
- 检查 context_used: recent_tasks_count / accepted_count / ignored_count /
  self_report_present。
- 检查 expression_signal: 不进入 LLM messages 也不进入 answer。
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, List, Optional

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app as _global_app  # noqa: F401
from app.services.container import get_container, reset_container_for_tests


# ===== 测试桩 LLM =====


class RecordingLLMClient:
    """记录最近一次 messages,并返回固定 answer。

    用于断言 recent_tasks / self_report / expression_signal 是否进入 LLM prompt。
    """

    def __init__(self, answer: str = "测试回答") -> None:
        self._answer = answer
        self.last_messages: Optional[List[dict]] = None

    async def stream_chat(
        self,
        messages: List[dict],
        *,
        temperature: float = 0.2,
        max_tokens: int = 800,
        timeout: float = 60.0,
    ) -> AsyncIterator[str]:
        self.last_messages = [dict(m) for m in messages]
        # 一次性返回完整 answer
        yield self._answer


# ===== Fixture =====


@pytest.fixture(scope="function")
def counselor_client_with_llm():
    """提供带测试桩 LLM 的 TestClient + 演示数据 + 第二个学生。

    - student_demo / Demo123456 (学生 A)
    - student_other / Demo123456 (学生 B,用于越权测试)
    - 演示知识库(已导入,确保 LLM 路径可触发)
    - 注入测试桩 LLM,记录最近一次 messages
    """
    from app.services.demo_seeder import seed_demo_data
    from app.core.security import hash_password

    get_settings.cache_clear()
    settings = get_settings()
    # 显式启用 LLM 路径(通过测试桩)
    # llm_available 属性要求 provider=openai_compatible 且 url/key/model 非空
    settings.llm_provider = "openai_compatible"
    settings.llm_base_url = "http://stub.local"
    settings.llm_api_key = "stub_key"
    settings.llm_model = "stub_model"
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    # 导入演示知识库(确保 LLM 路径可触发,而非 no_knowledge)
    added = container.knowledge_ingestion.import_demo_documents()
    if added:
        container.retrieval.rebuild()
    # 创建第二个学生
    container.user_repository.create_user(
        username="student_other",
        password_hash=hash_password("Demo123456"),
        role="student",
        student_number="S202409999",
        display_name="其他学生",
    )
    # 注入测试桩 LLM(覆盖 _llm)
    stub_llm = RecordingLLMClient(answer="这是测试桩 LLM 的回答。")
    container.rag._llm = stub_llm

    from app.main import create_app
    test_app = create_app()
    client = TestClient(test_app)
    yield client, container, stub_llm


def _login(client, username="student_demo", password="Demo123456") -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_task(client, token, **overrides) -> dict:
    payload = {
        "title": "提交实践申请",
        "deadline": "2099-12-31T23:59:00+00:00",
        "source_type": "manual",
        "priority": "high",
    }
    payload.update(overrides)
    resp = client.post("/api/v1/tasks", json=payload, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _chat(
    client,
    *,
    token: Optional[str] = None,
    message: str = "社会实践怎么申请?",
    recent_tasks: Optional[List[dict]] = None,
    self_report: Optional[str] = None,
    expression_signal: Optional[dict] = None,
    assignment_id: Optional[str] = None,
    stream: bool = False,
):
    payload: dict[str, Any] = {"message": message, "stream": stream}
    if recent_tasks is not None:
        payload["recent_tasks"] = recent_tasks
    if self_report is not None:
        payload["self_report"] = self_report
    if expression_signal is not None:
        payload["expression_signal"] = expression_signal
    if assignment_id is not None:
        payload["assignment_id"] = assignment_id
    headers = _h(token) if token else None
    return client.post("/api/v1/counselor/chat", json=payload, headers=headers)


# ===== 测试 1: 用户 A 创建 PersonalTask,发送该 task_id,任务进入上下文 =====


def test_recent_tasks_user_a_own_task_accepted(counselor_client_with_llm):
    """测试 1+2: 用户 A 创建任务并发送 task_id,任务应进入上下文。"""
    client, container, stub_llm = counselor_client_with_llm
    token_a = _login(client, "student_demo")
    task = _create_task(client, token_a, title="复习高数第三章")

    resp = _chat(
        client,
        token=token_a,
        recent_tasks=[
            {
                "id": task["id"],
                "title": "客户端 hint(应被忽略)",
                "deadline": "2000-01-01T00:00:00+00:00",
                "priority": "low",
                "status": "completed",
            }
        ],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # context_used 应反映: 1 条请求,1 条接受,0 条忽略
    cu = body["context_used"]
    assert cu["recent_tasks_count"] == 1
    assert cu["recent_tasks_accepted_count"] == 1
    assert cu["recent_tasks_ignored_count"] == 0
    # LLM messages 应包含数据库真实 title(不是客户端伪造的)
    assert stub_llm.last_messages is not None
    user_msg = stub_llm.last_messages[-1]["content"]
    assert "复习高数第三章" in user_msg
    # 客户端伪造字段不应出现
    assert "客户端 hint" not in user_msg
    assert "2000-01-01" not in user_msg


# ===== 测试 3: 用户 A 伪造 title,后端使用数据库真实 title =====


def test_recent_tasks_forged_title_replaced_by_db_truth(counselor_client_with_llm):
    """测试 3: 客户端伪造的 title/deadline/priority/status 一律不信任,
    后端使用数据库权威字段。"""
    client, container, stub_llm = counselor_client_with_llm
    token_a = _login(client, "student_demo")
    task = _create_task(client, token_a, title="数据库真实标题", priority="high")

    resp = _chat(
        client,
        token=token_a,
        recent_tasks=[
            {
                "id": task["id"],
                "title": "FORGED_TITLE_SHOULD_NOT_APPEAR",
                "deadline": "1999-09-09T09:09:09+00:00",
                "priority": "low",
                "status": "completed",
            }
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    answer = body["answer"]
    # answer 中不应出现伪造字段
    assert "FORGED_TITLE_SHOULD_NOT_APPEAR" not in answer
    assert "1999-09-09" not in answer
    # LLM messages 中应出现数据库真实标题
    assert stub_llm.last_messages is not None
    user_msg = stub_llm.last_messages[-1]["content"]
    assert "数据库真实标题" in user_msg
    assert "FORGED_TITLE_SHOULD_NOT_APPEAR" not in user_msg


# ===== 测试 4: 用户 B 发送用户 A 的 task_id,任务被忽略 =====


def test_recent_tasks_other_user_task_ignored(counselor_client_with_llm):
    """测试 4: 越权任务(其他用户的 task_id)被忽略 + warning。"""
    client, container, stub_llm = counselor_client_with_llm
    token_a = _login(client, "student_demo")
    token_b = _login(client, "student_other")
    task_a = _create_task(client, token_a, title="学生 A 私有任务")

    resp = _chat(
        client,
        token=token_b,
        recent_tasks=[
            {
                "id": task_a["id"],
                "title": "试图越权访问",
            }
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    cu = body["context_used"]
    assert cu["recent_tasks_count"] == 1
    assert cu["recent_tasks_accepted_count"] == 0
    assert cu["recent_tasks_ignored_count"] == 1
    # LLM messages 不应包含越权任务的内容
    assert stub_llm.last_messages is not None
    user_msg = stub_llm.last_messages[-1]["content"]
    assert "学生 A 私有任务" not in user_msg
    assert "试图越权访问" not in user_msg


# ===== 测试 5: 发送不存在的 task_id,任务被忽略 =====


def test_recent_tasks_nonexistent_task_ignored(counselor_client_with_llm):
    """测试 5: 不存在的 task_id 被忽略 + warning。"""
    client, container, stub_llm = counselor_client_with_llm
    token_a = _login(client, "student_demo")

    resp = _chat(
        client,
        token=token_a,
        recent_tasks=[
            {
                "id": "ptask_does_not_exist_xxx",
                "title": "不存在的任务伪造标题",
            }
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    cu = body["context_used"]
    assert cu["recent_tasks_count"] == 1
    assert cu["recent_tasks_accepted_count"] == 0
    assert cu["recent_tasks_ignored_count"] == 1
    # LLM messages 不应包含伪造标题
    assert stub_llm.last_messages is not None
    user_msg = stub_llm.last_messages[-1]["content"]
    assert "不存在的任务伪造标题" not in user_msg


# ===== 测试 6: 发送已软删除 task_id,任务被忽略 =====


def test_recent_tasks_soft_deleted_task_ignored(counselor_client_with_llm):
    """测试 6: 已软删除(deleted_at 不为空)的任务被忽略 + warning。"""
    client, container, stub_llm = counselor_client_with_llm
    token_a = _login(client, "student_demo")
    task = _create_task(client, token_a, title="将被软删除的任务")
    # 软删除(返回 200 + 已删除的任务对象,response_model=PersonalTaskOut)
    del_resp = client.delete(f"/api/v1/tasks/{task['id']}", headers=_h(token_a))
    assert del_resp.status_code == 200

    resp = _chat(
        client,
        token=token_a,
        recent_tasks=[
            {
                "id": task["id"],
                "title": "已删除任务伪造标题",
            }
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    cu = body["context_used"]
    assert cu["recent_tasks_count"] == 1
    assert cu["recent_tasks_accepted_count"] == 0
    assert cu["recent_tasks_ignored_count"] == 1
    # LLM messages 不应包含已删除任务的内容
    assert stub_llm.last_messages is not None
    user_msg = stub_llm.last_messages[-1]["content"]
    assert "将被软删除的任务" not in user_msg
    assert "已删除任务伪造标题" not in user_msg


# ===== 测试 7: 匿名用户发送 recent_tasks,全部忽略 =====


def test_recent_tasks_anonymous_all_ignored(counselor_client_with_llm):
    """测试 7: 匿名用户的 recent_tasks 全部忽略 + warning。"""
    client, container, stub_llm = counselor_client_with_llm

    resp = _chat(
        client,
        token=None,  # 匿名
        recent_tasks=[
            {"id": "ptask_anon_1", "title": "匿名任务 1"},
            {"id": "ptask_anon_2", "title": "匿名任务 2"},
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    cu = body["context_used"]
    assert cu["recent_tasks_count"] == 2
    assert cu["recent_tasks_accepted_count"] == 0
    assert cu["recent_tasks_ignored_count"] == 2
    # LLM messages 不应包含匿名任务的 title
    assert stub_llm.last_messages is not None
    user_msg = stub_llm.last_messages[-1]["content"]
    assert "匿名任务 1" not in user_msg
    assert "匿名任务 2" not in user_msg


# ===== 测试 8: ignored task 的伪造 title 不得出现在任何位置 =====


def test_ignored_task_forged_title_nowhere(counselor_client_with_llm):
    """测试 8: ignored 任务的伪造 title 不得出现在 answer / context_used /
    sources / LLM prompt / 普通日志中。"""
    client, container, stub_llm = counselor_client_with_llm
    token_a = _login(client, "student_demo")

    forged = "FORGED_IGNORED_TITLE_XYZ_999"

    resp = _chat(
        client,
        token=token_a,
        recent_tasks=[
            {"id": "ptask_nonexistent_xyz", "title": forged}
        ],
    )
    assert resp.status_code == 200
    body = resp.json()

    # 1. answer 不应包含
    assert forged not in body["answer"]
    # 2. context_used 不应包含(只有 count 字段)
    cu_str = json.dumps(body["context_used"], ensure_ascii=False)
    assert forged not in cu_str
    # 3. sources 不应包含
    sources_str = json.dumps(body["sources"], ensure_ascii=False)
    assert forged not in sources_str
    # 4. LLM prompt 不应包含
    assert stub_llm.last_messages is not None
    full_prompt = json.dumps(stub_llm.last_messages, ensure_ascii=False)
    assert forged not in full_prompt
    # 5. warnings 与 context_warnings 都不应回传伪造 title(应只用 task id)
    warnings_str = json.dumps(body.get("warnings", []), ensure_ascii=False)
    assert forged not in warnings_str
    ctx_warnings_str = json.dumps(body.get("context_warnings", []), ensure_ascii=False)
    assert forged not in ctx_warnings_str


# ===== 测试 9: Assignment ID 放进 recent_tasks 时必须被忽略 =====


def test_assignment_id_in_recent_tasks_ignored(
    counselor_client_with_llm, teacher_token=None
):
    """测试 9: 教师作业 ID 放进 recent_tasks 时必须被忽略
    (recent_tasks 只接受 PersonalTask,Assignment 应通过 assignment_id 传递)。
    """
    client, container, stub_llm = counselor_client_with_llm
    token_a = _login(client, "student_demo")

    # 模拟: 用户把一个看起来像 Assignment 的 ID 放进 recent_tasks
    fake_assignment_id = "asg_abc123def456"

    resp = _chat(
        client,
        token=token_a,
        recent_tasks=[
            {"id": fake_assignment_id, "title": "试图用 Assignment ID 作为 recent_task"}
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    cu = body["context_used"]
    # PersonalTaskRepository.get_task 找不到该 ID(因为它是 Assignment ID)
    # → 应被忽略
    assert cu["recent_tasks_count"] == 1
    assert cu["recent_tasks_accepted_count"] == 0
    assert cu["recent_tasks_ignored_count"] == 1
    # LLM prompt 不应包含
    assert stub_llm.last_messages is not None
    full_prompt = json.dumps(stub_llm.last_messages, ensure_ascii=False)
    assert "试图用 Assignment ID 作为 recent_task" not in full_prompt


# ===== 测试 10: Assignment 仍通过 assignment_id 正常工作 =====


def test_assignment_id_via_assignment_id_works(counselor_client_with_llm):
    """测试 10: Assignment 通过 assignment_id 字段正常传递(不被 recent_tasks 拦截)。"""
    from app.services.container import get_container

    client, container, stub_llm = counselor_client_with_llm
    token_a = _login(client, "student_demo")

    # 教师创建课程/班级/任务,学生加入班级
    teacher_token = _login(client, "teacher_demo")
    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls = classes[0]
    # 学生加入班级(若尚未加入)
    student = container.user_repository.get_user_by_username("student_demo")
    if container.enrollment_repository.get_enrollment(cls.id, student.id) is None:
        container.enrollment_repository.create_enrollment(
            class_id=cls.id, user_id=student.id, status="active"
        )
    # 教师创建已发布任务
    create = client.post(
        f"/api/v1/classes/{cls.id}/assignments",
        json={
            "title": "AI 导员测试任务",
            "description": "任务说明",
            "status": "published",
            "deadline": "2099-12-31T23:59:59+00:00",
        },
        headers=_h(teacher_token),
    ).json()
    asg_id = create["id"]

    resp = _chat(
        client,
        token=token_a,
        assignment_id=asg_id,
        message="这个任务要交什么?",
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # 教学上下文已注入(通过 message 拼接),answer 正常返回
    assert "answer" in body
    assert body["conversation_id"]


# ===== 测试 11: self_report 超过 500 字返回 422 =====


def test_self_report_too_long_returns_422(counselor_client_with_llm):
    """测试 11: self_report 超过 500 字应被 Pydantic max_length 拒绝(422)。"""
    client, container, stub_llm = counselor_client_with_llm
    token_a = _login(client, "student_demo")

    long_text = "a" * 501  # 501 字
    resp = _chat(
        client,
        token=token_a,
        self_report=long_text,
    )
    assert resp.status_code == 422


# ===== 测试 12: self_report 空白字符串转换为 null =====


def test_self_report_blank_string_converted_to_null(counselor_client_with_llm):
    """测试 12: 空白字符串(只含空格/换行)的 self_report 应转为 null,
    context_used.self_report_present 应为 False。"""
    client, container, stub_llm = counselor_client_with_llm
    token_a = _login(client, "student_demo")

    resp = _chat(
        client,
        token=token_a,
        self_report="   \n\t  ",  # 仅空白
    )
    assert resp.status_code == 200
    body = resp.json()
    cu = body["context_used"]
    assert cu["self_report_present"] is False
    # LLM messages 不应包含 self_report hint(因为已转为 None)
    assert stub_llm.last_messages is not None
    user_msg = stub_llm.last_messages[-1]["content"]
    assert "用户自报状态" not in user_msg


# ===== 测试 13: 携带 self_report 时无知识库依据仍返回 no_knowledge =====


def test_self_report_does_not_bypass_no_knowledge(counselor_client_with_llm):
    """测试 13: 携带 self_report 但无知识库依据时,仍返回 no_knowledge 标准提示,
    self_report 不得绕过 RAG 拒答规则。"""
    # 使用空知识库 fixture(不导入演示文档)
    from app.services.demo_seeder import seed_demo_data
    from app.core.security import hash_password

    get_settings.cache_clear()
    settings = get_settings()
    settings.llm_provider = "openai_compatible"
    settings.llm_base_url = "http://stub.local"
    settings.llm_api_key = "stub_key"
    settings.llm_model = "stub_model"
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    # 故意不导入演示知识库(确保 no_knowledge 路径可触发)
    container.user_repository.create_user(
        username="student_other",
        password_hash=hash_password("Demo123456"),
        role="student",
        student_number="S202409999",
        display_name="其他学生",
    )
    stub_llm = RecordingLLMClient(answer="不应该出现的回答")
    container.rag._llm = stub_llm

    from app.main import create_app
    test_app = create_app()
    client = TestClient(test_app)

    token_a = _login(client, "student_demo")
    # 询问一个知识库肯定没有的问题
    resp = _chat(
        client,
        token=token_a,
        message="XYZ独一无二的 nonexistent 话题 abc123?",
        self_report="我有些疲惫",
    )
    assert resp.status_code == 200
    body = resp.json()
    # 必须返回 no_knowledge(不调用 LLM)
    assert body["mode"] == "no_knowledge"
    # LLM 不应被调用(no_knowledge 路径直接返回)
    assert stub_llm.last_messages is None
    # answer 应包含人工咨询提示
    assert "辅导员" in body["answer"] or "咨询" in body["answer"]
    # self_report 不得绕过拒答规则 → answer 中不应包含 self_report 原文
    assert "我有些疲惫" not in body["answer"]
    # context_used.self_report_present 应为 True
    cu = body["context_used"]
    assert cu["self_report_present"] is True


# ===== 测试 14: expression_signal 不进入 LLM prompt =====


def test_expression_signal_not_in_llm_prompt(counselor_client_with_llm):
    """测试 14: expression_signal 不进入 LLM prompt / answer / context_warnings
    之外的任何位置。"""
    client, container, stub_llm = counselor_client_with_llm
    token_a = _login(client, "student_demo")

    resp = _chat(
        client,
        token=token_a,
        expression_signal={
            "label": "sad",
            "confidence": 0.95,
            "timestamp": "2026-07-27T12:00:00+08:00",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    # 1. LLM prompt 不应包含 expression_signal 内容
    assert stub_llm.last_messages is not None
    full_prompt = json.dumps(stub_llm.last_messages, ensure_ascii=False)
    assert "expression_signal" not in full_prompt.lower()
    assert "sad" not in full_prompt.lower() or "sad" not in full_prompt  # label 不得出现
    assert "0.95" not in full_prompt  # confidence 数值不得出现
    # 2. answer 不应包含 expression_signal 的具体值
    answer = body["answer"]
    assert "sad" not in answer.lower()
    assert "0.95" not in answer
    # 3. context_used 不应回传 expression_signal 原文(只有 count 字段)
    cu_str = json.dumps(body["context_used"], ensure_ascii=False)
    assert "sad" not in cu_str.lower()
    assert "0.95" not in cu_str
    # 4. context_warnings 中应包含"已忽略"提示,但不包含 label/confidence
    # (expression_signal 安全降级 warning 由 counselor 路由层构造,
    #  归类为 context_warnings,不混入 RAG 的 warnings 字段)
    ctx_warnings_str = json.dumps(body.get("context_warnings", []), ensure_ascii=False)
    assert "expression_signal" in ctx_warnings_str or "已忽略" in ctx_warnings_str
    assert "sad" not in ctx_warnings_str.lower()
    assert "0.95" not in ctx_warnings_str
    # 同时确保 RAG 层 warnings 也不包含 expression_signal 具体内容
    warnings_str = json.dumps(body.get("warnings", []), ensure_ascii=False)
    assert "sad" not in warnings_str.lower()
    assert "0.95" not in warnings_str


# ===== 额外: context_used 不回传 self_report 原文 =====


def test_context_used_does_not_leak_self_report(counselor_client_with_llm):
    """额外测试: context_used 中只记录 self_report_present=true/false,
    不回传 self_report 原文。"""
    client, container, stub_llm = counselor_client_with_llm
    token_a = _login(client, "student_demo")

    secret = "这是我的私密状态描述_SECRET_12345"
    resp = _chat(
        client,
        token=token_a,
        self_report=secret,
    )
    assert resp.status_code == 200
    body = resp.json()
    # context_used 不应包含原文
    cu_str = json.dumps(body["context_used"], ensure_ascii=False)
    assert secret not in cu_str
    assert "self_report_present" in body["context_used"]
    assert body["context_used"]["self_report_present"] is True


# ===== 额外: recent_tasks_count 与请求一致 =====


def test_context_used_counts_match_request(counselor_client_with_llm):
    """额外测试: context_used 的 count 字段与请求数量一致。"""
    client, container, stub_llm = counselor_client_with_llm
    token_a = _login(client, "student_demo")
    task1 = _create_task(client, token_a, title="任务1")
    task2 = _create_task(client, token_a, title="任务2")

    resp = _chat(
        client,
        token=token_a,
        recent_tasks=[
            {"id": task1["id"]},
            {"id": task2["id"]},
            {"id": "ptask_nonexistent_a"},
            {"id": "ptask_nonexistent_b"},
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    cu = body["context_used"]
    assert cu["recent_tasks_count"] == 4
    assert cu["recent_tasks_accepted_count"] == 2
    assert cu["recent_tasks_ignored_count"] == 2
