"""真实闭环端到端验收：真实容器 + 真实 HTTP 路由 + 真实 Worker。

这条用例回答的是"用户流程能不能走通"，而不是"某个函数对不对"：

  建目标 → 生成并接受计划 → 产生干预后事件 → 推进到观测窗 → Worker 评估
  → 真实 DECLINED → 持久化 REPLAN → 唯一后继 + 原子双向血缘
  → **通过 HTTP 接口回读**页面所依赖的那份数据

它刻意**不 mock** comparator、决策策略与计划替换逻辑 —— 那三处正是闭环的核心，
mock 掉之后这条用例就只剩自证。跨用户隔离与内部标识不泄漏也在这里一起钉住，
因为这两件事只有在真实路由上才谈得上。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.adaptive_agent.replanning_worker import AdaptiveReplanningWorker

from test_adaptive_closed_loop_integrity import (  # noqa: F401 - 复用真实下降场景
    _declining_scenario,
    _due_after,
    _evaluation_of,
    _rows,
    _successors,
)

PASSWORD = "Demo123456"
API = "/api/v1"


def _login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(f"{API}/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _tick(container, *, clock):
    """真实 Worker tick；只控制时钟，不替换任何决策逻辑。"""
    return AdaptiveReplanningWorker(
        repository=container.adaptive_intervention_repository,
        intervention_service=container.adaptive_intervention_service,
        clock=lambda: clock,
    ).tick(batch_size=10)


def _prepare():
    container, student, goal, planned = _declining_scenario("e2e_closed_loop_student")
    outsider = container.user_repository.create_user(
        username="e2e_closed_loop_outsider", password_hash=hash_password(PASSWORD), role="student"
    )
    client = TestClient(create_app())
    return container, student, outsider, goal, planned, client, _login(client, student.username), _login(
        client, outsider.username
    )


def test_closed_loop_runs_end_to_end_and_is_visible_through_the_api():
    container, student, _outsider, goal, planned, client, headers, _outsider_headers = _prepare()
    old_intervention = planned.intervention
    old_plan_id = planned.plan.plan_id

    # 观测窗到期后跑一轮真实 Worker：应当得到真实 REPLAN 并完成切换。
    report = _tick(container, clock=_due_after(planned))
    assert report.failed == 0, "闭环里不该有基础设施失败"
    assert report.applied == 1, "REPLAN 决策必须被真正应用"

    # ---- 通过 HTTP 回读页面所依赖的那份数据 ----
    outcome = client.get(f"{API}/adaptive-interventions/{old_intervention.intervention_id}/outcome", headers=headers)
    assert outcome.status_code == 200, outcome.text
    payload = outcome.json()

    assert payload["decision"] == "REPLAN", payload
    assert payload["decision_status"] == "APPLIED", "只有 APPLIED 才代表计划真的切换完成"
    assert payload["decision_reason_codes"], "决策必须带稳定 reason code"
    assert payload["observed_outcome"] == "DECLINED", "必须是真实投影比较得出的下降"

    # 计划血缘：页面要能显示"这份计划从哪来"。
    # 注意 `/outcome` 是**关于这条干预**的：它的 plan_id 仍是这条干预当初生成的计划，
    # 后继计划属于后继干预 —— 两者不能混为一谈。
    successors = _successors(container, student.id, old_intervention.intervention_id)
    assert len(successors) == 1, "只能有一个后继"
    new_plan_id = successors[0]["plan_id"]
    assert new_plan_id != old_plan_id
    assert payload["plan_id"] == old_plan_id, "outcome 描述的是这条干预自己的计划"
    assert payload["lineage"]["superseded_by_intervention_id"] == successors[0]["intervention_id"]

    lineage = {row["plan_id"]: row for row in _rows(
        container,
        "SELECT plan_id, supersedes_plan_id, superseded_by_plan_id FROM learning_plans WHERE user_id=?",
        (student.id,),
    )}
    assert lineage[old_plan_id]["superseded_by_plan_id"] == new_plan_id
    assert lineage[new_plan_id]["supersedes_plan_id"] == old_plan_id
    assert [pid for pid, row in lineage.items() if row["superseded_by_plan_id"] is None] == [new_plan_id], \
        "任何时刻只能有一份正式计划"

    # 列表接口也必须看得到后继，否则用户点进页面只能看到历史。
    listed = client.get(f"{API}/adaptive-interventions?page=1&page_size=10", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(item["intervention_id"] == successors[0]["intervention_id"] for item in listed.json()["items"])


def test_public_outcome_does_not_leak_internal_provenance_ids():
    container, student, _outsider, _goal, planned, client, headers, _outsider_headers = _prepare()
    _tick(container, clock=_due_after(planned))

    response = client.get(f"{API}/adaptive-interventions/{planned.intervention.intervention_id}/outcome", headers=headers)
    assert response.status_code == 200, response.text
    serialized = response.text
    for marker in ("lsnap_", "lrun_", "lprun_", "snapshot_id", "before_run_id", "after_run_id", "evidence_refs"):
        assert marker not in serialized, f"公开响应不得包含内部标识 {marker}"


def test_closed_loop_result_is_isolated_between_users():
    container, student, outsider, _goal, planned, client, _headers, outsider_headers = _prepare()
    _tick(container, clock=_due_after(planned))

    # 另一个学生既看不到列表项，也拿不到详情 —— 且两者都表现为 404，不泄露"存在与否"。
    listed = client.get(f"{API}/adaptive-interventions?page=1&page_size=10", headers=outsider_headers)
    assert listed.status_code == 200
    assert listed.json()["items"] == []

    detail = client.get(f"{API}/adaptive-interventions/{planned.intervention.intervention_id}", headers=outsider_headers)
    outcome = client.get(
        f"{API}/adaptive-interventions/{planned.intervention.intervention_id}/outcome",
        headers=outsider_headers,
    )
    assert detail.status_code == 404 and outcome.status_code == 404


# ================================================ 不该动计划的时候，就绝不能动

def test_without_a_real_decline_the_plan_is_never_switched():
    """没有真实下降就不许换计划 —— 闭环最危险的失效模式是"乱重规划"。"""
    from test_adaptive_closed_loop_integrity import _container, _add_tasks, _plan_intervention

    container, student = _container("e2e_no_decline_student")
    _add_tasks(container, student.id, count=1, day_offset=2)
    _goal, planned = _plan_intervention(container, student, key="e2e-no-decline")
    client = TestClient(create_app())
    headers = _login(client, student.username)

    report = _tick(container, clock=_due_after(planned))
    assert report.failed == 0

    payload = client.get(
        f"{API}/adaptive-interventions/{planned.intervention.intervention_id}/outcome", headers=headers
    ).json()
    assert payload["decision"] != "REPLAN", "没有下降却重规划了"
    assert payload["decision_status"] == "APPLIED", "决定本身应当已落库"

    # 计划必须原封不动：没有后继、没有血缘改动。
    assert _successors(container, student.id, planned.intervention.intervention_id) == []
    lineage = _rows(
        container,
        "SELECT plan_id, supersedes_plan_id, superseded_by_plan_id FROM learning_plans WHERE user_id=?",
        (student.id,),
    )
    assert len(lineage) == 1, "不该出现第二份计划"
    assert lineage[0]["superseded_by_plan_id"] is None and lineage[0]["supersedes_plan_id"] is None


def test_paused_data_source_degrades_conservatively_and_keeps_the_plan():
    """数据源被暂停时应当保守降级，而不是凭残缺证据改计划。"""
    from test_adaptive_closed_loop_integrity import _container, _add_tasks, _plan_intervention

    container, student = _container("e2e_paused_source_student")
    _add_tasks(container, student.id, count=1, day_offset=2)
    _goal, planned = _plan_intervention(container, student, key="e2e-paused")
    client = TestClient(create_app())
    headers = _login(client, student.username)

    container.learner_control_repository.upsert_source_control(
        user_id=student.id, source_key="CHAOXING", status="PAUSED",
    )
    assert container.learner_model_source_policy.get_paused_sources(user_id=student.id) >= {"CHAOXING"}

    report = _tick(container, clock=_due_after(planned))
    assert report.failed == 0, "数据源暂停是正常状态，不是基础设施失败"

    payload = client.get(
        f"{API}/adaptive-interventions/{planned.intervention.intervention_id}/outcome", headers=headers
    ).json()
    assert payload["decision"] in {"WAIT_FOR_EVIDENCE", "SUSPEND", "CONTINUE"}, payload
    assert _successors(container, student.id, planned.intervention.intervention_id) == [], \
        "证据受限时不得替换计划"


# ==================================================== 前端刷新 / 并发读取的稳定性

def test_repeated_page_reads_are_stable_and_do_not_create_work():
    """刷新页面只能回读同一份落库结果，不得因为读取而产生新决策或新计划。"""
    container, student, _outsider, _goal, planned, client, headers, _outsider_headers = _prepare()
    _tick(container, clock=_due_after(planned))

    url = f"{API}/adaptive-interventions/{planned.intervention.intervention_id}/outcome"
    first = client.get(url, headers=headers)
    second = client.get(url, headers=headers)
    third = client.get(url, headers=headers)
    assert first.status_code == second.status_code == third.status_code == 200
    assert first.json() == second.json() == third.json(), "同一份持久化结果必须逐字段稳定"

    decisions = _rows(
        container,
        "SELECT decision_id FROM adaptive_replan_decisions WHERE user_id=?",
        (student.id,),
    )
    assert len(decisions) == 1, "读页面不得产生第二条决策"
    assert len(_successors(container, student.id, planned.intervention.intervention_id)) == 1


def test_two_workers_racing_produce_exactly_one_successor():
    """两个 Worker 先后处理同一条决策：只能有一个后继、一份正式计划。"""
    container, student, _outsider, _goal, planned, client, headers, _outsider_headers = _prepare()
    due = _due_after(planned)

    first = _tick(container, clock=due)
    second = _tick(container, clock=due)  # 第二个 Worker 面对的是已经终态的决策
    assert first.failed == second.failed == 0

    successors = _successors(container, student.id, planned.intervention.intervention_id)
    assert len(successors) == 1, "并发只能产生一个后继"

    decisions = _rows(
        container,
        "SELECT status, lease_owner, lease_expires_at FROM adaptive_replan_decisions WHERE user_id=?",
        (student.id,),
    )
    assert len(decisions) == 1, "不得出现第二条决策"
    assert decisions[0]["status"] == "APPLIED"
    assert decisions[0]["lease_owner"] is None and decisions[0]["lease_expires_at"] is None, \
        "终态必须释放处理权"

    # 页面看到的后继数量也必须是一个。
    listed = client.get(f"{API}/adaptive-interventions?page=1&page_size=10", headers=headers).json()["items"]
    assert len(listed) == 2, "原干预 + 唯一后继"
