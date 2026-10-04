"""Contract checks accept compatible changes and reject broken wire contracts."""
import copy
import json
from enum import Enum

import pytest
from pydantic import create_model

from app.main import create_app
from app.schemas import agent_runtime
from scripts import verify_agent_contracts as gate


def test_string_enum_order_and_additions_are_compatible(monkeypatch):
    values = ["FUTURE_STATUS", *reversed(gate._FROZEN_ENUMS["RunStatus"])]
    monkeypatch.setitem(gate._ENUMS, "RunStatus", Enum("ChangedStatus", {value: value for value in values}, type=str))
    report = gate.Report()
    gate.verify_enums(report)
    assert report.passed and not report.warnings


def test_deleting_a_frozen_enum_string_fails(monkeypatch):
    values = gate._FROZEN_ENUMS["RunStatus"][1:]
    monkeypatch.setitem(gate._ENUMS, "RunStatus", Enum("BrokenStatus", {value: value for value in values}, type=str))
    report = gate.Report()
    gate.verify_enums(report)
    assert not report.passed
    assert "QUEUED" in report.errors[0]


def test_new_required_field_fails_but_defaulted_field_is_compatible():
    models = {name: getattr(agent_runtime, name) for name in gate._FROZEN_REQUIRED_FIELDS}
    for default, expected in [("default", True), (..., False)]:
        models["AgentErrorEnvelope"] = create_model(
            "FutureEnvelope", __base__=agent_runtime.AgentErrorEnvelope, future_field=(str, default),
        )
        report = gate.Report()
        gate.verify_required_fields(report, models=models)
        assert report.passed is expected


def test_fixture_validation_rejects_missing_fields_without_printing_payload(monkeypatch, tmp_path):
    for source in gate._FIXTURE_DIR.glob("*.json"):
        data = json.loads(source.read_text(encoding="utf-8"))
        if source.name == "runtime.json":
            data["run"].pop("run_id")
            data["run"]["user_id"] = "private-value-must-not-appear"
        (tmp_path / source.name).write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(gate, "_FIXTURE_DIR", tmp_path)
    report = gate.Report()
    gate.verify_fixtures(report)
    assert not report.passed
    assert "run_id" in str(report.errors)
    assert "private-value" not in str(report.errors)


@pytest.fixture(scope="module")
def openapi():
    return create_app().openapi()


@pytest.mark.parametrize("security", [[], [{}], [{"HTTPBearer": []}, {}]])
def test_routes_cannot_offer_an_anonymous_auth_branch(openapi, security):
    schema = copy.deepcopy(openapi)
    schema["paths"]["/api/v1/agent-runs/{run_id}/events/stream"]["get"]["security"] = security
    report = gate.Report()
    gate.verify_openapi_routes(report, schema=schema)
    assert not report.passed
    assert any("Bearer" in message for message in report.errors)


def test_sse_query_token_is_rejected(openapi):
    schema = copy.deepcopy(openapi)
    schema["paths"]["/api/v1/agent-runs/{run_id}/events/stream"]["get"]["parameters"].append(
        {"name": "token", "in": "query", "schema": {"type": "string"}},
    )
    report = gate.Report()
    gate.verify_openapi_routes(report, schema=schema)
    assert not report.passed
    assert any("token" in message for message in report.errors)
