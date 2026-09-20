"""CapabilityRegistry 测试 —— 受控、可审计、失败即停。

锁定四条边界:
1. 已发布能力 code 与语义被冻结,改名或改变策略都会在启动期被拒绝;
2. 清单损坏 / 引用不存在的角色、Skill、Handler、工具时阻止启动,不静默回退;
3. `/capabilities` 由注册表生成,不再硬编码;
4. 只支持配置级启停与角色绑定,不支持热加载 / 远程 URL / 插件加载。
"""
from __future__ import annotations

import json

import pytest

from app.core.config import Settings
from app.services.agent_runtime.capability_registry import (
    FROZEN_CAPABILITIES,
    Capability,
    CapabilityManifestError,
    CapabilityRegistry,
    build_capability_registry,
    load_capabilities_from_manifest,
)
from app.services.container import reset_container_for_tests

from app.services.agent_runtime.capability_registry import _MANIFEST_PATH as _MANIFEST


def _write_manifest(tmp_path, payload):
    path = tmp_path / "capabilities.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _baseline_payload():
    from app.services.agent_runtime.capability_registry import _MANIFEST_PATH

    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


class TestManifestSchema:
    def test_default_manifest_loads(self):
        capabilities = load_capabilities_from_manifest(_MANIFEST)
        codes = {c.code for c in capabilities}
        assert set(FROZEN_CAPABILITIES).issubset(codes)

    def test_broken_json_raises(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{ not json", encoding="utf-8")
        with pytest.raises(CapabilityManifestError, match="合法 JSON"):
            load_capabilities_from_manifest(path)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(CapabilityManifestError):
            load_capabilities_from_manifest(tmp_path / "nope.json")

    def test_empty_list_raises(self, tmp_path):
        path = _write_manifest(tmp_path, {"capabilities": []})
        with pytest.raises(CapabilityManifestError, match="非空"):
            load_capabilities_from_manifest(path)

    def test_duplicate_code_raises(self, tmp_path):
        payload = _baseline_payload()
        payload["capabilities"].append(payload["capabilities"][0])
        with pytest.raises(CapabilityManifestError, match="重复"):
            load_capabilities_from_manifest(_write_manifest(tmp_path, payload))

    def test_invalid_route_policy_raises(self, tmp_path):
        payload = _baseline_payload()
        payload["capabilities"][0]["route_policy"] = "free_for_all"
        with pytest.raises(CapabilityManifestError, match="route_policy"):
            load_capabilities_from_manifest(_write_manifest(tmp_path, payload))

    def test_invalid_risk_level_raises(self, tmp_path):
        payload = _baseline_payload()
        payload["capabilities"][0]["risk_level"] = "HARMLESS"
        with pytest.raises(CapabilityManifestError, match="risk_level"):
            load_capabilities_from_manifest(_write_manifest(tmp_path, payload))

    def test_non_boolean_requires_approval_raises(self, tmp_path):
        payload = _baseline_payload()
        payload["capabilities"][0]["requires_approval"] = "yes"
        with pytest.raises(CapabilityManifestError, match="requires_approval"):
            load_capabilities_from_manifest(_write_manifest(tmp_path, payload))

    def test_missing_code_raises(self, tmp_path):
        path = _write_manifest(tmp_path, {"capabilities": [{"version": "1.0"}]})
        with pytest.raises(CapabilityManifestError, match="code"):
            load_capabilities_from_manifest(path)


class TestFrozenSemantics:
    def test_published_capability_cannot_be_removed(self, tmp_path):
        payload = _baseline_payload()
        payload["capabilities"] = [
            c for c in payload["capabilities"] if c["code"] != "citation.verify"
        ]
        with pytest.raises(CapabilityManifestError, match="不得删除"):
            CapabilityRegistry(load_capabilities_from_manifest(_write_manifest(tmp_path, payload)))

    @pytest.mark.parametrize(
        "field,value",
        [
            ("route_policy", "fast_structured"),
            ("risk_level", "AUTO_SAFE"),
            ("requires_approval", False),
        ],
    )
    def test_published_capability_semantics_cannot_change(self, tmp_path, field, value):
        payload = _baseline_payload()
        for item in payload["capabilities"]:
            if item["code"] == "final_review.plan":
                item[field] = value
        with pytest.raises(CapabilityManifestError, match=field):
            CapabilityRegistry(load_capabilities_from_manifest(_write_manifest(tmp_path, payload)))

    def test_new_capability_can_be_appended(self, tmp_path):
        payload = _baseline_payload()
        payload["capabilities"].append({
            "code": "brand.new", "version": "1.0", "route_policy": "reasoning_primary",
            "risk_level": "AUTO_SAFE", "requires_approval": False, "enabled": True,
            "roles": [], "tools": [],
        })
        registry = CapabilityRegistry(load_capabilities_from_manifest(_write_manifest(tmp_path, payload)))
        assert "brand.new" in registry.codes()


class TestCrossValidation:
    def test_unknown_role_rejected(self):
        with pytest.raises(CapabilityManifestError, match="未注册角色"):
            CapabilityRegistry(
                [Capability(
                    code="final_review.plan", version="1.0", route_policy="reasoning_primary",
                    risk_level="CONFIRM_REQUIRED", requires_approval=True,
                    roles=("ghost",),
                )],
                agent_codes={"planner"},
            )

    def test_unknown_skill_rejected(self):
        with pytest.raises(CapabilityManifestError, match="未注册 Skill"):
            CapabilityRegistry(
                [Capability(
                    code="final_review.plan", version="1.0", route_policy="reasoning_primary",
                    risk_level="CONFIRM_REQUIRED", requires_approval=True,
                    skill="ghost_skill",
                )],
                skill_codes={"final_review"},
            )

    def test_unknown_handler_rejected(self):
        with pytest.raises(CapabilityManifestError, match="未注册的 Handler"):
            CapabilityRegistry(
                [Capability(
                    code="final_review.plan", version="1.0", route_policy="reasoning_primary",
                    risk_level="CONFIRM_REQUIRED", requires_approval=True,
                    job_kind="ghost_kind",
                )],
                handler_job_kinds={"learning_goal"},
            )

    def test_unknown_tool_rejected(self):
        with pytest.raises(CapabilityManifestError, match="未注册工具"):
            CapabilityRegistry(
                [Capability(
                    code="final_review.plan", version="1.0", route_policy="reasoning_primary",
                    risk_level="CONFIRM_REQUIRED", requires_approval=True,
                    tools=("ghost.tool",),
                )],
                tool_codes={"exam.read"},
            )

    def test_disabled_capability_is_not_requireable(self, tmp_path):
        payload = _baseline_payload()
        for item in payload["capabilities"]:
            if item["code"] == "final_review.plan":
                item["enabled"] = False
        registry = CapabilityRegistry(
            load_capabilities_from_manifest(_write_manifest(tmp_path, payload))
        )
        with pytest.raises(CapabilityManifestError, match="不可用"):
            registry.require("final_review.plan")
        assert registry.get("final_review.plan").enabled is False

    def test_registry_is_read_only(self):
        registry = build_capability_registry()
        assert registry.is_frozen is True
        assert not hasattr(registry, "register")


class TestStartupIntegration:
    def test_container_builds_capability_registry(self):
        container = reset_container_for_tests(
            Settings(app_env="test", database_url="sqlite:///:memory:")
        )
        registry = container.agent_capability_registry
        assert registry.is_frozen
        assert "learning_goal.run" in registry.codes()
        # 绑定的 Handler 必须真实存在
        assert registry.get("learning_goal.run").job_kind == "learning_goal"

    def test_corrupted_manifest_blocks_startup(self, tmp_path, monkeypatch):
        """生产环境清单损坏必须阻止 runtime 启动,不得静默回退到默认宽权限。"""
        broken = tmp_path / "capabilities.json"
        broken.write_text("{ broken", encoding="utf-8")
        monkeypatch.setattr(
            "app.services.container.build_capability_registry",
            lambda **kwargs: build_capability_registry(manifest_path=broken, **kwargs),
        )
        import base64

        with pytest.raises(CapabilityManifestError):
            reset_container_for_tests(
                Settings(
                    _env_file=None,
                    app_env="production",
                    database_url="sqlite:///:memory:",
                    jwt_secret="x" * 40,
                    edu_session_store="encrypted_sqlite",
                    edu_session_encryption_key=base64.b64encode(b"k" * 32).decode(),
                    edu_session_encryption_key_id="test-key",
                    auto_seed_demo_users=False,
                    agent_allow_mock_providers=False,
                    edu_allow_insecure_ssl=False,
                )
            )

    def test_capabilities_endpoint_uses_registry(self):
        from fastapi.testclient import TestClient

        from app.core.security import hash_password
        from app.main import create_app

        container = reset_container_for_tests(
            Settings(app_env="test", database_url="sqlite:///:memory:")
        )
        container.user_repository.create_user(
            username="caps_student", password_hash=hash_password("Demo123456"), role="student"
        )
        client = TestClient(create_app())
        token = client.post(
            "/api/v1/auth/login",
            json={"username": "caps_student", "password": "Demo123456"},
        ).json()["access_token"]
        body = client.get(
            "/api/v1/agent-runtime/capabilities",
            headers={"Authorization": f"Bearer {token}"},
        ).json()

        expected = {
            item["name"]: item
            for item in container.agent_capability_registry.describe()
        }
        actual = {item["name"]: item for item in body["capabilities"]}
        assert actual == expected
        # 已发布能力语义必须原样保留
        for code, frozen in FROZEN_CAPABILITIES.items():
            assert actual[code]["route_policy"] == frozen["route_policy"]
            assert actual[code]["risk_level"] == frozen["risk_level"]
            assert actual[code]["requires_approval"] == frozen["requires_approval"]

    def test_no_hot_reload_surface(self):
        """不允许运行时热加载、远程 URL、压缩包安装或 Python 插件加载。"""
        import app.services.agent_runtime.capability_registry as module

        source = module.__doc__ or ""
        assert "热加载" in source
        for forbidden in ("importlib", "urllib", "zipfile", "eval(", "exec("):
            assert not hasattr(module, forbidden.split("(")[0])
