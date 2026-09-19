import asyncio
import re
from pathlib import Path

from app.api.routes.openmaic_fusion import disabled_fusion_status
from app.schemas.openmaic_fusion import FusionStatus
from app.services.openmaic.capabilities import KNOWN_CAPABILITIES
from app.services.openmaic.fusion_client import SERVICE_SCOPE_SENTINEL, OpenMAICFusionClient
from app.services.openmaic.service_assertion import decode_service_assertion


def test_disabled_status_does_not_expose_service_details():
    status = disabled_fusion_status()
    assert isinstance(status, FusionStatus)
    assert status.model_dump() == {
        "enabled": False,
        "available": False,
        "capabilities": [],
        "reason": "disabled",
    }


def test_client_maps_service_timeout_to_safe_unavailable_status():
    class TimeoutTransport:
        async def get(self, *_args, **_kwargs):
            raise TimeoutError("internal address is not returned")

    async def run():
        client = OpenMAICFusionClient(
            base_url="http://127.0.0.1:4010",
            secret="test-secret",
            transport=TimeoutTransport(),
        )
        status = await client.status(user_id="u1")
        assert status.reason == "service_unavailable"
        assert status.available is False

    asyncio.run(run())


class _ReadyTransport:
    """Minimal stand-in for the internal service returning a readiness payload."""

    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.last_headers = None

    async def get(self, _url, *, headers=None, timeout=None):
        self.last_headers = headers or {}

        class _Response:
            pass

        response = _Response()
        response.status_code = self.status_code
        response.json = lambda: self.payload
        return response


def _status_for(payload, status_code=200):
    transport = _ReadyTransport(payload, status_code)

    async def run():
        client = OpenMAICFusionClient(
            base_url="http://127.0.0.1:4010",
            secret="test-secret",
            transport=transport,
        )
        return await client.status(user_id="u1")

    return asyncio.run(run()), transport


def test_client_keeps_only_capabilities_this_build_understands():
    status, _ = _status_for(
        {
            "status": "ready",
            "capabilities": ["workspace", "not-a-capability", "", 42, None, "tts"],
        }
    )
    assert status.reason == "ready"
    assert status.capabilities == ["workspace", "tts"]


def test_client_normalises_capability_order():
    forward, _ = _status_for({"capabilities": ["tts", "workspace", "player"]})
    reverse, _ = _status_for({"capabilities": ["player", "workspace", "tts"]})
    assert forward.capabilities == reverse.capabilities


def test_client_ignores_a_non_list_capability_payload():
    status, _ = _status_for({"capabilities": "workspace"})
    assert status.capabilities == []
    assert status.available is True


def test_client_sends_a_course_free_sentinel_for_status():
    _, transport = _status_for({"capabilities": []})
    assertion = transport.last_headers["X-CampusMate-Service-Assertion"]
    claims = decode_service_assertion(assertion, secret="test-secret")
    assert claims["scope"] == ["service:status"]
    assert claims["course_id"] == SERVICE_SCOPE_SENTINEL


def test_capability_vocabulary_matches_the_node_service():
    """The two lists are a contract; drift would silently hide new entry points."""
    service_source = (
        Path(__file__).resolve().parents[2]
        / "openmaic-service"
        / "src"
        / "capabilities.ts"
    )
    text = service_source.read_text(encoding="utf-8")
    block = text.split("KNOWN_CAPABILITIES = [", 1)[1].split("] as const", 1)[0]
    node_values = re.findall(r"'([a-z0-9-]+)'", block)
    assert node_values == list(KNOWN_CAPABILITIES)
