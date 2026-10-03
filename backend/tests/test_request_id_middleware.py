from concurrent.futures import ThreadPoolExecutor
import asyncio

from fastapi.testclient import TestClient
from fastapi import Request
from loguru import logger

from app.core.exceptions import AppException
from app.core.config import Settings
from app.core.logging import configure_logging
import app.main as main_module
from app.main import create_app


def test_request_id_is_shared_by_handler_error_envelope_and_header():
    app = create_app()

    @app.get("/request-id-test")
    def fail():
        raise AppException("test failure", code="TEST_FAILURE", http_status=400)

    # 不启动真实 Worker 或任何外部服务。
    client = TestClient(app)
    for request_id in (None, "caller-request-id", "x" * 200):
        headers = {"X-Request-ID": request_id} if request_id else {}
        response = client.get("/request-id-test", headers=headers)
        body = response.json()
        assert response.status_code == 400
        assert body["request_id"] == response.headers["x-request-id"]
        if request_id:
            assert body["request_id"] == request_id[:128]
        else:
            assert body["request_id"].startswith("req_")


def test_request_id_is_attached_to_request_logs(capsys, monkeypatch):
    settings = Settings(_env_file=None, app_env="test", log_requests=True)
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    configure_logging(settings)
    app = create_app()

    @app.get("/request-log-test")
    async def log_request(request: Request):
        await asyncio.sleep(0.01)
        logger.info("request handler marker={}", request.headers["x-marker"])
        return {"ok": True}

    client = TestClient(app)
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(
            lambda marker: client.get(
                "/request-log-test",
                headers={"X-Request-ID": f"request-log-{marker}", "X-Marker": marker},
            ),
            ("a", "b"),
        ))
    assert all(response.status_code == 200 for response in responses)
    output = capsys.readouterr().out
    lines = output.splitlines()
    for marker in ("a", "b"):
        assert any(
            f"request_id=request-log-{marker}" in line
            and f"request handler marker={marker}" in line
            for line in lines
        )
        assert any(
            f"request_id=request-log-{marker}" in line
            and f"http_request method=GET path=/request-log-test status=200 headers_duration_ms=" in line
            for line in lines
        )


def test_request_logging_can_be_disabled(capsys, monkeypatch):
    settings = Settings(_env_file=None, app_env="test", log_requests=False)
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    configure_logging(settings)
    client = TestClient(create_app())
    assert client.get("/").status_code == 200
    assert "http_request method=" not in capsys.readouterr().out
