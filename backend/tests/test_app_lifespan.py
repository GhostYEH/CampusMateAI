"""Exercise the application lifecycle, including partial startup and shutdown failure."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from app import main
from app.core.config import Settings


@pytest.fixture
def services(monkeypatch):
    report = SimpleNamespace(scanned=0, evaluated=0, reused=0, decisions=0, applied=0, failed=0)
    container = SimpleNamespace(
        agent_worker=SimpleNamespace(start=AsyncMock(), stop=AsyncMock()),
        adaptive_replanning_worker=SimpleNamespace(tick=Mock(return_value=report), start=AsyncMock(), stop=AsyncMock()),
        agent_provider_registry=SimpleNamespace(add_fake=Mock()),
        university_repository=SimpleNamespace(seed_from_json=Mock(return_value=(0, 0))),
        llm=SimpleNamespace(aclose=AsyncMock()),
        tts=SimpleNamespace(aclose=AsyncMock()),
    )
    settings = Settings(app_env="test", llm_provider="none", auto_seed_demo_users=False,
                        auto_import_demo=False, agent_allow_mock_providers=False)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "configure_logging", lambda _settings: None)
    monkeypatch.setattr(main, "build_container", lambda _settings: container)
    return container


def assert_closed(services):
    services.agent_worker.stop.assert_awaited_once()
    services.adaptive_replanning_worker.stop.assert_awaited_once()
    services.llm.aclose.assert_awaited_once()
    services.tts.aclose.assert_awaited_once()


def test_testclient_context_runs_startup_and_shutdown(services):
    with TestClient(main.create_app()) as client:
        services.agent_worker.start.assert_awaited_once()
        services.adaptive_replanning_worker.tick.assert_called_once_with(batch_size=25)
        services.adaptive_replanning_worker.start.assert_awaited_once()
        assert client.get("/openapi.json").status_code == 200
        services.llm.aclose.assert_not_awaited()
    assert_closed(services)


def test_first_tick_failure_still_starts_and_closes_background_workers(services):
    services.adaptive_replanning_worker.tick.side_effect = RuntimeError("tick unavailable")
    with TestClient(main.create_app()):
        services.adaptive_replanning_worker.start.assert_awaited_once()
    assert_closed(services)


def test_partial_startup_failure_closes_already_started_services(services):
    services.adaptive_replanning_worker.start.side_effect = RuntimeError("scheduler failed")
    with pytest.raises(RuntimeError, match="scheduler failed"):
        with TestClient(main.create_app()):
            pytest.fail("startup must propagate its failure")
    assert_closed(services)


def test_one_shutdown_failure_does_not_skip_other_resources(services):
    services.agent_worker.stop.side_effect = RuntimeError("stop failed")
    with TestClient(main.create_app()):
        pass
    assert_closed(services)
