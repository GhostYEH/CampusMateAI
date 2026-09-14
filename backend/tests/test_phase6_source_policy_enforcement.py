"""Phase 6.1-4: 验证 LearnerModelSourcePolicy 真正作用于数据链路。"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import InvalidTransition
from app.core.security import hash_password
from app.main import create_app
from app.models.model_capability import ModelCapabilityRequest
from app.services.container import reset_container_for_tests


def _setup():
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    student = container.user_repository.create_user(
        username="sp_student", password_hash=hash_password("Demo123456"), role="student", display_name="S"
    )
    client = TestClient(create_app())
    resp = client.post("/api/v1/auth/login", json={"username": "sp_student", "password": "Demo123456"})
    auth = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    return client, container, auth, student.id


def _pause(container, uid, source_key):
    container.learner_control_repository.upsert_source_control(
        user_id=uid, source_key=source_key, status="PAUSED"
    )


def _resume(container, uid, source_key):
    container.learner_control_repository.upsert_source_control(
        user_id=uid, source_key=source_key, status="ENABLED"
    )


def test_projection_includes_warning_when_source_paused():
    client, container, auth, uid = _setup()
    _pause(container, uid, "CHAOXING")
    now = datetime.now(timezone.utc)
    result = container.learner_state_service.project_user(uid, as_of=now, trigger="test")
    assert "learner_data_source_paused" in result.warnings


def test_projection_no_warning_when_all_enabled():
    client, container, auth, uid = _setup()
    now = datetime.now(timezone.utc)
    result = container.learner_state_service.project_user(uid, as_of=now, trigger="test")
    assert "learner_data_source_paused" not in result.warnings


def test_chaoxing_event_skipped_when_paused():
    client, container, auth, uid = _setup()
    _pause(container, uid, "CHAOXING")
    course = container.course_repository.create_course(
        owner_user_id=uid, provider="chaoxing", external_id="cx_test_001",
        name="测试课程", source_url="https://example.com",
        last_synced_at=datetime.now(timezone.utc).isoformat(),
    )
    result = container.learner_event_service.record_chaoxing_course_synced(course)
    assert result is None
    events, total = container.learner_event_repository.list_for_user(user_id=uid, page=1, page_size=10)
    assert total == 0


def test_core_event_not_skipped_when_chaoxing_paused():
    client, container, auth, uid = _setup()
    _pause(container, uid, "CHAOXING")
    session = container.study_session_repository.create_session(
        user_id=uid, mode="focus", experience_mode="QUIET", planned_duration_seconds=600
    )
    completed = container.study_session_repository.finish(session_id=session.id, user_id=uid)
    result = container.learner_event_service.record_study_session_finished(completed)
    assert result is not None
    events, total = container.learner_event_repository.list_for_user(user_id=uid, page=1, page_size=10)
    assert total == 1


def test_plan_generation_rejected_when_proactive_paused():
    client, container, auth, uid = _setup()
    _pause(container, uid, "PROACTIVE_SUGGESTIONS")
    try:
        container.learning_planner_service.generate(
            user_id=uid, available_minutes=30, idempotency_key="plan1"
        )
        assert False, "应抛出 InvalidTransition"
    except InvalidTransition:
        pass


def test_plan_generation_works_when_proactive_enabled():
    client, container, auth, uid = _setup()
    container.personal_task_repository.create_task(
        user_id=uid, title="测试任务", source="test", external_id="t1",
    )
    plan = container.learning_planner_service.generate(
        user_id=uid, available_minutes=30, idempotency_key="plan1"
    )
    assert plan is not None


def _make_shadow_request(uid, req_id="req_test_001"):
    return ModelCapabilityRequest(
        capability_name="learning_summary_v1",
        capability_version="v1",
        subject_user_id=uid,
        input_payload={
            "plan_id": "plan-1",
            "warning_codes": [],
            "explanation_codes": ["deadline_urgent"],
            "item_type": "TASK_FOCUS",
            "estimated_minutes": 30,
            "data_quality": "verified",
            "evidence_count": 1,
            "deadline_bucket": "DUE_24H",
            "state_band": None,
            "confidence_bucket": "HIGH",
        },
        request_id=req_id,
    )


def test_shadow_runner_skipped_when_paused():
    client, container, auth, uid = _setup()
    _pause(container, uid, "MODEL_SHADOW")
    runner = container.model_shadow_runner
    runner.enabled = True
    request = _make_shadow_request(uid)
    result = asyncio.run(runner.run(request))
    assert result.failure_code == "MODEL_SHADOW_PAUSED"
    assert result.used_fallback is True


def test_shadow_runner_not_paused_when_enabled():
    client, container, auth, uid = _setup()
    runner = container.model_shadow_runner
    runner.enabled = True
    request = _make_shadow_request(uid, req_id="req_test_002")
    result = asyncio.run(runner.run(request))
    assert result.failure_code != "MODEL_SHADOW_PAUSED"


def test_multiple_sources_paused():
    client, container, auth, uid = _setup()
    _pause(container, uid, "CHAOXING")
    _pause(container, uid, "EDU")
    now = datetime.now(timezone.utc)
    result = container.learner_state_service.project_user(uid, as_of=now, trigger="test")
    assert result.warnings.count("learner_data_source_paused") == 1


def test_resume_source_clears_warning():
    client, container, auth, uid = _setup()
    _pause(container, uid, "CHAOXING")
    now = datetime.now(timezone.utc)
    result1 = container.learner_state_service.project_user(uid, as_of=now, trigger="test")
    assert "learner_data_source_paused" in result1.warnings
    _resume(container, uid, "CHAOXING")
    result2 = container.learner_state_service.project_user(uid, as_of=now, trigger="test")
    assert "learner_data_source_paused" not in result2.warnings
