from __future__ import annotations

from datetime import datetime, timezone

from test_phase4_learning_plans import _request, _setup
from app.schemas.learner_event import EvidenceReference, LearnerEventCreate


def test_evaluation_is_observational_and_preserves_history() -> None:
    client, container, headers, _ = _setup()
    user_id = container.user_repository.get_user_by_username("phase4_student").id
    container.personal_task_repository.create_task(
        user_id=user_id, title="测试任务", source="test", external_id="t1",
    )
    generated = client.post("/api/v1/learning-plans/generate", json=_request(), headers=headers).json()
    plan_id = generated["plan_id"]
    first = client.get(f"/api/v1/learning-plans/{plan_id}/evaluation", headers=headers)
    assert first.status_code == 200
    assert first.json()["evaluation_status"] == "INSUFFICIENT_EVIDENCE"
    container.learner_event_repository.append_idempotent(user_id=user_id, event=LearnerEventCreate(
        source="study", event_type="study_session_finished", occurred_at=datetime.now(timezone.utc),
        course_id=None, subject_type="USER", subject_id="followup-1", outcome="completed",
        evidence_reference=EvidenceReference(kind="EVENT", table="study_sessions", row_id="followup-1"),
        data_quality="partial", dedupe_key="phase4-followup-1",
    ))
    second = client.get(f"/api/v1/learning-plans/{plan_id}/evaluation", headers=headers)
    assert second.status_code == 200
    body = second.json()
    assert body["plan_id"] == plan_id
    assert "caused" not in second.text and "improved" not in second.text
    assert body["evaluator_version"]

def test_evaluation_preserves_general_priority_factors() -> None:
    client, container, headers, _ = _setup()
    user_id = container.user_repository.get_user_by_username("phase4_student").id
    container.personal_task_repository.create_task(
        user_id=user_id, title="因子验证", source="test", external_id="t1",
    )
    generated = client.post("/api/v1/learning-plans/generate", json=_request(), headers=headers).json()
    expected_factors = {
        "goal_alignment", "deadline_urgency", "workload_relief",
        "schedule_fit", "evidence_confidence", "expected_progress", "data_freshness",
    }
    for item in generated["items"]:
        assert set(item["priority_components"].keys()) == expected_factors
