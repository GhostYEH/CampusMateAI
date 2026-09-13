"""Regression coverage for the generic learner-state source and event contracts."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.schemas.learner_event import LearnerEventCreate
from app.services.container import reset_container_for_tests


def _setup():
    container = reset_container_for_tests(
        Settings(app_env="test", database_url="sqlite:///:memory:")
    )
    student = container.user_repository.create_user(
        username="generic_contract_student",
        password_hash=hash_password("Demo123456"),
        role="student",
        display_name="Student",
    )
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "generic_contract_student", "password": "Demo123456"},
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return client, container, auth, student.id


def test_data_controls_expose_only_current_generic_sources():
    client, _container, auth, _user_id = _setup()
    response = client.get("/api/v1/learner-state/data-controls", headers=auth)

    assert response.status_code == 200
    assert {item["source_key"] for item in response.json()["items"]} == {
        "CORE_STUDY",
        "PERSONAL_TASK",
        "CHAOXING",
        "EDU",
        "MODEL_SHADOW",
        "PROACTIVE_SUGGESTIONS",
    }


def test_retired_practice_source_is_not_writable():
    client, _container, auth, _user_id = _setup()
    response = client.put(
        "/api/v1/learner-state/data-controls/PRACTICE",
        json={"status": "PAUSED", "idempotency_key": "retired-practice"},
        headers=auth,
    )

    assert response.status_code in (400, 404)


def test_retired_practice_event_is_not_writable():
    with pytest.raises(ValidationError):
        LearnerEventCreate(
            source="practice",
            event_type="practice_answered",
            occurred_at=datetime.now(timezone.utc),
            subject_type="practice_attempt",
            subject_id="retired-attempt",
            outcome="observed_completed",
            data_quality="verified",
            consent_scope="core_learning_record",
            dedupe_key="retired-practice-event",
            evidence_reference={
                "kind": "retired",
                "table": "retired",
                "row_id": "retired-attempt",
            },
        )
