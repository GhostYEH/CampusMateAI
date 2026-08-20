from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.focus_realtime_voice_service import (
    FocusRealtimeVoiceService,
    RealtimeVoiceProviderError,
    VolcengineVoiceChatClient,
    reset_focus_realtime_voice_service_for_tests,
)


class StubVoiceChat:
    def __init__(self, fail_start=False): self.fail_start, self.started, self.stopped = fail_start, [], []
    def start(self, body):
        if self.fail_start: raise RealtimeVoiceProviderError()
        self.started.append(body)
    def stop(self, body): self.stopped.append(body)


def make_client(voice_chat):
    settings = Settings(
        app_env="test", database_url="sqlite:///:memory:", auto_seed_demo_users=True,
        volc_rtc_app_id="123456789012345678901234", volc_rtc_app_key="test-app-key",
        volc_access_key_id="test-ak", volc_secret_access_key="test-sk",
        volc_rtc_voicechat_config_json='{"Config":{"LLMConfig":{}}}',
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    reset_focus_realtime_voice_service_for_tests(FocusRealtimeVoiceService(settings, voice_chat))
    return TestClient(create_app())


def auth(client, username="student_demo"):
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "Demo123456"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_realtime_voice_requires_authentication():
    assert make_client(StubVoiceChat()).post("/api/v1/focus/realtime-voice/sessions").status_code == 401


def test_realtime_voice_creates_bound_token_and_stops_owner_session():
    voice_chat = StubVoiceChat()
    client = make_client(voice_chat)
    response = client.post("/api/v1/focus/realtime-voice/sessions", headers=auth(client))
    assert response.status_code == 201
    body = response.json()
    assert body["app_id"] == "123456789012345678901234"
    assert body["token"].startswith("001123456789012345678901234")
    assert "test-app-key" not in str(body)
    assert voice_chat.started[0]["AgentConfig"]["TargetUserId"] == [body["user_id"]]
    assert client.delete(f"/api/v1/focus/realtime-voice/sessions/{body['session_id']}", headers=auth(client)).status_code == 200
    assert voice_chat.stopped


def test_realtime_voice_hides_provider_failure():
    client = make_client(StubVoiceChat(fail_start=True))
    response = client.post("/api/v1/focus/realtime-voice/sessions", headers=auth(client))
    assert response.status_code == 502
    assert "secret" not in response.json()["message"].lower()
