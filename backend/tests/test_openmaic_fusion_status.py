import asyncio

from app.api.routes.openmaic_fusion import disabled_fusion_status
from app.schemas.openmaic_fusion import FusionStatus
from app.services.openmaic.fusion_client import OpenMAICFusionClient


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
