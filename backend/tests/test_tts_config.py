"""MiMo TTS runtime configuration contract."""

from app.core.config import Settings


def test_mimo_tts_is_unavailable_without_api_key() -> None:
    settings = Settings(_env_file=None, mimo_api_key="")

    assert settings.mimo_tts_available is False


def test_mimo_tts_defaults_match_streaming_bingtang_contract() -> None:
    settings = Settings(_env_file=None, mimo_api_key="test-key")

    assert settings.mimo_tts_available is True
    assert settings.mimo_base_url == "https://api.xiaomimimo.com/v1"
    assert settings.mimo_tts_model == "mimo-v2.5-tts"
    assert settings.mimo_tts_voice == "冰糖"
    assert settings.mimo_tts_sample_rate == 24_000
    assert settings.mimo_tts_max_chars == 4_000
