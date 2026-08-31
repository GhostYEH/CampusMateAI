from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.focus_realtime_voice_service import FocusRealtimeVoiceService, reset_focus_realtime_voice_service_for_tests


def make_client(api_key="test-seeduplex-key"):
    settings = Settings(
        app_env="test", database_url="sqlite:///:memory:", auto_seed_demo_users=True,
        volc_seeduplex_api_key=api_key,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    reset_focus_realtime_voice_service_for_tests(FocusRealtimeVoiceService(settings))
    return TestClient(create_app())


def auth(client, username="student_demo"):
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "Demo123456"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_realtime_voice_requires_authentication():
    assert make_client().post("/api/v1/focus/realtime-voice/sessions").status_code == 401


def test_realtime_voice_creates_backend_owned_websocket_session_and_stops_owner_session():
    client = make_client()
    response = client.post("/api/v1/focus/realtime-voice/sessions", headers=auth(client))
    assert response.status_code == 201
    body = response.json()
    assert body["websocket_path"].endswith(body["session_id"])
    assert "key" not in str(body).lower()
    assert client.delete(f"/api/v1/focus/realtime-voice/sessions/{body['session_id']}", headers=auth(client)).status_code == 200


def test_realtime_voice_does_not_create_when_api_key_is_missing():
    client = make_client(api_key="")
    response = client.post("/api/v1/focus/realtime-voice/sessions", headers=auth(client))
    assert response.status_code == 503
    assert "key" not in response.text.lower()


def test_session_create_event_keeps_api_key_out_of_upstream_payload():
    event = FocusRealtimeVoiceService(Settings(volc_seeduplex_api_key="x")).session_create_event()
    assert event["session"]["model"] == "1.2.6.1"
    assert "key" not in str(event).lower()
