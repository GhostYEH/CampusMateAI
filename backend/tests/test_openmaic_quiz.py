from __future__ import annotations

from app.api.routes import openmaic_quiz
from test_openmaic_workspaces import _setup


def _path(course_id: str, suffix: str = "") -> str:
    return f"/api/v1/courses/{course_id}/workspaces/ws_1/stages/stg_1/scenes/scn_1/quiz-attempt{suffix}"


def test_quiz_attempt_lifecycle_survives_refresh_and_is_user_scoped():
    container, _, http, headers, course_id = _setup([])
    response = http.get(_path(course_id), headers=headers)
    assert response.status_code == 200
    attempt_id = response.json()["attempt_id"]
    assert response.json()["state"] is None

    payload = {"attempt_id": attempt_id, "phase": "draft", "answers": {"q1": "a"}}
    saved = http.post(_path(course_id), json=payload, headers=headers)
    assert saved.status_code == 200
    assert saved.json()["state"]["phase"] == "draft"

    reviewed = http.post(_path(course_id), json={
        **payload,
        "phase": "reviewed",
        "results": [{"questionId": "q1", "correct": True, "earned": 1, "analysis": "解析"}],
    }, headers=headers)
    assert reviewed.status_code == 200
    reread = http.get(_path(course_id), headers=headers)
    assert reread.json()["state"]["phase"] == "reviewed"
    assert reread.json()["state"]["results"][0]["analysis"] == "解析"


def test_quiz_retry_rolls_to_a_new_attempt_without_losing_the_old_review():
    _, _, http, headers, course_id = _setup([])
    current = http.get(_path(course_id), headers=headers).json()["attempt_id"]
    http.post(_path(course_id), json={"attempt_id": current, "phase": "reviewed", "answers": {"q1": "a"}, "results": []}, headers=headers)
    retry = http.post(_path(course_id), json={"attempt_id": current, "phase": "draft", "answers": {}, "start_new_attempt": True}, headers=headers)
    assert retry.status_code == 200
    assert retry.json()["attempt_id"] != current
    assert retry.json()["state"]["phase"] == "draft"


def test_quiz_attempt_rejects_phase_regression():
    _, _, http, headers, course_id = _setup([])
    attempt_id = http.get(_path(course_id), headers=headers).json()["attempt_id"]
    http.post(_path(course_id), json={"attempt_id": attempt_id, "phase": "reviewed", "answers": {}, "results": []}, headers=headers)
    response = http.post(_path(course_id), json={"attempt_id": attempt_id, "phase": "draft", "answers": {}}, headers=headers)
    assert response.status_code == 409
