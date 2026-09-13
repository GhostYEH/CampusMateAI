from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.schemas.agent_runtime import (
    AgentApprovalOut,
    AgentArtifactOut,
    AgentErrorEnvelope,
    AgentEventOut,
    AgentRunOut,
    CourseResearchContract,
    FinalReviewContract,
    NoticeWorkflowContract,
)


FIXTURES = Path(__file__).parent / "fixtures" / "agent_runtime" / "v1"


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("runtime.json", AgentRunOut),
        ("final_review.json", FinalReviewContract),
        ("course_research.json", CourseResearchContract),
        ("notice_workflow.json", NoticeWorkflowContract),
    ],
)
def test_canonical_contract_fixture_round_trips(filename, model):
    payload = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
    assert model.model_validate(payload).model_dump(mode="json") == payload


def test_agent_event_contract_rejects_hidden_fields():
    payload = {
        "id": "evt_1",
        "type": "RUN_STARTED",
        "run_id": "run_1",
        "sequence": 1,
        "status": "RUNNING",
        "phase": "CONTEXT_BUILDING",
        "role": "planner",
        "summary": "开始准备上下文",
        "progress": {"current": 0, "total": 4, "percent": 0},
        "artifact_id": None,
        "approval_id": None,
        "created_at": "2026-09-12T10:00:00Z",
        "prompt": "secret",
    }
    with pytest.raises(ValidationError):
        AgentEventOut.model_validate(payload)


def test_public_contracts_reject_credentials_and_unknown_fields():
    for model, payload in (
        (AgentErrorEnvelope, {"code": "AGENT_INVALID_STATE", "message": "bad", "request_id": "req_1", "api_key": "x"}),
        (AgentArtifactOut, {"artifact_id": "a", "run_id": "r", "artifact_type": "DAILY_AGENDA", "version": 1, "mime_type": "application/json", "size_bytes": 1, "content_hash": "a" * 64, "created_at": "2026-09-12T10:00:00Z", "token": "x"}),
        (AgentApprovalOut, {"approval_id": "a", "run_id": "r", "status": "PENDING", "risk_level": "CONFIRM_REQUIRED", "summary": "确认", "expires_at": "2026-09-12T10:10:00Z", "created_at": "2026-09-12T10:00:00Z", "raw_arguments": {}}),
    ):
        with pytest.raises(ValidationError):
            model.model_validate(payload)


def test_every_error_response_has_request_id_header_and_body():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/definitely-missing-agent-route")
    assert response.status_code == 404
    assert response.headers["x-request-id"]
    assert response.json()["request_id"] == response.headers["x-request-id"]
