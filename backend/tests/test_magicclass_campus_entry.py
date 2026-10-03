"""The campus entry must keep free topics and course materials in their own scopes."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import magicclass_classroom as routes
from app.core.config import Settings
from app.schemas.magicclass import MagicClassGenerateRequest
from app.services.magicclass.course_context import LearningContext
from app.services.magicclass.result_store import MagicClassSession


def test_free_topic_requires_a_topic_and_rejects_course_material_ids():
    user = SimpleNamespace(id=7, role="student")
    container = SimpleNamespace(settings=SimpleNamespace())
    service = SimpleNamespace()
    with pytest.raises(HTTPException) as empty:
        asyncio.run(routes.generate_self_classroom(
            MagicClassGenerateRequest(learning_objective="  "), user, container, service
        ))
    assert empty.value.status_code == 400
    with pytest.raises(HTTPException) as selected:
        asyncio.run(routes.generate_self_classroom(
            MagicClassGenerateRequest(learning_objective="Linux", selected_material_ids=["other-course"]),
            user, container, service,
        ))
    assert selected.value.status_code == 400


def test_free_topic_uses_private_student_scope_and_own_text():
    seen = {}

    class Service:
        async def generate(self, **kwargs):
            seen.update(kwargs)
            return MagicClassSession(
                session_id="om_free", course_id=routes.SELF_COURSE_ID,
                user_id="7", mode="explain", requested_mode="explain",
            )

    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    output = asyncio.run(routes.generate_self_classroom(
        MagicClassGenerateRequest(mode="explain", learning_objective="学 Linux 文件权限"),
        SimpleNamespace(id=7, role="student"), SimpleNamespace(settings=settings), Service(),
    ))
    assert output.session.course_id == routes.SELF_COURSE_ID
    assert seen["user_id"] == 7
    assert "Linux 文件权限" in seen["context"].text
    assert seen["context"].selected_material_ids == ()


def test_uploaded_course_material_text_is_used_only_after_service_resolution(monkeypatch):
    class AuthorizedClient:
        async def resolve_materials(self, *, user_id, course_id, material_ids):
            assert (user_id, course_id, material_ids) == ("7", "course-1", ["m1", "unknown"])
            return {"resolved": [{"id": "m1", "filename": "linux.txt", "extraction_status": "extracted"}]}

        async def get_material(self, *, user_id, course_id, material_id):
            assert (user_id, course_id, material_id) == ("7", "course-1", "m1")
            return {"text": "chmod 755 changes permissions"}

    monkeypatch.setattr(routes, "_material_client", lambda _: AuthorizedClient())
    container = SimpleNamespace(settings=SimpleNamespace(
        magicclass_fusion_enabled=True, magicclass_course_context_max_chars=1000
    ))
    source = LearningContext(text="course facts", unresolved_material_ids=("m1", "unknown"))
    result = asyncio.run(routes._attach_uploaded_materials(
        container, SimpleNamespace(id=7), "course-1", source
    ))
    assert "chmod 755 changes permissions" in result.material_text
    assert result.selected_material_ids == ("m1",)
    assert result.unresolved_material_ids == ("unknown",)
