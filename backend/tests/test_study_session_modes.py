from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client() -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app())


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_study_session_persists_its_mode() -> None:
    client = _client()
    headers = _headers(client)

    created = client.post(
        "/api/v1/study/sessions",
        headers=headers,
        json={"mode": "short_break"},
    )

    assert created.status_code == 201
    assert created.json()["mode"] == "short_break"
    assert client.get("/api/v1/study/sessions", headers=headers).json()[0]["mode"] == "short_break"


def test_study_session_rejects_an_unknown_mode() -> None:
    client = _client()

    response = client.post(
        "/api/v1/study/sessions",
        headers=_headers(client),
        json={"mode": "nap"},
    )

    assert response.status_code == 422


def test_finish_session_round_trips_privacy_safe_behavior_summary() -> None:
    client = _client()
    headers = _headers(client)
    created = client.post(
        "/api/v1/study/sessions",
        headers=headers,
        json={"mode": "focus", "planned_duration_seconds": 1500},
    )
    assert created.status_code == 201

    summary = {
        "observed_seconds": 600,
        "study_seconds": 510,
        "paused_seconds": 60,
        "longest_continuous_study_seconds": 330,
        "meaningful_switch_count": 2,
        "phone_interaction_count": 1,
        "possible_distraction_count": 1,
        "absent_count": 0,
        "reminder_count": 1,
        "model_version": "READY_BEHAVIOR_HYBRID_V4",
    }
    finished = client.post(
        f"/api/v1/study/sessions/{created.json()['id']}/finish",
        headers=headers,
        json={"behavior_summary": summary},
    )

    assert finished.status_code == 200
    assert finished.json()["behavior_summary"] == summary
    detail = client.get(
        f"/api/v1/study/sessions/{created.json()['id']}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["behavior_summary"] == summary


def test_finish_session_rejects_frame_level_behavior_payload() -> None:
    client = _client()
    headers = _headers(client)
    created = client.post(
        "/api/v1/study/sessions",
        headers=headers,
        json={"mode": "focus"},
    )

    finished = client.post(
        f"/api/v1/study/sessions/{created.json()['id']}/finish",
        headers=headers,
        json={
            "behavior_summary": {
                "observed_seconds": 10,
                "study_seconds": 8,
                "paused_seconds": 0,
                "longest_continuous_study_seconds": 8,
                "meaningful_switch_count": 0,
                "phone_interaction_count": 0,
                "possible_distraction_count": 0,
                "absent_count": 0,
                "reminder_count": 0,
                "model_version": "test",
                "frames": [{"label": "READ"}],
            }
        },
    )

    assert finished.status_code == 422
