from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.edu import EduCookie
from app.services.edu.adapters.zhengfang_http import ZhengfangHttpClient
from app.services.edu.adapters.zhengfang_strategy import (
    school_allowed_origins,
    school_config_from_dict,
)
from app.services.edu.connector import EduConnectorService


def test_connector_and_adapter_share_one_effective_allowed_origin_set() -> None:
    system = SimpleNamespace(
        base_url="https://jw.parent.example.edu.cn/jwglxt",
        login_url="https://jw.parent.example.edu.cn/login",
        provider_version="jwgl2",
        sso_url="https://sso.example.edu.cn/cas",
        vpn_url=None,
        auth_type="form",
        login_execution_mode="client_webview",
        captcha_type="none",
        requires_campus_network=False,
        requires_vpn=False,
        provider="zhengfang",
        adapter_config=json.dumps({
            "allowed_origin": "https://assets.example.edu.cn/static",
            "allowed_origins": [
                "https://sso.example.edu.cn/duplicate",
                "javascript://evil.example.edu.cn",
            ],
        }),
    )
    connection = SimpleNamespace(
        edu_system_id="system-1",
        portal_url="https://portal.example.edu.cn/current-entry",
    )
    connector = object.__new__(EduConnectorService)
    connector._edu_repo = SimpleNamespace(get_connection=lambda _id: connection)
    connector._registry = SimpleNamespace(get_system_by_id=lambda _id: system)

    config = connector._build_config_dict(system, portal_url=connection.portal_url)
    school = school_config_from_dict(config)
    assert school is not None
    expected = [
        "https://jw.parent.example.edu.cn",
        "https://assets.example.edu.cn",
        "https://sso.example.edu.cn",
        "https://portal.example.edu.cn",
    ]
    assert school_allowed_origins(school) == expected
    assert connector.allowed_origins_for_connection("connection-1") == expected
    assert config["base_url"] == system.base_url
    assert config["login_url"] == system.login_url

    client = ZhengfangHttpClient(base_url=school.base_url)
    client.set_cookie_jar(
        [
            {"name": f"cookie-{index}", "value": "ok", "source_url": origin, "path": None}
            for index, origin in enumerate(expected)
        ],
        allowed_origins=school_allowed_origins(school),
    )
    assert client._allowed_origins == set(expected)


@pytest.mark.parametrize("field,value", [
    ("host_only", 1),
    ("host_only", "true"),
    ("secure", 0),
    ("http_only", "false"),
    ("expires", True),
    ("expires", "123"),
])
def test_cookie_contract_rejects_coerced_boolean_and_integer_values(field, value) -> None:
    with pytest.raises(ValidationError):
        EduCookie(name="sid", value="ok", **{field: value})
