from __future__ import annotations

import pytest

from whisper_hub.config import Config, load_dotenv


def test_env_parsing_and_url_normalisation():
    config = Config.from_env(
        {
            "WHUB_PORT": "9001",
            "WHUB_MODEL": "large-v3-turbo",
            "WHUB_PUBLIC_URL": "http://hub.lan:8765/",
            "WHUB_HTTPS_URL": "https://hub.example.com/",
            "WHUB_LANG_CONFIDENCE": "0.62",
            "WHUB_MAX_UPLOAD_MB": "12",
            "WHUB_HONOR_CLIENT_LANGUAGE": "yes",
            "WHUB_MODEL_IDLE_UNLOAD_SECONDS": "30",
            "WHUB_ENGLISH_ENGINE": "parakeet",
            "WHUB_PARAKEET_MODEL": "moondream/parakeet-ultra",
        }
    )
    assert config.port == 9001
    assert config.model == "large-v3-turbo"
    assert config.public_url == "http://hub.lan:8765"
    assert config.https_url == "https://hub.example.com"
    assert config.lang_confidence == 0.62
    assert config.max_upload_bytes == 12 * 1024 * 1024
    assert config.honor_client_language is True
    assert config.model_idle_unload_seconds == 30
    assert config.uses_turbo_without_translator is True
    assert config.english_engine == "parakeet"
    assert config.parakeet_model == "moondream/parakeet-ultra"


def test_invalid_values_are_rejected():
    with pytest.raises(ValueError):
        Config(port=0)
    with pytest.raises(ValueError):
        Config(lang_confidence=1.5)
    with pytest.raises(ValueError):
        Config.from_env({"WHUB_DEVICE": "tpu"})
    with pytest.raises(ValueError):
        Config(english_engine="parakeet-ultra")
    with pytest.raises(ValueError):
        Config(parakeet_model="  ")


def test_dotenv_parsing(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "WHUB_MODEL=base\n"
        'export WHUB_PUBLIC_URL="http://hub.lan:8765/"\n'
        "WHUB_MAX_UPLOAD_MB=7 # inline comment\n",
        encoding="utf-8",
    )
    values = load_dotenv(env_file)
    assert values["WHUB_MODEL"] == "base"
    assert values["WHUB_PUBLIC_URL"] == "http://hub.lan:8765/"
    assert values["WHUB_MAX_UPLOAD_MB"] == "7"
