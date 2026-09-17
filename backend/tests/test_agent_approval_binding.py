"""P1-2：审批必须绑定到"具体工具 + 具体参数 + 具体 Run/工具调用"。

修复前的真实漏洞：`ToolInvocationGateway` 复核审批时只看
`approval.user_id == 当前用户` 与 `approval.status == APPROVED`，既不看工具名也不看
参数指纹；而 Web 在批准后**又创建一个新 Job 并携带旧 approval_id**。于是一次批准
可以被复用到另一门课程、另一种 mode 或另一组参数上。

本文件同时覆盖两层：
- HTTP 层：客户端伪造 `input_ref.approval_id` 必须完全无效；
- Gateway 层：直接构造不匹配的审批去调用工具必须被拒绝。

全部上游流量由 `httpx.MockTransport` 模拟。
"""
from __future__ import annotations

import asyncio
from typing import List

import httpx
import pytest

from app.core.exceptions import AgentToolRejected
from app.schemas.agent_contract_enums import RiskLevel
from app.services.agent_runtime.handlers.final_review import PLAN_ACTIVATE_TOOL
from app.services.agent_runtime.handlers.interactive_classroom import GENERATE_TOOL
from app.services.agent_runtime.tool_gateway import ToolInvocationRequest, build_request_hash
from final_review_helpers import drain_worker
from test_openmaic_student_integration import (
    _bootstrap,
    _first_course,
    _recording_handler,
)


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


def _create_job(tc, headers, course_id, **overrides):
    payload = {"course_id": course_id, "mode": "quiz", **overrides}
    return tc.post(
        "/api/v1/agent-jobs",
        headers=headers,
        json={"job_kind": "interactive_classroom", "input_ref": payload},
    )


def _pending_approvals(container, job_id):
    repo = container.agent_runtime_repository
    run = repo.get_run_by_job(job_id)
    return [
        item
        for item in repo.list_approvals_by_run(run["run_id"])
        if item.get("status") == "PENDING"
    ]


def _approve(container, tc, headers, approval_id):
    resp = tc.post(
        f"/api/v1/agent-approvals/{approval_id}/decision",
        headers=headers,
        json={"decision": "APPROVED"},
    )
    assert resp.status_code == 200, resp.text
    return resp


def _run_status(container, job_id):
    return container.agent_runtime_repository.get_run_by_job(job_id)["status"]


# ===== A. 批准后续跑原 Run，且不产生第二个 Job =====


def test_approval_resumes_original_run_without_creating_a_second_job(tmp_path):
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    job_id = _create_job(tc, headers, cid).json()["job_id"]
    drain_worker(container)
    assert _submits(recorder) == [], "审批前不得触达上游"
    assert _run_status(container, job_id) == "AWAITING_APPROVAL"

    approval_id = _pending_approvals(container, job_id)[-1]["approval_id"]
    _approve(container, tc, headers, approval_id)
    drain_worker(container)

    # 只提交一次，且落在**原来那个 job/run** 上
    assert len(_submits(recorder)) == 1
    assert _run_status(container, job_id) == "SUCCEEDED"

    repo = container.agent_runtime_repository
    jobs = [j for j in repo.list_jobs(repo.get_job(job_id)["user_id"])]
    assert len(jobs) == 1, f"批准不应产生第二个 Job，实际 {len(jobs)} 个"


def test_duplicate_approve_and_drain_submits_once(tmp_path):
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    job_id = _create_job(tc, headers, cid).json()["job_id"]
    drain_worker(container)
    approval_id = _pending_approvals(container, job_id)[-1]["approval_id"]

    _approve(container, tc, headers, approval_id)
    drain_worker(container)
    drain_worker(container)
    # 重复点击"批准"会被 ApprovalGate 以 409 拒绝（已处理），这里断言不产生副作用
    again = tc.post(
        f"/api/v1/agent-approvals/{approval_id}/decision",
        headers=headers,
        json={"decision": "APPROVED"},
    )
    assert again.status_code in (409, 200)
    drain_worker(container)
    assert len(_submits(recorder)) == 1, "重复确认不得重复提交"


# ===== B. 客户端伪造 approval_id 必须无效 =====


def test_client_supplied_approval_id_is_ignored(tmp_path):
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    first = _create_job(tc, headers, cid, mode="quiz").json()["job_id"]
    drain_worker(container)
    approval_id = _pending_approvals(container, first)[-1]["approval_id"]

    # 另一门形态 + 伪造带上第一张审批
    forged = _create_job(
        tc, headers, cid, mode="review", approval_id=approval_id
    )
    assert forged.status_code in (200, 202), forged.text
    forged_job = forged.json()["job_id"]
    drain_worker(container)

    assert _submits(recorder) == [], "伪造审批不得触达上游"
    assert _run_status(container, forged_job) == "AWAITING_APPROVAL", (
        "伪造 approval_id 必须被忽略，该请求应重新等待自己的审批"
    )


# ===== C. Gateway 层：审批绑定工具 + 参数 + Run =====


def _invoke_gateway(container, *, run_id, tool_name, arguments, approval_id, user_id):
    return asyncio.run(
        container.agent_tool_gateway.invoke(
            ToolInvocationRequest(
                run_id=run_id,
                role_code="tutor",
                tool_name=tool_name,
                arguments=arguments,
                idempotency_key=f"test:{run_id}",
                approval_id=approval_id,
            )
        )
    )


def _generate_args(cid: str, user_id: str, mode: str = "quiz"):
    return {
        "course_id": cid,
        "user_id": user_id,
        "mode": mode,
        "learning_objective": None,
        "current_difficulty": None,
        "desired_duration_minutes": None,
        "difficulty_level": None,
        "wants_more_practice": False,
        "selected_material_ids": [],
    }


def test_gateway_rejects_approval_for_different_arguments(tmp_path):
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    user_id = container.user_repository.get_user_by_username("student_demo").id
    job_id = _create_job(tc, headers, cid, mode="quiz").json()["job_id"]
    drain_worker(container)
    run = container.agent_runtime_repository.get_run_by_job(job_id)
    approval_id = _pending_approvals(container, job_id)[-1]["approval_id"]

    # 用同一张（仍是 PENDING 的）审批，但参数换成 review → 必须被拒
    with pytest.raises((AgentToolRejected, Exception)) as excinfo:
        _invoke_gateway(
            container,
            run_id=run["run_id"],
            tool_name=GENERATE_TOOL,
            arguments=_generate_args(cid, user_id, mode="review"),
            approval_id=approval_id,
            user_id=user_id,
        )
    assert "参数" in str(excinfo.value) or "审批" in str(excinfo.value)
    assert _submits(recorder) == []


def test_gateway_rejects_approval_for_other_tool(tmp_path):
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    user_id = container.user_repository.get_user_by_username("student_demo").id
    job_id = _create_job(tc, headers, cid).json()["job_id"]
    drain_worker(container)
    run = container.agent_runtime_repository.get_run_by_job(job_id)
    approval_id = _pending_approvals(container, job_id)[-1]["approval_id"]

    # 互动课堂的审批不能授权期末复习工具
    with pytest.raises(Exception) as excinfo:
        _invoke_gateway(
            container,
            run_id=run["run_id"],
            tool_name=PLAN_ACTIVATE_TOOL,
            arguments={"campaign_id": "c1", "version": 1, "user_id": user_id},
            approval_id=approval_id,
            user_id=user_id,
        )
    assert "审批" in str(excinfo.value) or "工具" in str(excinfo.value)
    assert _submits(recorder) == []


def test_gateway_rejects_approval_from_another_run(tmp_path):
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    user_id = container.user_repository.get_user_by_username("student_demo").id
    first = _create_job(tc, headers, cid, mode="quiz").json()["job_id"]
    drain_worker(container)
    approval_id = _pending_approvals(container, first)[-1]["approval_id"]
    # 先批准并让它正常执行完，得到一张"已批准且已被用过"的审批
    _approve(container, tc, headers, approval_id)
    drain_worker(container)
    baseline = len(_submits(recorder))
    assert baseline == 1, "第一次生成应当恰好提交一次"

    second = _create_job(tc, headers, cid, mode="review").json()["job_id"]
    drain_worker(container)
    run2 = container.agent_runtime_repository.get_run_by_job(second)

    with pytest.raises(Exception) as excinfo:
        _invoke_gateway(
            container,
            run_id=run2["run_id"],
            tool_name=GENERATE_TOOL,
            arguments=_generate_args(cid, user_id, mode="review"),
            approval_id=approval_id,
            user_id=user_id,
        )
    assert "审批" in str(excinfo.value)
    assert len(_submits(recorder)) == baseline, "跨 Run 复用已批准的审批不得触达上游"


def test_gateway_rejects_approval_of_another_user(tmp_path):
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    job_id = _create_job(tc, headers, cid).json()["job_id"]
    drain_worker(container)
    run = container.agent_runtime_repository.get_run_by_job(job_id)
    approval_id = _pending_approvals(container, job_id)[-1]["approval_id"]

    with pytest.raises(Exception):
        _invoke_gateway(
            container,
            run_id=run["run_id"],
            tool_name=GENERATE_TOOL,
            arguments=_generate_args(cid, "someone_else"),
            approval_id=approval_id,
            user_id="someone_else",
        )
    assert _submits(recorder) == []


def test_approval_binding_columns_are_populated(tmp_path):
    """审批记录必须真的带上工具名与参数指纹，否则绑定校验形同虚设。"""
    container, tc, headers, _ = _setup(tmp_path)
    cid = _first_course(tc, headers)
    user_id = container.user_repository.get_user_by_username("student_demo").id
    job_id = _create_job(tc, headers, cid).json()["job_id"]
    drain_worker(container)
    approval = container.agent_runtime_repository.get_approval(
        _pending_approvals(container, job_id)[-1]["approval_id"]
    )
    assert approval.tool_name == GENERATE_TOOL
    assert approval.call_id, "Gateway 创建的审批必须绑定到具体工具调用"
    assert approval.request_hash == build_request_hash(
        GENERATE_TOOL, _generate_args(cid, user_id, mode="quiz")
    )


# ===== D. 拒绝 / 过期绝不执行 =====


def test_rejected_approval_never_executes(tmp_path):
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    job_id = _create_job(tc, headers, cid).json()["job_id"]
    drain_worker(container)
    approval_id = _pending_approvals(container, job_id)[-1]["approval_id"]

    resp = tc.post(
        f"/api/v1/agent-approvals/{approval_id}/decision",
        headers=headers,
        json={"decision": "REJECTED", "reason": "不想要这个"},
    )
    assert resp.status_code == 200
    drain_worker(container)
    drain_worker(container)
    assert _submits(recorder) == [], "拒绝后绝不得触达上游"
    assert _run_status(container, job_id) in {"CANCELLED", "FAILED"}


def test_expired_approval_never_executes(tmp_path):
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    job_id = _create_job(tc, headers, cid).json()["job_id"]
    drain_worker(container)
    approval_id = _pending_approvals(container, job_id)[-1]["approval_id"]

    # 手工把审批置为 EXPIRED（模拟超时）
    container.agent_runtime_repository.resolve_approval(
        approval_id, status="EXPIRED"
    )
    # 让原 Run 重新可领取，验证"过期绝不等于批准"
    run = container.agent_runtime_repository.get_run_by_job(job_id)
    container.agent_run_manager.transition(run["run_id"], "QUEUED", phase="QUEUED")
    drain_worker(container)
    drain_worker(container)
    assert _submits(recorder) == [], "过期审批绝不得触达上游"
    assert _run_status(container, job_id) == "FAILED"


# ===== E. 审批前 / 崩溃恢复的恰好一次 =====


def test_no_upstream_submit_before_approval(tmp_path):
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    _create_job(tc, headers, cid).json()["job_id"]
    drain_worker(container)
    drain_worker(container)
    assert _submits(recorder) == []


def test_crash_recovery_after_approval_submits_once(tmp_path):
    """批准后即使 Worker 重排多次，也只能向上游提交一次。"""
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    job_id = _create_job(tc, headers, cid).json()["job_id"]
    drain_worker(container)
    approval_id = _pending_approvals(container, job_id)[-1]["approval_id"]
    _approve(container, tc, headers, approval_id)

    # 连续多轮：模拟 Worker 重试 / 重复领取
    for _ in range(4):
        drain_worker(container)
    assert len(_submits(recorder)) == 1
    assert _run_status(container, job_id) == "SUCCEEDED"


# ===== F. 其他工具不能被互动课堂审批授权（反向） =====


def test_other_tool_approval_cannot_authorize_interactive_classroom(tmp_path):
    container, tc, headers, recorder = _setup(tmp_path)
    cid = _first_course(tc, headers)
    user_id = container.user_repository.get_user_by_username("student_demo").id
    job_id = _create_job(tc, headers, cid).json()["job_id"]
    drain_worker(container)
    run = container.agent_runtime_repository.get_run_by_job(job_id)

    # 手工造一张绑定到"别的工具"的审批
    other_approval = container.agent_approval_gate.require(
        run_id=run["run_id"],
        user_id=user_id,
        risk_level=RiskLevel.CONFIRM_REQUIRED,
        action_summary="别的工具",
        tool_name=PLAN_ACTIVATE_TOOL,
        request_hash="deadbeef",
    )
    with pytest.raises(Exception):
        _invoke_gateway(
            container,
            run_id=run["run_id"],
            tool_name=GENERATE_TOOL,
            arguments=_generate_args(cid, user_id),
            approval_id=other_approval,
            user_id=user_id,
        )
    assert _submits(recorder) == []
