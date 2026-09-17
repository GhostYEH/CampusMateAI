"""第一轮审查：审批决策的幂等性与并发安全。

修复前发现的两个真实缺陷：

1. `POST /agent-approvals/{id}/decision` 声明了 `Idempotency-Key` 头却**从不使用**；
   重复提交同一个批准会走到 `apv.status != PENDING` 分支并抛 409 ——
   也就是说"同一 approve 重发"既不幂等，客户端还会因此误判为失败。
2. `resolve_approval` 是**无条件 UPDATE**（`WHERE approval_id = ?`），
   `ApprovalGate.resolve` 又是"先读后写"：并发的 approve / reject 可以双双通过
   PENDING 检查，两个相反的决定都被写入 —— 典型的 lost update。
"""
from __future__ import annotations

import threading
from typing import List

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.demo_seeder import seed_demo_data
from app.services.openmaic.classroom_service import OpenMAICClassroomService
from app.services.openmaic.client import OpenMAICClient
from app.services.openmaic.result_store import OpenMAICResultStore
from final_review_helpers import drain_worker
from test_openmaic_student_integration import (
    BASE,
    _bootstrap,
    _first_course,
    _recording_handler,
    _test_settings,
)


def _setup(tmp_path, **overrides):
    recorder: List[httpx.Request] = []
    container, tc, headers, _ = _bootstrap(
        tmp_path, _recording_handler(recorder), **overrides
    )
    return container, tc, headers, recorder


def _create_job(tc, headers, course_id, **overrides):
    payload = {"course_id": course_id, "mode": "quiz", **overrides}
    return tc.post(
        "/api/v1/agent-jobs",
        headers=headers,
        json={"job_kind": "interactive_classroom", "input_ref": payload},
    )


def _pending_approval_id(container, job_id) -> str:
    repo = container.agent_runtime_repository
    run = repo.get_run_by_job(job_id)
    pending = [
        item
        for item in repo.list_approvals_by_run(run["run_id"])
        if item.get("status") == "PENDING"
    ]
    assert pending, "应当存在待审批记录"
    return pending[-1]["approval_id"]


def _awaiting_job(tmp_path, **overrides):
    """创建一个停在 AWAITING_APPROVAL 的互动课堂 Job。"""
    container, tc, headers, recorder = _setup(tmp_path, **overrides)
    cid = _first_course(tc, headers)
    job_id = _create_job(tc, headers, cid).json()["job_id"]
    drain_worker(container)
    approval_id = _pending_approval_id(container, job_id)
    return container, tc, headers, recorder, job_id, approval_id


def _awaiting_job_file_db(tmp_path, **overrides):
    """用**文件库**建同一个场景。

    并发测试必须用文件库：内存模式下 `Database._connect()` 会让所有调用方复用
    **同一条** sqlite 连接，多线程交错使用同一条连接会读到空结果
    （表现为莫名的 `AGENT_RUN_NOT_FOUND`），那是测试脚手架的缺陷，不是被测逻辑。
    文件库下每次 `_conn()` 都是独立连接，与生产一致。
    """
    import app.database.sqlite_db as sqlite_db

    from app.services.container import build_container

    settings = _test_settings(
        database_url=f"sqlite:///{(tmp_path / 'approval.db').as_posix()}",
        **overrides,
    )
    sqlite_db._db_instance = None
    container = build_container(settings)
    seed_demo_data(container, force=True)
    store = OpenMAICResultStore(tmp_path / "openmaic_classrooms")
    container.openmaic_result_store = store
    container.openmaic_classroom_service = OpenMAICClassroomService(
        settings,
        store,
        client=OpenMAICClient(
            base_url=BASE,
            timeout_seconds=5.0,
            origin=BASE,
            transport=httpx.MockTransport(_recording_handler([])),
            access_code=settings.openmaic_access_code,
        ),
    )
    tc = TestClient(create_app())
    login = tc.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    cid = _first_course(tc, headers)
    job_id = _create_job(tc, headers, cid).json()["job_id"]
    drain_worker(container)
    return container, job_id, _pending_approval_id(container, job_id)


def _decide(tc, headers, approval_id, decision, *, key=None):
    extra = {"Idempotency-Key": key} if key else {}
    return tc.post(
        f"/api/v1/agent-approvals/{approval_id}/decision",
        headers={**headers, **extra},
        json={"decision": decision},
    )


# ===== 1. 同一 approve 重发必须幂等返回同一结果 =====


def test_repeated_approve_is_idempotent(tmp_path):
    container, tc, headers, recorder, job_id, approval_id = _awaiting_job(tmp_path)

    first = _decide(tc, headers, approval_id, "APPROVED")
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "APPROVED"

    second = _decide(tc, headers, approval_id, "APPROVED")
    assert second.status_code == 200, f"重复批准必须幂等，而不是 409: {second.text}"
    assert second.json()["status"] == "APPROVED"
    assert second.json()["approval_id"] == approval_id

    drain_worker(container)
    submits = [
        r
        for r in recorder
        if r.method == "POST" and r.url.path.endswith("/api/generate-classroom")
    ]
    assert len(submits) == 1, "重复批准不得触发第二次上游生成"


def test_repeated_approve_with_same_idempotency_key_is_idempotent(tmp_path):
    container, tc, headers, recorder, job_id, approval_id = _awaiting_job(tmp_path)
    key = "approve-once-1"

    first = _decide(tc, headers, approval_id, "APPROVED", key=key)
    assert first.status_code == 200, first.text
    second = _decide(tc, headers, approval_id, "APPROVED", key=key)
    assert second.status_code == 200, second.text
    assert second.json()["status"] == first.json()["status"]
    assert second.json()["run_id"] == first.json()["run_id"]


def test_idempotency_key_is_recorded_not_ignored(tmp_path):
    """声明了 Idempotency-Key 就必须真的落库，而不是收下后丢掉。"""
    container, tc, headers, recorder, job_id, approval_id = _awaiting_job(tmp_path)
    key = "approve-key-recorded"
    assert _decide(tc, headers, approval_id, "APPROVED", key=key).status_code == 200

    repo = container.agent_runtime_repository
    run = repo.get_run_by_job(job_id)
    assert repo.find_control(run["run_id"], key), "Idempotency-Key 必须被真正记录"


# ===== 2. 相反决定必须冲突 =====


def test_reject_after_approve_is_rejected_with_conflict(tmp_path):
    container, tc, headers, recorder, job_id, approval_id = _awaiting_job(tmp_path)
    assert _decide(tc, headers, approval_id, "APPROVED").status_code == 200

    conflict = _decide(tc, headers, approval_id, "REJECTED")
    assert conflict.status_code == 409, f"相反决定必须 409，实际: {conflict.text}"
    apv = container.agent_runtime_repository.get_approval(approval_id)
    assert apv.status == "APPROVED", "先到的决定必须保持生效"


def test_approve_after_reject_is_rejected_with_conflict(tmp_path):
    container, tc, headers, recorder, job_id, approval_id = _awaiting_job(tmp_path)
    assert _decide(tc, headers, approval_id, "REJECTED").status_code == 200

    conflict = _decide(tc, headers, approval_id, "APPROVED")
    assert conflict.status_code == 409, conflict.text
    assert container.agent_runtime_repository.get_approval(approval_id).status == "REJECTED"


# ===== 3. 并发 approve / reject：只有一个决定生效 =====


def test_concurrent_approve_and_reject_only_one_wins(tmp_path):
    """直接在 Gate 层做**真并发**（文件库 → 每线程独立连接），验证 CAS 而不是"先读后写"。"""
    from app.services.agent_runtime.approval_gate import ApprovalGate

    container, job_id, approval_id = _awaiting_job_file_db(tmp_path)
    repo = container.agent_runtime_repository
    gate = ApprovalGate(repo)
    user_id = repo.get_approval(approval_id).user_id

    results: List[str] = []
    barrier = threading.Barrier(2)

    def decide(decision: str) -> None:
        barrier.wait()
        try:
            outcome = gate.resolve(approval_id, decision=decision, user_id=user_id)
            results.append(f"ok:{outcome['status']}")
        except Exception as exc:  # noqa: BLE001
            results.append(f"err:{getattr(exc, 'code', type(exc).__name__)}")

    threads = [
        threading.Thread(target=decide, args=("APPROVED",)),
        threading.Thread(target=decide, args=("REJECTED",)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ok = [r for r in results if r.startswith("ok:")]
    assert len(ok) == 1, f"并发决策只能有一个成功: {results}"
    final = repo.get_approval(approval_id).status
    assert final in ("APPROVED", "REJECTED")
    assert ok[0] == f"ok:{final}", f"生效的决定必须与返回一致: {results} / {final}"


def test_concurrent_same_decision_is_idempotent(tmp_path):
    """并发同向决策：CAS 只允许一个"首次落定"，另一个按幂等重放处理，两者都返回成功。"""
    from app.services.agent_runtime.approval_gate import ApprovalGate

    container, job_id, approval_id = _awaiting_job_file_db(tmp_path)
    repo = container.agent_runtime_repository
    gate = ApprovalGate(repo)
    user_id = repo.get_approval(approval_id).user_id

    results: List[str] = []
    barrier = threading.Barrier(2)

    def decide() -> None:
        barrier.wait()
        try:
            gate.resolve(approval_id, decision="APPROVED", user_id=user_id)
            results.append("ok")
        except Exception as exc:  # noqa: BLE001
            results.append(f"err:{getattr(exc, 'code', type(exc).__name__)}")

    threads = [threading.Thread(target=decide) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == ["ok", "ok"], f"同向并发也必须幂等: {results}"
    assert repo.get_approval(approval_id).status == "APPROVED"


def test_cas_primitive_only_lets_one_caller_settle(tmp_path):
    """原子原语本身：第一次 True，之后一律 False（这才是并发唯一性的依据）。"""
    container, job_id, approval_id = _awaiting_job_file_db(tmp_path)
    repo = container.agent_runtime_repository
    assert repo.resolve_approval_if_pending(approval_id, status="APPROVED") is True
    assert repo.resolve_approval_if_pending(approval_id, status="REJECTED") is False
    assert repo.get_approval(approval_id).status == "APPROVED"


# ===== 4. 审批始终续跑同一个 Job =====


def test_approval_never_creates_a_parallel_job(tmp_path):
    container, tc, headers, recorder, job_id, approval_id = _awaiting_job(tmp_path)
    jobs_before = {j["job_id"] for j in container.agent_runtime_repository.list_jobs(
        container.agent_runtime_repository.get_job(job_id)["user_id"]
    )}

    _decide(tc, headers, approval_id, "APPROVED")
    _decide(tc, headers, approval_id, "APPROVED")
    drain_worker(container)

    jobs_after = {j["job_id"] for j in container.agent_runtime_repository.list_jobs(
        container.agent_runtime_repository.get_job(job_id)["user_id"]
    )}
    assert jobs_after == jobs_before, "审批不得创建平行 Job"
    assert container.agent_runtime_repository.get_run_by_job(job_id)["status"] == "SUCCEEDED"


# ===== 5. 只有审批归属人能处理 =====


def test_other_user_cannot_decide(tmp_path):
    container, tc, headers, recorder, job_id, approval_id = _awaiting_job(tmp_path)
    from app.core.exceptions import AgentRuntimeError
    from app.services.agent_runtime.approval_gate import ApprovalGate

    gate = ApprovalGate(container.agent_runtime_repository)
    try:
        gate.resolve(approval_id, decision="APPROVED", user_id="someone_else")
    except AgentRuntimeError as exc:
        assert exc.http_status == 403
    else:  # pragma: no cover
        raise AssertionError("他人不得处理该审批")
    assert container.agent_runtime_repository.get_approval(approval_id).status == "PENDING"


# ===== 6. 过期审批不得被"复活"成已批准 =====


def test_expired_approval_cannot_be_approved(tmp_path):
    container, tc, headers, recorder, job_id, approval_id = _awaiting_job(tmp_path)
    repo = container.agent_runtime_repository
    # 直接把过期时间调到过去
    repo._conn().execute(
        "UPDATE agent_approvals SET expires_at = ? WHERE approval_id = ?",
        ("2000-01-01T00:00:00+00:00", approval_id),
    )
    repo._conn().commit()

    resp = _decide(tc, headers, approval_id, "APPROVED")
    assert resp.status_code == 410, resp.text
    assert repo.get_approval(approval_id).status == "EXPIRED"
