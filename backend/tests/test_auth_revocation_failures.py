from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.api.routes.auth import admin_update_user, logout
from app.core.exceptions import AppException
from app.schemas.multi_role import LogoutRequest, UserAdminUpdate


def test_logout_does_not_report_success_when_device_revocation_fails():
    repository = Mock()
    repository.revoke_by_token_hash.side_effect = RuntimeError("private database details")
    request = Request({"type": "http", "headers": [(b"cookie", b"trusted-device=synthetic-cookie")]})
    with pytest.raises(AppException) as raised:
        logout(
            LogoutRequest(), request, Response(), user=SimpleNamespace(id="user"),
            settings=SimpleNamespace(trusted_device_cookie_name="trusted-device"),
            container=SimpleNamespace(trusted_device_repository=repository),
        )
    assert raised.value.http_status == 503
    assert "private database details" not in raised.value.message
    repository.revoke_by_token_hash.assert_called_once()


def test_deactivation_does_not_report_success_when_device_revocation_fails():
    repository = Mock()
    repository.revoke_all_for_user.side_effect = RuntimeError("private database details")
    users = Mock()
    users.get_user_by_id.return_value = SimpleNamespace(id="target-user")
    with pytest.raises(AppException) as raised:
        admin_update_user(
            "target-user", UserAdminUpdate(is_active=False), user=SimpleNamespace(id="admin"),
            container=SimpleNamespace(user_repository=users, trusted_device_repository=repository),
        )
    assert raised.value.http_status == 503
    assert "private database details" not in raised.value.message
    repository.revoke_all_for_user.assert_called_once_with("target-user")
