from pathlib import Path
import pytest

from autoslide.runtime.adapters import (
    AntigravityAdapter,
    ClaudeAdapter,
    CodexAdapter,
    GeminiAdapter,
)
from autoslide.runtime.discovery import RuntimeRegistry
from autoslide.runtime.models import RuntimeStatus


def test_discovery_reports_missing_runtime(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    status = CodexAdapter().detect()
    assert status.installed is False
    assert status.authenticated is False
    assert status.executable is None


def test_discovery_does_not_read_api_key_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-read")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-be-read-claude")
    monkeypatch.setenv("GEMINI_API_KEY", "must-not-be-read-gemini")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/codex")

    status = CodexAdapter().detect()
    assert "must-not-be-read" not in repr(status)
    assert not hasattr(status, "api_key")


def test_registry_detect_all_returns_supported_runtimes(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    registry = RuntimeRegistry()
    statuses = registry.detect_all()

    names = [s.name for s in statuses]
    assert "codex" in names
    assert "gemini" in names
    assert "claude" in names
    assert "antigravity" in names
    assert all(not s.installed for s in statuses)


def test_registry_get_returns_correct_adapter():
    registry = RuntimeRegistry()
    assert isinstance(registry.get("codex"), CodexAdapter)
    assert isinstance(registry.get("gemini"), GeminiAdapter)
    assert isinstance(registry.get("claude"), ClaudeAdapter)
    assert isinstance(registry.get("antigravity"), AntigravityAdapter)

    with pytest.raises(KeyError, match="unknown"):
        registry.get("unknown")
