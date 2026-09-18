"""Discovery and registration registry for agent CLI runtime adapters."""

from __future__ import annotations

from autoslide.runtime.adapters import ClaudeAdapter, CodexAdapter, GeminiAdapter
from autoslide.runtime.base import RuntimeAdapter
from autoslide.runtime.models import RuntimeStatus


class RuntimeRegistry:
    """Registry maintaining available CLI adapters and probing their status."""

    def __init__(self, adapters: list[RuntimeAdapter] | None = None):
        if adapters is None:
            default_adapters: list[RuntimeAdapter] = [
                CodexAdapter(),
                GeminiAdapter(),
                ClaudeAdapter(),
            ]
            self._adapters = {a.name: a for a in default_adapters}
        else:
            self._adapters = {a.name: a for a in adapters}

    def register(self, adapter: RuntimeAdapter) -> None:
        """Register a new or override an existing runtime adapter."""
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> RuntimeAdapter:
        """Retrieve a registered adapter by its identifier."""
        if name not in self._adapters:
            raise KeyError(f"Unknown runtime adapter: '{name}'")
        return self._adapters[name]

    def detect_all(self) -> list[RuntimeStatus]:
        """Query status for all registered adapters without exposing secrets."""
        return [adapter.detect() for adapter in self._adapters.values()]
