from __future__ import annotations

from test_phase4_learning_plans import _request, _setup


def test_feedback_is_fixed_enum_and_same_feedback_is_idempotent() -> None:
    client, _, headers, other_headers = _setup()
    generated = client.post("/api/v1/learning-plans/generate", json=_request(), headers=headers).json()
    path = f"/api/v1/learning-plans/{generated['plan_id']}/feedback"
    first = client.post(path, json={"feedback": "HELPFUL"}, headers=headers)
    second = client.post(path, json={"feedback": "HELPFUL"}, headers=headers)
    assert first.status_code == second.status_code == 200
    assert client.post(path, json={"feedback": "free text"}, headers=headers).status_code == 422
    assert client.post(path, json={"feedback": "HELPFUL"}, headers=other_headers).status_code == 404


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
