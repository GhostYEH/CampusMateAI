import re

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client():
    container = reset_container_for_tests(
        Settings(
            app_env="test",
            database_url="sqlite:///:memory:",
            auto_seed_demo_users=True,
            auto_import_demo=False,
            llm_provider="none",
        )
    )
    seed_demo_data(container, force=True)
    return container, TestClient(create_app())


def _login(client, username):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_learner_state_api_requires_student_auth_and_never_returns_raw_payload():
    container, client = _client()
    assert client.get("/api/v1/learner-state/snapshots").status_code == 401
    headers = _login(client, "student_demo")
    response = client.get("/api/v1/learner-state/snapshots", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert all("payload" not in item for item in body["items"])
    assert all("mastered" not in str(item).lower() for item in body["items"])
    workload = next(item for item in body["items"] if item["state_type"] == "task_workload")
    evidence = client.get(
        f"/api/v1/learner-state/snapshots/{workload['snapshot_id']}/evidence",
        headers=headers,
    )
    assert evidence.status_code == 200
    assert evidence.json()["items"]
    assert all({"evidence_kind", "source_category", "role", "explanation_code"} <= set(item) for item in evidence.json()["items"])
    assert all("source_id" not in item and "row_id" not in item for item in evidence.json()["items"])


def test_learner_state_api_preserves_cross_user_snapshot_isolation():
    container, client = _client()
    admin_headers = _login(client, "content_demo_owner")
    assert client.get("/api/v1/learner-state/snapshots", headers=admin_headers).status_code == 200
    student_headers = _login(client, "student_demo")
    response = client.get("/api/v1/learner-state/snapshots", headers=student_headers)
    snapshot_id = response.json()["items"][0]["snapshot_id"]
    other_headers = _login(client, "student_demo_01")
    assert client.get(
        f"/api/v1/learner-state/snapshots/{snapshot_id}/evidence",
        headers=other_headers,
    ).status_code == 404


def test_state_type_and_value_model_registries_never_drift():
    """防漂移护栏：StateType 的每个取值都必须有值模型、且在 StateValue 联合类型里。

    历史上这三处各写一份，`knowledge_mastery_observation` 只加进了校验映射表、
    没加进 Union，导致 ACADEMIC 快照序列化时逐个试错并抛出上百条 validation error
    ——也就是接口直接 500，而单元测试因为只测 service 层完全没发现。
    """
    from typing import get_args

    from app.schemas.learner_state import (
        ACADEMIC_STATE_TYPES,
        STATE_TYPE_PATTERN,
        STATE_VALUE_MODELS,
        StateType,
        StateValue,
    )

    state_types = set(get_args(StateType))
    assert set(STATE_VALUE_MODELS) == state_types
    union_members = set(get_args(get_args(StateValue)[0]))
    assert set(STATE_VALUE_MODELS.values()) <= union_members
    # Query pattern 由 StateType 派生，不能再出现手写枚举漏项。
    for state_type in state_types:
        assert re.fullmatch(STATE_TYPE_PATTERN, state_type), state_type
    assert set(ACADEMIC_STATE_TYPES) <= state_types
    assert "knowledge_mastery_observation" in ACADEMIC_STATE_TYPES


def test_academic_endpoint_keeps_total_pagination_and_evidence_metadata():
    container, client = _client()
    headers = _login(client, "student_demo")
    user_id = container.user_repository.get_user_by_username("student_demo").id
    response = client.get(
        "/api/v1/learner-state/academic?page_size=1", headers=headers,
    )
    assert response.status_code == 200
    first = response.json()
    assert first["total"] > 1
    assert first["has_more"] is True
    snapshots = first["items"][:]
    for page in range(2, first["total"] + 1):
        response = client.get(
            f"/api/v1/learner-state/academic?page_size=1&page={page}",
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == first["total"]
        assert body["has_more"] is (page < first["total"])
        snapshots.extend(body["items"])
    assert len({item["state_type"] for item in snapshots}) == first["total"]
    for item in snapshots:
        run = container.learner_state_repository.get_run(item["run_id"], user_id=user_id)
        assert item["projection_kind"] == "ACADEMIC"
        assert item["estimator_version"] == run.estimator_version
        assert item["input_digest"] == run.input_digest
        assert item["as_of"] is not None
        assert item["warning_codes"] == run.warnings
        evidence = client.get(
            f"/api/v1/learner-state/snapshots/{item['snapshot_id']}/evidence",
            headers=headers,
        )
        assert evidence.status_code == 200
        assert item["evidence_count"] == evidence.json()["total"]
    empty = client.get(
        f"/api/v1/learner-state/academic?page_size=1&page={first['total'] + 1}",
        headers=headers,
    ).json()
    assert empty["items"] == []
    assert empty["total"] == first["total"]
    assert empty["has_more"] is False


@pytest.mark.parametrize("projection_kind", ["CORE", "ACADEMIC", "WORLD"])
def test_runs_and_implicit_changes_support_each_projection_family(projection_kind):
    _, client = _client()
    headers = _login(client, "student_demo")
    runs = client.get(
        "/api/v1/learner-state/runs",
        params={"projection_kind": projection_kind}, headers=headers,
    )
    assert runs.status_code == 200
    body = runs.json()
    assert body["items"]
    assert {item["projection_kind"] for item in body["items"]} == {projection_kind}
    current_run = next(item for item in body["items"] if item["is_current"])
    changes = client.get(
        "/api/v1/learner-state/changes",
        params={"projection_kind": projection_kind, "include_unchanged": True},
        headers=headers,
    )
    assert changes.status_code == 200
    assert changes.json()["to_run_id"] == current_run["run_id"]
    assert changes.json()["total"] == current_run["snapshot_count"]
    assert client.get(
        "/api/v1/learner-state/changes",
        params={"to_run_id": current_run["run_id"]},
        headers=_login(client, "student_demo_01"),
    ).status_code == 404


@pytest.mark.parametrize("endpoint", ["runs", "changes"])
def test_history_endpoints_reject_unknown_projection_family(endpoint):
    _, client = _client()
    response = client.get(
        f"/api/v1/learner-state/{endpoint}",
        params={"projection_kind": "UNKNOWN"},
        headers=_login(client, "student_demo"),
    )
    assert response.status_code == 422
