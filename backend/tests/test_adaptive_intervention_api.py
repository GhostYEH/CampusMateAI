"""状态驱动干预的只读接口 —— 隔离、分页与不泄露内部结构。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests


def _setup():
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    student = container.user_repository.create_user(
        username="adaptive_api_student", password_hash=hash_password("Demo123456"), role="student"
    )
    other = container.user_repository.create_user(
        username="adaptive_api_other", password_hash=hash_password("Demo123456"), role="student"
    )
    container.user_repository.create_user(
        username="adaptive_api_teacher", password_hash=hash_password("Demo123456"), role="teacher"
    )
    client = TestClient(create_app())

    def login(username: str) -> dict[str, str]:
        response = client.post("/api/v1/auth/login", json={"username": username, "password": "Demo123456"})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return container, student, other, client, login(student.username), login(other.username), login(
        "adaptive_api_teacher"
    )


def _seed(container, user_id: str, *, count: int = 2) -> list[str]:
    container.personal_task_repository.create_task(
        user_id=user_id, title="复习概率论",
        deadline=(datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
    )
    goal = container.student_goal_repository.create_goal(
        user_id=user_id, name="完成概率论期末复习", category="ACADEMIC",
        target_date=(datetime.now(timezone.utc) + timedelta(days=14)).date().isoformat(),
        idempotency_key="adaptive-api-goal-1",
    )[0]
    intervention_ids = []
    for index in range(count):
        outcome = container.adaptive_intervention_service.plan_for_goal(
            user_id=user_id, goal_id=goal.goal_id, available_minutes=60,
            idempotency_key=f"run:api_{index}",
        )
        intervention_ids.append(outcome.intervention.intervention_id)
    return intervention_ids


def test_list_and_detail_are_scoped_and_paginated() -> None:
    container, student, _other, client, headers, _other_headers, _teacher_headers = _setup()
    intervention_ids = _seed(container, student.id)

    listed = client.get("/api/v1/adaptive-interventions?page=1&page_size=1", headers=headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] == 2
    assert body["page"] == 1 and body["page_size"] == 1
    assert body["has_more"] is True
    assert len(body["items"]) == 1

    second_page = client.get("/api/v1/adaptive-interventions?page=2&page_size=1", headers=headers).json()
    assert second_page["has_more"] is False
    assert {item["intervention_id"] for item in body["items"]}.isdisjoint(
        {item["intervention_id"] for item in second_page["items"]}
    )

    detail = client.get(f"/api/v1/adaptive-interventions/{intervention_ids[0]}", headers=headers)
    assert detail.status_code == 200, detail.text
    item = detail.json()
    assert item["intervention_id"] == intervention_ids[0]
    assert item["status"] == "PLAN_GENERATED"
    assert item["plan_id"]
    assert item["strategy_code"] and item["strategy_version"]
    assert item["problem_types"]
    assert item["rationale_codes"]
    assert item["data_quality"] in {"verified", "partial", "stale", "unavailable"}


def test_response_does_not_leak_internal_identity_or_raw_payloads() -> None:
    container, student, _other, client, headers, _other_headers, _teacher_headers = _setup()
    intervention_ids = _seed(container, student.id, count=1)

    listed = client.get("/api/v1/adaptive-interventions", headers=headers)
    detail = client.get(f"/api/v1/adaptive-interventions/{intervention_ids[0]}", headers=headers)
    for response in (listed, detail):
        assert response.status_code == 200
        payload = response.text
        assert student.id not in payload
        for forbidden in ("user_id", "assessment_json", "strategy_json", "baseline_state_digest", "idempotency_key"):
            assert forbidden not in payload
        # 原始评估 JSON 里的字段名也不该以任何形式出现在响应里。
        for forbidden in ("state_features", "evidence_refs", "planning_parameters"):
            assert forbidden not in payload


def test_cross_user_access_is_not_distinguishable_from_missing() -> None:
    container, student, other, client, _headers, other_headers, _teacher_headers = _setup()
    intervention_ids = _seed(container, student.id, count=1)

    assert client.get(
        f"/api/v1/adaptive-interventions/{intervention_ids[0]}", headers=other_headers
    ).status_code == 404
    assert client.get(
        "/api/v1/adaptive-interventions/intervention_does_not_exist", headers=other_headers
    ).status_code == 404
    other_list = client.get("/api/v1/adaptive-interventions", headers=other_headers).json()
    assert other_list["total"] == 0 and other_list["items"] == []
    assert container.adaptive_intervention_repository.count_for_user(user_id=other.id) == 0


def test_authentication_and_role_are_enforced() -> None:
    container, student, _other, client, headers, _other_headers, teacher_headers = _setup()
    intervention_ids = _seed(container, student.id, count=1)

    assert client.get("/api/v1/adaptive-interventions").status_code == 401
    assert client.get(
        f"/api/v1/adaptive-interventions/{intervention_ids[0]}"
    ).status_code == 401
    assert client.get("/api/v1/adaptive-interventions", headers=teacher_headers).status_code == 403
    assert client.get(
        f"/api/v1/adaptive-interventions/{intervention_ids[0]}", headers=teacher_headers
    ).status_code == 403


@pytest.mark.parametrize("query", ["page=0", "page_size=0", "page_size=101", "page=-1"])
def test_pagination_bounds_are_validated(query: str) -> None:
    container, student, _other, client, headers, _other_headers, _teacher_headers = _setup()
    assert client.get(f"/api/v1/adaptive-interventions?{query}", headers=headers).status_code == 422


def test_interface_is_read_only() -> None:
    container, student, _other, client, headers, _other_headers, _teacher_headers = _setup()
    intervention_ids = _seed(container, student.id, count=1)
    assert client.post("/api/v1/adaptive-interventions", json={}, headers=headers).status_code == 405
    assert client.patch(
        f"/api/v1/adaptive-interventions/{intervention_ids[0]}", json={"status": "ACCEPTED"}, headers=headers
    ).status_code == 405
    assert client.delete(
        f"/api/v1/adaptive-interventions/{intervention_ids[0]}", headers=headers
    ).status_code == 405


# --------------------------------------------------------------- 结果评估接口


def _accept_and_execute(container, user_id: str, intervention_id: str) -> str:
    row = container.adaptive_intervention_repository.get(
        user_id=user_id, intervention_id=intervention_id
    )
    container.learning_planner_service.decide(user_id=user_id, plan_id=row.plan_id, decision="ACCEPT")
    container.learning_planner_service.execute(user_id=user_id, plan_id=row.plan_id)
    return row.plan_id


def test_outcome_endpoint_explains_the_evaluation_and_advances_status() -> None:
    container, student, _other, client, headers, _other_headers, _teacher_headers = _setup()
    intervention_ids = _seed(container, student.id, count=1)
    intervention_id = intervention_ids[0]

    # 计划刚生成：还没有可判断的结果，结论可读但不落库。
    early = client.get(f"/api/v1/adaptive-interventions/{intervention_id}/outcome", headers=headers)
    assert early.status_code == 200, early.text
    body = early.json()
    assert body["verdict"] == "NOT_OBSERVED"
    assert body["execution_signal"] == "NOT_STARTED"
    assert body["created_at"] == ""
    assert body["outcome_checks"] and all(
        {"code", "verdict", "reason_code"} == set(check) for check in body["outcome_checks"]
    )

    _accept_and_execute(container, student.id, intervention_id)
    response = client.get(f"/api/v1/adaptive-interventions/{intervention_id}/outcome", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verdict"] in {"PARTIALLY_EFFECTIVE", "EFFECTIVE"}
    assert body["execution_signal"] == "IN_PROGRESS"
    assert body["observation_status"] == "IN_PROGRESS"
    assert body["plan_fidelity"] in {"MATCHED", "MISMATCHED", "UNVERIFIABLE"}
    assert body["execution_signals"]["planned_item_count"] >= 1
    assert body["window_start"] and body["window_end"]
    assert body["created_at"]
    # 结论必须可解释：每条判定都带有限理由码。
    assert all(check["reason_code"] for check in body["outcome_checks"])

    detail = client.get(f"/api/v1/adaptive-interventions/{intervention_id}", headers=headers).json()
    assert detail["status"] == "OBSERVING"
    assert detail["outcome_verdict"] == body["verdict"]
    assert detail["observation_started_at"] and detail["evaluated_at"] is None


def test_outcome_endpoint_is_idempotent_for_the_same_observation() -> None:
    container, student, _other, client, headers, _other_headers, _teacher_headers = _setup()
    intervention_ids = _seed(container, student.id, count=1)
    intervention_id = intervention_ids[0]
    _accept_and_execute(container, student.id, intervention_id)

    first = client.get(f"/api/v1/adaptive-interventions/{intervention_id}/outcome", headers=headers).json()
    second = client.get(f"/api/v1/adaptive-interventions/{intervention_id}/outcome", headers=headers).json()
    assert first["evaluation_id"] == second["evaluation_id"]
    assert len(container.adaptive_intervention_repository.list_evaluations(
        user_id=student.id, intervention_id=intervention_id
    )) == 1


def test_outcome_endpoint_is_scoped_and_role_guarded() -> None:
    container, student, other, client, headers, other_headers, teacher_headers = _setup()
    intervention_ids = _seed(container, student.id, count=1)
    path = f"/api/v1/adaptive-interventions/{intervention_ids[0]}/outcome"

    # 跨用户与不存在返回同样的 404，且不会为对方产生任何评估记录。
    assert client.get(path, headers=other_headers).status_code == 404
    assert client.get(
        "/api/v1/adaptive-interventions/intv_missing/outcome", headers=other_headers
    ).status_code == 404
    assert container.adaptive_intervention_repository.get_evaluation(
        user_id=other.id, intervention_id=intervention_ids[0]
    ) is None

    assert client.get(path).status_code == 401
    assert client.get(path, headers=teacher_headers).status_code == 403


def test_outcome_response_does_not_leak_internal_payloads() -> None:
    container, student, _other, client, headers, _other_headers, _teacher_headers = _setup()
    intervention_ids = _seed(container, student.id, count=1)
    intervention_id = intervention_ids[0]
    _accept_and_execute(container, student.id, intervention_id)

    response = client.get(f"/api/v1/adaptive-interventions/{intervention_id}/outcome", headers=headers)
    assert response.status_code == 200
    payload = response.text
    assert student.id not in payload
    for forbidden in (
        "user_id", "assessment_json", "strategy_json", "evaluation_json", "baseline_state_digest",
        # 证据引用只保留在服务端：客户端拿到的是判定与理由码，不是内部引用。
        "evidence_refs", "projection_kind", "snapshot_id", "run_id",
    ):
        assert forbidden not in payload


def test_outcome_endpoint_is_read_only() -> None:
    container, student, _other, client, headers, _other_headers, _teacher_headers = _setup()
    intervention_ids = _seed(container, student.id, count=1)
    path = f"/api/v1/adaptive-interventions/{intervention_ids[0]}/outcome"
    assert client.post(path, json={}, headers=headers).status_code == 405
    assert client.patch(path, json={"verdict": "EFFECTIVE"}, headers=headers).status_code == 405
    assert client.delete(path, headers=headers).status_code == 405
