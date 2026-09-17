"""阶段 5 —— CPM 经受管 Agent Runtime 触发互动课堂生成。

覆盖：
- 能力/Handler/工具确实注册，且 generate 是 CONFIRM_REQUIRED + 需要审批；
- 只读工具是 AUTO_SAFE；
- CPM 只**提出**建议，不创建任何 OpenMAIC 任务；
- 建议必须经过课程权限校验；
- 创建 agent job 后处于 AWAITING_APPROVAL，审批前绝不调用上游；
- 审批 + Worker 排空后恰好提交一次，并返回 CampusMate 内部深链；
- 不同输入各自需要审批（"确认后参数变化必须重新确认"）；
- 同幂等键 + 同请求重放；同幂等键 + 不同请求 409；
- 工具结果不含凭据、不含 OpenMAIC 内部地址。

上游 OpenMAIC 全部由 `httpx.MockTransport` 模拟；本文件不声称做过真实联调。
"""
from __future__ import annotations

from typing import List

import httpx
import pytest

from app.services.agent_runtime.handlers.interactive_classroom import (
    GENERATE_TOOL,
    INSPECT_TOOL,
    LIST_TOOL,
    OPEN_TOOL,
    PROPOSE_TOOL,
    STATUS_TOOL,
    classroom_deep_link,
)
from test_openmaic_student_integration import (
    BASE,
    _bootstrap,
    _first_course,
    _recording_handler,
)
from final_review_helpers import drain_worker


def _setup(tmp_path, **overrides):
    recorder: List[httpx.Request] = []
    container, tc, headers, _ = _bootstrap(
        tmp_path, _recording_handler(recorder), **overrides
    )
    return container, tc, headers, recorder


def _submits(recorder) -> List[httpx.Request]:
    return [
        r
        for r in recorder
        if r.method == "POST" and r.url.path.endswith("/api/generate-classroom")
    ]


def _user_id(container, username="student_demo") -> str:
    return container.user_repository.get_user_by_username(username).id


# ===== A. 注册与风险等级 =====


def test_capability_handler_and_tools_are_registered(tmp_path):
    container, _, _, _ = _setup(tmp_path)
    assert "interactive_classroom" in container.agent_handler_registry.job_kinds()
    assert container.agent_handler_registry.is_enabled("interactive_classroom")
    codes = {spec.tool_code for spec in container.agent_tool_registry.list_tools()}
    for tool in (INSPECT_TOOL, LIST_TOOL, PROPOSE_TOOL, GENERATE_TOOL, STATUS_TOOL, OPEN_TOOL):
        assert tool in codes, f"缺少工具注册: {tool}"
    caps = {item.get("name") or item.get("code") for item in container.agent_capability_registry.describe()}
    assert "interactive_classroom.generate" in caps


def test_generate_tool_is_confirm_required_and_needs_approval(tmp_path):
    container, _, _, _ = _setup(tmp_path)
    spec = container.agent_tool_registry.get(GENERATE_TOOL)
    assert spec is not None
    assert spec.requires_approval is True
    assert str(spec.risk_level).endswith("CONFIRM_REQUIRED")
    assert spec.executor is not None, "必须绑定真实执行器，不能只是声明"


def test_readonly_tools_are_auto_safe(tmp_path):
    container, _, _, _ = _setup(tmp_path)
    for tool in (INSPECT_TOOL, LIST_TOOL, PROPOSE_TOOL, STATUS_TOOL, OPEN_TOOL):
        spec = container.agent_tool_registry.get(tool)
        assert spec.requires_approval is False, f"{tool} 不应需要审批"
        assert str(spec.risk_level).endswith("AUTO_SAFE"), f"{tool} 应为只读安全"


def test_handler_only_declares_the_generate_tool(tmp_path):
    container, _, _, _ = _setup(tmp_path)
    handler = container.agent_handler_registry.get("interactive_classroom")
    assert tuple(handler.tools) == (GENERATE_TOOL,)


# ===== B. CPM 只提建议，不创建任务 =====


def test_cpm_proposal_is_read_only(tmp_path):
    _, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    resp = tc.post(
        "/api/v1/counselor/chat",
        headers=headers,
        json={"message": "帮我复习一下这门课", "stream": False, "course_id": cid},
    )
    assert resp.status_code == 200, resp.text
    actions = resp.json()["suggested_actions"]
    proposals = [a for a in actions if a["type"] == "interactiveClassroomProposal"]
    assert proposals, f"应提出互动课堂建议，实际: {actions}"
    data = proposals[0]["data"]
    assert data["course_id"] == cid
    assert data["mode"] == "review"
    assert data["job_kind"] == "interactive_classroom"
    assert data["requires_confirmation"] is True
    assert "生成意图" in data["intent_note"]
    # 关键：只提建议，不得创建任何上游任务
    assert _submits(recorder) == [], "CPM 建议不得创建 OpenMAIC 任务"


def test_cpm_proposal_carries_a_unique_nonce(tmp_path):
    """每个提案必须有唯一 `proposal_id`。

    `SuggestedAction.id` 是常量（同类提案共用），客户端无法据此区分"同一门课的
    第二个提案"，于是会复用第一个提案的 job / 幂等键 / 深链。nonce 由服务端下发。
    """
    _, tc, headers, _ = _setup(tmp_path)
    cid = _first_course(tc, headers)

    def propose(message: str) -> dict:
        resp = tc.post(
            "/api/v1/counselor/chat",
            headers=headers,
            json={"message": message, "stream": False, "course_id": cid},
        )
        assert resp.status_code == 200, resp.text
        proposals = [
            a
            for a in resp.json()["suggested_actions"]
            if a["type"] == "interactiveClassroomProposal"
        ]
        assert proposals, "应提出互动课堂建议"
        return proposals[0]["data"]

    first = propose("帮我复习一下这门课")
    assert first.get("proposal_id"), "提案必须携带 proposal_id"
    assert first["proposal_id"].startswith("icp_")
    # 同样的提问、同样的课程与模式，第二次仍必须是**另一个**提案
    second = propose("帮我复习一下这门课")
    assert second["proposal_id"] != first["proposal_id"], (
        "两次提案必须可区分，否则客户端会把第二个提案误当成第一个"
    )
    assert second["course_id"] == first["course_id"]
    assert second["mode"] == first["mode"]


def test_cpm_proposal_nonce_is_not_a_credential_or_internal_url(tmp_path):
    _, tc, headers, _ = _setup(tmp_path)
    cid = _first_course(tc, headers)
    resp = tc.post(
        "/api/v1/counselor/chat",
        headers=headers,
        json={"message": "帮我复习一下这门课", "stream": False, "course_id": cid},
    )
    blob = resp.text
    assert BASE not in blob
    assert "openmaic:3000" not in blob
    for token in ("access_code", "Cookie", "Authorization"):
        assert token not in blob


def test_cpm_proposal_infers_intent_from_message(tmp_path):
    _, tc, headers, _ = _setup(tmp_path)
    cid = _first_course(tc, headers)
    cases = {
        "给我做一个交互实验": "simulation",
        "帮我画个思维导图": "mindmap",
        "我想练编程": "coding",
        "给我出几道自测题": "quiz",
        "讲讲这个知识点": "explain",
        "随便看看": "adaptive",
    }
    for message, expected in cases.items():
        resp = tc.post(
            "/api/v1/counselor/chat",
            headers=headers,
            json={"message": message, "stream": False, "course_id": cid},
        ).json()
        proposals = [
            a for a in resp["suggested_actions"] if a["type"] == "interactiveClassroomProposal"
        ]
        assert proposals and proposals[0]["data"]["mode"] == expected, message


def test_cpm_proposal_requires_course_permission(tmp_path):
    _, tc, headers, _ = _setup(tmp_path)
    resp = tc.post(
        "/api/v1/counselor/chat",
        headers=headers,
        json={"message": "帮我复习", "stream": False, "course_id": "course_not_mine"},
    )
    assert resp.status_code == 200
    assert [
        a for a in resp.json()["suggested_actions"] if a["type"] == "interactiveClassroomProposal"
    ] == []


def test_cpm_without_course_id_proposes_nothing(tmp_path):
    _, tc, headers, _ = _setup(tmp_path)
    resp = tc.post(
        "/api/v1/counselor/chat",
        headers=headers,
        json={"message": "帮我复习", "stream": False},
    )
    assert resp.status_code == 200
    assert [
        a for a in resp.json()["suggested_actions"] if a["type"] == "interactiveClassroomProposal"
    ] == []


def test_cpm_proposal_still_offered_when_service_unavailable(tmp_path):
    """服务不可用时仍给建议，但明确标注 available=false，由 UI 决定怎么提示。"""
    _, tc, headers, _ = _setup(
        tmp_path, openmaic_enabled=False, openmaic_embed_origin=""
    )
    cid = _first_course(tc, headers)
    resp = tc.post(
        "/api/v1/counselor/chat",
        headers=headers,
        json={"message": "帮我复习", "stream": False, "course_id": cid},
    ).json()
    proposals = [
        a for a in resp["suggested_actions"] if a["type"] == "interactiveClassroomProposal"
    ]
    assert proposals
    assert proposals[0]["data"]["available"] is False


# ===== C. 受管生成：审批门 =====


def _create_job(tc, headers, course_id, **overrides):
    payload = {"course_id": course_id, "mode": "quiz", **overrides}
    return tc.post(
        "/api/v1/agent-jobs",
        headers=headers,
        json={"job_kind": "interactive_classroom", "input_ref": payload},
    )


def _approve_and_resume(container, tc, headers, job_id, *, expect_approval=True):
    """批准待处理审批单；路由会把**原 Run** 重新排队，Worker 继续执行。

    不再创建"携带 approval_id 的第二个 Job"—— 那正是"一次批准被复用到别的
    课程/参数"的漏洞入口。审批 id 由服务端 checkpoint 与工具调用记录持有。
    """
    repo = container.agent_runtime_repository
    run = repo.get_run_by_job(job_id)
    approvals = [
        item
        for item in repo.list_approvals_by_run(run["run_id"])
        if item.get("status") == "PENDING"
    ]
    if expect_approval:
        assert approvals, "应当产生审批单"
    if not approvals:
        return job_id
    approval_id = approvals[-1]["approval_id"]
    resp = tc.post(
        f"/api/v1/agent-approvals/{approval_id}/decision",
        headers=headers,
        json={"decision": "APPROVED"},
    )
    assert resp.status_code == 200, resp.text
    drain_worker(container)
    return job_id


def test_agent_job_awaits_approval_and_does_not_touch_upstream(tmp_path):
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    resp = _create_job(tc, headers, cid)
    assert resp.status_code in (200, 202), resp.text
    job_id = resp.json()["job_id"]

    drain_worker(container)
    assert _submits(recorder) == [], "审批前绝不能调用上游生成"

    run = container.agent_runtime_repository.get_run_by_job(job_id)
    assert run["status"] == "AWAITING_APPROVAL"


def test_approval_then_worker_generates_exactly_once(tmp_path):
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    job_id = _create_job(tc, headers, cid).json()["job_id"]

    drain_worker(container)
    resumed_job_id = _approve_and_resume(container, tc, headers, job_id)

    submits = _submits(recorder)
    assert len(submits) == 1, f"审批后应恰好提交一次，实际 {len(submits)} 次"

    repo = container.agent_runtime_repository
    assert repo.get_run_by_job(resumed_job_id)["status"] == "SUCCEEDED"
    # 再排一次不应产生第二次副作用（幂等声明 + checkpoint 双重保护）
    drain_worker(container)
    assert len(_submits(recorder)) == 1


def test_job_output_exposes_internal_deep_link_only(tmp_path):
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    job_id = _create_job(tc, headers, cid).json()["job_id"]
    drain_worker(container)
    resumed_job_id = _approve_and_resume(container, tc, headers, job_id)

    job = container.agent_runtime_repository.get_job(resumed_job_id)
    raw = job.get("output") or job.get("input_ref") or job.get("input_ref_json") or {}
    if isinstance(raw, str):
        import json as _json

        raw = _json.loads(raw)
    output = raw if isinstance(raw, dict) else {}
    assert output.get("session_id"), f"应返回 session_id，实际 {output}"
    assert output.get("deep_link") == classroom_deep_link(cid, output["session_id"])
    assert output["deep_link"].startswith("/courses/")
    blob = str(output)
    # 绝不返回 OpenMAIC 内部地址或凭据
    assert BASE not in blob
    assert "access_code" not in blob
    assert "openmaic_access" not in blob


def test_different_arguments_need_their_own_approval(tmp_path):
    """确认绑定具体请求内容：换一门课/换一个形态必须重新走审批。"""
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)

    first = _create_job(tc, headers, cid, mode="quiz").json()["job_id"]
    drain_worker(container)
    _approve_and_resume(container, tc, headers, first)
    assert len(_submits(recorder)) == 1

    second = _create_job(tc, headers, cid, mode="review").json()["job_id"]
    assert second != first
    drain_worker(container)
    assert len(_submits(recorder)) == 1, "新参数在获得审批前不得执行"
    run2 = container.agent_runtime_repository.get_run_by_job(second)
    assert run2["status"] == "AWAITING_APPROVAL", "换了参数必须重新审批"

    # 批准第二个参数后才允许执行。注意：同一 (user, course) 的首个课堂仍在
    # 进行中时，后端会**复用**该任务（既有的同课程幂等语义），因此这里断言
    # "执行成功"，而不是"又提交了一次"。
    resumed2 = _approve_and_resume(container, tc, headers, second)
    assert (
        container.agent_runtime_repository.get_run_by_job(resumed2)["status"]
        == "SUCCEEDED"
    )
    assert len(_submits(recorder)) == 1, "同课程在途任务必须被复用，不重复提交"


def test_same_idempotency_key_same_request_replays(tmp_path):
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    body = {"job_kind": "interactive_classroom", "input_ref": {"course_id": cid, "mode": "quiz"}}
    first = tc.post(
        "/api/v1/agent-jobs", headers={**headers, "Idempotency-Key": "k1"}, json=body
    )
    second = tc.post(
        "/api/v1/agent-jobs", headers={**headers, "Idempotency-Key": "k1"}, json=body
    )
    assert first.json()["job_id"] == second.json()["job_id"]
    assert second.status_code == 200


def test_same_idempotency_key_different_request_conflicts(tmp_path):
    container, tc, headers, _ = _setup(tmp_path)
    cid = _first_course(tc, headers)
    tc.post(
        "/api/v1/agent-jobs",
        headers={**headers, "Idempotency-Key": "k2"},
        json={"job_kind": "interactive_classroom", "input_ref": {"course_id": cid, "mode": "quiz"}},
    )
    conflict = tc.post(
        "/api/v1/agent-jobs",
        headers={**headers, "Idempotency-Key": "k2"},
        json={"job_kind": "interactive_classroom", "input_ref": {"course_id": cid, "mode": "pbl"}},
    )
    assert conflict.status_code == 409


def test_unknown_job_kind_is_rejected(tmp_path):
    _, tc, headers, _ = _setup(tmp_path)
    cid = _first_course(tc, headers)
    resp = tc.post(
        "/api/v1/agent-jobs",
        headers=headers,
        json={"job_kind": "totally_unknown", "input_ref": {"course_id": cid}},
    )
    assert resp.status_code == 422


def test_job_requires_login(tmp_path):
    _, tc, headers, _ = _setup(tmp_path)
    cid = _first_course(tc, headers)
    assert tc.post(
        "/api/v1/agent-jobs",
        json={"job_kind": "interactive_classroom", "input_ref": {"course_id": cid}},
    ).status_code in (401, 403)


def test_job_rejects_foreign_course_at_execution(tmp_path):
    """课程权限在工具执行层再校验一次：越权课程不得触达上游。"""
    container, tc, headers, recorder = _setup(tmp_path)
    job_id = _create_job(tc, headers, "course_not_mine").json()["job_id"]
    drain_worker(container)
    _approve_and_resume(container, tc, headers, job_id)
    assert _submits(recorder) == []
    run = container.agent_runtime_repository.get_run_by_job(job_id)
    assert run["status"] in {"FAILED", "AWAITING_APPROVAL", "SUCCEEDED"} or run.get("error_code")
