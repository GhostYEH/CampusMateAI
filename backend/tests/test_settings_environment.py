import base64

import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize("app_env", ["prod", "Production", "staging"])
def test_settings_rejects_unknown_environment_names(app_env):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env=app_env)


@pytest.mark.parametrize("app_env", ["development", "test", "production"])
def test_settings_accepts_supported_environments(app_env):
    overrides = {}
    if app_env == "production":
        overrides = {
            "jwt_secret": "production-test-secret-that-is-long-enough-123456",
            "edu_session_store": "encrypted_sqlite",
            "edu_session_encryption_key": base64.b64encode(b"k" * 32).decode("ascii"),
        }

    assert Settings(_env_file=None, app_env=app_env, **overrides).app_env == app_env


def test_production_rejects_weak_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET must be explicitly configured"):
        Settings(_env_file=None, app_env="production", jwt_secret="short-secret")
