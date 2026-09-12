from __future__ import annotations

from test_phase4_learning_plans import _request, _setup


def test_feedback_is_fixed_enum_and_same_feedback_is_idempotent() -> None:
    client, container, headers, other_headers = _setup()
    generated = client.post("/api/v1/learning-plans/generate", json=_request(), headers=headers).json()
    path = f"/api/v1/learning-plans/{generated['plan_id']}/feedback"
    first = client.post(path, json={"feedback": "HELPFUL"}, headers=headers)
    second = client.post(path, json={"feedback": "HELPFUL"}, headers=headers)
    assert first.status_code == second.status_code == 200
    assert client.post(path, json={"feedback": "free text"}, headers=headers).status_code == 422
    assert client.post(path, json={"feedback": "HELPFUL"}, headers=other_headers).status_code == 404
    user_id = container.user_repository.get_user_by_username("phase4_student").id
    events, total = container.learner_event_repository.list_for_user(
        user_id=user_id,
        source="ai_learning_feedback",
        event_type="ai_learning_feedback_recorded",
    )
    assert total == 1
    assert events[0].payload == {"feedback_kind": "HELPFUL", "data_quality": "verified"}


def test_feedback_does_not_echo_free_text_or_internal_references() -> None:
    client, _, headers, _ = _setup()
    generated = client.post("/api/v1/learning-plans/generate", json=_request(), headers=headers).json()
    response = client.post(
        f"/api/v1/learning-plans/{generated['plan_id']}/feedback",
        json={"feedback": "MISSING_CONTEXT", "comment": "private material"}, headers=headers,
    )
    assert response.status_code == 200
    assert "private material" not in response.text
    assert "source_id" not in response.text
