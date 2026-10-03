from loguru import logger

from app.core.config import Settings
from app.core.logging import configure_logging


def test_configured_sink_keeps_logs_and_redacts_sensitive_messages(capsys):
    configure_logging(Settings(app_env="test", log_level="INFO"))

    logger.info("ordinary diagnostic marker")
    logger.info("request token=secret-token-value")

    output = capsys.readouterr().out
    assert "ordinary diagnostic marker" in output
    assert "[redacted: 含敏感字段，已脱敏]" in output
    assert "secret-token-value" not in output
    assert "request_id=-" in output
