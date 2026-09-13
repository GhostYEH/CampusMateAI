from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routes.course_research import _session_to_out
from app.core.config import Settings
from app.main import create_app
from app.schemas.agent_contract_enums import AssistanceMode
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def test_course_research_response_uses_frozen_effective_assistance_mode_field() -> None:
    session = SimpleNamespace(
        run_id="run_contract",
        session_id="session_contract",
        user_id="user_contract",
        course_id="course_contract",
        question="解释事务隔离级别",
        assistance_mode="EXPLAIN",
        academic_policy="UNKNOWN",
        source_policy_json=(
            '{"course_material_priority":true,"allow_web":false,'
            '"allow_user_upload":true}'
        ),
        status="SUCCEEDED",
        created_at="2026-09-13T00:00:00+00:00",
        updated_at="2026-09-13T00:00:01+00:00",
        finished_at="2026-09-13T00:00:01+00:00",
        error_code=None,
    )

    result = _session_to_out(
        session,
        artifact_ids=["artifact_contract"],
        effective_mode=AssistanceMode.HINT,
    )

    assert result.effective_assistance_mode == AssistanceMode.HINT
    assert "effective_mode" not in result.model_dump()


def test_course_research_create_returns_queued_contract_then_background_completes() -> None:
    container = reset_container_for_tests(
        Settings(
            app_env="test",
            database_url="sqlite:///:memory:",
            auto_seed_demo_users=True,
            auto_import_demo=False,
            llm_provider="none",
            agent_allow_mock_providers=True,
        )
    )
    seed_demo_data(container, force=True)
    container.agent_provider_registry.add_fake("fake")
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = client.post(
        "/api/v1/course-research/runs",
        headers={**headers, "Idempotency-Key": "course-contract-background"},
        json={
            "question": "解释事务隔离级别",
            "assistance_mode": "EXPLAIN",
            "academic_policy": "UNKNOWN",
            "source_policy": {
                "course_material_priority": True,
                "allow_web": False,
                "allow_user_upload": False,
            },
        },
    )

    assert created.status_code == 200, created.text
    assert created.json()["status"] == "QUEUED"
    assert created.json()["effective_assistance_mode"] == "EXPLAIN"
    completed = client.get(
        f"/api/v1/course-research/runs/{created.json()['run_id']}",
        headers=headers,
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] in {"SUCCEEDED", "PARTIAL"}
