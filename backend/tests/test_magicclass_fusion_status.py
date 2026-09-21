import asyncio
import re
from pathlib import Path

from app.api.routes.magicclass_fusion import disabled_fusion_status
from app.schemas.magicclass_fusion import FusionState, FusionStatus
from app.services.magicclass.capabilities import KNOWN_CAPABILITIES
from app.services.magicclass.fusion_client import SERVICE_SCOPE_SENTINEL, MagicClassFusionClient
from app.services.magicclass.service_assertion import decode_service_assertion


def test_disabled_status_does_not_expose_service_details():
    status = disabled_fusion_status()
    assert isinstance(status, FusionStatus)
    assert status.model_dump() == {
        "enabled": False,
        "available": False,
        "state": "disabled",
        "capabilities": [],
        "reason": "disabled",
    }


class _Transport:
    """Minimal stand-in for the internal service returning a readiness payload."""

    def __init__(self, payload=None, status_code=200, raises=None):
        self.payload = payload
        self.status_code = status_code
        self.raises = raises
        self.last_headers = None

    async def get(self, _url, *, headers=None, timeout=None):
        self.last_headers = headers or {}
        if self.raises is not None:
            raise self.raises

        class _Response:
            pass

        response = _Response()
        response.status_code = self.status_code
        response.json = lambda: self.payload
        return response


def _status_for(payload=None, status_code=200, raises=None, **client_kwargs):
    transport = _Transport(payload, status_code, raises)

    async def run():
        client = MagicClassFusionClient(
            base_url=client_kwargs.pop("base_url", "http://127.0.0.1:4010"),
            secret=client_kwargs.pop("secret", "test-secret"),
            transport=transport,
            **client_kwargs,
        )
        return await client.status(user_id="u1")

    return asyncio.run(run()), transport


# ===== 状态机：disabled / unavailable / degraded / ready =====


def test_client_maps_a_transport_failure_to_unavailable():
    status, _ = _status_for(raises=TimeoutError("internal address is not returned"))
    assert status.state is FusionState.UNAVAILABLE
    assert status.reason == "service_unreachable"
    assert status.available is False
    assert status.enabled is True


def test_client_maps_a_5xx_to_unavailable():
    status, _ = _status_for({"status": "ready"}, status_code=500)
    assert status.state is FusionState.UNAVAILABLE
    assert status.reason == "service_unreachable"
    assert status.available is False


def test_client_maps_a_rejected_assertion_to_unavailable():
    for code in (401, 403):
        status, _ = _status_for(None, status_code=code)
        assert status.state is FusionState.UNAVAILABLE, code
        assert status.reason == "assertion_rejected", code


def test_client_maps_a_503_to_degraded_rather_than_unavailable():
    """A 503 means the service is up and a dependency is down: that is degraded."""
    status, _ = _status_for(
        {"status": "degraded", "reason": "dependency_unavailable", "capabilities": []},
        status_code=503,
    )
    assert status.state is FusionState.DEGRADED
    assert status.reason == "dependency_unavailable"
    assert status.available is False


def test_client_maps_a_ready_http_status_that_denies_readiness_to_degraded():
    status, _ = _status_for({"status": "degraded", "capabilities": ["workspace"]})
    assert status.state is FusionState.DEGRADED
    assert status.capabilities == []


def test_client_reports_unconfigured_when_the_gateway_lacks_address_or_secret():
    for kwargs in ({"base_url": ""}, {"secret": ""}):
        status, transport = _status_for({"status": "ready"}, **kwargs)
        assert status.state is FusionState.UNAVAILABLE, kwargs
        assert status.reason == "service_unconfigured", kwargs
        assert transport.last_headers is None, kwargs


def test_only_ready_exposes_capabilities():
    """Claiming a capability while degraded would open an entry point that must fail."""
    ready, _ = _status_for({"status": "ready", "capabilities": ["workspace", "tts"]})
    degraded, _ = _status_for({"status": "degraded"}, status_code=503)
    unavailable, _ = _status_for(raises=RuntimeError("boom"))
    assert ready.capabilities == ["workspace", "tts"]
    assert degraded.capabilities == []
    assert unavailable.capabilities == []
    assert [ready.state, degraded.state, unavailable.state] == [
        FusionState.READY,
        FusionState.DEGRADED,
        FusionState.UNAVAILABLE,
    ]


# ===== capability 白名单与断言 =====


def test_client_keeps_only_capabilities_this_build_understands():
    status, _ = _status_for(
        {
            "status": "ready",
            "capabilities": ["workspace", "not-a-capability", "", 42, None, "tts"],
        }
    )
    assert status.state is FusionState.READY
    assert status.reason == "ready"
    assert status.capabilities == ["workspace", "tts"]


def test_client_normalises_capability_order():
    forward, _ = _status_for({"status": "ready", "capabilities": ["tts", "workspace", "player"]})
    reverse, _ = _status_for({"status": "ready", "capabilities": ["player", "workspace", "tts"]})
    assert forward.capabilities == reverse.capabilities


def test_client_ignores_a_non_list_capability_payload():
    status, _ = _status_for({"status": "ready", "capabilities": "workspace"})
    assert status.capabilities == []
    assert status.available is True


def test_client_sends_a_course_free_sentinel_for_status():
    _, transport = _status_for({"status": "ready", "capabilities": []})
    assertion = transport.last_headers["X-CampusMate-Service-Assertion"]
    claims = decode_service_assertion(assertion, secret="test-secret")
    assert claims["scope"] == ["service:status"]
    assert claims["course_id"] == SERVICE_SCOPE_SENTINEL


def test_capability_vocabulary_matches_the_node_service():
    """The two lists are a contract; drift would silently hide new entry points."""
    service_source = (
        Path(__file__).resolve().parents[2]
        / "magicclass-service"
        / "src"
        / "capabilities.ts"
    )
    text = service_source.read_text(encoding="utf-8")
    block = text.split("KNOWN_CAPABILITIES = [", 1)[1].split("] as const", 1)[0]
    node_values = re.findall(r"'([a-z0-9-]+)'", block)
    assert node_values == list(KNOWN_CAPABILITIES)
