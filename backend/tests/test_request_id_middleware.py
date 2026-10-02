from fastapi.testclient import TestClient

from app.core.exceptions import AppException
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
