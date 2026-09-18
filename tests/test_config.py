from pathlib import Path
import pytest

from autoslide.config import Settings


def test_defaults_are_local_and_api_key_free(tmp_path: Path):
    settings = Settings.from_env({"AUTOSLIDE_DATA_ROOT": str(tmp_path)})
    assert settings.data_root == tmp_path
    assert settings.allowed_runtimes == ("codex", "gemini", "claude", "antigravity")
    assert not hasattr(settings, "provider_api_key")


def test_paths_are_created_by_explicit_bootstrap(tmp_path: Path):
    settings = Settings.from_env({"AUTOSLIDE_DATA_ROOT": str(tmp_path / "data")})
    settings.ensure_directories()
    assert (tmp_path / "data" / "jobs").is_dir()
    assert (tmp_path / "data" / "artifacts").is_dir()


def test_rejects_relative_data_root():
    with pytest.raises(ValueError, match="absolute"):
        Settings.from_env({"AUTOSLIDE_DATA_ROOT": "relative/path"})


def test_rejects_invalid_runtime():
    with pytest.raises(ValueError, match="runtime"):
        Settings.from_env({
            "AUTOSLIDE_DATA_ROOT": "/tmp/test",
            "AUTOSLIDE_ALLOWED_RUNTIMES": "codex,unknown_runtime",
        })


def test_custom_limits_and_timeout():
    settings = Settings.from_env({
        "AUTOSLIDE_DATA_ROOT": "/tmp/test",
        "AUTOSLIDE_MAX_JOB_SIZE_BYTES": "10485760",
        "AUTOSLIDE_JOB_TIMEOUT_SECONDS": "120",
        "AUTOSLIDE_ALLOWED_RUNTIMES": "codex,gemini",
    })
    assert settings.max_job_size_bytes == 10485760
    assert settings.job_timeout_seconds == 120
    assert settings.allowed_runtimes == ("codex", "gemini")


def test_settings_is_frozen(tmp_path: Path):
    settings = Settings.from_env({"AUTOSLIDE_DATA_ROOT": str(tmp_path)})
    with pytest.raises(Exception):
        settings.data_root = Path("/other")  # type: ignore
